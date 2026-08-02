import json
from httpx import AsyncClient

HEADERS = {"X-API-Key": "test-key"}


async def test_remember_returns_id(client: AsyncClient):
    resp = await client.post("/remember", headers=HEADERS, json={
        "agent_name": "opencode",
        "project": "opencode",
        "category": "context",
        "content": json.dumps({"s": "fato X", "r": None, "c": True}),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert isinstance(body["id"], int)
    assert body["id"] > 0


async def test_status_returns_readable_text(client: AsyncClient):
    await client.post("/remember", headers=HEADERS, json={
        "agent_name": "opencode",
        "project": "opencode",
        "category": "task_pending",
        "content": json.dumps({"s": "Tarefa pendente legivel", "r": None, "c": True}),
    })
    resp = await client.get("/status/opencode", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending"] == ["Tarefa pendente legivel"]
