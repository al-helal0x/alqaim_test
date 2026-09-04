import uuid

import pytest_asyncio
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.types import CHAR, JSON, TypeDecorator


class _SQLiteUUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


@pytest_asyncio.fixture
async def db_session():
    from models import ai_models  # noqa: F401
    from shared_kernel.db_base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PGUUID) or type(col.type).__name__ == "UUID":
                col.type = _SQLiteUUID()
            elif isinstance(col.type, JSONB) or type(col.type).__name__ == "JSONB" or isinstance(col.type, ARRAY):
                col.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
