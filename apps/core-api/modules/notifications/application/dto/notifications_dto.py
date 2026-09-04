from datetime import datetime

from pydantic import BaseModel

from shared_kernel.pydantic_types import UUIDStr


class NotificationResponse(BaseModel):
    id: UUIDStr
    event_name: str
    title: str
    body: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
