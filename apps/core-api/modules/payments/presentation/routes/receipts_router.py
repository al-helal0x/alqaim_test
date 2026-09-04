from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.application.dto.payments_dto import ReceiptCreateRequest, ReceiptResponse
from modules.payments.application.use_cases.payments_use_cases import CreateReceiptUseCase
from modules.payments.infrastructure.repositories.payments_repository import ReceiptRepository
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "", response_model=ReceiptResponse, status_code=201,
    dependencies=[Depends(require_permission("payments.receipt.create"))],
)
async def create_receipt(
    request: ReceiptCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ReceiptResponse:
    receipt = await CreateReceiptUseCase(session).execute(ctx, request)
    return ReceiptResponse.model_validate(receipt)


@router.get("", response_model=list[ReceiptResponse])
async def list_receipts(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[ReceiptResponse]:
    receipts = await ReceiptRepository(session).list_for_company(company_id=ctx.company_id)
    return [ReceiptResponse.model_validate(r) for r in receipts]
