"""add camera dual lens fields

Revision ID: 004_camera_dual_lens_fields
Revises: 003_occurrence_vehicle_fields
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa


revision = "004_camera_dual_lens_fields"
down_revision = "003_occurrence_vehicle_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("dual_lens", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("cameras", sa.Column("lens_side", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "lens_side")
    op.drop_column("cameras", "dual_lens")
