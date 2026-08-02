import pytest
from httpx import AsyncClient

MASTER = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_rotacionar_estacao_gera_nova_chave(client: AsyncClient):
    await client.post("/api/estacoes/registrar",
                      json={"hostname": "est-rot", "chave": "chave-rot-old"},
                      headers=MASTER)
    r = await client.post("/api/estacoes/rotacionar",
                          headers={"X-API-Key": "chave-rot-old"})
    assert r.status_code == 200
    nova = r.json()["chave"]
    assert nova != "chave-rot-old"
    r_old = await client.post("/api/estacoes/ping", headers={"X-API-Key": "chave-rot-old"})
    assert r_old.status_code == 401
    r_new = await client.post("/api/estacoes/ping", headers={"X-API-Key": nova})
    assert r_new.status_code == 200


@pytest.mark.asyncio
async def test_rotacionar_requer_chave_valida(client: AsyncClient):
    r = await client.post("/api/estacoes/rotacionar",
                          headers={"X-API-Key": "chave-nao-existe"})
    assert r.status_code == 401