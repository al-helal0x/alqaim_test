"""حساب الضريبة — قاعدة نطاق صِرفة، بلا اعتماد على SQLAlchemy/FastAPI."""
from decimal import ROUND_HALF_UP, Decimal


def calculate_tax_amount(base_amount: Decimal, rate_percent: Decimal) -> Decimal:
    """يحسب مبلغ الضريبة من مبلغ أساسي ونسبة مئوية، بتقريب لأقرب فِلس
    (4 خانات عشرية، متوافق مع دقة Numeric(18,4) في journal_entry_lines)."""
    if base_amount < 0:
        raise ValueError("المبلغ الأساسي لا يمكن أن يكون سالباً")
    if rate_percent < 0:
        raise ValueError("نسبة الضريبة لا يمكن أن تكون سالبة")

    amount = (base_amount * rate_percent) / Decimal(100)
    return amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
