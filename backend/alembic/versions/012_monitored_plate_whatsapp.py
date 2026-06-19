"""add alert_whatsapp to monitored_plates

Revision ID: 012
Revises: 011
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitored_plates",
        sa.Column("alert_whatsapp", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitored_plates", "alert_whatsapp")
