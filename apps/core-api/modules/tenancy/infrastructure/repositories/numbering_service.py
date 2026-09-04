"""تنفيذ INumberingService — القسم 17: يجب أن يكون آمناً تحت التزامن العالي.

الطريقة: SELECT ... FOR UPDATE على صف (company_id, document_type) لضمان أن
عمليتين متزامنتين لا تحصلان أبداً على نفس الرقم، حتى تحت حمل شديد.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.tenancy.infrastructure.models.tenancy_models import NumberingSequence


class SqlNumberingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_number(self, *, company_id: str, document_type: str) -> str:
        stmt = (
            select(NumberingSequence)
            .where(
                NumberingSequence.company_id == company_id,
                NumberingSequence.document_type == document_type,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        seq = result.scalar_one_or_none()

        if seq is None:
            seq = NumberingSequence(
                company_id=company_id, document_type=document_type, last_value=0
            )
            self._session.add(seq)
            await self._session.flush()

        seq.last_value += 1
        formatted = str(seq.last_value).zfill(seq.padding)
        await self._session.commit()
        return f"{seq.prefix}{formatted}"
