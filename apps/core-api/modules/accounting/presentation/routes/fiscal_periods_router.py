from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.application.dto.accounting_dto import (
    FiscalYearCreateRequest,
    FiscalYearResponse,
)
from modules.accounting.application.use_cases.fiscal_period_use_cases import (
    ClosePeriodUseCase,
    CreateFiscalYearUseCase,
    FiscalPeriodAlreadyClosedError,
    FiscalPeriodNotFoundError,
    ListFiscalYearsUseCase,
    RetainedEarningsAccountMissingError,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from platform_core.event_bus import event_bus

router = APIRouter()


@router.get("/years", response_model=list[FiscalYearResponse])
async def list_fiscal_years(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[FiscalYearResponse]:
    years = await ListFiscalYearsUseCase(session).execute(ctx.company_id)
    return [FiscalYearResponse.model_validate(y) for y in years]


@router.post(
    "/years",
    response_model=FiscalYearResponse,
    dependencies=[Depends(require_permission("accounting.fiscal_year.create"))],
)
async def create_fiscal_year(
    request: FiscalYearCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> FiscalYearResponse:
    fiscal_year = await CreateFiscalYearUseCase(session).execute(ctx.company_id, request)
    return FiscalYearResponse.model_validate(fiscal_year)


@router.post(
    "/{period_id}/close",
    dependencies=[Depends(require_permission("accounting.fiscal_period.close"))],
)
async def close_fiscal_period(
    period_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # طبقة التوصيل (Composition Root): إقفال الفترة يبني قيد إقفال فعلي
    # فيحتاج نفس INumberingService الذي يستخدمه أي ترحيل آخر (يطابق نمط
    # journal_entries_router.py)، ويحقن event_bus الحقيقي (Singleton
    # العملية) بدل استيراده مباشرة داخل الـ Use Case — نفس نمط
    # CreatePaymentUseCase في modules/payments/presentation/routes
    # /payments_router.py، ويسمح باختبار الـ Use Case بمعزل تام عبر حقن
    # EventBus محلي في الاختبارات.
    numbering_service = SqlNumberingService(session)
    try:
        period = await ClosePeriodUseCase(session, numbering_service, event_bus).execute(
            ctx.company_id, period_id
        )
    except FiscalPeriodNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (FiscalPeriodAlreadyClosedError, RetainedEarningsAccountMissingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return {"id": str(period.id), "is_closed": period.is_closed}
