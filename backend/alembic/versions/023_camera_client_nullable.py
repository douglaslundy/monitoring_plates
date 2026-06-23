"""camera client_id nullable for super_admin cameras

Revision ID: 023_camera_client_nullable
Revises: 022_face_camera_alert_config
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa

revision = "023_camera_client_nullable"
down_revision = "022_face_camera_alert_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("cameras", "client_id", existing_type=sa.Uuid(as_uuid=True), nullable=True)


def downgrade() -> None:
    # Rows with NULL client_id must be cleaned up before downgrading
    op.execute("DELETE FROM cameras WHERE client_id IS NULL")
    op.alter_column("cameras", "client_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)
