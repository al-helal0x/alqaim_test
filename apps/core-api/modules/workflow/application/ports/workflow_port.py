"""IWorkflowPort — واجهة عامة تتيح لأي Module تشغيلي (Sales/Purchasing/...)
بدء "نسخة موافقة" (Approval Instance) على محرك workflow العام والاستعلام عن
حالتها الحالية، دون معرفة أي شيء عن infrastructure/جداول workflow الداخلية
(قاعدة الاستيراد الإلزامية، القسم 11.2 — الوحدات المستهلكة تستورد فقط من
هذا الملف application/ports، تماماً كنمط IAccountingPort/IInventoryPort).

هذا أول مستهلك فعلي لمحرك workflow (مهمة #12 — sales↔workflow: فاتورة بيع
> 10,000 تحتاج موافقة مدير). القرار المعماري الموثَّق سابقاً في
workflow/README.md ("لا اشتراك في Event Bus هذه الجولة، الربط عبر استدعاء
صريح فقط") لا يزال قائماً: sales هي من تستدعي IWorkflowPort صراحة (عبر
Use Case خاص بها يستجيب لحدثها الداخلي SalesInvoiceCreated) — workflow نفسها
ما زالت لا تشترك في أي حدث مباشرة.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ApprovalWorkflowRequest:
    company_id: str
    entity_type: str
    entity_id: str
    # اسم تعريف سير العمل (workflow_definitions.name) — يُنشأ تلقائياً أول
    # مرة فقط إن لم يكن موجوداً بعد لهذه الشركة/entity_type (بنفس states/
    # transitions الممرَّرة هنا)، ثم يُعاد استخدامه في كل نداء تالٍ دون أي
    # تكرار لإنشاء التعريف.
    definition_name: str
    states: list[str]
    transitions: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowInstanceRef:
    instance_id: str
    current_state: str


class IWorkflowPort(Protocol):
    async def ensure_approval_started(
        self, request: ApprovalWorkflowRequest
    ) -> WorkflowInstanceRef:
        """Idempotent عمداً: نداء متكرر لنفس (entity_type, entity_id) لا
        يُنشئ أكثر من نسخة واحدة — يعيد النسخة الموجودة فعلياً إن وُجدت بدل
        رفع خطأ أو تكرار الإنشاء."""
        ...

    async def get_latest_instance_state(
        self, *, company_id: str, entity_type: str, entity_id: str
    ) -> str | None:
        """`None` تعني: لا توجد أي نسخة موافقة لهذا الكيان (لم تُبدَأ أصلاً،
        غالباً لأن المبلغ لم يتجاوز الحد) — يُفهَم من طرف المستدعي كـ "لا
        اعتراض"، وليس كخطأ."""
        ...
