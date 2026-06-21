"""alert_sent supports face alerts (person_id, face_detection_id) and nullable plate refs

Revision ID: 020_alert_sent_face
Revises: 019_face_engine_config
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "020_alert_sent_face"
down_revision = "019_face_engine_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts_sent", sa.Column("person_id", sa.Uuid(), nullable=True))
    op.add_column("alerts_sent", sa.Column("face_detection_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_alerts_sent_person_id", "alerts_sent", "persons", ["person_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_alerts_sent_face_detection_id",
        "alerts_sent",
        "face_detections",
        ["face_detection_id"],
        ["id"],
    )
    # occurrence_id / monitored_plate_id passam a aceitar NULL (alertas de face).
    # SQLite não suporta ALTER COLUMN; o alter é no-op aceitável lá.
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("alerts_sent", "occurrence_id", existing_type=sa.Uuid(), nullable=True)
        op.alter_column("alerts_sent", "monitored_plate_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("alerts_sent", "monitored_plate_id", existing_type=sa.Uuid(), nullable=False)
        op.alter_column("alerts_sent", "occurrence_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint("fk_alerts_sent_face_detection_id", "alerts_sent", type_="foreignkey")
    op.drop_constraint("fk_alerts_sent_person_id", "alerts_sent", type_="foreignkey")
    op.drop_column("alerts_sent", "face_detection_id")
    op.drop_column("alerts_sent", "person_id")
