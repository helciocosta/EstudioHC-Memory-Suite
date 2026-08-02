import pytest
from httpx import AsyncClient

from src.main import app

MASTER = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_hermes_estacao_403(client: AsyncClient):
    await client.post("/api/estacoes/registrar", json={"hostname": "est-hx", "chave": "chave-hx"}, headers=MASTER)
    r = await client.post("/api/hermes", json={"mensagem": "oi"}, headers={"X-API-Key": "chave-hx"})
    assert r.status_code == 403
