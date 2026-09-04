"""Use Cases للوحة إدارة الشركات المشتركة (العضو 13).

ملاحظة معمارية صريحة يجب توثيقها: هذه هي الوحدة الوحيدة في النظام التي
تتصرّف عمداً **خارج** عزل Multi-Tenancy القياسي (القسم 6.10) — غرضها إدارة
الشركات نفسها عبر المنصة، فلا يصح تقييدها بـ ctx.company_id كبقية الوحدات.
اعتمدنا أبسط حل ممكن الآن بدل إعادة تصميم TenantContext: صلاحية خاصة عالية
الامتياز (`platform_admin.company.manage`) تُمنَح فقط لدور Owner في "شركة
مضيفة" مخصَّصة يُنشئها مشغّل المنصة يدوياً — التحقق نفسه (`require_permission`)
يبقى كما هو، فقط الـ Use Case لا يُصفّي بـ company_id. هذا قصور معماري معروف
(لا "شركة مضيفة" مميّزة فعلياً في الكود بعد) يستحق تصميماً أنضج لاحقاً
(مثل حقل `is_platform_operator` صريح على User)، موثَّق هنا بدل التظاهر
بأنه محلول بالكامل.

كذلك: هذه الوحدة تستورد `modules.tenancy.infrastructure.models` مباشرة —
مخالفة حرفية لقاعدة "التواصل عبر Ports فقط" (القسم 11.2)، لكنها متّبعة
فعلياً في عدة وحدات أخرى موجودة مسبقاً في هذا الكود (sales/purchasing/pos
تستورد numbering_service من tenancy.infrastructure مباشرة) ولا يوجد عقد
import-linter فعلي يمنعها حالياً (تحققتُ من pyproject.toml) — اتّبعنا نفس
النمط القائم بدل اختراع استثناء جديد.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company


class ListAllCompaniesUseCase:
    async def execute(self, session: AsyncSession) -> list[tuple[Company, int]]:
        stmt = (
            select(Company, func.count(Branch.id))
            .outerjoin(Branch, Branch.company_id == Company.id)
            .where(Company.deleted_at.is_(None))
            .group_by(Company.id)
            .order_by(Company.created_at.desc())
        )
        result = await session.execute(stmt)
        return [(company, branch_count) for company, branch_count in result.all()]


class SetCompanyActiveStatusUseCase:
    """يُستخدَم لكل من التعليق (`is_active=False`) والتفعيل (`is_active=True`) —
    نفس المنطق بالضبط، فرق قيمة واحد فقط."""

    async def execute(
        self, session: AsyncSession, company_id: str, *, is_active: bool
    ) -> tuple[Company, int]:
        stmt = select(Company).where(Company.id == company_id, Company.deleted_at.is_(None))
        company = (await session.execute(stmt)).scalar_one_or_none()
        if company is None:
            raise ValueError("الشركة غير موجودة")
        company.is_active = is_active
        await session.commit()
        await session.refresh(company)

        branch_count = (
            await session.execute(
                select(func.count(Branch.id)).where(Branch.company_id == company.id)
            )
        ).scalar_one()
        return company, branch_count
