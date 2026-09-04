from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.infrastructure.models.payments_models import BankAccount, Payment, Receipt


class BankAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_company(self, *, company_id: str) -> list[BankAccount]:
        stmt = select(BankAccount).where(
            BankAccount.company_id == company_id, BankAccount.deleted_at.is_(None)
        )
        return list((await self._session.execute(stmt)).scalars().all())


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, payment_id: str, *, company_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id, Payment.company_id == company_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(self, *, company_id: str) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.company_id == company_id, Payment.deleted_at.is_(None))
            .order_by(Payment.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())


class ReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, receipt_id: str, *, company_id: str) -> Receipt | None:
        stmt = select(Receipt).where(Receipt.id == receipt_id, Receipt.company_id == company_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_company(self, *, company_id: str) -> list[Receipt]:
        stmt = (
            select(Receipt)
            .where(Receipt.company_id == company_id, Receipt.deleted_at.is_(None))
            .order_by(Receipt.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())
