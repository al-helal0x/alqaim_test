from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.application.dto.tenancy_dto import (
    BranchCreateRequest,
    CompanyCreateRequest,
    WarehouseCreateRequest,
)
from modules.tenancy.infrastructure.models.tenancy_models import Branch, Company, Warehouse
from platform_core.auth_middleware import TenantContext


class CreateCompanyUseCase:
    """يُستدعى فقط من مسار التسجيل الأولي (Bootstrap) أو من لوحة مزوّد الخدمة —
    وليس من endpoint عام مفتوح لأي مستخدم مسجَّل دخوله بالفعل."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, request: CompanyCreateRequest) -> Company:
        company = Company(
            name=request.name,
            legal_name=request.legal_name,
            tax_number=request.tax_number,
            default_currency=request.default_currency,
        )
        self._session.add(company)
        await self._session.flush()
        return company


class CreateBranchUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: BranchCreateRequest) -> Branch:
        branch = Branch(company_id=ctx.company_id, name=request.name)
        self._session.add(branch)
        await self._session.commit()
        await self._session.refresh(branch)
        return branch


class CreateWarehouseUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, request: WarehouseCreateRequest) -> Warehouse:
        # تحقق عزل الشركة: الفرع المطلوب يجب أن يعود لنفس شركة المستخدم الحالي
        stmt = select(Branch).where(
            Branch.id == request.branch_id, Branch.company_id == ctx.company_id
        )
        result = await self._session.execute(stmt)
        branch = result.scalar_one_or_none()
        if branch is None:
            raise ValueError("الفرع غير موجود أو لا يعود لشركتك")

        warehouse = Warehouse(
            company_id=ctx.company_id, branch_id=branch.id, name=request.name
        )
        self._session.add(warehouse)
        await self._session.commit()
        await self._session.refresh(warehouse)
        return warehouse


class ListBranchesUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext) -> list[Branch]:
        stmt = select(Branch).where(
            Branch.company_id == ctx.company_id, Branch.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class ListWarehousesUseCase:
    """أضيفت لسدّ فجوة حقيقية: لا وسيلة كانت متاحة لاسترجاع مستودعات الشركة
    بعد إنشائها (فقط POST كان موجوداً) — الواجهة (العضو 7) تحتاجها لاختيار
    مستودع في شاشات المخزون. نفس نمط ListBranchesUseCase تماماً."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, branch_id: str | None = None) -> list[Warehouse]:
        conditions = [Warehouse.company_id == ctx.company_id, Warehouse.deleted_at.is_(None)]
        if branch_id:
            conditions.append(Warehouse.branch_id == branch_id)
        stmt = select(Warehouse).where(*conditions)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
