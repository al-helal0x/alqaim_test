from decimal import Decimal

from pydantic import BaseModel, Field

from modules.catalog.domain.rules import ProductType
from shared_kernel.pydantic_types import UUIDStr


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None


class CategoryResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    name: str
    parent_id: UUIDStr | None

    model_config = {"from_attributes": True}


class UomCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=100)


class UomResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    code: str
    name: str

    model_config = {"from_attributes": True}


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    product_type: ProductType = ProductType.PRODUCT
    category_id: str | None = None
    base_uom_id: str
    sale_price: Decimal = Decimal(0)
    purchase_price: Decimal = Decimal(0)
    track_inventory: bool = True


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: str | None = None
    sale_price: Decimal | None = None
    purchase_price: Decimal | None = None
    track_inventory: bool | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    sku: str
    name: str
    product_type: ProductType
    category_id: UUIDStr | None
    base_uom_id: UUIDStr
    sale_price: Decimal
    purchase_price: Decimal
    track_inventory: bool
    is_active: bool

    model_config = {"from_attributes": True}


class ProductDTO(BaseModel):
    """DTO المعلَن في docs/architecture/contracts.md §3 — يُستهلك من inventory/sales/
    purchasing/ai-platform عبر IProductLookup. لا يتغيّر إلا بموافقة الفريق."""

    id: UUIDStr
    sku: str
    name: str
    uom: str
    is_active: bool
    company_id: UUIDStr

    model_config = {"from_attributes": True}


class ProductImportRowResult(BaseModel):
    """نتيجة معالجة سطر واحد من ملف /products/import (blueprint القسم 9.4)."""

    row_number: int
    sku: str
    success: bool
    error: str | None = None


class ProductImportSummary(BaseModel):
    total_rows: int
    succeeded: int
    failed: int
    rows: list[ProductImportRowResult]


class PriceListCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    currency: str = Field(default="IQD", min_length=3, max_length=3)
    is_default: bool = False


class PriceListResponse(BaseModel):
    id: UUIDStr
    company_id: UUIDStr
    name: str
    currency: str
    is_default: bool

    model_config = {"from_attributes": True}


class PriceListItemCreateRequest(BaseModel):
    product_id: str
    price: Decimal = Field(ge=0)


class PriceListItemResponse(BaseModel):
    id: UUIDStr
    price_list_id: UUIDStr
    product_id: UUIDStr
    price: Decimal

    model_config = {"from_attributes": True}
