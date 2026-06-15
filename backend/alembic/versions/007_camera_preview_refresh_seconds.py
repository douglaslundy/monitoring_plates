"""camera preview refresh seconds

Revision ID: 007
Revises: 006
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column(
            "preview_refresh_seconds",
            sa.Float(),
            nullable=False,
            server_default=sa.text("2.5"),
        ),
    )


def downgrade() -> None:
    op.drop_column("cameras", "preview_refresh_seconds")
