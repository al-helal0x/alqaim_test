"""Initial schema: tenancy + identity foundation tables.

Revision ID: platform_20260804_0001
Revises:
Create Date: 2026-08-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "platform_20260804_0001"
down_revision = None
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("tax_number", sa.String(64), nullable=True),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="IQD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )

    op.create_table(
        "branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )
    op.create_index("ix_branches_company_id", "branches", ["company_id"])

    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
    )
    op.create_index("ix_warehouses_company_id", "warehouses", ["company_id"])
    op.create_index("ix_warehouses_branch_id", "warehouses", ["branch_id"])

    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "key", name="uq_setting_company_key"),
    )
    op.create_index("ix_system_settings_company_id", "system_settings", ["company_id"])

    op.create_table(
        "numbering_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False, server_default=""),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("padding", sa.Integer(), nullable=False, server_default="6"),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "document_type", name="uq_numbering_company_doctype"),
    )
    op.create_index("ix_numbering_sequences_company_id", "numbering_sequences", ["company_id"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_system_role", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit_columns(),
        sa.UniqueConstraint("company_id", "code", name="uq_roles_company_code"),
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])

    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id"), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    op.create_table(
        "user_company_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company"),
    )
    op.create_index("ix_user_company_roles_user_id", "user_company_roles", ["user_id"])
    op.create_index("ix_user_company_roles_company_id", "user_company_roles", ["company_id"])
    op.create_index("ix_user_company_roles_role_id", "user_company_roles", ["role_id"])


def downgrade() -> None:
    op.drop_table("user_company_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("numbering_sequences")
    op.drop_table("system_settings")
    op.drop_table("warehouses")
    op.drop_table("branches")
    op.drop_table("companies")
