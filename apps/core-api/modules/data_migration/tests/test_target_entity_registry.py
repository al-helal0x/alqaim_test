import pytest

from modules.data_migration.application.ports.target_entity_registry import get_binding
from modules.data_migration.domain.value_objects.enums import TargetEntity
from modules.partners.application.use_cases.partner_use_cases import CreatePartnerUseCase


def test_partners_binding_is_supported():
    binding = get_binding(TargetEntity.PARTNERS)
    assert binding.use_case_cls is CreatePartnerUseCase


def test_chart_of_accounts_is_explicitly_unsupported():
    """يثبت أننا لا ندّعي دعم استيراد شجرة الحسابات وهو غير موجود فعلياً —
    هذا الاختبار سيفشل تلقائياً (كتذكير) في اليوم الذي يُبنى فيه
    CreateAccountUseCase فعلياً في modules.accounting، وعندها يجب تحديث
    السجل بدل تجاهل فشل الاختبار."""
    with pytest.raises(NotImplementedError, match="CreateAccountUseCase"):
        get_binding(TargetEntity.CHART_OF_ACCOUNTS)


def test_unknown_entity_raises_value_error():
    with pytest.raises(ValueError):
        get_binding("not_a_real_entity")  # type: ignore[arg-type]
