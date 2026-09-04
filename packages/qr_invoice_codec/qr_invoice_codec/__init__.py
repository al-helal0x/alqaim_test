"""qr_invoice_codec — ترميز/فك ترميز فاتورة مُهيكَلة داخل رمز QR (TASK-AI-05a).

الاستخدام النموذجي:

    from qr_invoice_codec import encode, decode, QrInvoicePayload

    payload = QrInvoicePayload(...)
    qr_text = encode(payload).decode("ascii")   # نص جاهز لأي مولّد QR
    ...
    payload2 = decode(qr_text)                  # بعد قراءة رمز QR من صورة
"""
from .checksum import compute_checksum
from .codec import (
    ChecksumMismatchError,
    MalformedPayloadError,
    QrCodecError,
    UnsupportedVersionError,
    decode,
    encode,
)
from .schema import QrInvoiceLine, QrInvoicePayload, QrInvoiceSupplier

__all__ = [
    "ChecksumMismatchError",
    "MalformedPayloadError",
    "QrCodecError",
    "QrInvoiceLine",
    "QrInvoicePayload",
    "QrInvoiceSupplier",
    "UnsupportedVersionError",
    "compute_checksum",
    "decode",
    "encode",
]
