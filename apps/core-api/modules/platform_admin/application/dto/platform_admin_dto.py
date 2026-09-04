from datetime import datetime

from pydantic import BaseModel


class CompanyAdminSummaryResponse(BaseModel):
    id: str
    name: str
    default_currency: str
    is_active: bool
    branch_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
