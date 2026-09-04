from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.infrastructure.models.documents_models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, document_id: str, *, company_id: str) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
            Document.deleted_at.is_(None),
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_entity(
        self, *, company_id: str, entity_type: str, entity_id: str
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(
                Document.company_id == company_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())
