"""اختبارات qr_invoice_codec — تغطي كل بند في 00_TASK_PACKAGE.md § TASK-AI-05a
→ "Tests Required". منطق Python صرف، بلا حاجة لأي بيئة حقيقية (DoD: IMPLEMENTED
+ TESTED بمعزل)."""
from __future__ import annotations

import base45
import pytest
from pydantic import ValidationError

from qr_invoice_codec import (
    ChecksumMismatchError,
    MalformedPayloadError,
    QrInvoiceLine,
    QrInvoicePayload,
    QrInvoiceSupplier,
    UnsupportedVersionError,
    decode,
    encode,
)


def _make_payload(n_lines: int = 1, *, arabic: bool = False) -> QrInvoicePayload:
    supplier_name = "شركة الفرات للتجارة العامة" if arabic else "Furat General Trading Co"
    product_name = "أسلاك كهربائية 3×5 مم — لفة 100م" if arabic else "Cable 3x5mm - 100m roll"

    lines = [
        QrInvoiceLine(p=f"{product_name} #{i}", q=10 + i, u=25.5, tax=15)
        for i in range(n_lines)
    ]
    total = round(sum(line.q * line.u * (1 + line.tax / 100) for line in lines), 2)

    return QrInvoicePayload(
        co="3101234567",
        sup=QrInvoiceSupplier(n=supplier_name, tax="3101234567"),
        cur="SAR",
        dt="2026-08-16",
        no="INV-2026-00042",
        ln=lines,
        tot=total,
    )


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def _assert_same_payload_ignoring_chk(a: QrInvoicePayload, b: QrInvoicePayload) -> None:
    """chk هو حقل مشتق (يُحسب دائماً في encode()، ليس جزءاً من "هوية" الفاتورة
    من منظور المستدعي) — لذا المقارنة المنطقية الصحيحة تستثنيه، لا تشترط أن
    يكون مطابقاً لقيمة افتراضية فارغة في نسخة لم تمر بـencode() بعد."""
    assert a.model_dump(exclude={"chk"}) == b.model_dump(exclude={"chk"})


def test_round_trip_single_line():
    payload = _make_payload(n_lines=1)
    qr_text = encode(payload).decode("ascii")
    decoded = decode(qr_text)
    _assert_same_payload_ignoring_chk(decoded, payload)


def test_round_trip_twenty_lines():
    payload = _make_payload(n_lines=20)
    qr_text = encode(payload).decode("ascii")
    decoded = decode(qr_text)
    _assert_same_payload_ignoring_chk(decoded, payload)
    assert len(decoded.ln) == 20


def test_round_trip_arabic_unicode_fields():
    payload = _make_payload(n_lines=3, arabic=True)
    qr_text = encode(payload).decode("ascii")
    decoded = decode(qr_text)
    _assert_same_payload_ignoring_chk(decoded, payload)
    assert decoded.sup.n == payload.sup.n
    assert "شركة" in decoded.sup.n


def test_round_trip_accepts_bytes_input():
    payload = _make_payload(n_lines=1)
    encoded_bytes = encode(payload)
    assert isinstance(encoded_bytes, (bytes, bytearray))
    decoded = decode(encoded_bytes)
    _assert_same_payload_ignoring_chk(decoded, payload)


def test_encoded_output_is_ascii_base45_alphabet():
    payload = _make_payload(n_lines=5)
    qr_text = encode(payload).decode("ascii")
    # أبجدية base45 القياسية بالكامل: 0-9 A-Z $%*+-./: والمسافة (RFC 9285).
    allowed = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:")
    assert set(qr_text) <= allowed


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------


def test_tampered_checksum_raises_explicit_error():
    payload = _make_payload(n_lines=1)
    qr_text = encode(payload).decode("ascii")

    # نغيّر حرفاً واحداً في منتصف النص المُرمَّز (تلف تصوير جزئي محاكى) —
    # نتجنب أول/آخر حرف لضمان بقاء النص base45 صالح الشكل (طول زوجي/فردي).
    mid = len(qr_text) // 2
    swapped_char = "A" if qr_text[mid] != "A" else "B"
    tampered = qr_text[:mid] + swapped_char + qr_text[mid + 1 :]
    assert tampered != qr_text

    with pytest.raises((ChecksumMismatchError, MalformedPayloadError)):
        decode(tampered)


def test_checksum_mismatch_is_specific_not_generic():
    payload = _make_payload(n_lines=1)
    data = payload.model_dump(mode="json")
    data.pop("chk", None)
    data["chk"] = "deadbeef"  # checksum خاطئ عمداً، لكن الحمولة سليمة الشكل

    import json
    import zlib

    compact_json = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    compressed = zlib.compress(compact_json.encode("utf-8"), level=9)
    qr_text = base45.b45encode(compressed).decode("ascii")

    with pytest.raises(ChecksumMismatchError):
        decode(qr_text)


