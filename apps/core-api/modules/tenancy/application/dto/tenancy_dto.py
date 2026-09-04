from pydantic import BaseModel, Field

from shared_kernel.pydantic_types import UUIDStr


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    legal_name: str | None = None
    tax_number: str | None = None
    default_currency: str = Field(default="IQD", min_length=3, max_length=3)


class CompanyResponse(BaseModel):
    id: UUIDStr
    name: str
    default_currency: str
    is_active: bool

    model_config = {"from_attributes": True}


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class BranchResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class WarehouseCreateRequest(BaseModel):
    branch_id: str
    name: str = Field(min_length=2, max_length=255)


class WarehouseResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    branch_id: UUIDStr
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class NextNumberResponse(BaseModel):
    document_type: str
    number: str
