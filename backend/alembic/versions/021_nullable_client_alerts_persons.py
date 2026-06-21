"""monitored_plates.client_id e persons.client_id nullable (registros globais do admin)

Revision ID: 021_nullable_client
Revises: 020_alert_sent_face
Create Date: 2026-06-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "021_nullable_client"
down_revision = "020_alert_sent_face"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # client_id passa a aceitar NULL = registro "global" do super_admin (casa
    # contra todas as câmeras). SQLite não suporta ALTER COLUMN; no-op aceitável
    # lá (os testes criam as tabelas a partir dos modelos, já nullable).
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("monitored_plates", "client_id", existing_type=sa.Uuid(), nullable=True)
        op.alter_column("persons", "client_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("persons", "client_id", existing_type=sa.Uuid(), nullable=False)
        op.alter_column("monitored_plates", "client_id", existing_type=sa.Uuid(), nullable=False)
