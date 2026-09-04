"""موصل SQL Server — يخدم كلاً من SourceType.ALAMEEN_MSSQL و GENERIC_MSSQL.
تنفيذ فعلي عبر pyodbc. الاستيراد مؤجَّل داخل الدوال عمداً (وليس أعلى الملف)
حتى لا يفشل تحميل core-api الأساسي بالكامل إن لم تُثبَّت pyodbc على بيئة لا
تحتاج هذه الميزة (راجع PYPROJECT_ADDITIONS.md — سبب فصلها كاعتماد اختياري).
"""
from modules.data_migration.application.ports.source_connector import SourceConnector
from modules.data_migration.domain.entities.import_job import TableDescriptor

_SAMPLE_ROWS = 20


class MssqlConnector(SourceConnector):
    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string
        self._conn = None
        self._known_tables: set[str] | None = None  # allow-list بعد أول discover_schema

    async def connect(self) -> None:
        import asyncio

        import pyodbc

        def _connect():
            # مستخدم قراءة فقط مُتوقَّع في connection_string نفسها (مسؤولية
            # من يبني الاتصال، راجع ملاحظة أمنية في README الموديول) — لا
            # فرض صلاحيات إضافي هنا لأن pyodbc لا يوفّر ذلك على مستوى العميل.
            return pyodbc.connect(self._connection_string, timeout=10)

        self._conn = await asyncio.get_event_loop().run_in_executor(None, _connect)

    async def discover_schema(self) -> list[TableDescriptor]:
        import asyncio

        if self._conn is None:
            await self.connect()

        def _discover() -> list[TableDescriptor]:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
            )
            table_names = [row.TABLE_NAME for row in cursor.fetchall()]

            descriptors: list[TableDescriptor] = []
            for table_name in table_names:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
                    table_name,
                )
                columns = [row.COLUMN_NAME for row in cursor.fetchall()]

                # اسم الجدول هنا قادم من INFORMATION_SCHEMA نفسها (مصدر
                # موثوق، وليس مُدخَلاً من المستخدم) لذلك التضمين المباشر في
                # SELECT TOP هنا آمن؛ يبقى ممنوعاً في read_batch (أدناه) حيث
                # table_name يصل من خارج هذه الدالة.
                cursor.execute(f"SELECT TOP {_SAMPLE_ROWS} * FROM [{table_name}]")
                col_names = [c[0] for c in cursor.description]
                sample_rows = [dict(zip(col_names, row, strict=True)) for row in cursor.fetchall()]

                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                estimated_row_count = cursor.fetchone()[0]

                descriptors.append(
                    TableDescriptor(
                        table_name=table_name,
                        columns=columns,
                        estimated_row_count=estimated_row_count,
                        sample_rows=sample_rows,
                    )
                )
            cursor.close()
            return descriptors

        descriptors = await asyncio.get_event_loop().run_in_executor(None, _discover)
        self._known_tables = {d.table_name for d in descriptors}
        return descriptors

    def _assert_known_table(self, table_name: str) -> None:
        """يمنع SQL Injection عبر اسم جدول: لا يُقبَل أي اسم جدول لم يُكتشَف
        فعلياً عبر discover_schema أولاً. discover_schema يجب أن يُستدعى قبل
        أي read_batch/row_count — هذا هو الترتيب المفروض في خط السير أصلاً
        (§4.3، المرحلة 2 قبل المرحلة 4/5)."""
        if self._known_tables is None or table_name not in self._known_tables:
            raise ValueError(
                f"جدول غير معروف أو لم يُكتشَف بعد عبر discover_schema: {table_name!r}"
            )

    async def row_count(self, table_name: str) -> int:
        import asyncio

        self._assert_known_table(table_name)

        def _count():
            cursor = self._conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            n = cursor.fetchone()[0]
            cursor.close()
            return n

        return await asyncio.get_event_loop().run_in_executor(None, _count)

    async def read_batch(self, table_name: str, *, offset: int, limit: int) -> list[dict]:
        import asyncio

        self._assert_known_table(table_name)

        def _read():
            cursor = self._conn.cursor()
            # ORDER BY إلزامي مع OFFSET/FETCH في SQL Server — بدونه لا يُضمَن
            # ترتيب ثابت بين الدفعات المتتالية (قد يتكرر أو يُفقَد سجل).
            # نرتّب حسب أول عمود مكتشَف (غالباً المفتاح الأساسي) كافتراض
            # معقول عام؛ mapping profile لكل مصدر قد يحدّد عموداً أدق لاحقاً.
            cursor.execute(
                f"SELECT * FROM [{table_name}] ORDER BY 1 OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
                offset,
                limit,
            )
            col_names = [c[0] for c in cursor.description]
            rows = [dict(zip(col_names, row, strict=True)) for row in cursor.fetchall()]
            cursor.close()
            return rows

        return await asyncio.get_event_loop().run_in_executor(None, _read)

    async def close(self) -> None:
        import asyncio

        if self._conn is not None:
            conn = self._conn
            self._conn = None
            await asyncio.get_event_loop().run_in_executor(None, conn.close)
