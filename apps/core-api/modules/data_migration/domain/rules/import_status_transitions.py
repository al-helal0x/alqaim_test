"""قاعدة عمل صرفة — بدون أي I/O. تُستدعى من use_cases قبل أي تغيير حالة."""
from modules.data_migration.domain.value_objects.enums import ImportStatus

# كل حالة → مجموعة الحالات المسموح الانتقال إليها منها مباشرة.
_ALLOWED_TRANSITIONS: dict[ImportStatus, set[ImportStatus]] = {
    ImportStatus.CONNECTED: {ImportStatus.DISCOVERED, ImportStatus.FAILED},
    ImportStatus.DISCOVERED: {ImportStatus.MAPPED, ImportStatus.FAILED},
    ImportStatus.MAPPED: {ImportStatus.PREVIEWED, ImportStatus.FAILED},
    ImportStatus.PREVIEWED: {ImportStatus.COMMITTING, ImportStatus.FAILED},
    ImportStatus.COMMITTING: {ImportStatus.COMPLETED, ImportStatus.FAILED},
    ImportStatus.COMPLETED: set(),
    ImportStatus.FAILED: set(),
}


class InvalidImportStatusTransition(Exception):
    pass


def assert_valid_transition(current: ImportStatus, new: ImportStatus) -> None:
    """يفرض المسار الإلزامي: connected → discovered → mapped → previewed →
    committing → completed. لا يجوز تخطي مرحلة (مثلاً القفز من discovered
    مباشرة إلى committing) — هذا هو الضمان البرمجي لمبدأ 'لا ترحيل فعلي بدون
    معاينة إلزامية' المذكور في خطة الميزة §4.1."""
    if new not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidImportStatusTransition(
            f"لا يمكن الانتقال من {current.value} إلى {new.value} مباشرة"
        )
