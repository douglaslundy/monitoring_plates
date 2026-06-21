"""persons and person_faces tables

Revision ID: 017_persons
Revises: 016_face_toggles
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "017_persons"
down_revision = "016_face_toggles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("cpf", sa.String(length=14), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_path", sa.String(length=500), nullable=True),
        sa.Column("alert_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("alert_email", sa.String(length=255), nullable=True),
        sa.Column("alert_whatsapp", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "person_faces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("engine_type", sa.String(length=30), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("person_faces")
    op.drop_table("persons")
