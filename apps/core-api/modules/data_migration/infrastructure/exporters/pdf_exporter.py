"""تصدير PDF — تنفيذ فعلي عبر reportlab. **اكتشاف صادق أثناء البناء:** فحصت
فعلياً modules/documents في المستودع الأساسي ولا يوجد به أي محرّك توليد PDF
حالياً (لا reportlab ولا weasyprint ولا fpdf ضمن اعتماديات المشروع) — أي أن
"عدم إعادة بناء محرك موجود" (الملاحظة في README الموديول) غير قابلة للتطبيق
الآن لعدم وجود محرك أصلاً؛ reportlab أُضيف هنا كأول محرك PDF في المشروع
كله، وليس فقط لهذا الموديول. يستحق نقاشاً مع الفريق: هل يُنقَل هذا الاعتماد
ليكون عاماً في shared_kernel بدل حصره داخل data_migration، بما أن أي موديول
آخر قد يحتاج توليد PDF مستقبلاً (فواتير، تقارير محاسبية...)."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import (
    stringWidth,  # noqa: F401  # يُستخدَم لاحقاً لضبط عرض الأعمدة تلقائياً
)
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def export_rows_to_pdf(*, rows: list[dict], title: str, company_header: dict, out_path: str) -> str:
    """⚠️ قيد معروف وغير محلول بعد: reportlab لا يدعم تشكيل الحروف العربية
    المتصلة ولا اتجاه RTL أصلاً — نص عربي سيظهر بحروف منفصلة وباتجاه معكوس
    كما هو. الحل المعروف صناعياً هو تمرير كل نص عربي عبر `arabic_reshaper`
    ثم `python-bidi` قبل تمريره لـ reportlab. لم يُضَف هنا عمداً (اعتماديان
    إضافيان يحتاجان قراراً من الفريق)، وهذا **يجعل هذا الملف غير صالح فعلياً
    لتقارير عربية حتى تُحل هذه النقطة** — يجب تسجيلها صراحة في build plan
    كمهمة فرعية إلزامية قبل إغلاق TASK-MIG-06، لا كتفصيل تجميلي لاحق."""
    """company_header المتوقَّع: {"name": str, "tax_number": str | None}.
    راجع خطة الميزة §5 — ترويسة الشركة يجب أن تُجلَب فعلياً من modules.tenancy
    لا أن تُمرَّر يدوياً؛ هذا التمرير اليدوي مؤقت لإثبات أن محرك PDF نفسه
    يعمل، والربط الفعلي بـ tenancy مهمة منفصلة (TASK-MIG-06 الفرعية)."""
    if not rows:
        raise ValueError("لا توجد بيانات للتصدير")

    doc = SimpleDocTemplate(
        out_path, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm
    )
    styles_title = ParagraphStyle(
        "ar_title", fontSize=16, leading=20, spaceAfter=6, alignment=1
    )
    styles_sub = ParagraphStyle("ar_sub", fontSize=10, leading=14, alignment=1, textColor=colors.grey)

    elements = [
        Paragraph(company_header.get("name", ""), styles_title),
        Paragraph(title, styles_sub),
        Spacer(1, 0.5 * cm),
    ]

    headers = list(rows[0].keys())
    table_data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C447C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return out_path
