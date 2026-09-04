"""جداول catalog — product_categories/units_of_measure/products/price_lists/
price_list_items (blueprint القسم 8، سطر 690-691 وREADME الوحدة).

ملاحظة القسم 8 (سطر 695): لا يوجد حقل current_stock ثابت هنا — الرصيد يُحسب من
stock_movements في وحدة inventory (العضو 3)، وليس من هذه الوحدة.
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class ProductCategory(BaseModel):
    __tablename__ = "product_categories"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # تصنيف شجري (blueprint سطر 180) — self-referencing، بدون علاقة ORM صريحة
    # لتفادي تعقيد دوري غير ضروري في هذه المرحلة؛ الاستعلام الشجري يُبنى في التطبيق.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True
    )


class UnitOfMeasure(BaseModel):
    """وحدات القياس (بلا تحويلات في هذه المرحلة الأولى — Skeleton). التحويلات
    (كرتون↔قطعة، blueprint سطر 181) تُضاف كحقل uom_conversions لاحقاً عند الحاجة
    الفعلية من Sales/POS/Inventory دون كسر هذا العقد."""

    __tablename__ = "units_of_measure"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_uom_company_code"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Product(BaseModel):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[str] = mapped_column(String(16), nullable=False, default="product")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True
    )
    base_uom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False
    )
    sale_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PriceList(BaseModel):
    __tablename__ = "price_lists"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PriceListItem(BaseModel):
    __tablename__ = "price_list_items"
    __table_args__ = (
        UniqueConstraint("price_list_id", "product_id", name="uq_price_list_item_product"),
    )

    price_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
