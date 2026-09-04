from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.application.dto.accounting_dto import (
    JournalEntryCreateRequest,
    JournalEntryResponse,
)
from modules.accounting.application.use_cases.journal_use_cases import (
    AccountNotFoundError,
    FiscalPeriodClosedError,
    ListJournalEntriesUseCase,
    NoOpenFiscalPeriodError,
    PostManualJournalEntryUseCase,
)
from modules.accounting.domain.rules.journal_balance_rule import (
    EmptyJournalEntryError,
    UnbalancedJournalEntryError,
)
from modules.accounting.infrastructure.models.accounting_models import JournalEntry
from modules.tenancy.infrastructure.repositories.numbering_service import SqlNumberingService
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


@router.get("", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[JournalEntryResponse]:
    entries = await ListJournalEntriesUseCase(session).execute(ctx.company_id)
    return [JournalEntryResponse.model_validate(e) for e in entries]


@router.post(
    "",
    response_model=JournalEntryResponse,
    dependencies=[Depends(require_permission("accounting.journal_entry.post"))],
)
async def post_manual_journal_entry(
    request: JournalEntryCreateRequest,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> JournalEntryResponse:
    # طبقة التوصيل (Composition Root): هنا فقط يُحقن التنفيذ الفعلي لـ
    # INumberingService من وحدة tenancy — منطق الأعمال في journal_use_cases
    # لا يعرف شيئاً عن SqlNumberingService (القسم 11.2).
    numbering_service = SqlNumberingService(session)

    try:
        entry = await PostManualJournalEntryUseCase(session, numbering_service).execute(
            company_id=ctx.company_id,
            entry_date=request.entry_date,
            memo=request.memo,
            currency=request.currency,
            lines=request.lines,
        )
    except (
        UnbalancedJournalEntryError,
        EmptyJournalEntryError,
        NoOpenFiscalPeriodError,
        FiscalPeriodClosedError,
        AccountNotFoundError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return JournalEntryResponse.model_validate(entry)


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> JournalEntryResponse:
    stmt = (
        select(JournalEntry)
        .where(JournalEntry.id == entry_id, JournalEntry.company_id == ctx.company_id)
        .options(selectinload(JournalEntry.lines))
    )
    entry = (await session.execute(stmt)).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="القيد غير موجود")
    return JournalEntryResponse.model_validate(entry)
