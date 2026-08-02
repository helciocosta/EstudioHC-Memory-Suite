import pytest
from httpx import AsyncClient

from src.main import app

MASTER = {"X-API-Key": "test-key"}


async def _registrar(client, hostname, chave):
    await client.post("/api/estacoes/registrar", json={"hostname": hostname, "chave": chave}, headers=MASTER)


async def _sync_projeto(client, chave, nome):
    await client.post(
        "/api/projetos/sync",
        json={"projetos": [{"nome": nome, "local_caminho": "/tmp/proj", "estacao": "central"}]},
        headers={"X-API-Key": chave},
    )


@pytest.mark.asyncio
async def test_tarefa_filha_projeto_da_estacao(client: AsyncClient):
    await _registrar(client, "est-tx", "chave-tx")
    await _registrar(client, "est-ty", "chave-ty")
    await _sync_projeto(client, "chave-tx", "projeto-tx")
    await _sync_projeto(client, "chave-ty", "projeto-ty")
    # obtém o id real do projeto-tx (DB session-scoped é compartilhado; ids não são determinísticos)
    rp = await client.get("/api/projetos", headers={"X-API-Key": "chave-tx"})
    pid = next(p["id"] for p in rp.json() if p["nome"] == "projeto-tx")
    # x cria tarefa no projeto-x
    r = await client.post("/api/tarefas", json={"projeto_id": pid, "titulo": "tarefa de tx"}, headers={"X-API-Key": "chave-tx"})
    assert r.status_code == 200
    # y não vê a tarefa de x
    r2 = await client.get("/api/tarefas", headers={"X-API-Key": "chave-ty"})
    assert all(t["titulo"] != "tarefa de tx" for t in r2.json())
    # x vê a própria
    r3 = await client.get("/api/tarefas", headers={"X-API-Key": "chave-tx"})
    assert any(t["titulo"] == "tarefa de tx" for t in r3.json())


@pytest.mark.asyncio
async def test_relatorio_get_retorna_405(client: AsyncClient):
    r = await client.get("/api/projetos/relatorio?nome=proj", headers=MASTER)
    assert r.status_code == 405


@pytest.mark.asyncio
async def test_relatorio_post_sem_master_403(client: AsyncClient):
    await _registrar(client, "est-tx", "chave-tx")
    r = await client.post("/api/projetos/gerar-relatorio", json={"nome": "proj"}, headers={"X-API-Key": "chave-tx"})
    assert r.status_code == 403
