from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.purchasing.infrastructure.models.purchasing_models import (
    PurchaseInvoice,
    PurchaseOrder,
)


class PurchaseOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: str, *, company_id: str) -> PurchaseOrder | None:
        stmt = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(PurchaseOrder.id == order_id, PurchaseOrder.company_id == company_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(self, *, company_id: str) -> list[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(PurchaseOrder.company_id == company_id, PurchaseOrder.deleted_at.is_(None))
            .order_by(PurchaseOrder.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())


class PurchaseInvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, invoice_id: str, *, company_id: str) -> PurchaseInvoice | None:
        stmt = (
            select(PurchaseInvoice)
            .options(selectinload(PurchaseInvoice.lines))
            .where(PurchaseInvoice.id == invoice_id, PurchaseInvoice.company_id == company_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(self, *, company_id: str) -> list[PurchaseInvoice]:
        """أضيفت لسدّ فجوة: لم يكن هناك سبيل لاسترجاع فواتير الشراء كقائمة
        (فقط get_by_id) — الواجهة (العضو 7) تحتاجها. نفس نمط
        PurchaseOrderRepository.list_for_company تماماً."""
        stmt = (
            select(PurchaseInvoice)
            .options(selectinload(PurchaseInvoice.lines))
            .where(PurchaseInvoice.company_id == company_id, PurchaseInvoice.deleted_at.is_(None))
            .order_by(PurchaseInvoice.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_by_ai_draft_id(
        self, *, company_id: str, source_ai_draft_id: str
    ) -> PurchaseInvoice | None:
        """جزء من TASK-AI-01 (Idempotency: draft_id كـ idempotency_key) —
        نفس نمط `_find_invoice_by_idempotency_key` في sales_use_cases.py."""
        stmt = (
            select(PurchaseInvoice)
            .options(selectinload(PurchaseInvoice.lines))
            .where(
                PurchaseInvoice.company_id == company_id,
                PurchaseInvoice.source_ai_draft_id == source_ai_draft_id,
            )
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
