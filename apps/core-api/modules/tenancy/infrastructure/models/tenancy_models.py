"""جداول tenancy — companies/branches/warehouses/system_settings/numbering_sequences
(القسم 8). كل الجداول التشغيلية في النظام تحمل company_id (عزل صارم Multi-Tenant).
"""
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_kernel.db_base import BaseModel


class Company(BaseModel):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), default="IQD", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    branches: Mapped[list["Branch"]] = relationship(back_populates="company")


class Branch(BaseModel):
    __tablename__ = "branches"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="branches")
    warehouses: Mapped[list["Warehouse"]] = relationship(back_populates="branch")


class Warehouse(BaseModel):
    __tablename__ = "warehouses"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    branch: Mapped["Branch"] = relationship(back_populates="warehouses")


class SystemSetting(BaseModel):
    __tablename__ = "system_settings"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_setting_company_key"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)


class NumberingSequence(BaseModel):
    """خدمة الترقيم المركزية — القسم 12 (INumberingService).

    صف واحد لكل (company_id, document_type). التزامن يُضمَن عبر قفل صف
    قاعدة البيانات (SELECT ... FOR UPDATE) داخل NumberingService، وليس
    عبر منطق تطبيقي — لتفادي تكرار الأرقام تحت الحمل المتزامن (القسم 17).
    """

    __tablename__ = "numbering_sequences"
    __table_args__ = (
        UniqueConstraint("company_id", "document_type", name="uq_numbering_company_doctype"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    last_value: Mapped[int] = mapped_column(default=0, nullable=False)
    padding: Mapped[int] = mapped_column(default=6, nullable=False)
