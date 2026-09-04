"""IValidator — القسم 7.5: فحوصات المنطق المالي بعد الاستخراج.

قاعدة صارمة من الوثيقة (7.5 + 17): **لا ترحيل تلقائي أبداً عند وجود أي
تنبيه غير محلول** — هذا التنفيذ يُرجع تنبيهات فقط، ولا يتخذ أي قرار ترحيل.
"""
from application.ports.ai_ports import InvoiceDraft, ValidationWarning

_AMOUNT_TOLERANCE = 0.05  # هامش تقريب بسيط لأخطاء OCR على الكسور العشرية


class InvoiceValidator:
    def validate(self, draft: InvoiceDraft, *, company_currency: str) -> list[ValidationWarning]:
        warnings: list[ValidationWarning] = []

        if draft.total_guess is None:
            warnings.append(
                ValidationWarning(
                    code="MISSING_TOTAL", message="لم يتم استخراج الإجمالي", field="total_guess",
                    severity="error",
                )
            )

        if draft.lines:
            lines_sum = sum(line.line_total or 0 for line in draft.lines)
            tax = draft.tax_guess or 0
            discount = draft.discount_guess or 0
            expected_total = lines_sum + tax - discount
            if draft.total_guess is not None and abs(expected_total - draft.total_guess) > _AMOUNT_TOLERANCE:
                warnings.append(
                    ValidationWarning(
                        code="TOTAL_MISMATCH",
                        message=(
                            f"مجموع البنود ({lines_sum}) + الضريبة ({tax}) - الخصم ({discount}) "
                            f"= {expected_total} لا يطابق الإجمالي المستخرج ({draft.total_guess})"
                        ),
                        field="total_guess",
                        severity="error",
                    )
                )

        for idx, line in enumerate(draft.lines):
            if line.quantity is not None and line.quantity <= 0:
                warnings.append(
                    ValidationWarning(
                        code="ZERO_OR_NEGATIVE_QUANTITY",
                        message=f"كمية غير صالحة في البند {idx + 1}: {line.quantity}",
                        field=f"lines[{idx}].quantity",
                        severity="error",
                    )
                )
            if line.unit_price is not None and line.unit_price < 0:
                warnings.append(
                    ValidationWarning(
                        code="NEGATIVE_PRICE",
                        message=f"سعر سالب في البند {idx + 1}: {line.unit_price}",
                        field=f"lines[{idx}].unit_price",
                        severity="error",
                    )
                )

        if draft.currency_guess and draft.currency_guess != company_currency:
            warnings.append(
                ValidationWarning(
                    code="CURRENCY_MISMATCH",
                    message=(
                        f"عملة الفاتورة المستخرجة ({draft.currency_guess}) تختلف عن عملة "
                        f"الشركة ({company_currency}) — يلزم سعر صرف صريح"
                    ),
                    field="currency_guess",
                    severity="warning",
                )
            )

        if not draft.invoice_number_guess:
            warnings.append(
                ValidationWarning(
                    code="MISSING_INVOICE_NUMBER",
                    message="لم يتم استخراج رقم الفاتورة",
                    field="invoice_number_guess",
                    severity="warning",
                )
            )

        return warnings
