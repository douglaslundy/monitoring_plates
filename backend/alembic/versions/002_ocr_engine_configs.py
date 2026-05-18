"""ocr engine configs

Revision ID: 002
Revises: 001
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ocr_engine_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("engine_type", sa.String(30), nullable=False),
        sa.Column("mode", sa.String(15), nullable=False, server_default="cloud"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("api_token", sa.String(255), nullable=True),
        sa.Column("api_url", sa.String(500), nullable=True),
        sa.Column("license_key", sa.String(255), nullable=True),
        sa.Column("regions", sa.JSON(), nullable=True),
        sa.Column("enable_mmc", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_ocr_engine_configs_engine_type", "ocr_engine_configs", ["engine_type"])

    op.add_column(
        "plans",
        sa.Column("ocr_engine", sa.String(30), nullable=False, server_default="system_default"),
    )


def downgrade() -> None:
    op.drop_column("plans", "ocr_engine")
    op.drop_index("ix_ocr_engine_configs_engine_type", "ocr_engine_configs")
    op.drop_table("ocr_engine_configs")
