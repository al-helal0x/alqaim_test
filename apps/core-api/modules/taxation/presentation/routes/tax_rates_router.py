from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.taxation.application.dto.taxation_dto import (
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxRateCreateRequest,
    TaxRateResponse,
)
from modules.taxation.application.use_cases.tax_use_cases import (
    CalculateTaxUseCase,
    CreateTaxRateUseCase,
    ListTaxRatesUseCase,
    TaxRateNotFoundError,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.get("", response_model=list[TaxRateResponse])
async def list_tax_rates(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaxRateResponse]:
    rates = await ListTaxRatesUseCase(session).execute(ctx.company_id)
    return [TaxRateResponse.model_validate(r) for r in rates]


@router.post(
    "",
    response_model=TaxRateResponse,
    dependencies=[Depends(require_permission("taxation.tax_rate.create"))],
)
async def create_tax_rate(
    request: TaxRateCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> TaxRateResponse:
    tax_rate = await CreateTaxRateUseCase(session).execute(ctx.company_id, request)
    return TaxRateResponse.model_validate(tax_rate)


@router.post("/calculate", response_model=TaxCalculationResponse)
async def calculate_tax(
    request: TaxCalculationRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> TaxCalculationResponse:
    try:
        result = await CalculateTaxUseCase(session).execute(
            ctx.company_id, request.tax_rate_id, request.base_amount
        )
    except TaxRateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TaxCalculationResponse(**result)
