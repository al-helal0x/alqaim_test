from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.partners.application.dto.partner_dto import (
    PartnerCreateRequest,
    PartnerUpdateRequest,
)
from modules.partners.domain.rules import WALK_IN_PARTNER_NAME, PartnerType, validate_credit_limit
from modules.partners.infrastructure.models.partner_models import Partner
from platform_core.auth_middleware import TenantContext
from shared_kernel.pagination import PageParams, paginate


class PartnerNotFoundError(ValueError):
    """يُستخدَم بدل ValueError عام في _get_owned_partner كي يستطيع الراوتر
    تمييز "غير موجود/لا يعود لشركتك" (يجب أن يُصبح 404) عن أخطاء تحقّق
    عمل حقيقية أخرى مثل validate_credit_limit (تبقى 400) — قبل هذا التمييز
    كان UpdatePartnerUseCase يُرجع 400 لكلتا الحالتين، وهو ما اكتُشِف فقط
    بتشغيل test_idor_partners.py::test_partner_update_is_isolated فعلياً
    هنا (العزل نفسه كان يعمل بشكل صحيح دائماً — لا تسريب بيانات، فقط رمز
    حالة HTTP غير متسق مع GET /partners/{id} المجاور الذي يُرجع 404 بالفعل
    لنفس هذه الحالة عبر GetPartnerUseCase)."""


class DuplicateTaxNumberError(ValueError):
    """QA_FINDINGS_apps_web_manual_test.md #2 — تُستخدَم بدل السماح لـ
    IntegrityError الخام بالتسرب كـ500 غير معالَج. القيد الحالي
    (`UniqueConstraint("company_id", "tax_number")` في partner_models.py)
    عالمي على مستوى الشركة بلا تفرقة حسب `partner_type` — هذا سؤال تصميم
    منتجي (هل عميل ومورد بنفس الرقم الضريبي حالة مسموحة؟) لم يُحسَم هنا
    عمداً، فقط تُرجَم رسالة الخطأ الخام لرسالة عربية مفهومة بدل تغيير سلوك
    القيد نفسه من طرف واحد."""


class CreatePartnerUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: PartnerCreateRequest) -> Partner:
        validate_credit_limit(request.credit_limit)

        partner = Partner(
            company_id=ctx.company_id,
            name=request.name,
            partner_type=request.partner_type.value,
            tax_number=request.tax_number,
            phone=request.phone,
            email=request.email,
            address=request.address,
            credit_limit=request.credit_limit,
            payment_terms_days=request.payment_terms_days,
        )
        self._session.add(partner)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if request.tax_number and "tax_number" in str(getattr(exc, "orig", exc)):
                raise DuplicateTaxNumberError(
                    "الرقم الضريبي مستخدَم بالفعل من طرف عميل أو مورد آخر لهذه الشركة"
                ) from exc
            raise
        await self._session.refresh(partner)
        return partner


