"""Outbox pattern: create `outbox_events` table (مهمة #6 — راجع
DELIVERY_CARD_TASK_06.md لشكل الحقول).

⚠️ Task #6-S2 (Migration Chain Fix) — ملاحظة الرأس:
بطاقة تسليم #6 الأصلية والـ README الخاص بهذه الحزمة و ADR-001 §القرار 5
كلها ذكرت `identity_20260808_0003` كالرأس الفعلي الحالي، وبطاقة التسليم
تحديدًا اقترحت `down_revision = wfna_20260808_0002` (فرع منفصل قديم حتى).
تحقّقتُ بنفسي (لا افتراضًا) عبر `alembic heads` و`ScriptDirectory.get_heads()`
على قاعدة Postgres حقيقية بكامل سلسلة الـ versions المرفَقة، والرأس الفعلي
الوحيد وقت كتابة هذا الملف هو **`sales_20260809_0001`** — أُضيفت لاحقًا
(2026-08-09، أثناء دمج الدفعة الثالثة) فوق `identity_20260808_0003` لسد
migration ناقصة من مهمة #11. أي ملف يُبنى فوق `identity_20260808_0003`
أو `wfna_20260808_0002` الآن سينتج رأسين منفصلين (فرع)، لا رأسًا واحدًا،
وهو بالضبط ما تمنعه معيار القبول (`alembic heads` → نتيجة واحدة). لذلك
`down_revision` هنا = `sales_20260809_0001`، خلافًا للنص الحرفي في
التعليمات، تنفيذًا لخطوة 1 من الإجراء الإلزامي ("تحقّق بنفسك أولاً، لا
تفترض") وليس مخالفة لها.

الجدول: `outbox_events` — تعريف بنية فقط (لا Worker، لا منطق تسليم؛ ذلك
من اختصاص تنفيذ #6 الفعلي لاحقًا). الحقول مطابقة تمامًا لما ورد في
DELIVERY_CARD_TASK_06.md ولـ platform_core/outbox_models.py (OutboxEvent):
event_name, payload (JSONB), status, attempts, last_error, dispatched_at,
next_attempt_at, بالإضافة إلى id/created_at القياسيين.

فهرس مركّب (status, next_attempt_at) مضاف لأنه استعلام الاستطلاع الطبيعي
لأي worker على هذا الجدول (WHERE status = 'pending' AND next_attempt_at <= now())
— هذا فهرس DDL بحت ضمن حدود "التعريف فقط"، وليس منطق تسليم.

Revision ID: platform_20260809_0002
Revises: sales_20260809_0001
Create Date: 2026-08-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "platform_20260809_0002"
down_revision = "sales_20260809_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outbox_events_event_name", "outbox_events", ["event_name"])
    op.create_index(
        "ix_outbox_events_status_next_attempt_at",
        "outbox_events",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_status_next_attempt_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_name", table_name="outbox_events")
    op.drop_table("outbox_events")
