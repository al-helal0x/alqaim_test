from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.application.dto.payments_dto import (
    BankAccountCreateRequest,
    BankAccountResponse,
)
from modules.payments.application.use_cases.payments_use_cases import CreateBankAccountUseCase
from modules.payments.infrastructure.repositories.payments_repository import (
    BankAccountRepository,
)
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("payments.bank_account.create"))],
)
async def create_bank_account(
    request: BankAccountCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> BankAccountResponse:
    account = await CreateBankAccountUseCase(session).execute(ctx, request)
    return BankAccountResponse.model_validate(account)


@router.get("", response_model=list[BankAccountResponse])
async def list_bank_accounts(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[BankAccountResponse]:
    accounts = await BankAccountRepository(session).list_for_company(company_id=ctx.company_id)
    return [BankAccountResponse.model_validate(a) for a in accounts]
