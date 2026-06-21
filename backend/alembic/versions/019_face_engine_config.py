"""face_engine_configs table

Revision ID: 019_face_engine_config
Revises: 018_face_detections
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "019_face_engine_config"
down_revision = "018_face_detections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "face_engine_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("engine_type", sa.String(length=30), nullable=False),
        sa.Column("mode", sa.String(length=15), nullable=False, server_default="cloud"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("api_token", sa.String(length=255), nullable=True),
        sa.Column("api_secret", sa.String(length=255), nullable=True),
        sa.Column("api_url", sa.String(length=500), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False, server_default="0.80"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("face_engine_configs")
