"""إنشاء السنوات/الفترات المالية وإقفالها.

إقفال فترة يُنشر حدث `FiscalPeriodClosed` عبر event_bus (contracts.md §2)
حتى تمنع كل الوحدات الأخرى الترحيل عليها من جهتها هي أيضاً (دفاع مضاعف:
هذه الوحدة تمنع الترحيل المباشر، والحدث يُبلّغ البقية فوراً).
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.application.dto.accounting_dto import FiscalYearCreateRequest
from modules.accounting.infrastructure.models.accounting_models import FiscalPeriod, FiscalYear
from platform_core.event_bus import event_bus


class FiscalPeriodNotFoundError(ValueError):
    pass


def _add_one_month(d: date) -> date:
    """يضيف شهراً واحداً إلى تاريخ، معالجاً تدوير السنة يدوياً بلا اعتماديات
    خارجية إضافية (تفادي إضافة حزمة جديدة لـ pyproject.toml لأجل هذا فقط)."""
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


class CreateFiscalYearUseCase:
    """ينشئ السنة المالية ويولّد فتراتها الشهرية تلقائياً (period_count فترة
    بالتساوي بين start_date و end_date)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, request: FiscalYearCreateRequest) -> FiscalYear:
        fiscal_year = FiscalYear(
            company_id=company_id,
            code=request.code,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        self._session.add(fiscal_year)
        await self._session.flush()

        period_start = request.start_date
        for period_number in range(1, request.period_count + 1):
            if period_number == request.period_count:
                period_end = request.end_date
            else:
                next_month_first_day = _add_one_month(
                    period_start.replace(day=1)
                )
                period_end = min(next_month_first_day - timedelta(days=1), request.end_date)
            self._session.add(
                FiscalPeriod(
                    company_id=company_id,
                    fiscal_year_id=fiscal_year.id,
                    period_number=period_number,
                    start_date=period_start,
                    end_date=period_end,
                )
            )
            period_start = period_end + timedelta(days=1)
            if period_start > request.end_date:
                break

        await self._session.commit()
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.id == fiscal_year.id)
            .options(selectinload(FiscalYear.periods))
        )
        return (await self._session.execute(stmt)).scalar_one()


class ClosePeriodUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str, period_id: str) -> FiscalPeriod:
        stmt = select(FiscalPeriod).where(
            FiscalPeriod.id == period_id, FiscalPeriod.company_id == company_id
        )
        period = (await self._session.execute(stmt)).scalar_one_or_none()
        if period is None:
            raise FiscalPeriodNotFoundError("الفترة المالية غير موجودة لهذه الشركة")

        period.is_closed = True
        period.closed_at = date.today()
        await self._session.commit()
        await self._session.refresh(period)

        await event_bus.publish(
            "FiscalPeriodClosed",
            {
                "company_id": company_id,
                "period_id": str(period.id),
                "closed_at": period.closed_at.isoformat(),
            },
        )
        return period


class ListFiscalYearsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, company_id: str) -> list[FiscalYear]:
        stmt = (
            select(FiscalYear)
            .where(FiscalYear.company_id == company_id, FiscalYear.deleted_at.is_(None))
            .options(selectinload(FiscalYear.periods))
            .order_by(FiscalYear.start_date)
        )
        return list((await self._session.execute(stmt)).scalars().all())
