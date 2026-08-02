import pytest
from httpx import AsyncClient
from sqlalchemy import inspect

from src.database import engine


@pytest.mark.asyncio
async def test_estacao_tem_chave_hash(client: AsyncClient):
    async with engine.connect() as conn:
        cols = {c["name"] for c in await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("estacoes"))}
    assert "chave_hash" in cols


@pytest.mark.asyncio
async def test_agent_memory_tem_estacao(client: AsyncClient):
    async with engine.connect() as conn:
        cols = {c["name"] for c in await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("agent_memory"))}
    assert "estacao" in cols
