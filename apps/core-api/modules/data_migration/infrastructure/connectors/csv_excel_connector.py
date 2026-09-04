"""موصل CSV/Excel — تنفيذ فعلي عبر pandas/openpyxl. كل 'جدول' هنا يقابل: اسم
ملف واحد لـ CSV، أو اسم ورقة (sheet) واحدة داخل ملف xlsx واحد — بحيث تبقى
الواجهة متسقة مع MssqlConnector رغم اختلاف طبيعة المصدر تماماً. هذا هو
الإثبات العملي (TASK-MIG-05) أن التصميم عام فعلاً: لا سطر واحد هنا يعرف شيئاً
عن use_cases أو عن الأمين تحديداً."""
from pathlib import Path

from modules.data_migration.application.ports.source_connector import SourceConnector
from modules.data_migration.domain.entities.import_job import TableDescriptor

_SAMPLE_ROWS = 20


class CsvExcelConnector(SourceConnector):
    """`file_path` مصدره مستند مرفوع مسبقاً عبر modules.documents الموجود
    بالفعل — لا آلية رفع مستقلة تُبنى هنا (راجع README الموديول)."""

    def __init__(self, file_path: str) -> None:
        self._file_path = Path(file_path)
        self._is_excel = self._file_path.suffix.lower() in {".xlsx", ".xls"}

    def _sheet_names(self) -> list[str]:
        if not self._is_excel:
            return [self._file_path.stem]  # ملف CSV واحد = "جدول" واحد باسم الملف
        import openpyxl

        wb = openpyxl.load_workbook(self._file_path, read_only=True)
        try:
            return list(wb.sheetnames)
        finally:
            wb.close()

    async def discover_schema(self) -> list[TableDescriptor]:
        import asyncio

        def _discover() -> list[TableDescriptor]:
            import pandas as pd

            descriptors = []
            for table_name in self._sheet_names():
                if self._is_excel:
                    df = pd.read_excel(self._file_path, sheet_name=table_name, nrows=_SAMPLE_ROWS)
                    full_len = pd.read_excel(
                        self._file_path, sheet_name=table_name, usecols=[0]
                    ).shape[0]
                else:
                    df = pd.read_csv(self._file_path, nrows=_SAMPLE_ROWS)
                    full_len = sum(1 for _ in open(self._file_path, encoding="utf-8-sig")) - 1

                descriptors.append(
                    TableDescriptor(
                        table_name=table_name,
                        columns=list(df.columns.astype(str)),
                        estimated_row_count=max(full_len, 0),
                        sample_rows=df.to_dict(orient="records"),
                    )
                )
            return descriptors

        return await asyncio.get_event_loop().run_in_executor(None, _discover)

    async def row_count(self, table_name: str) -> int:
        tables = await self.discover_schema()
        for t in tables:
            if t.table_name == table_name:
                return t.estimated_row_count
        raise ValueError(f"جدول/ورقة غير معروفة: {table_name!r}")

    async def read_batch(self, table_name: str, *, offset: int, limit: int) -> list[dict]:
        import asyncio

        def _read() -> list[dict]:
            import pandas as pd

            if self._is_excel:
                # openpyxl لا يدعم قراءة نطاق أسطر جزئي مباشرة بكفاءة عالية
                # لملفات كبيرة جداً؛ pandas.read_excel(skiprows/nrows) كافٍ
                # لحجم الدفعات المتوقَّع هنا (500) — قياس أداء فعلي مطلوب في
                # TASK-MIG-05 على ملف كبير حقيقي قبل الحسم النهائي.
                df = pd.read_excel(
                    self._file_path,
                    sheet_name=table_name,
                    skiprows=range(1, offset + 1),
                    nrows=limit,
                )
            else:
                df = pd.read_csv(self._file_path, skiprows=range(1, offset + 1), nrows=limit)
            return df.to_dict(orient="records")

        return await asyncio.get_event_loop().run_in_executor(None, _read)

    async def close(self) -> None:
        return None  # لا اتصال دائم يحتاج إغلاقاً — كل قراءة تفتح وتغلق الملف فوراً
