"""جدول partners — كيان موحّد لعملاء/موردين (blueprint القسم 8، سطر 700-701).

partner_type[customer|supplier|both] بدلاً من جدولين منفصلين، لتفادي ازدواج
البيانات عندما يكون نفس الطرف عميلاً ومورداً معاً (حالة شائعة تجارياً).
"""
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db_base import BaseModel


class Partner(BaseModel):
    __tablename__ = "partners"
    __table_args__ = (
        UniqueConstraint("company_id", "tax_number", name="uq_partners_company_tax_number"),
        # PKG-B1: يمنع أكثر من "عميل نقدي" (walk-in) واحد لكل شركة على مستوى DB.
        # Partial Unique Index — لا علاقة له بـ tax_number (غالباً NULL للعميل النقدي)
        # ولا بالاسم (ليس Business Identifier صالحاً). راجع 00_TASK_PACKAGE.md § PKG-B1.
        # ⚠️ فجوة حقيقية اكتُشِفت عند الدمج هنا: `postgresql_where=` وحدها
        # dialect-specific — على SQLite (تختبِر عليها كل الاختبارات الأخرى
        # في هذا المشروع، تبني الجدول من هذا التعريف مباشرة لا من migration)
        # يتجاهلها SQLAlchemy تماماً، فيتحول الفهرس فعلياً إلى UNIQUE **كامل**
        # على company_id — أي شركة واحدة فقط تملك partner واحد على الإطلاق!
        # هذا كسر فعلياً `test_partners_list_is_paginated` (فحص حقيقي:
        # IntegrityError عند إدراج عميل ثانٍ لنفس الشركة). SQLite يدعم
        # partial indexes فعلياً (منذ 3.8.0) — إضافة `sqlite_where=` بنفس
        # الشرط تحديداً تُصلح الفجوة على كلا القاعدتين معاً.
        Index(
            "uq_partners_company_system_managed",
            "company_id",
            unique=True,
            postgresql_where=text("is_system_managed = true"),
            sqlite_where=text("is_system_managed = true"),
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(16), nullable=False, default="customer")
    tax_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # PKG-B1: تمييز نظامي صريح — عمود منفصل عن partner_type، يُستخدم حصراً من الكود
    # النظامي (مثل endpoint walk-in في PKG-B2)، وليس من إدخال المستخدم مباشرة.
    is_system_managed: Mapped[bool] = mapped_column(default=False, nullable=False)
