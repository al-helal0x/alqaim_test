from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.application.dto.accounting_dto import (
    BalanceSheetResponse,
    IncomeStatementResponse,
    StatementRowResponse,
    TrialBalanceResponse,
    TrialBalanceRow,
)
from modules.reporting.application.dto.business_pulse_dto import BusinessPulseResponse
from modules.reporting.application.use_cases.business_pulse_use_case import BusinessPulseUseCase
from modules.reporting.application.use_cases.financial_statements_use_case import (
    FiscalYearNotFoundError,
    GetBalanceSheetUseCase,
    GetIncomeStatementUseCase,
)
from modules.reporting.application.use_cases.trial_balance_use_case import GetTrialBalanceUseCase
from platform_core.auth_middleware import TenantContext, get_current_context
from platform_core.database import get_db_session

router = APIRouter()


@router.get("/business-pulse", response_model=BusinessPulseResponse)
async def get_business_pulse(
    period_days: int = Query(default=7, ge=1, le=90),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> BusinessPulseResponse:
    """TASK-BI-01 — لوحة "نبض الشركة اليومي": 5 مؤشرات فقط (راجع بطاقة
    المهمة)، بلا أي طبقة AI/تفسير — عرض بيانات خام مُجمَّعة حصراً."""
    return await BusinessPulseUseCase(session).execute(ctx, period_days=period_days)


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    fiscal_period_id: str = Query(...),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> TrialBalanceResponse:
    rows = await GetTrialBalanceUseCase(session).execute(ctx.company_id, fiscal_period_id)

    response_rows = [
        TrialBalanceRow(
            account_id=str(r.account_id),
            account_code=r.account_code,
            account_name=r.account_name,
            total_debit=r.total_debit,
            total_credit=r.total_credit,
            balance=r.balance,
        )
        for r in rows
    ]
    total_debit = sum((r.total_debit for r in response_rows), Decimal(0))
    total_credit = sum((r.total_credit for r in response_rows), Decimal(0))

    return TrialBalanceResponse(
        fiscal_period_id=fiscal_period_id,
        rows=response_rows,
        is_balanced=(total_debit == total_credit),
    )


@router.get("/income-statement", response_model=IncomeStatementResponse)
async def get_income_statement(
    fiscal_year_id: str = Query(...),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> IncomeStatementResponse:
    try:
        result = await GetIncomeStatementUseCase(session).execute(ctx.company_id, fiscal_year_id)
    except FiscalYearNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return IncomeStatementResponse(
        fiscal_year_id=result["fiscal_year_id"],
        revenue_rows=[StatementRowResponse(**vars(r)) for r in result["revenue_rows"]],
        expense_rows=[StatementRowResponse(**vars(r)) for r in result["expense_rows"]],
        total_revenue=result["total_revenue"],
        total_expense=result["total_expense"],
        net_income=result["net_income"],
    )


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def get_balance_sheet(
    fiscal_year_id: str = Query(...),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> BalanceSheetResponse:
    try:
        result = await GetBalanceSheetUseCase(session).execute(ctx.company_id, fiscal_year_id)
    except FiscalYearNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return BalanceSheetResponse(
        fiscal_year_id=result["fiscal_year_id"],
        asset_rows=[StatementRowResponse(**vars(r)) for r in result["asset_rows"]],
        liability_rows=[StatementRowResponse(**vars(r)) for r in result["liability_rows"]],
        equity_rows=[StatementRowResponse(**vars(r)) for r in result["equity_rows"]],
        current_period_net_income=result["current_period_net_income"],
        total_assets=result["total_assets"],
        total_liabilities=result["total_liabilities"],
        total_equity=result["total_equity"],
        is_balanced=result["is_balanced"],
    )
