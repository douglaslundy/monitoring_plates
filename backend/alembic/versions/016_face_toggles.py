"""face toggles on plan and camera

Revision ID: 016_face_toggles
Revises: 015_alerts_sent_message
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "016_face_toggles"
down_revision = "015_alerts_sent_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("ocr_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("plans", sa.Column("face_recognition_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("plans", sa.Column("face_engine", sa.String(length=30), nullable=False, server_default="system_default"))
    op.add_column("cameras", sa.Column("enable_ocr", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("cameras", sa.Column("enable_face", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    for col in ("enable_face", "enable_ocr"):
        op.drop_column("cameras", col)
    for col in ("face_engine", "face_recognition_enabled", "ocr_enabled"):
        op.drop_column("plans", col)
