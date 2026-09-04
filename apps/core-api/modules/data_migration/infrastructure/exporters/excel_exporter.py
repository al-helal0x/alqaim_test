"""تصدير Excel احترافي (القسم §5 من خطة الميزة) — تنسيق فعلي، وليس تفريغ خام:
رأس جدول ملوّن، حدود، تجميد الصف الأول. يعتمد على openpyxl (موجودة أصلاً في
اعتماديات مشروع مشابهة — تحقّق من عدم التكرار في pyproject عند الدمج)."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill(start_color="0C447C", end_color="0C447C", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True)


def export_rows_to_xlsx(*, rows: list[dict], sheet_title: str, out_path: str) -> str:
    """TODO (TASK-MIG-06): استبدال هذا التنفيذ العام بقوالب مخصَّصة لكل تقرير
    (ميزان مراجعة، كشف حساب...) بترويسة شركة من modules.tenancy، تماماً كما
    هو موضَّح في خطة الميزة §5. هذا هو التنفيذ العام الأدنى الذي يثبت أن خط
    الأنابيب (Job → بيانات → ملف) يعمل قبل إضافة التخصيص البصري الكامل."""
    if not rows:
        raise ValueError("لا توجد بيانات للتصدير")

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]  # حد Excel لاسم الورقة

    headers = list(rows[0].keys())
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = max(14, len(header) + 4)

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, header in enumerate(headers, start=1):
            ws.cell(row=row_idx, column=col_idx, value=row.get(header))

    ws.freeze_panes = "A2"
    wb.save(out_path)
    return out_path
