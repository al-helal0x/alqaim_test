"""ملاحظة (مهمة #11): هذا الملف يفترض وجود `StartManagerApprovalForSalesInvoiceUseCase`
في `sales_use_cases.py`، وهي غير موجودة بعد في النسخة الأساسية الحالية لذلك
الملف (راجع تعليق مماثل في `presentation/routes/invoices_router.py` وREADME
حزمة مهمة #11) — تُستكمل مع حسم تعارض #6×#12، وليست جزءاً من مهمة #11.

معالج حدث `SalesInvoiceCreated` — يبدأ سير موافقة مدير تلقائياً عند تجاوز
حد المبلغ (مهمة #12، Workflow). يستقبل `IWorkflowPort` **جاهزاً** (مُحقَناً
من `main.py`، نقطة التوصيل/Composition Root) — هذا الملف لا يستورد أي شيء
من `workflow/infrastructure` مباشرة، فقط منطق sales الخاص (Use Case) وواجهة
Port المعلنة، طبقاً لقاعدة الاستيراد الإلزامية (القسم 11.2). نفس نمط
`modules/purchasing/infrastructure/event_handlers.py:apply_payment_to_invoice`
(معالج خفيف مُسجَّل مركزياً في `main.py`)، مع فارق واحد: تلك الوحدة توّاصلت
عبر Event Bus بلا حاجة لـ Port لأنها لا تحتاج شيئاً من payments سوى الحمولة
نفسها؛ هنا sales تحتاج فعلياً تشغيل محرك workflow (وحدة أخرى) فتمر عبر
IWorkflowPort الصريح.
"""
from modules.sales.application.use_cases.sales_use_cases import (
    StartManagerApprovalForSalesInvoiceUseCase,
)
from modules.workflow.application.ports.workflow_port import IWorkflowPort


async def handle_sales_invoice_created(workflow_port: IWorkflowPort, payload: dict) -> None:
    await StartManagerApprovalForSalesInvoiceUseCase(workflow_port).execute(payload)
