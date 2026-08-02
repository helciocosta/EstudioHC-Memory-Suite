import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete

from src.database import async_session_factory
from src.models.agenda import Agenda

HEADERS = {"X-API-Key": "test-key"}


@pytest_asyncio.fixture(autouse=True)
async def _limpa_agenda():
    async with async_session_factory() as session:
        await session.execute(delete(Agenda))
        await session.commit()


async def test_post_merge_preserva_evento_nao_enviado(client: AsyncClient):
    await client.post("/api/agenda", headers=HEADERS, json={"eventos": [
        {"id": "a1", "data": "2026-08-03", "hora": "09:00", "titulo": "Reuniao"},
    ]})
    await client.post("/api/agenda", headers=HEADERS, json={"eventos": [
        {"id": "a2", "data": "2026-08-04", "hora": "14:00", "titulo": "Deploy"},
    ]})
    resp = await client.get("/api/agenda", headers=HEADERS)
    ids = {e["id"] for e in resp.json()}
    assert ids == {"a1", "a2"}


async def test_post_upsert_atualiza_evento_existente(client: AsyncClient):
    await client.post("/api/agenda", headers=HEADERS, json={"eventos": [
        {"id": "a1", "data": "2026-08-03", "hora": "09:00", "titulo": "Antigo"},
    ]})
    await client.post("/api/agenda", headers=HEADERS, json={"eventos": [
        {"id": "a1", "data": "2026-08-03", "hora": "09:00", "titulo": "Novo"},
    ]})
    resp = await client.get("/api/agenda", headers=HEADERS)
    eventos = resp.json()
    assert len(eventos) == 1
    assert eventos[0]["titulo"] == "Novo"


async def test_delete_remove_unico_evento(client: AsyncClient):
    await client.post("/api/agenda", headers=HEADERS, json={"eventos": [
        {"id": "a1", "data": "2026-08-03", "hora": "09:00", "titulo": "Um"},
        {"id": "a2", "data": "2026-08-04", "hora": "14:00", "titulo": "Dois"},
    ]})
    resp = await client.delete("/api/agenda/a1", headers=HEADERS)
    assert resp.status_code == 200
    eventos = (await client.get("/api/agenda", headers=HEADERS)).json()
    ids = {e["id"] for e in eventos}
    assert ids == {"a2"}


async def test_delete_404_quando_id_nao_existe(client: AsyncClient):
    resp = await client.delete("/api/agenda/nao-existe", headers=HEADERS)
    assert resp.status_code == 404


async def _registrar(client, hostname, chave):
    await client.post("/api/estacoes/registrar", json={"hostname": hostname, "chave": chave}, headers=HEADERS)


async def test_estacao_so_ve_sua_propria_agenda(client: AsyncClient):
    await _registrar(client, "estacao-x", "chave-x")
    await _registrar(client, "estacao-y", "chave-y")
    # estacao-x grava evento
    r = await client.post(
        "/api/agenda",
        json={"eventos": [{"id": "e1", "data": "2026-08-02", "hora": "09:00", "titulo": "de x", "estacao": "central"}]},
        headers={"X-API-Key": "chave-x"},
    )
    assert r.status_code == 200
    # estacao-y não vê o evento de x
    r2 = await client.get("/api/agenda", headers={"X-API-Key": "chave-y"})
    assert r2.status_code == 200
    assert all(e["estacao"] == "estacao-y" for e in r2.json())
    # estacao-x vê o próprio (estacao gravada = identidade, não payload)
    r3 = await client.get("/api/agenda", headers={"X-API-Key": "chave-x"})
    assert len(r3.json()) == 1
    assert r3.json()[0]["estacao"] == "estacao-x"
    assert r3.json()[0]["titulo"] == "de x"


async def test_estacao_nao_sobrescreve_evento_de_outra(client: AsyncClient):
    await _registrar(client, "estacao-x", "chave-x")
    await _registrar(client, "estacao-y", "chave-y")
    # x cria e1
    await client.post("/api/agenda", json={"eventos": [{"id": "e1", "data": "2026-08-02", "hora": "09:00", "titulo": "original"}]}, headers={"X-API-Key": "chave-x"})
    # y tenta sobrescrever e1 (que pertence a x) -> 403
    r = await client.post("/api/agenda", json={"eventos": [{"id": "e1", "data": "2026-08-02", "hora": "10:00", "titulo": "hack"}]}, headers={"X-API-Key": "chave-y"})
    assert r.status_code == 403
    r2 = await client.get("/api/agenda", headers={"X-API-Key": "chave-x"})
    itens = r2.json()
    assert len(itens) == 1
    assert itens[0]["titulo"] == "original"  # não foi sobrescrito


async def test_estacao_nao_delete_evento_de_outra(client: AsyncClient):
    await _registrar(client, "estacao-x", "chave-x")
    await _registrar(client, "estacao-y", "chave-y")
    await client.post("/api/agenda", json={"eventos": [{"id": "e1", "data": "2026-08-02", "hora": "09:00", "titulo": "original"}]}, headers={"X-API-Key": "chave-x"})
    r = await client.delete("/api/agenda/e1", headers={"X-API-Key": "chave-y"})
    assert r.status_code == 404
    r2 = await client.get("/api/agenda", headers={"X-API-Key": "chave-x"})
    assert len(r2.json()) == 1
