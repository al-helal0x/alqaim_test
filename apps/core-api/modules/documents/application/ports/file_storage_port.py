"""IFileStorage — واجهة تخزين المرفقات المجرَّدة (القسم 11.2: التواصل بين
الوحدات عبر Ports فقط). المستهلك الوحيد حالياً: modules/documents، لكن
الواجهة عامة عمداً ليمكن لأي Module آخر يحتاج رفع ملفات (مثل مرفقات فاتورة
شراء ممسوحة ضوئياً) استهلاكها لاحقاً دون معرفة تفاصيل التخزين الفعلي.
"""
from typing import Protocol


class IFileStorage(Protocol):
    async def save(self, *, company_id: str, key: str, content: bytes) -> str:
        """يحفظ المحتوى تحت مفتاح فريد ضمن نطاق الشركة، ويُعيد storage_key
        النهائي (قد يختلف عن `key` المُدخَل — مثلاً بإضافة بادئة الشركة)."""
        ...

    async def load(self, storage_key: str) -> bytes:
        """يقرأ المحتوى كاملاً. يرفع FileNotFoundError إن لم يوجد المفتاح."""
        ...

    async def delete(self, storage_key: str) -> None:
        """حذف صامت — لا يرفع خطأً إن كان المفتاح غير موجود أصلاً."""
        ...
