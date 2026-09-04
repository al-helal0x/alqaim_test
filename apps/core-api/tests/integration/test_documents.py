"""يغطي معيار تسليم العضو 13 (documents): رفع مرفق فعلي على القرص عبر
LocalFileStorage، سرده لكيان محدَّد، تنزيله والتأكد أن البايتات مطابقة
لما رُفِع، ثم حذفه (Soft-delete على الجدول + حذف فعلي من التخزين)."""
import shutil
import tempfile

import pytest

from modules.documents.application.use_cases.documents_use_cases import (
    DeleteDocumentUseCase,
    DownloadDocumentUseCase,
    ListDocumentsUseCase,
    UploadDocumentUseCase,
)
from modules.documents.infrastructure.external.local_file_storage import LocalFileStorage
from modules.identity.application.dto.identity_dto import RegisterCompanyRequest
from modules.identity.application.use_cases.auth_use_cases import RegisterCompanyUseCase
from platform_core.auth_middleware import TenantContext
from platform_core.security import decode_token

pytestmark = pytest.mark.asyncio


async def _register(db_session, email: str) -> TenantContext:
    tokens = await RegisterCompanyUseCase(db_session).execute(
        RegisterCompanyRequest(
            company_name=f"Company for {email}", admin_full_name="Admin",
            admin_email=email, admin_password="StrongPass123",
        )
    )
    payload = decode_token(tokens.access_token, expected_type="access")
    return TenantContext(company_id=payload["company_id"], user_id=payload["sub"])


@pytest.fixture
def tmp_storage():
    tmp_dir = tempfile.mkdtemp(prefix="alqaim_documents_test_")
    yield LocalFileStorage(base_dir=tmp_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)


async def test_upload_list_download_delete_document(db_session, tmp_storage):
    ctx = await _register(db_session, "docs-a@alqaim-demo.com")
    content = b"%PDF-1.4 fake invoice scan bytes"

    document = await UploadDocumentUseCase(db_session, tmp_storage).execute(
        ctx,
        entity_type="purchase_invoice",
        entity_id="inv-123",
        file_name="scan.pdf",
        content_type="application/pdf",
        content=content,
    )
    assert document.size_bytes == len(content)

    listed = await ListDocumentsUseCase(db_session).execute(
        ctx, entity_type="purchase_invoice", entity_id="inv-123"
    )
    assert len(listed) == 1
    assert listed[0].id == document.id

    fetched_document, fetched_bytes = await DownloadDocumentUseCase(db_session, tmp_storage).execute(
        ctx, str(document.id)
    )
    assert fetched_bytes == content
    assert fetched_document.file_name == "scan.pdf"

    await DeleteDocumentUseCase(db_session, tmp_storage).execute(ctx, str(document.id))

    remaining = await ListDocumentsUseCase(db_session).execute(
        ctx, entity_type="purchase_invoice", entity_id="inv-123"
    )
    assert remaining == []

    with pytest.raises(ValueError):
        await DownloadDocumentUseCase(db_session, tmp_storage).execute(ctx, str(document.id))


async def test_document_upload_enforces_size_and_isolation(db_session, tmp_storage):
    ctx_a = await _register(db_session, "docs-b@alqaim-demo.com")
    ctx_b = await _register(db_session, "docs-c@alqaim-demo.com")

    with pytest.raises(ValueError):
        await UploadDocumentUseCase(db_session, tmp_storage).execute(
            ctx_a, entity_type="x", entity_id="1", file_name="empty.txt",
            content_type="text/plain", content=b"",
        )

    document = await UploadDocumentUseCase(db_session, tmp_storage).execute(
        ctx_a, entity_type="note", entity_id="n1", file_name="a.txt",
        content_type="text/plain", content=b"hello",
    )

    # عزل الشركات: شركة أخرى لا تستطيع رؤية المستند حتى لو عرفت معرِّفه
    other_company_view = await ListDocumentsUseCase(db_session).execute(
        ctx_b, entity_type="note", entity_id="n1"
    )
    assert other_company_view == []

    with pytest.raises(ValueError):
        await DownloadDocumentUseCase(db_session, tmp_storage).execute(ctx_b, str(document.id))
