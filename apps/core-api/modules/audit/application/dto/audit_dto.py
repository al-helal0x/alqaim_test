from datetime import datetime

from pydantic import BaseModel

from shared_kernel.pydantic_types import UUIDStr


class AuditLogEntryResponse(BaseModel):
    id: UUIDStr
    event_name: str
    payload: dict
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
