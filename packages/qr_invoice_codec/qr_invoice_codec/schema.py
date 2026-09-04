"""qr_invoice_codec.schema — مخطط بيانات فاتورة QR (v1).

الحقول مضغوطة عمداً (مفاتيح قصيرة) لتقليل حجم النص المُرمَّز داخل QR، الذي
له سعة محدودة فعلياً حسب نسخة الرمز ومستوى تصحيح الخطأ (انظر 00_TASK_PACKAGE.md
§ "حمولة عند حدود السعة"). المخطط مطابق بالحرف لما ورد في 00_TASK_PACKAGE.md
§ TASK-AI-05a.

ملاحظة تصميم مهمة: `v` هنا معلومة فقط للتوثيق الذاتي للنموذج (يُستخدم عند بناء
`QrInvoicePayload` بعد اجتياز فحص الإصدار). فحص الإصدار الفعلي — الذي يجب أن
يرفض `v != 1` صراحةً بـ`UnsupportedVersionError` بدل خطأ `pydantic` عام — يتم
في `codec.decode()` **قبل** أي محاولة بناء هذا النموذج، حتى لا نخلط بين "حمولة
تالفة/غير صالحة لهذا الإصدار" و"إصدار مستقبلي غير مدعوم بعد" (رسالتان مختلفتان
تماماً للمستخدم النهائي وللمطوّر الذي يقرأ الـlogs).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QrInvoiceLine(BaseModel):
    """بند واحد في الفاتورة (`ln[]`)."""

    model_config = ConfigDict(extra="forbid")

    p: str = Field(..., min_length=1, description="SKU أو وصف نصي للصنف")
    q: float = Field(..., gt=0, description="الكمية")
    u: float = Field(..., ge=0, description="سعر الوحدة")
    tax: float = Field(default=0, ge=0, le=100, description="نسبة الضريبة على البند (%)")


class QrInvoiceSupplier(BaseModel):
    """بيانات المورّد (`sup`)."""

    model_config = ConfigDict(extra="forbid")

    n: str = Field(..., min_length=1, description="اسم المورد")
    tax: str = Field(..., min_length=1, description="الرقم الضريبي للمورد")


class QrInvoicePayload(BaseModel):
    """الحمولة الكاملة المُرمَّزة داخل رمز QR.

    `v: Literal[1]` — إصدار هذا المخطط هو 1 حصراً هنا؛ أي قيمة أخرى تُرفَض
    عند بناء هذا النموذج (دفاع ثانٍ في العمق)، لكن الرفض *الرسمي* الموجَّه
    للمستدعي يجب أن يمر عبر `UnsupportedVersionError` في `codec.decode()`
    قبل الوصول لهذه النقطة أصلاً — انظر الملاحظة أعلى الملف.
    """

    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = 1
    co: str = Field(..., min_length=1, description="company_id أو tax_number المورّد")
    sup: QrInvoiceSupplier
    cur: str = Field(..., min_length=3, max_length=3, description="رمز العملة (ISO 4217، مثال SAR)")
    dt: str = Field(..., min_length=1, description="تاريخ الفاتورة، YYYY-MM-DD")
    no: str = Field(..., min_length=1, description="رقم الفاتورة عند المورّد")
    ln: list[QrInvoiceLine] = Field(..., min_length=1, description="بنود الفاتورة")
    tot: float = Field(..., ge=0, description="الإجمالي النهائي للفاتورة")
    chk: str = Field(default="", description="checksum — يُحسب/يُتحقق حصراً في codec.py")
