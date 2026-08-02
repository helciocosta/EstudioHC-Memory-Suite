import pytest
from httpx import AsyncClient

from src.main import app
from src.security import station_key_hash
from src.database import async_session_factory
from src.models.estacoes import Estacao
from sqlalchemy import select

MASTER = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_registrar_sem_master_401(client: AsyncClient):
    r = await client.post("/api/estacoes/registrar", json={"hostname": "estacao-a", "chave": "chave-a"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_registrar_master_cria_estacao_e_ping_ok(client: AsyncClient):
    r = await client.post("/api/estacoes/registrar", json={"hostname": "estacao-a", "chave": "chave-a"}, headers=MASTER)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # ping com a chave da estação funciona (identidade derivada do servidor)
    r2 = await client.post("/api/estacoes/ping", headers={"X-API-Key": "chave-a"})
    assert r2.status_code == 200
    async with async_session_factory() as db:
        res = await db.execute(select(Estacao).where(Estacao.hostname == "estacao-a"))
        row = res.scalar_one_or_none()
        assert row is not None
        assert row.chave_hash == station_key_hash("chave-a")


@pytest.mark.asyncio
async def test_chave_invalida_401(client: AsyncClient):
    r = await client.post("/api/estacoes/ping", headers={"X-API-Key": "nao-existe"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_estacao_nao_reve_ips_de_outras(client: AsyncClient):
    await client.post("/api/estacoes/registrar", json={"hostname": "estacao-a", "chave": "chave-a"}, headers=MASTER)
    await client.post("/api/estacoes/registrar", json={"hostname": "estacao-b", "chave": "chave-b"}, headers=MASTER)
    # estacao-b lista; master vê todas, estacao só vê a própria (sem IP de outra)
    r_estacao = await client.get("/api/estacoes", headers={"X-API-Key": "chave-b"})
    dados = r_estacao.json()
    assert all(x["hostname"] == "estacao-b" for x in dados)
