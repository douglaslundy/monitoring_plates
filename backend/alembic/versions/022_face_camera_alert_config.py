"""face_camera_alert_configs: alertas de face por câmera (unknown + schedule + cooldown)

Revision ID: 022_face_camera_alert_config
Revises: 021_nullable_client
Create Date: 2026-06-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "022_face_camera_alert_config"
down_revision = "021_nullable_client"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "face_camera_alert_configs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("camera_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("unknown_face_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unknown_face_email", sa.String(255), nullable=True),
        sa.Column("unknown_face_whatsapp", sa.String(30), nullable=True),
        sa.Column("schedule_start_time", sa.String(8), nullable=True),
        sa.Column("schedule_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("schedule_days_of_week", sa.String(50), nullable=True),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("camera_id"),
    )
    op.create_index("ix_face_camera_alert_configs_camera_id", "face_camera_alert_configs", ["camera_id"])


def downgrade() -> None:
    op.drop_index("ix_face_camera_alert_configs_camera_id", table_name="face_camera_alert_configs")
    op.drop_table("face_camera_alert_configs")
