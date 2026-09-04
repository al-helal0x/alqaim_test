"""قواعد نطاق pos الصرفة."""
from enum import StrEnum


class PosSessionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class PosSyncItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
