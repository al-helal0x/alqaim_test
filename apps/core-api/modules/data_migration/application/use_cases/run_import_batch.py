from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.data_migration.application.dto.data_migration_dto import CommitResultResponse
from modules.data_migration.application.ports.source_connector import SourceConnector
from modules.data_migration.application.ports.target_entity_registry import get_binding
from modules.data_migration.domain.entities.import_job import FieldMapping, apply_field_mappings
from modules.data_migration.domain.rules.import_status_transitions import assert_valid_transition
from modules.data_migration.domain.value_objects.enums import ImportStatus, TargetEntity
from modules.data_migration.infrastructure.models.data_migration_models import (
    ImportBatch,
    ImportRowError,
)
from modules.data_migration.infrastructure.repositories.data_migration_repository import (
    ImportJobRepository,
)
from platform_core.auth_middleware import TenantContext

_BATCH_SIZE = 500


class RunImportBatchUseCase:
    """المرحلة 5 (§4.3). الترحيل الفعلي: يستدعي use case الهدف الموجود
    فعلياً في كل موديول (عبر `target_entity_registry`) — **بلا استثناء** —
    تماماً كما حدث فعلياً مع TASK-AI-01 (استدعاء use case موجود، لا مسار
    مختصر يتجاوز قواعد العمل). سطر فاشل واحد يُسجَّل في ImportRowError ولا
    يوقف بقية الدفعة."""

    def __init__(self, session: AsyncSession, connector: SourceConnector) -> None:
        self._session = session
        self._connector = connector

    async def execute(
        self, ctx: TenantContext, job_id: str, target_entity: TargetEntity, source_table: str
    ) -> CommitResultResponse:
        job = await ImportJobRepository(self._session).get_by_id(job_id, company_id=ctx.company_id)
        if job is None:
            raise ValueError("مهمة الاستيراد غير موجودة")

        assert_valid_transition(ImportStatus(job.status), ImportStatus.COMMITTING)
        binding = get_binding(target_entity)  # يرفع NotImplementedError بوضوح إن كان غير مدعوم

        field_mappings = [
            FieldMapping(
                target_entity=TargetEntity(m["target_entity"]),
                source_column=m["source_column"],
                target_field=m["target_field"],
                transform=m.get("transform"),
            )
            for m in job.mappings
            if m.get("target_entity") == target_entity.value
        ]

        job.status = ImportStatus.COMMITTING.value
        await self._session.commit()

        # نلتقط job.id في متغيّر محلي الآن، قبل أي rollback محتمل داخل حلقة
        # المعالجة أدناه. AsyncSessionLocal مُعرَّفة بـ`expire_on_commit=False`
        # (platform_core/database.py) فتحمي القراءة بعد commit، لكن هذا
        # الإعداد لا يشمل rollback()، الذي يُفرِغ (expire) كل الخصائص دائماً
        # بصرف النظر عنه. فأي قراءة لاحقة لـjob.id بعد rollback ستحاول تحديثاً
        # متزامناً ضمنياً من القرص — وهذا يرمي MissingGreenlet تحت AsyncSession
        # (لا يمكن انتظاره ضمن وصول متزامن لخاصية). القراءة (set) على
        # job.status/job.processed_rows أدناه آمنة رغم ذلك لأن SQLAlchemy لا
        # يحتاج تحميل القيمة القديمة قبل الكتابة فوقها.
        job_id = job.id

        use_case = binding.use_case_cls(self._session)
        total = await self._connector.row_count(source_table)
        processed, error_count = 0, 0

        try:
            for offset in range(0, total, _BATCH_SIZE):
                rows = await self._connector.read_batch(source_table, offset=offset, limit=_BATCH_SIZE)
                batch_ok = True

                for row_number, row in enumerate(rows, start=offset + 1):
                    mapped = apply_field_mappings(row, field_mappings, target_entity=target_entity)
                    try:
                        request = binding.request_dto_cls.model_validate(mapped)
                        await use_case.execute(ctx, request)
                    except (ValidationError, ValueError, TypeError) as exc:
                        batch_ok = False
                        error_count += 1
                        # ⚠️ إصلاح ترتيب حرج: rollback أولاً لتنظيف أي حالة معاملة
                        # فاشلة خلّفها use_case.execute() (مثال: IntegrityError من
                        # قاعدة بيانات حقيقية)، ثم إضافة ImportRowError بعد ذلك.
                        # النسخة الأصلية كانت تُضيف الخطأ ثم تعمل rollback فوراً —
                        # وهذا يمحو سجل الخطأ نفسه قبل أن يُكتَب أبداً (rollback
                        # يُلغي أي كائن مُضاف لم يُلتزَم بعد)، فتضيع كل أخطاء
                        # الصفوف الفاشلة بصمت رغم نجاح استيراد بقية الدفعة.
                        await self._session.rollback()
                        self._session.add(
                            ImportRowError(
                                job_id=job_id,
                                row_number=row_number,
                                table_name=target_entity.value,
                                message=str(exc),
                                raw_row=row,
                            )
                        )
                    else:
                        processed += 1

                self._session.add(
                    ImportBatch(
                        job_id=job_id,
                        target_entity=target_entity.value,
                        offset=offset,
                        row_count=len(rows),
                        success=batch_ok,
                    )
                )
                job.processed_rows = processed
                await self._session.commit()  # commit بعد كل دفعة، لا دفعة ضخمة واحدة في النهاية
        finally:
            await self._connector.close()

        job.status = ImportStatus.COMPLETED.value
        job.total_rows = total
        await self._session.commit()

        return CommitResultResponse(
            job_id=job_id,
            status=ImportStatus.COMPLETED,
            processed_rows=processed,
            error_count=error_count,
        )
