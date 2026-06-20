"""add message to alerts_sent

Revision ID: 015_alerts_sent_message
Revises: 014_whatsapp_test_recipient
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "015_alerts_sent_message"
down_revision = "014_whatsapp_test_recipient"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerts_sent",
        sa.Column("message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alerts_sent", "message")
