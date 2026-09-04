"""qr_invoice_codec.checksum — اكتشاف تلف تصوير جزئي لرمز QR.

**هذا ليس أماناً تشفيرياً وليس مقصوداً كذلك** (لا حماية من تلاعب متعمّد بالبيانات
— أي طرف يملك النص المُرمَّز يقدر يعيد حساب checksum صحيح لبيانات معدَّلة).
الهدف الوحيد: اكتشاف تلف تصوير جزئي/غير مقصود (إضاءة، انعكاس، دقة كاميرا ضعيفة)
قبل تمرير بيانات مشبوهة لأي مرحلة لاحقة (بناء Draft، إلخ). CRC32 مقتطَع
(8 أحرف hex) يكفي تماماً لهذا الغرض المحدود.

الحماية الأمنية الفعلية من `company_id` مزوَّر تتم لاحقاً في TASK-AI-05b عبر
مطابقة `TenantContext` — لا علاقة لها بهذا الـchecksum إطلاقاً.
"""
from __future__ import annotations

import json
import zlib
from typing import Any

# طول ثابت مقصود: 8 أحرف hex (32 بت CRC كاملة) — يوازن بين وضوح رفض التلف
# وصغر الحجم النهائي داخل QR (كل حرف إضافي يقلّل الهامش المتاح لبنود الفاتورة).
_CHECKSUM_HEX_LENGTH = 8


def compute_checksum(payload_dict_without_chk: dict[str, Any]) -> str:
    """يحسب CRC32 على تمثيل JSON قانوني (canonical) للحمولة **بدون** حقل `chk`.

    `sort_keys=True` إلزامي هنا: يضمن أن يكون الناتج حتمياً بغض النظر عن
    ترتيب إدخال الحقول في القاموس المُمرَّر (مثال: قاموس آتٍ من
    `model_dump()` مقابل قاموس آتٍ من `json.loads()` بعد فك الترميز — لا
    ضمان أن يحافظا على نفس ترتيب المفاتيح، والـchecksum يجب أن يتطابق في
    الحالتين لنفس البيانات).
    """
    if "chk" in payload_dict_without_chk:
        raise ValueError(
            "compute_checksum يجب أن يُستدعى على قاموس لا يحتوي 'chk' — "
            "مرّر البيانات بدونه صراحةً لتجنّب دائرية الحساب."
        )

    canonical = json.dumps(
        payload_dict_without_chk,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    crc = zlib.crc32(canonical.encode("utf-8")) & 0xFFFFFFFF
    return format(crc, f"0{_CHECKSUM_HEX_LENGTH}x")
