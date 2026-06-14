"""camera roi fields

Revision ID: 006
Revises: 005
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("roi_x", sa.Float(), nullable=True))
    op.add_column("cameras", sa.Column("roi_y", sa.Float(), nullable=True))
    op.add_column("cameras", sa.Column("roi_width", sa.Float(), nullable=True))
    op.add_column("cameras", sa.Column("roi_height", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "roi_height")
    op.drop_column("cameras", "roi_width")
    op.drop_column("cameras", "roi_y")
    op.drop_column("cameras", "roi_x")
