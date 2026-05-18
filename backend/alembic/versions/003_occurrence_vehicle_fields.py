"""occurrence vehicle fields

Revision ID: 003
Revises: 002
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("occurrences", sa.Column("vehicle_type", sa.String(30), nullable=True))
    op.add_column("occurrences", sa.Column("vehicle_color", sa.String(50), nullable=True))
    op.add_column("occurrences", sa.Column("vehicle_make_model", sa.String(100), nullable=True))
    op.add_column("occurrences", sa.Column("region_code", sa.String(10), nullable=True))
    op.add_column("occurrences", sa.Column("ocr_engine_used", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("occurrences", "ocr_engine_used")
    op.drop_column("occurrences", "region_code")
    op.drop_column("occurrences", "vehicle_make_model")
    op.drop_column("occurrences", "vehicle_color")
    op.drop_column("occurrences", "vehicle_type")
