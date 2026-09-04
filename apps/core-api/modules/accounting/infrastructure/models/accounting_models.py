"""جداول accounting — شجرة حسابات/قيود/سنوات وفترات مالية/مراكز تكلفة (القسم 13
— العضو 6). هذه الوحدة تُنتِج IAccountingPort، أهم واجهة في النظام، لذا كل
قاعدة هنا مصمَّمة حول ضمانتين لا يُسمح بكسرهما إطلاقاً:

1. أي قيد (JournalEntry) يجب أن يكون متوازناً: مجموع المدين = مجموع الدائن
   عبر كل أسطره (JournalEntryLine) — يُفرض في application layer (انظر
   domain/rules/journal_balance_rule.py) وليس فقط DB Constraint، لأن قاعدة
   البيانات لا تعرف "التوازن عبر عدة صفوف" مباشرة.
2. لا قيد جديد يُقبل على فترة مالية مُقفلة (FiscalPeriod.is_closed=True).
"""
import enum
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared_kernel.db_base import BaseModel


class AccountType(enum.StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class AccountNormalBalance(enum.StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class Account(BaseModel):
    """شجرة حسابات هرمية (Chart of Accounts) لكل شركة على حدة."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ⚠️ name= صريح إلزامي هنا: بلا تحديده، SQLAlchemy يشتق اسم نوع Postgres
    # تلقائياً من اسم كلاس Python بحروف صغيرة بلا underscore (AccountType →
    # "accounttype")، بينما الـmigration (accounting_20260804_0003) أنشأت
    # النوع فعلياً باسم "account_type" (بـunderscore، مطابق لاسم العمود).
    # المفارقة كانت تُسبب `UndefinedObjectError: type "accounttype" does not
    # exist` عند أي INSERT فعلي — اكتُشفت أثناء اختبار زرع شجرة الحسابات
    # الافتراضية يدوياً (19 أغسطس 2026)، لم تظهر في أي اختبار تلقائي سابق
    # لأن اختبارات المشروع تُنشئ الجداول عبر `Base.metadata.create_all`
    # مباشرة (تتجاوز الـmigrations كليةً) فلا تكتشف تعارض اسم كهذا أبداً.
    account_type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType,
            name="account_type",
            # ⚠️ إلزامي: بلا هذا، SQLAlchemy يخزّن .name لعضو الـPython enum
            # (مثال: "ASSET" بحروف كبيرة) بدل .value الفعلي ("asset")، رغم
            # أن AccountType هو enum.StrEnum. النوع في Postgres (المُنشَأ عبر
            # الـmigration) يقبل فقط القيم الصغيرة المعرَّفة صراحة هناك
            # ("asset", "liability", ...) — أي INSERT بدون هذا كان سيفشل
            # بـ`invalid input value for enum account_type: "ASSET"` حتى بعد
            # إصلاح تعارض اسم النوع نفسه.
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    normal_balance: Mapped[AccountNormalBalance] = mapped_column(
        Enum(
            AccountNormalBalance,
            name="account_normal_balance",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    is_postable: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )  # False لحسابات التجميع (parents) التي لا تُرحَّل عليها قيود مباشرة
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CostCenter(BaseModel):
    __tablename__ = "cost_centers"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_cost_centers_company_code"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FiscalYear(BaseModel):
    __tablename__ = "fiscal_years"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_fiscal_years_company_code"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. "2026"
    start_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    end_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    periods: Mapped[list["FiscalPeriod"]] = relationship(back_populates="fiscal_year")


class FiscalPeriod(BaseModel):
    """فترة مالية (شهرية عادة) ضمن سنة مالية. القيد الحاسم: is_closed=True يمنع
    أي ترحيل جديد على هذه الفترة (تُفحص في RecordDocumentPostingUseCase)."""

    __tablename__ = "fiscal_periods"
    __table_args__ = (
        UniqueConstraint("fiscal_year_id", "period_number", name="uq_fiscal_period_number"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    fiscal_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fiscal_years.id"), nullable=False, index=True
    )
    period_number: Mapped[int] = mapped_column(nullable=False)  # 1..12
    start_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    end_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    closed_at: Mapped["Date | None"] = mapped_column(Date, nullable=True)

    fiscal_year: Mapped["FiscalYear"] = relationship(back_populates="periods")


class JournalEntry(BaseModel):
    """رأس القيد. `source_document_type`/`source_document_id` يربطان القيد
    بالمستند التشغيلي الذي ولّده (فاتورة بيع، دفعة...) دون اعتماد مباشر على
    Modules أخرى — فقط نص/معرّف حر (Loose Coupling عبر IAccountingPort)."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("company_id", "entry_number", name="uq_journal_entries_number"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fiscal_periods.id"), nullable=False, index=True
    )
    entry_number: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_date: Mapped["Date"] = mapped_column(Date, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="IQD")
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    lines: Mapped[list["JournalEntryLine"]] = relationship(
        back_populates="journal_entry", cascade="all, delete-orphan"
    )


class JournalEntryLine(BaseModel):
    __tablename__ = "journal_entry_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    debit: Mapped["Numeric"] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    credit: Mapped["Numeric"] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    journal_entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()