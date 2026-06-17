"""client plan_activated_at

Data de ativação do plano atual do cliente. Preenchida no cadastro e
atualizada quando o plano do cliente muda. Para os clientes existentes,
inicializa com a data de cadastro (created_at).

Revision ID: 010
Revises: 009
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("plan_activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Inicializa os clientes existentes com a data de cadastro.
    op.execute(
        "UPDATE clients SET plan_activated_at = created_at WHERE plan_activated_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("clients", "plan_activated_at")
