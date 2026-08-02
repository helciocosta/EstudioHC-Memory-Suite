"""adiciona identidade por estação (chave_hash + agent_memory.estacao)

Revision ID: 002
Revises: 001
Create Date: 2026-08-02
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("estacoes", sa.Column("chave_hash", sa.String(length=64), nullable=True))
    op.add_column("agent_memory", sa.Column("estacao", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_memory", "estacao")
    op.drop_column("estacoes", "chave_hash")
