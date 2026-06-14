"""vehicle events

Revision ID: 005
Revises: 004
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicle_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("camera_id", sa.Uuid(as_uuid=True), sa.ForeignKey("cameras.id"), nullable=False),
        sa.Column("occurrence_id", sa.Uuid(as_uuid=True), sa.ForeignKey("occurrences.id"), nullable=True),
        sa.Column("vehicle_type", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox_x", sa.Integer(), nullable=False),
        sa.Column("bbox_y", sa.Integer(), nullable=False),
        sa.Column("bbox_w", sa.Integer(), nullable=False),
        sa.Column("bbox_h", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(op.f("ix_vehicle_events_camera_id"), "vehicle_events", ["camera_id"], unique=False)
    op.create_index(op.f("ix_vehicle_events_detected_at"), "vehicle_events", ["detected_at"], unique=False)
    op.create_index(op.f("ix_vehicle_events_occurrence_id"), "vehicle_events", ["occurrence_id"], unique=False)
    op.create_index(op.f("ix_vehicle_events_vehicle_type"), "vehicle_events", ["vehicle_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vehicle_events_vehicle_type"), table_name="vehicle_events")
    op.drop_index(op.f("ix_vehicle_events_occurrence_id"), table_name="vehicle_events")
    op.drop_index(op.f("ix_vehicle_events_detected_at"), table_name="vehicle_events")
    op.drop_index(op.f("ix_vehicle_events_camera_id"), table_name="vehicle_events")
    op.drop_table("vehicle_events")
