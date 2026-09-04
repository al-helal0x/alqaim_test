"""infrastructure/qr_reader.py — قراءة رمز QR خام من صورة (TASK-AI-05b).

**مسار مختلف كلياً عن OCR — لا Tesseract هنا إطلاقاً** (00_TASK_PACKAGE.md
§ TASK-AI-05b خطوة 1). هذا الملف جديد بالكامل، معزول، لا يمسّ أي ملف من
مسار `/analyze` القائم (`services/ocr/*`, `process_document_pipeline.py`).

تنفيذ افتراضي عبر `pyzbar` (+ Pillow لفتح الصورة). القرار بين `pyzbar` و
`zxing-cpp` مفتوح فعلياً — راجع 00_TASK_PACKAGE.md § "ملخص القرارات التي
تحتاج تأكيدك" بند 1؛ `pyzbar` يعتمد على مكتبة نظام `libzbar0` (حزمة apt
خفيفة وشائعة)، بينما `zxing-cpp` يشحن ثنائياته الخاصة عبر wheel بلا تبعية
نظام إضافية لكنه أثقل حجماً. اخترنا `pyzbar` هنا كنقطة بداية بسيطة؛ تبديل
التنفيذ لاحقاً لا يمسّ شيئاً خارج هذا الملف بفضل واجهة `IQrCodeReader`.
"""
from __future__ import annotations

import io
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class IQrCodeReader(Protocol):
    def read(self, image_bytes: bytes) -> str | None:
        """النص الخام لأول رمز QR موجود في الصورة، أو `None` لو لم يُعثَر على
        أي رمز QR فيها إطلاقاً.

        ملاحظة تمييز مهمة: `None` هنا يعني "لا يوجد QR في الصورة أصلاً"
        (→ 422 "لم يُعثَر على رمز QR في الصورة" في الراوتر) — وهذا **مختلف
        تماماً** عن رمز QR موجود لكن تالف (تُكتشَف تلك الحالة لاحقاً في
        `qr_invoice_codec.decode()` عبر `ChecksumMismatchError`، → 422
        "رمز QR تالف أو غير مكتمل"). لا تخلط الحالتين في التنفيذ.
        """
        ...


class PyzbarQrCodeReader:
    """تنفيذ `IQrCodeReader` عبر `pyzbar` + `Pillow`.

    الاستيرادات داخل `read()` عمداً (lazy import) — حتى لا تفرض هذه الحزمة
    تبعية `pyzbar`/`libzbar0` على أي كود آخر في `ai-platform` لا يستخدم مسار
    QR إطلاقاً (مثال: بيئات اختبار وحدة لا تحتاج قراءة صور فعلياً، تحقن
    reader وهمي بدلاً من هذا التنفيذ).
    """

    def read(self, image_bytes: bytes) -> str | None:
        from PIL import Image
        from pyzbar.pyzbar import ZBarSymbol
        from pyzbar.pyzbar import decode as zbar_decode

        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as exc:  # noqa: BLE001 — أي صورة غير قابلة للفتح أصلاً
            logger.info("تعذَّر فتح الصورة المرسَلة لقراءة QR: %s", exc)
            return None

        results = zbar_decode(image, symbols=[ZBarSymbol.QRCODE])
        if not results:
            return None

        # نأخذ أول رمز QR فقط عمداً — لو وُجد أكثر من رمز في نفس الصورة
        # (نادر لهذا الاستخدام)، فك ترميز الأول يكفي لهذا المسار؛ لو فشل
        # فك ترميزه لاحقاً في qr_invoice_codec سيظهر ذلك كـChecksumMismatchError
        # أو UnsupportedVersionError بوضوح للمستخدم بدل تخمين أي رمز هو المقصود.
        return results[0].data.decode("utf-8")