class GetOrCreateWalkInPartnerUseCase:
    """PKG-B2 — find-or-create لِـ"عميل نقدي" (walk-in) الخاص بالشركة.

    الكاشير "يطلب" العميل النقدي، لا "ينشئه" — لذلك هذا use case منفصل عن
    CreatePartnerUseCase تماماً (لا يمر بـ endpoint العام `POST /partners`
    ولا بصلاحيته `partners.partner.create`؛ يُستهلَك حصراً من endpoint محمي
    بـ`pos.sale.create`، راجع partners_walkin_router.py).

    اعتماد السباق: التحقق قبل الإدخال (check-then-insert) وحده قابل للسباق
    نظرياً بين طلبين شبه-متزامنين؛ خط الدفاع الفعلي هو Partial Unique
    Index على `(company_id) WHERE is_system_managed = true` من PKG-B1 على
    مستوى DB. عند تصادم سباق فعلي (IntegrityError)، لا يُرفَع الخطأ للمستخدم
    النهائي — نُعيد البحث ونُعيد نفس الصف الذي أنشأه الطلب الآخر (نفس نمط
    idempotency #11 الموجود مسبقاً في SyncPosSalesUseCase: check-then-insert
    مع fallback بدل فشل ظاهر للمستخدم).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext) -> Partner:
        existing = await self._find(ctx)
        if existing is not None:
            return existing

        partner = Partner(
            company_id=ctx.company_id,
            name=WALK_IN_PARTNER_NAME,
            partner_type=PartnerType.CUSTOMER.value,
            is_system_managed=True,
        )
        self._session.add(partner)
        try:
            await self._session.commit()
        except IntegrityError:
            # سباق حقيقي: طلب آخر متزامن نجح بالإدخال قبلنا بجزء من الثانية.
            # الفهرس الجزئي الفريد (PKG-B1) هو ما رفض إدخالنا هنا — نتعافى
            # بإعادة البحث بدل تمرير الخطأ للمستخدم (لا فشل ظاهر له في أي حالة).
            await self._session.rollback()
            existing = await self._find(ctx)
            if existing is None:
                # احتياط دفاعي صريح: IntegrityError حدث فعلاً لكن لا يوجد صف
                # walk-in ظاهر بعد إعادة البحث (مثال: قيد آخر غير متوقع على
                # الجدول) — لا نُخفي هذه الحالة الشاذة، نُعيد رفع الخطأ الأصلي.
                raise
            return existing

        await self._session.refresh(partner)
        return partner

    async def _find(self, ctx: TenantContext) -> Partner | None:
        stmt = select(Partner).where(
            Partner.company_id == ctx.company_id,
            Partner.is_system_managed.is_(True),
            Partner.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class UpdatePartnerUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, partner_id: str, request: PartnerUpdateRequest
    ) -> Partner:
        partner = await _get_owned_partner(self._session, ctx, partner_id)

        updates = request.model_dump(exclude_unset=True)
        if "credit_limit" in updates:
            validate_credit_limit(updates["credit_limit"])
        if "partner_type" in updates and updates["partner_type"] is not None:
            updates["partner_type"] = updates["partner_type"].value

        for field, value in updates.items():
            setattr(partner, field, value)

        await self._session.commit()
        await self._session.refresh(partner)
        return partner


class GetPartnerUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, partner_id: str) -> Partner:
        return await _get_owned_partner(self._session, ctx, partner_id)


class ListPartnersUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, *, partner_type: str | None = None
    ) -> list[Partner]:
        stmt = select(Partner).where(
            Partner.company_id == ctx.company_id, Partner.deleted_at.is_(None)
        )
        if partner_type is not None:
            stmt = stmt.where(Partner.partner_type == partner_type)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ListPartnersPageUseCase:
    """نسخة مرقّمة (Pagination) من ListPartnersUseCase — القسم 9.3. مستقلة عن
    الأصلية لتفادي كسر أي مستهلك داخلي يعتمد على قائمة كاملة غير مقسّمة."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self, ctx: TenantContext, params: PageParams, *, partner_type: str | None = None
    ) -> tuple[list[Partner], int]:
        stmt = select(Partner).where(
            Partner.company_id == ctx.company_id, Partner.deleted_at.is_(None)
        )
        if partner_type is not None:
            stmt = stmt.where(Partner.partner_type == partner_type)
        return await paginate(self._session, stmt, Partner, params)


async def _get_owned_partner(session: AsyncSession, ctx: TenantContext, partner_id: str) -> Partner:
    """يفرض عزل الشركة: لا يُسمح مطلقاً بالوصول لشريك يعود لشركة أخرى (القسم 6.10)."""
    stmt = select(Partner).where(
        Partner.id == partner_id,
        Partner.company_id == ctx.company_id,
        Partner.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    partner = result.scalar_one_or_none()
    if partner is None:
        raise PartnerNotFoundError("الشريك غير موجود أو لا يعود لشركتك")
    return partner
