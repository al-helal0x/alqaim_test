# tests/ (ai-platform)

```bash
cd apps/ai-platform
pip install -e ".[dev]" --break-system-packages
apt-get install -y tesseract-ocr tesseract-ocr-ara   # مطلوب مرة واحدة على مستوى النظام
PYTHONPATH=. pytest tests/ -v
```

- `unit/` — منطق صرف بلا DB ولا صور: `test_validator.py` (فحوصات القسم 7.5)،
  `test_entity_matcher.py` (Fuzzy Matching)، `test_invoice_parser.py` (Regex
  على نص جاهز).
- `integration/` — تكامل حقيقي:
  - `test_ocr_pipeline_end_to_end.py`: **يولّد صورة فاتورة فعلية عبر PIL**
    ويمرّرها عبر Preprocessing (OpenCV) → OCR (Tesseract حقيقي) → Parsing →
    Validation → Matching، ويتحقق من صحة القيم المستخرجة من البكسلات فعلياً.
  - `test_pipeline_persists_draft.py`: نفس الشيء + يتحقق من التخزين الفعلي
    في قاعدة بيانات (SQLite للاختبار) بحالة `pending_review` دائماً.

**15/15 اختبار ناجح حالياً** — تغطي المسار الكامل MVP (القسم 7.13، المرحلة
الأولى) من صورة حتى مسودة تنتظر مراجعة بشرية.
