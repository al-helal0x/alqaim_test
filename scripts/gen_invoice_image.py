#!/usr/bin/env python3
"""يُشغَّل داخل ai-platform فقط (فيها Pillow) — يولّد صورة الفاتورة
التركيبية ويحفظها كملف، حتى يمكن نسخها لاحقاً واستخدامها من core-api
(التي لا تملك Pillow ضمن تبعياتها، ولا حاجة لها أصلاً).

⚠️ إصلاح (2026-08-17، بعد أول تشغيل E2E حي فعلي عبر GATE-05): النسخة
السابقة كانت ترسم النص بخط PIL الافتراضي (ImageFont.load_default) —
ارتفاعه الفعلي على القماش لا يتجاوز ~10px (تحقّق: textbbox أعطى ارتفاعاً
2→12px فقط). هذا غير قابل للقراءة عملياً بواسطة OCR حتى بلا أي معالجة
مسبقة، ويتفاقم أكثر مع OpenCvPreprocessor (denoising + adaptive threshold
بحجم نافذة 31px مصمَّم لصور مسح حقيقية) الذي يمحو تفاصيل الخط الصغير
تماماً. النتيجة الفعلية المُلاحَظة: OCR أعاد "Domo Supplisr For Matching
Widget" بدل "Demo Supplier For Matching" — تشابه ضبابي 0.81 فقط، أقل من
عتبة المطابقة التلقائية 0.92 في ProcessInvoiceDocumentUseCase، فبقي
matched_supplier_id فارغاً رغم أن كل شيء آخر في الأنبوب يعمل بشكل صحيح.

الإصلاح: خط TrueType حقيقي (DejaVuSans، يتطلب حزمة fonts-dejavu-core على
مستوى النظام — أُضيفت في Dockerfile.ai-platform) بحجم 28px على قماش أكبر،
بدل الخط الافتراضي المصغَّر. تحقَّق محلياً: نفس نص هذا الملف عبر نفس
Preprocessor+OCR الحقيقيين ينتج نصاً نظيفاً تماماً بلا أخطاء إملائية،
ومطابقة ضبابية 0.95 مع "Demo Supplier For Matching" — تتجاوز عتبة 0.92.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

lines = [
    "Invoice Number: INV-2026-001",
    "Date: 17/08/2026",
    "Supplier: Demo Supplier For Matching",
    "",
    "Widget A          10   500   5000",
    "Widget B           5   300   1500",
    "",
    "Subtotal: 6500",
    "Tax: 0",
    "Total: 6500",
]

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SIZE = 28

if Path(FONT_PATH).exists():
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
else:
    # تراجع آمن فقط لبيئات تفتقد الحزمة (لن يحدث داخل صورة ai-platform
    # الرسمية بعد إصلاح Dockerfile) — يُحافظ على تشغيل السكربت بلا كسر،
    # لكن جودة OCR الناتجة ستعود للمشكلة الأصلية.
    print(f"⚠️  خط {FONT_PATH} غير موجود — رجوع للخط الافتراضي (جودة OCR ستكون أضعف).")
    font = ImageFont.load_default()

img = Image.new("RGB", (1400, 700), color="white")
draw = ImageDraw.Draw(img)
y = 40
for line in lines:
    draw.text((40, y), line, fill="black", font=font)
    y += 60

img.save("/app/invoice.png", format="PNG")
print("✅ تم إنشاء /app/invoice.png")
