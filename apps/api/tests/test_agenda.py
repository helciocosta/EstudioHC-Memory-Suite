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
