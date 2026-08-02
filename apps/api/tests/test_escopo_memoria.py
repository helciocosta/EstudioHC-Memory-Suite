import pytest
from httpx import AsyncClient

from src.main import app

MASTER = {"X-API-Key": "test-key"}


async def _registrar(client, hostname, chave):
    await client.post("/api/estacoes/registrar", json={"hostname": hostname, "chave": chave}, headers=MASTER)


@pytest.mark.asyncio
async def test_recall_escopo_por_estacao(client: AsyncClient):
    await _registrar(client, "est-mx", "chave-mx")
    await _registrar(client, "est-my", "chave-my")
    await client.post("/remember", json={"agent_name": "opencode", "project": "proj1", "content": "memoria de x"}, headers={"X-API-Key": "chave-mx"})
    r = await client.get("/recall/proj1", headers={"X-API-Key": "chave-my"})
    assert r.status_code == 200
    assert r.json() == []
    r2 = await client.get("/recall/proj1", headers={"X-API-Key": "chave-mx"})
    assert len(r2.json()) == 1
    assert r2.json()[0]["estacao"] == "est-mx"


@pytest.mark.asyncio
async def test_recall_limit_com_teto(client: AsyncClient):
    await _registrar(client, "est-mx", "chave-mx")
    for i in range(3):
        await client.post("/remember", json={"agent_name": "a", "project": "proj1", "content": f"m{i}"}, headers={"X-API-Key": "chave-mx"})
    r = await client.get("/recall/proj1?limit=2", headers={"X-API-Key": "chave-mx"})
    assert len(r.json()) == 2
    r_inv = await client.get("/recall/proj1?limit=-1", headers={"X-API-Key": "chave-mx"})
    assert r_inv.status_code == 422


@pytest.mark.asyncio
async def test_nota_grava_estacao_da_identidade(client: AsyncClient):
    await _registrar(client, "est-mx", "chave-mx")
    await client.post("/api/nota", json={"texto": "nota de x", "estacao": "central"}, headers={"X-API-Key": "chave-mx"})
    r = await client.get("/api/diarios", headers={"X-API-Key": "chave-mx"})
    assert r.status_code == 200
    # diários de x contêm o dia de hoje
    dias = [d["data"] for d in r.json()]
    assert any(d >= "2026-01-01" for d in dias)
