"""add test_recipient to whatsapp_channel_settings

Revision ID: 014_whatsapp_test_recipient
Revises: 013_whatsapp_channel_settings
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "014_whatsapp_test_recipient"
down_revision = "013_whatsapp_channel_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_channel_settings",
        sa.Column("test_recipient", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_channel_settings", "test_recipient")
