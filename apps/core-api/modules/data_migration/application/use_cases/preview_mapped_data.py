from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.data_migration.application.dto.data_migration_dto import PreviewResultResponse
from modules.data_migration.application.ports.source_connector import SourceConnector
from modules.data_migration.application.ports.target_entity_registry import get_binding
from modules.data_migration.domain.entities.import_job import apply_field_mappings
from modules.data_migration.domain.rules.import_status_transitions import assert_valid_transition
from modules.data_migration.domain.value_objects.enums import ImportStatus, TargetEntity
from modules.data_migration.infrastructure.repositories.data_migration_repository import (
    ImportJobRepository,
)
from platform_core.auth_middleware import TenantContext

_PREVIEW_SAMPLE_SIZE = 200  # لا نمعاين كل الملايين — عيّنة كافية لتقدير جودة البيانات


class PreviewMappedDataUseCase:
    """المرحلة 4 (§4.3) — الأهم أمنياً: **صفر كتابة** على قاعدة بيانات
    AlQaim هنا. نقرأ عيّنة من المصدر، نطبّق mapping، ثم نُشغّل نفس DTO الهدف
    (Pydantic) الذي يستخدمه use case الإنشاء الفعلي — لكن فقط `.model_validate`
    وليس `.execute()` — فنحصل على أخطاء التحقق الحقيقية بلا أي كتابة."""

    def __init__(self, session: AsyncSession, connector: SourceConnector) -> None:
        self._session = session
        self._connector = connector

    async def execute(
        self, ctx: TenantContext, job_id: str, target_entity: TargetEntity, source_table: str
    ) -> PreviewResultResponse:
        job = await ImportJobRepository(self._session).get_by_id(job_id, company_id=ctx.company_id)
        if job is None:
            raise ValueError("مهمة الاستيراد غير موجودة")

        assert_valid_transition(ImportStatus(job.status), ImportStatus.PREVIEWED)

        binding = get_binding(target_entity)  # يرفع NotImplementedError بوضوح إن كان الكيان غير مدعوم بعد

        mappings = [
            m for m in job.mappings if m.get("target_entity") == target_entity.value
        ]
        if not mappings:
            raise ValueError(f"لا يوجد تعيين محفوظ لـ {target_entity.value} على هذه المهمة بعد")

        from modules.data_migration.domain.entities.import_job import FieldMapping

        field_mappings = [
            FieldMapping(
                target_entity=TargetEntity(m["target_entity"]),
                source_column=m["source_column"],
                target_field=m["target_field"],
                transform=m.get("transform"),
            )
            for m in mappings
        ]

        try:
            total_rows = await self._connector.row_count(source_table)
            sample = await self._connector.read_batch(
                source_table, offset=0, limit=min(_PREVIEW_SAMPLE_SIZE, total_rows or _PREVIEW_SAMPLE_SIZE)
            )
        finally:
            await self._connector.close()

        valid_rows, sample_errors = 0, []
        for row in sample:
            mapped = apply_field_mappings(row, field_mappings, target_entity=target_entity)
            try:
                binding.request_dto_cls.model_validate(mapped)
            except ValidationError as exc:
                sample_errors.append(str(exc.errors()[0]["msg"]) if exc.errors() else str(exc))
            except (ValueError, TypeError) as exc:
                sample_errors.append(str(exc))
            else:
                valid_rows += 1

        job.status = ImportStatus.PREVIEWED.value
        await self._session.commit()

        return PreviewResultResponse(
            target_entity=target_entity,
            total_rows=total_rows,
            valid_rows=valid_rows,
            error_count=len(sample) - valid_rows,
            sample_errors=sample_errors[:10],
        )
