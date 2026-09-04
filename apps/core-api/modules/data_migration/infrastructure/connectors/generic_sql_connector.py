"""موصل عام لأي قاعدة بيانات SQL أخرى (Postgres/MySQL...) عبر SQLAlchemy —
تنفيذ فعلي، وليس مجرد توثيق نوايا. مفيد مثلاً لعميل قادم من نظام آخر غير
الأمين يخزّن بياناته على Postgres عادي، أو لاستيراد بين شركتين تستخدمان
AlQaim V2 نفسه. لا يحتاج تبعية إضافية (SQLAlchemy موجودة أصلاً في المشروع)."""
from modules.data_migration.application.ports.source_connector import SourceConnector
from modules.data_migration.domain.entities.import_job import TableDescriptor

_SAMPLE_ROWS = 20


class GenericSqlConnector(SourceConnector):
    def __init__(self, sqlalchemy_url: str) -> None:
        self._url = sqlalchemy_url
        self._engine = None
        self._known_tables: set[str] | None = None

    async def _get_engine(self):
        if self._engine is None:
            from sqlalchemy import create_engine

            # create_engine متزامن عمداً (وليس create_async_engine) — هذا
            # الموصل عام لمصادر خارجية غير معروفة سلفاً، وقد لا تملك سائق
            # async متاحاً؛ يُشغَّل داخل executor مثل بقية الموصلات هنا.
            self._engine = create_engine(self._url)
        return self._engine

    async def discover_schema(self) -> list[TableDescriptor]:
        import asyncio

        def _discover() -> list[TableDescriptor]:
            from sqlalchemy import inspect, text

            engine = self._engine
            inspector = inspect(engine)
            descriptors = []
            for table_name in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns(table_name)]
                with engine.connect() as conn:
                    sample = conn.execute(
                        text(f'SELECT * FROM "{table_name}" LIMIT :n'), {"n": _SAMPLE_ROWS}
                    )
                    sample_rows = [dict(row._mapping) for row in sample]
                    count = conn.execute(
                        text(f'SELECT COUNT(*) FROM "{table_name}"')
                    ).scalar_one()
                descriptors.append(
                    TableDescriptor(
                        table_name=table_name,
                        columns=columns,
                        estimated_row_count=count,
                        sample_rows=sample_rows,
                    )
                )
            return descriptors

        await self._get_engine()
        descriptors = await asyncio.get_event_loop().run_in_executor(None, _discover)
        self._known_tables = {d.table_name for d in descriptors}
        return descriptors

    def _assert_known_table(self, table_name: str) -> None:
        if self._known_tables is None or table_name not in self._known_tables:
            raise ValueError(
                f"جدول غير معروف أو لم يُكتشَف بعد عبر discover_schema: {table_name!r}"
            )

    async def row_count(self, table_name: str) -> int:
        import asyncio

        self._assert_known_table(table_name)

        def _count():
            from sqlalchemy import text

            with self._engine.connect() as conn:
                return conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()

        return await asyncio.get_event_loop().run_in_executor(None, _count)

    async def read_batch(self, table_name: str, *, offset: int, limit: int) -> list[dict]:
        import asyncio

        self._assert_known_table(table_name)

        def _read():
            from sqlalchemy import text

            with self._engine.connect() as conn:
                result = conn.execute(
                    text(f'SELECT * FROM "{table_name}" ORDER BY 1 OFFSET :o LIMIT :l'),
                    {"o": offset, "l": limit},
                )
                return [dict(row._mapping) for row in result]

        return await asyncio.get_event_loop().run_in_executor(None, _read)

    async def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
