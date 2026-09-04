from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.application.dto.accounting_dto import AccountCreateRequest, AccountResponse
from modules.accounting.application.use_cases.chart_of_accounts_seed_use_case import (
    ChartOfAccountsAlreadySeededError,
    SeedDefaultChartOfAccountsUseCase,
)
from modules.accounting.application.use_cases.journal_use_cases import (
    CreateAccountUseCase,
    ListAccountsUseCase,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[AccountResponse]:
    accounts = await ListAccountsUseCase(session).execute(ctx.company_id)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.post(
    "",
    response_model=AccountResponse,
    dependencies=[Depends(require_permission("accounting.account.create"))],
)
async def create_account(
    request: AccountCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> AccountResponse:
    account = await CreateAccountUseCase(session).execute(ctx.company_id, request)
    return AccountResponse.model_validate(account)


@router.post(
    "/seed-defaults",
    response_model=list[AccountResponse],
    dependencies=[Depends(require_permission("accounting.account.create"))],
)
async def seed_default_chart_of_accounts(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[AccountResponse]:
    """يزرع شجرة حسابات افتراضية (~25 حساباً) لشركة جديدة بلا حسابات بعد.
    يفشل صراحةً (409) إن كانت الشركة تملك حسابات مسبقاً."""
    try:
        accounts = await SeedDefaultChartOfAccountsUseCase(session).execute(ctx.company_id)
    except ChartOfAccountsAlreadySeededError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [AccountResponse.model_validate(a) for a in accounts]
