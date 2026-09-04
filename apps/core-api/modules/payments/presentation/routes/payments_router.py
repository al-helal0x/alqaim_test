from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payments.application.dto.payments_dto import PaymentCreateRequest, PaymentResponse
from modules.payments.application.use_cases.payments_use_cases import CreatePaymentUseCase
from modules.payments.infrastructure.repositories.payments_repository import PaymentRepository
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session
from platform_core.event_bus import event_bus

router = APIRouter()


@router.post(
    "", response_model=PaymentResponse, status_code=201,
    dependencies=[Depends(require_permission("payments.payment.create"))],
)
async def create_payment(
    request: PaymentCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentResponse:
    payment = await CreatePaymentUseCase(session, event_bus).execute(ctx, request)
    return PaymentResponse.model_validate(payment)


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[PaymentResponse]:
    payments = await PaymentRepository(session).list_for_company(company_id=ctx.company_id)
    return [PaymentResponse.model_validate(p) for p in payments]
