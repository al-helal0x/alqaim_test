"""سجل صريح: TargetEntity → (Use Case الهدف الفعلي، DTO الهدف الفعلي).

هذا الملف هو المكان الوحيد في الموديول الذي يستورد من موديولات أخرى
(partners, catalog...) — مسموح لأنه application layer يستدعي use case
معلَن، وليس تسريباً لـ infrastructure خاص بموديول آخر (القسم 6.4).

**ملاحظة صادقة مهمة (اكتُشِفت أثناء البناء الفعلي، وليست افتراضاً):**
فحصت فعلياً `modules/accounting/application/use_cases/` في المستودع، ولا
يوجد به use case عام لإنشاء حساب مفرد من بيانات خارجية — الموجود فقط
`SeedDefaultChartOfAccountsUseCase` (يزرع شجرة حسابات افتراضية ثابتة، وليس
استيراد حسابات عميل فعلية). لذلك `CHART_OF_ACCOUNTS` مُعطَّل صراحة أدناه
حتى يُبنى use case مناسب في `modules/accounting` نفسه (خارج نطاق هذا
الموديول) — هذا يُغيّر ترتيب التنفيذ الموصى به في خطة البناء الأصلية
(كانت شجرة الحسابات هي أول كيان)، وسبب التغيير موثَّق في build plan §تحديث.
"""
from dataclasses import dataclass
from typing import Any

from modules.catalog.application.dto.catalog_dto import ProductCreateRequest
from modules.catalog.application.use_cases.catalog_use_cases import CreateProductUseCase
from modules.data_migration.domain.value_objects.enums import TargetEntity
from modules.partners.application.dto.partner_dto import PartnerCreateRequest
from modules.partners.application.use_cases.partner_use_cases import CreatePartnerUseCase


@dataclass(frozen=True)
class TargetEntityBinding:
    use_case_cls: type
    request_dto_cls: type[Any]
    unsupported_reason: str | None = None


TARGET_ENTITY_REGISTRY: dict[TargetEntity, TargetEntityBinding] = {
    TargetEntity.PARTNERS: TargetEntityBinding(
        use_case_cls=CreatePartnerUseCase,
        request_dto_cls=PartnerCreateRequest,
    ),
    TargetEntity.CATALOG_ITEMS: TargetEntityBinding(
        use_case_cls=CreateProductUseCase,
        request_dto_cls=ProductCreateRequest,
        unsupported_reason=(
            "CreateProductUseCase يتطلب base_uom_id (مرجع لوحدة قياس موجودة "
            "فعلياً في الشركة) — يحتاج استيراد وحدات القياس وربطها أولاً قبل "
            "أي منتج (راجع build plan: بند فرعي جديد لوحدات القياس)."
        ),
    ),
    TargetEntity.CHART_OF_ACCOUNTS: TargetEntityBinding(
        use_case_cls=None,  # type: ignore[arg-type]
        request_dto_cls=None,  # type: ignore[arg-type]
        unsupported_reason=(
            "لا يوجد use case عام لإنشاء حساب مفرد في modules/accounting "
            "حالياً — الموجود فقط SeedDefaultChartOfAccountsUseCase (شجرة "
            "افتراضية ثابتة). يجب بناء CreateAccountUseCase في accounting "
            "نفسه أولاً (خارج نطاق هذا الموديول) قبل تفعيل هذا الكيان هنا."
        ),
    ),
    TargetEntity.OPENING_BALANCES_INVENTORY: TargetEntityBinding(
        use_case_cls=None,  # type: ignore[arg-type]
        request_dto_cls=None,  # type: ignore[arg-type]
        unsupported_reason="لم يُفحَص بعد — راجع modules/inventory/application/use_cases/inventory_use_cases.py",
    ),
    TargetEntity.OPENING_BALANCES_ACCOUNTING: TargetEntityBinding(
        use_case_cls=None,  # type: ignore[arg-type]
        request_dto_cls=None,  # type: ignore[arg-type]
        unsupported_reason="يعتمد على حل CHART_OF_ACCOUNTS أولاً",
    ),
    TargetEntity.HISTORICAL_JOURNAL_ENTRIES: TargetEntityBinding(
        use_case_cls=None,  # type: ignore[arg-type]
        request_dto_cls=None,  # type: ignore[arg-type]
        unsupported_reason="مؤجَّل عمداً — اختياري حسب رغبة العميل (راجع خطة الميزة §4.4)",
    ),
}


def get_binding(target_entity: TargetEntity) -> TargetEntityBinding:
    binding = TARGET_ENTITY_REGISTRY.get(target_entity)
    if binding is None:
        raise ValueError(f"كيان هدف غير مسجَّل إطلاقاً: {target_entity}")
    if binding.unsupported_reason is not None:
        raise NotImplementedError(
            f"استيراد {target_entity.value} غير مدعوم بعد: {binding.unsupported_reason}"
        )
    return binding
