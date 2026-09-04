from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.infrastructure.adapters.accounting_port_adapter import SqlAccountingPort
from modules.sales.application.dto.sales_dto import CreditNoteCreateRequest, CreditNoteResponse
from modules.sales.application.use_cases.sales_use_cases import (
    CreateAndPostCreditNoteUseCase,
    InvoiceNotDraftError,
)
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.post(
    "",
    response_model=CreditNoteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("sales.credit_note.create"))],
)
async def create_credit_note(
    request: CreditNoteCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> CreditNoteResponse:
    numbering_service = SqlNumberingService(session)
    use_case = CreateAndPostCreditNoteUseCase(
        session, SqlAccountingPort(session, numbering_service), numbering_service
    )
    try:
        credit_note = await use_case.execute(ctx, request)
    except (InvoiceNotDraftError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CreditNoteResponse.model_validate(credit_note)
