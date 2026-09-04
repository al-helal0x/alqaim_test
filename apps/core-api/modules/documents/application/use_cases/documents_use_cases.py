"""Use Cases لموديول documents (العضو 13). التخزين الفعلي يمر حصراً عبر
IFileStorage (Port) — لا مسار قرص مكتوب هنا مباشرة، حتى يمكن استبدال
LocalFileStorage بتنفيذ MinIO لاحقاً دون تعديل هذه الطبقة (القسم 11.2)."""
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.application.ports.file_storage_port import IFileStorage
from modules.documents.infrastructure.models.documents_models import Document
from modules.documents.infrastructure.repositories.documents_repository import (
    DocumentRepository,
)
from platform_core.auth_middleware import TenantContext

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25MB — حد معقول لمرفقات فواتير/مستندات ممسوحة ضوئياً


class UploadDocumentUseCase:
    def __init__(self, session: AsyncSession, storage: IFileStorage) -> None:
        self._session = session
        self._storage = storage

    async def execute(
        self,
        ctx: TenantContext,
        *,
        entity_type: str,
        entity_id: str,
        file_name: str,
        content_type: str,
        content: bytes,
    ) -> Document:
        if not content:
            raise ValueError("الملف فارغ")
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"حجم الملف يتجاوز الحد الأقصى المسموح ({MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB)"
            )

        storage_key = await self._storage.save(
            company_id=ctx.company_id, key=file_name, content=content
        )
        document = Document(
            company_id=ctx.company_id,
            entity_type=entity_type,
            entity_id=entity_id,
            file_name=file_name,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(content),
            storage_key=storage_key,
            uploaded_by=ctx.user_id,
        )
        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)
        return document


class ListDocumentsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, ctx: TenantContext, *, entity_type: str, entity_id: str) -> list[Document]:
        return await DocumentRepository(self._session).list_for_entity(
            company_id=ctx.company_id, entity_type=entity_type, entity_id=entity_id
        )


class DownloadDocumentUseCase:
    def __init__(self, session: AsyncSession, storage: IFileStorage) -> None:
        self._session = session
        self._storage = storage

    async def execute(self, ctx: TenantContext, document_id: str) -> tuple[Document, bytes]:
        document = await DocumentRepository(self._session).get_by_id(
            document_id, company_id=ctx.company_id
        )
        if document is None:
            raise ValueError("المستند غير موجود")
        content = await self._storage.load(document.storage_key)
        return document, content


class DeleteDocumentUseCase:
    def __init__(self, session: AsyncSession, storage: IFileStorage) -> None:
        self._session = session
        self._storage = storage

    async def execute(self, ctx: TenantContext, document_id: str) -> None:
        repo = DocumentRepository(self._session)
        document = await repo.get_by_id(document_id, company_id=ctx.company_id)
        if document is None:
            raise ValueError("المستند غير موجود")
        await self._storage.delete(document.storage_key)
        document.deleted_at = datetime.now(UTC)
        await self._session.commit()
