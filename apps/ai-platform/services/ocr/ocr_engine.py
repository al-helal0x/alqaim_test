"""IOCREngine — تنفيذ Tesseract (ذاتي التشغيل، دعم عربي/إنجليزي — القسم 7.12
'التوصية: نموذج هجين... PaddleOCR كافتراضي ذاتي التشغيل'؛ Tesseract هنا هو
التنفيذ الأول الفعلي لأن PaddleOCR أثقل تثبيتاً — كلاهما خلف نفس IOCREngine
تماماً كما يقتضي القسم 7.9/7.10، فاستبداله لاحقاً لا يمس أي كود مستهلك).
"""
import io

import pytesseract
from PIL import Image

from application.ports.ai_ports import RawOcrResult


class TesseractOCREngine:
    def extract(self, image_bytes: bytes, *, languages: str = "ara+eng") -> RawOcrResult:
        image = Image.open(io.BytesIO(image_bytes))

        data = pytesseract.image_to_data(
            image, lang=languages, output_type=pytesseract.Output.DICT
        )
        words_with_confidence = [
            (word, int(conf))
            for word, conf in zip(data["text"], data["conf"], strict=False)  # مخرجات pytesseract غير مضمونة التساوي رسمياً في كل الإصدارات
            if word.strip() and int(conf) >= 0
        ]
        text = " ".join(w for w, _ in words_with_confidence)
        avg_confidence = (
            sum(c for _, c in words_with_confidence) / len(words_with_confidence) / 100.0
            if words_with_confidence
            else 0.0
        )
        return RawOcrResult(text=text, confidence=round(avg_confidence, 4), engine="tesseract")
