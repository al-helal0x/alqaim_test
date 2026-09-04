"""Outbox pattern: add `aggregate_id` to `outbox_events` (تنفيذ #6×#11×#12×#10
— Track 1 gap-fill).

⚠️ فجوة اكتُشفت عند الدمج النهائي (وليست جزءاً من أي Track فردي — الثلاثة
Tracks ممنوعة صراحة من لمس أي migration): العقد المجمَّد
`INTERFACE_CONTRACT_OUTBOX.md` يفرض `enqueue_event(session, *, event_name,
payload, aggregate_id)` — `aggregate_id` معامل إلزامي. لكن جدول
`outbox_events` كما زُرع في `platform_20260809_0002_outbox_events.py` لا
يتضمّن عموداً له إطلاقاً. الحل هنا: migration تالية تضيف العمود (Nullable —
معلومة استعلام مفيدة، وليست قيد عمل)، بدل تعديل `platform_20260809_0002`
القائمة أصلاً (قد تكون مُطبَّقة فعلاً على بيئة حقيقية — تعديل migration
مُطبَّقة سلوك خاطئ، إضافة migration تالية هي الصحيح).

Revision ID: platform_20260812_0003
Revises: platform_20260809_0002
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "platform_20260812_0003"
down_revision = "platform_20260809_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outbox_events", sa.Column("aggregate_id", sa.String(128), nullable=True)
    )
    op.create_index(
        "ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_column("outbox_events", "aggregate_id")
