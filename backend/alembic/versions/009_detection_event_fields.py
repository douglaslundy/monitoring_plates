"""add detection category/track_id to vehicle_events

Revision ID: 009
Revises: 008
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("vehicle_events")}
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("vehicle_events")}

    if "category" not in cols:
        op.add_column(
            "vehicle_events",
            sa.Column("category", sa.String(length=10), nullable=False, server_default="vehicle"),
        )
    if "ix_vehicle_events_category" not in indexes:
        op.create_index("ix_vehicle_events_category", "vehicle_events", ["category"])

    if "track_id" not in cols:
        op.add_column("vehicle_events", sa.Column("track_id", sa.String(length=40), nullable=True))
    if "ix_vehicle_events_track_id" not in indexes:
        op.create_index("ix_vehicle_events_track_id", "vehicle_events", ["track_id"])


def downgrade() -> None:
    op.drop_index("ix_vehicle_events_track_id", table_name="vehicle_events")
    op.drop_index("ix_vehicle_events_category", table_name="vehicle_events")
    op.drop_column("vehicle_events", "track_id")
    op.drop_column("vehicle_events", "category")
