"""الواجهة العامة التي يطبّقها أي مصدر بيانات (Protocol، وليس ABC — نفس أسلوب
IWebhookSender في modules/integrations). use_cases تعتمد على هذه الواجهة فقط
ولا تعرف شيئاً عن SQL Server أو Excel أو أي مصدر بعينه."""
from typing import Protocol

from modules.data_migration.domain.entities.import_job import TableDescriptor


class SourceConnector(Protocol):
    async def discover_schema(self) -> list[TableDescriptor]:
        """يرجع بنية الجداول (أسماء + أعمدة + عينة صغيرة)، بدون قراءة البيانات
        كاملة. يُستخدَم في مرحلة 'الاكتشاف' (المرحلة 2 من خط السير)."""
        ...

    async def row_count(self, table_name: str) -> int:
        """العدد الكلي لسجلات جدول — لتقسيم العمل إلى دفعات ولعرض شريط تقدّم
        دقيق قبل بدء القراءة الفعلية."""
        ...

    async def read_batch(
        self, table_name: str, *, offset: int, limit: int
    ) -> list[dict]:
        """يقرأ دفعة محدودة فقط (مثلاً 500 سجل) — أبداً الجدول كاملاً دفعة
        واحدة، لأن مصادر مثل الأمين قد تحوي ملايين القيود (راجع خطة الميزة
        §2 — 'الحجم')."""
        ...

    async def close(self) -> None:
        """يُغلق أي اتصال مفتوح (اتصال SQL Server، مقبض ملف...). يجب استدعاؤه
        دائماً عبر try/finally في use_cases — لا اعتماد على garbage collection."""
        ...
