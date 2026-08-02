"""create initial tables

Revision ID: 001
Revises:
Create Date: 2026-06-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.String(length=32), nullable=True),
        sa.Column("agent_name", sa.String(length=128), nullable=True),
        sa.Column("project", sa.String(length=256), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agenda",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("data", sa.String(length=16), nullable=True),
        sa.Column("hora", sa.String(length=8), nullable=True),
        sa.Column("titulo", sa.String(length=256), nullable=True),
        sa.Column("estacao", sa.String(length=128), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "estacoes",
        sa.Column("hostname", sa.String(length=128), nullable=False),
        sa.Column("ip_tailscale", sa.String(length=64), nullable=True),
        sa.Column("ultimo_ping", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("hostname"),
    )
    op.create_table(
        "notas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("estacao", sa.String(length=128), nullable=True),
        sa.Column("texto", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "projetos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.String(length=256), nullable=True),
        sa.Column("local_caminho", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("tags", sa.String(length=512), nullable=True),
        sa.Column("readme_preview", sa.Text(), nullable=True),
        sa.Column("estacao", sa.String(length=128), nullable=True),
        sa.Column("ultima_atualizacao", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "resumos_diarios",
        sa.Column("data", sa.String(length=16), nullable=False),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("agente", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("data"),
    )
    op.create_table(
        "tarefas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("projeto_id", sa.Integer(), nullable=True),
        sa.Column("titulo", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("prioridade", sa.String(length=16), nullable=True),
        sa.Column("data_limite", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["projeto_id"], ["projetos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("tarefas")
    op.drop_table("resumos_diarios")
    op.drop_table("projetos")
    op.drop_table("notas")
    op.drop_table("agenda")
    op.drop_table("estacoes")
    op.drop_table("agent_memory")