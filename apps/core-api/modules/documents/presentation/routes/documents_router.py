from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.application.dto.documents_dto import DocumentResponse
from modules.documents.application.use_cases.documents_use_cases import (
    DeleteDocumentUseCase,
    DownloadDocumentUseCase,
    ListDocumentsUseCase,
    UploadDocumentUseCase,
)
from modules.documents.infrastructure.external.local_file_storage import LocalFileStorage
from platform_core.auth_middleware import TenantContext, get_current_context, require_permission
from platform_core.database import get_db_session

router = APIRouter()


def _storage() -> LocalFileStorage:
    return LocalFileStorage()


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents.upload"))],
)
async def upload_document(
    entity_type: str = Form(...),
    entity_id: str = Form(...),
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    content = await file.read()
    try:
        document = await UploadDocumentUseCase(session, _storage()).execute(
            ctx,
            entity_type=entity_type,
            entity_id=entity_id,
            file_name=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DocumentResponse.model_validate(document)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentResponse]:
    documents = await ListDocumentsUseCase(session).execute(
        ctx, entity_type=entity_type, entity_id=entity_id
    )
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    try:
        document, content = await DownloadDocumentUseCase(session, _storage()).execute(
            ctx, document_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="الملف غير موجود في التخزين"
        ) from exc
    return Response(
        content=content,
        media_type=document.content_type,
        headers={"Content-Disposition": f'attachment; filename="{document.file_name}"'},
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("documents.delete"))],
)
async def delete_document(
    document_id: str,
    ctx: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await DeleteDocumentUseCase(session, _storage()).execute(ctx, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