def test_missing_chk_field_raises_checksum_error():
    payload = _make_payload(n_lines=1)
    data = payload.model_dump(mode="json")
    data.pop("chk", None)  # لا نضيف chk إطلاقاً

    import json
    import zlib

    compact_json = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    compressed = zlib.compress(compact_json.encode("utf-8"), level=9)
    qr_text = base45.b45encode(compressed).decode("ascii")

    with pytest.raises(ChecksumMismatchError):
        decode(qr_text)


# ---------------------------------------------------------------------------
# Version rejection
# ---------------------------------------------------------------------------


def test_unsupported_version_raises_explicit_error():
    payload = _make_payload(n_lines=1)
    data = payload.model_dump(mode="json")
    data.pop("chk", None)
    data["v"] = 2  # إصدار مستقبلي غير مدعوم بعد

    import json
    import zlib

    from qr_invoice_codec.checksum import compute_checksum

    data["chk"] = compute_checksum(data)
    compact_json = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    compressed = zlib.compress(compact_json.encode("utf-8"), level=9)
    qr_text = base45.b45encode(compressed).decode("ascii")

    with pytest.raises(UnsupportedVersionError):
        decode(qr_text)


def test_schema_itself_rejects_unsupported_version_as_second_line_of_defense():
    with pytest.raises(ValidationError):
        QrInvoicePayload(
            v=2,  # type: ignore[arg-type]
            co="123",
            sup=QrInvoiceSupplier(n="x", tax="123"),
            cur="SAR",
            dt="2026-08-16",
            no="1",
            ln=[QrInvoiceLine(p="x", q=1, u=1)],
            tot=1,
        )


# ---------------------------------------------------------------------------
# Malformed input (not a checksum failure — not our payload at all)
# ---------------------------------------------------------------------------


def test_garbage_text_raises_malformed_payload_error():
    with pytest.raises(MalformedPayloadError):
        decode("this is definitely not a valid base45/zlib/json qr payload !!")


def test_empty_string_raises_malformed_payload_error():
    with pytest.raises(MalformedPayloadError):
        decode("")


# ---------------------------------------------------------------------------
# Capacity near the practical limit
# ---------------------------------------------------------------------------


def test_twenty_line_payload_fits_within_qr_v25_30_capacity_m():
    """حمولة 20 سطراً (استهداف اختباري صريح في 00_TASK_PACKAGE.md) يجب أن
    تبقى ضمن سعة QR نسخة 25-30 بمستوى تصحيح خطأ M.

    الحد المستخدَم هنا (1000 حرف) تقريبي متحفِّظ عمداً: سعة Alphanumeric عند
    ECC=M لنسخة 25 تقارب ~1046 حرفاً ولنسخة 30 أعلى من ذلك — نستخدم حداً أدنى
    من هذا النطاق لهامش أمان. **الرقم الدقيق يحتاج تأكيداً فعلياً عبر مولّد QR
    حقيقي في الاختبار اليدوي المطلوب في GATE-QR**، هذا الاختبار فقط يمنع
    انحرافاً كبيراً وصامتاً في الحجم (مثال: تعطيل الضغط بالخطأ) قبل الوصول
    لتلك الخطوة اليدوية.
    """
    payload = _make_payload(n_lines=20, arabic=True)
    qr_text = encode(payload).decode("ascii")
    assert len(qr_text) < 1000, (
        f"حمولة 20 سطراً أنتجت {len(qr_text)} حرفاً — قريبة جداً أو تتجاوز "
        "سعة QR نسخة 25-30 (ECC=M)، يحتاج مراجعة (تقليل حقول، أو رفع نسخة QR "
        "المستهدَفة في مولّد الرمز عند التنفيذ الفعلي)."
    )


def test_single_line_payload_is_compact():
    payload = _make_payload(n_lines=1)
    qr_text = encode(payload).decode("ascii")
    # فاتورة سطر واحد يجب أن تبقى ضمن سعة QR متوسط الحجم (نسخة ~10-15، شائعة
    # جداً للطباعة على فاتورة عادية) — حد متحفِّظ مشابه لأعلاه بنفس المنطق.
    assert len(qr_text) < 300


# ---------------------------------------------------------------------------
# extra="forbid" — رفض حقول غير معروفة (دفاع إضافي غير مطلوب صراحة في
# 00_TASK_PACKAGE.md لكنه اتساق طبيعي مع "رفض صريح بدل تفسير خاطئ" العام)
# ---------------------------------------------------------------------------


def test_unknown_extra_field_rejected_by_schema():
    with pytest.raises(ValidationError):
        QrInvoicePayload(
            v=1,
            co="123",
            sup=QrInvoiceSupplier(n="x", tax="123"),
            cur="SAR",
            dt="2026-08-16",
            no="1",
            ln=[QrInvoiceLine(p="x", q=1, u=1)],
            tot=1,
            unexpected_field="should not be allowed",  # type: ignore[call-arg]
        )
