"""IInvoiceParser — القسم 7.3: يحوّل نص OCR الخام إلى حقول مُهيكَلة.

**حدود هذا التنفيذ (صراحةً وليس ادّعاءً بأكثر مما هو موجود):** الوثيقة
(القسم 7.12) توصي بنموذج Document Understanding (LayoutLM أو خدمة سحابية)
كتنفيذ إنتاجي كامل يدمج موقع النص المكاني مع معناه. هذا غير متاح في بيئة
تطوير محلية بلا اتصال بخدمة سحابية أو GPU. لذلك هذا التنفيذ **Baseline قائم
على Regex/الكلمات المفتاحية** (عربي+إنجليزي) لاستخراج الحقول الشائعة من نص
مسطّح — يعمل فعلياً على فواتير بتخطيط بسيط/واضح، ويُستبدَل خلف نفس الواجهة
IInvoiceParser بنموذج Document Understanding دون أي تعديل في بقية الأنبوب
(القسم 7.9) عندما تتوفر بيئة إنتاج فعلية.
"""
import re

from application.ports.ai_ports import InvoiceDraft, InvoiceLineDraft

_NUMBER = r"[\d٠-٩]+(?:[.,][\d٠-٩]+)?"  # noqa: RUF001 — نطاق أرقام عربية-هندية داخل regex مقصود لمطابقة فواتير OCR بالعربي، وليس نصاً معروضاً للقراءة

_INVOICE_NUMBER_PATTERNS = [
    r"(?:رقم\s*الفاتورة|فاتورة\s*رقم|Invoice\s*(?:No\.?|Number|#)?)\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
]
_DATE_PATTERNS = [
    r"(?:التاريخ|Date)\s*[:#]?\s*(\d{1,4}[\/\-]\d{1,2}[\/\-]\d{1,4})",
]
_TOTAL_PATTERNS = [
    r"(?<!sub)(?<!Sub)(?:الإجمالي|المجموع\s*الكلي|Total\s*Amount|Grand\s*Total|Total)\s*[:#]?\s*(" + _NUMBER + r")",
]
_TAX_PATTERNS = [
    r"(?:الضريبة|ضريبة\s*المبيعات|VAT|Tax)\s*[:#]?\s*(" + _NUMBER + r")",
]
_DISCOUNT_PATTERNS = [
    r"(?:الخصم|Discount)\s*[:#]?\s*(" + _NUMBER + r")",
]
_SUBTOTAL_PATTERNS = [
    r"(?:المجموع\s*الفرعي|Subtotal)\s*[:#]?\s*(" + _NUMBER + r")",
]
_SUPPLIER_PATTERNS = [
    r"(?:المورد|اسم\s*الشركة|Supplier|Vendor|From)\s*[:#]?\s*([^\n\d]{2,60})",
]
_CURRENCY_MAP = {
    "iqd": "IQD", "دينار": "IQD", "د.ع": "IQD",
    "usd": "USD", "$": "USD", "دولار": "USD",
}

# سطر بند مبسّط: وصف نصي ثم رقمين أو ثلاثة (كمية/سعر/إجمالي) — Baseline بسيط
_LINE_ITEM_PATTERN = re.compile(
    r"^(?P<desc>[^\d\n]{3,60}?)\s+(?P<qty>" + _NUMBER + r")\s+(?P<price>" + _NUMBER + r")"
    r"(?:\s+(?P<total>" + _NUMBER + r"))?$"
)

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = raw.translate(_ARABIC_DIGITS).replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


class HeuristicInvoiceParser:
    """Baseline Regex/Keyword Parser — انظر توثيق الحدود أعلى الملف."""

    def parse(self, raw_text: str) -> InvoiceDraft:
        draft = InvoiceDraft()
        confidence: dict[str, float] = {}

        draft.invoice_number_guess = _first_match(_INVOICE_NUMBER_PATTERNS, raw_text)
        confidence["invoice_number"] = 0.75 if draft.invoice_number_guess else 0.0

        draft.invoice_date_guess = _first_match(_DATE_PATTERNS, raw_text)
        confidence["invoice_date"] = 0.7 if draft.invoice_date_guess else 0.0

        draft.total_guess = _to_float(_first_match(_TOTAL_PATTERNS, raw_text))
        confidence["total"] = 0.8 if draft.total_guess is not None else 0.0

        draft.tax_guess = _to_float(_first_match(_TAX_PATTERNS, raw_text))
        draft.discount_guess = _to_float(_first_match(_DISCOUNT_PATTERNS, raw_text))
        draft.subtotal_guess = _to_float(_first_match(_SUBTOTAL_PATTERNS, raw_text))

        supplier_raw = _first_match(_SUPPLIER_PATTERNS, raw_text)
        draft.supplier_name_guess = supplier_raw.strip() if supplier_raw else None
        confidence["supplier_name"] = 0.6 if draft.supplier_name_guess else 0.0

        lower_text = raw_text.lower()
        for token, code in _CURRENCY_MAP.items():
            if token in lower_text:
                draft.currency_guess = code
                confidence["currency"] = 0.65
                break

        for line in raw_text.splitlines():
            m = _LINE_ITEM_PATTERN.match(line.strip())
            if not m:
                continue
            qty = _to_float(m.group("qty"))
            price = _to_float(m.group("price"))
            total = _to_float(m.group("total")) if m.group("total") else (
                round(qty * price, 2) if qty is not None and price is not None else None
            )
            draft.lines.append(
                InvoiceLineDraft(
                    description=m.group("desc").strip(),
                    quantity=qty,
                    unit_price=price,
                    line_total=total,
                    confidence=0.55,
                )
            )

        draft.field_confidence = confidence
        return draft
