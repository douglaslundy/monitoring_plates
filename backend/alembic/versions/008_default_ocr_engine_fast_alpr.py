"""migra motor OCR padrão de easyocr para fast_alpr (local ONNX)

Revision ID: 008
Revises: 007
Create Date: 2026-06-16

`engine_type` é VARCHAR(30), então não há alteração de schema — apenas dados:
configs/planos que apontavam para o EasyOCR (removido) passam a usar o motor
local fast-alpr.
"""

from alembic import op


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE ocr_engine_configs SET engine_type = 'fast_alpr' WHERE engine_type = 'easyocr'"
    )
    op.execute(
        "UPDATE plans SET ocr_engine = 'system_default' WHERE ocr_engine = 'easyocr'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE ocr_engine_configs SET engine_type = 'easyocr' WHERE engine_type = 'fast_alpr'"
    )
