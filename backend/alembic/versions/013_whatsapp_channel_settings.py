"""add whatsapp channel settings

Revision ID: 013_whatsapp_channel_settings
Revises: 012_monitored_plate_whatsapp
Create Date: 2026-06-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "013_whatsapp_channel_settings"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_channel_settings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("evolution_base_url", sa.String(length=255), nullable=False),
        sa.Column("evolution_instance_name", sa.String(length=100), nullable=False),
        sa.Column("evolution_api_key", sa.String(length=255), nullable=True),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("20")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_channel_settings")
