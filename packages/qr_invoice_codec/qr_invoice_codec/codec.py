"""qr_invoice_codec.codec — encode()/decode() لحمولة فاتورة QR (TASK-AI-05a).

encode: `QrInvoicePayload` → JSON مضغوط → `zlib.compress(level=9)` →
`base45` → نص ASCII جاهز لتمريره لأي مولّد QR.

decode: العكس بالضبط — لكن **بترتيب تحقق متعمّد**: `chk` أولاً (قبل حتى
تفسير `v` أو أي حقل آخر)، لأن الـchecksum يغطي كامل الحمولة بما فيها `v`
نفسها؛ لا معنى للثقة بأي حقل من حمولة لم يثبت أنها غير تالفة أصلاً.

نستخدم `base45` (RFC 9285 — نفس المستخدَم في EU Digital COVID Certificate):
مكتبة PyPI خفيفة بلا تبعيات إضافية، وأبجديتها متوافقة تماماً مع نمط
Alphanumeric في QR (أكفأ من Byte mode لنفس المحتوى).
"""
from __future__ import annotations

import json
import zlib
from typing import Any

import base45
from pydantic import ValidationError

from .checksum import compute_checksum
from .schema import QrInvoicePayload

_SUPPORTED_VERSIONS = {1}


class QrCodecError(Exception):
    """الأصل المشترك لكل استثناءات هذه الحزمة.

    يسمح بـ `except QrCodecError` واحد للمستدعي الذي لا يهتم بالتمييز الدقيق
    (مثال: تسجيل خطأ عام)، مع بقاء الأنواع الفرعية دقيقة لمن يحتاج التمييز
    الفعلي (مثال: `documents_router.py` في TASK-AI-05b يحتاج تمييز
    `ChecksumMismatchError` عن غياب QR كلياً في الصورة، لرسالتَي 422 مختلفتين).
    """


class ChecksumMismatchError(QrCodecError):
    """فشل التحقق من `chk` — الرمز تالف أو غير مكتمل (تصوير جزئي، انعكاس ضوء،
    دقة كاميرا ضعيفة، إلخ). **لا** يعني بالضرورة تلاعباً متعمداً — انظر
    ملاحظة الأمان في checksum.py."""


class UnsupportedVersionError(QrCodecError):
    """قيمة `v` في الحمولة غير مدعومة من هذا الإصدار من المكتبة. يُرفَض صراحة
    بدل محاولة تفسير الحمولة بمخطط v1 قد لا يتوافق معها فعلياً."""


class MalformedPayloadError(QrCodecError):
    """فشل عام في فك الترميز (base45/zlib/json) أو في التحقق من بنية
    الحمولة عبر Pydantic بعد اجتياز فحصَي checksum والإصدار بنجاح."""


def encode(payload: QrInvoicePayload) -> bytes:
    """`QrInvoicePayload` → نص ASCII (base45) جاهز لمولّد QR.

    يُهمَل أي `chk` مُمرَّر مسبقاً في `payload` (لو وُجد) ويُعاد حسابه دائماً
    هنا، حتى يستحيل تمرير حمولة بـchecksum غير متوافق مع بقية حقولها الفعلية.
    """
    data = payload.model_dump(mode="json")
    data.pop("chk", None)
    data["chk"] = compute_checksum(data)

    compact_json = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    compressed = zlib.compress(compact_json.encode("utf-8"), level=9)
    return base45.b45encode(compressed)


def decode(qr_text: str | bytes) -> QrInvoicePayload:
    """نص/بايتات مقروءة من رمز QR → `QrInvoicePayload` مُتحقَّق منه بالكامل.

    ترتيب التحقق (متعمَّد، لا يُغيَّر بلا مبرر قوي):
    1. فك base45 ثم zlib ثم JSON — أي فشل هنا يعني الصورة/النص ليس حمولة
       QR صالحة من هذه الحزمة أصلاً → `MalformedPayloadError`.
    2. **`chk` أولاً** بين حقول الحمولة نفسها — قبل النظر لأي حقل آخر بما
       فيها `v` — لأن الـchecksum يغطي الحمولة كاملة.
    3. `v` بعد ثبوت سلامة الحمولة — رفض صريح لإصدار غير مدعوم.
    4. بناء/تحقق `QrInvoicePayload` عبر Pydantic (أنواع الحقول، الحدود، إلخ).
    """
    if isinstance(qr_text, bytes):
        qr_text = qr_text.decode("ascii")

    try:
        compressed = base45.b45decode(qr_text)
    except Exception as exc:
        raise MalformedPayloadError(f"فشل فك ترميز base45: {exc}") from exc

    try:
        compact_json = zlib.decompress(compressed).decode("utf-8")
    except Exception as exc:
        raise MalformedPayloadError(f"فشل فك ضغط zlib: {exc}") from exc

    try:
        data: Any = json.loads(compact_json)
    except Exception as exc:
        raise MalformedPayloadError(f"فشل تفسير JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise MalformedPayloadError("الحمولة بعد فك الترميز ليست كائن JSON (object)")

    # (2) chk أولاً — قبل النظر لـ v أو أي حقل آخر.
    received_checksum = data.get("chk")
    data_without_chk = {k: v for k, v in data.items() if k != "chk"}
    expected_checksum = compute_checksum(data_without_chk)
    if not isinstance(received_checksum, str) or received_checksum != expected_checksum:
        raise ChecksumMismatchError("رمز QR تالف أو غير مكتمل")

    # (3) الإصدار — بعد ثبوت سلامة الحمولة عبر الـchecksum فقط.
    version = data.get("v")
    if version not in _SUPPORTED_VERSIONS:
        raise UnsupportedVersionError(
            f"إصدار مخطط غير مدعوم: v={version!r} "
            f"(المدعوم حالياً: {sorted(_SUPPORTED_VERSIONS)})"
        )

    # (4) البنية الكاملة عبر Pydantic.
    try:
        return QrInvoicePayload.model_validate(data)
    except ValidationError as exc:
        raise MalformedPayloadError(f"فشل التحقق من بنية الحمولة: {exc}") from exc
