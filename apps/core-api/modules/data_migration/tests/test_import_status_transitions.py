"""أول اختبار قابل للتشغيل فعلياً في هذا الموديول منذ اللحظة الأولى — لا
يحتاج قاعدة بيانات ولا أي connector، فقط منطق domain صرف. شغّله للتحقق من
سلامة بيئة العمل قبل البدء بأي كود آخر:
    pytest apps/core-api/modules/data_migration/tests/test_import_status_transitions.py -v
"""
import pytest

from modules.data_migration.domain.rules.import_status_transitions import (
    InvalidImportStatusTransition,
    assert_valid_transition,
)
from modules.data_migration.domain.value_objects.enums import ImportStatus


def test_connected_to_discovered_is_allowed():
    assert_valid_transition(ImportStatus.CONNECTED, ImportStatus.DISCOVERED)


def test_cannot_skip_directly_to_committing():
    """الضمان الأهم في كل الميزة: لا ترحيل فعلي بدون معاينة إلزامية أولاً."""
    with pytest.raises(InvalidImportStatusTransition):
        assert_valid_transition(ImportStatus.DISCOVERED, ImportStatus.COMMITTING)


def test_any_state_can_fail():
    assert_valid_transition(ImportStatus.MAPPED, ImportStatus.FAILED)


def test_completed_is_terminal():
    with pytest.raises(InvalidImportStatusTransition):
        assert_valid_transition(ImportStatus.COMPLETED, ImportStatus.DISCOVERED)
