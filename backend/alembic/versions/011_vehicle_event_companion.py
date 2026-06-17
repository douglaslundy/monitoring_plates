"""add companion (rider) fields to vehicle_events

Permite gravar UMA detecção para o conjunto moto+pessoa (piloto), mantendo a
contagem dos dois nas estatísticas: o evento da moto guarda a pessoa como
companion_category/companion_type.

Revision ID: 011
Revises: 010
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("vehicle_events")}

    if "companion_category" not in cols:
        op.add_column(
            "vehicle_events",
            sa.Column("companion_category", sa.String(length=10), nullable=True),
        )
    if "companion_type" not in cols:
        op.add_column(
            "vehicle_events",
            sa.Column("companion_type", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("vehicle_events", "companion_type")
    op.drop_column("vehicle_events", "companion_category")
