from httpx import AsyncClient


async def test_api_key_required_when_configured(client: AsyncClient):
    resp = await client.post("/remember", json={
        "agent_name": "opencode", "project": "x",
        "category": "context", "content": "sem chave",
    })
    assert resp.status_code == 401


async def test_api_key_accepted(client: AsyncClient):
    resp = await client.post(
        "/remember",
        json={"agent_name": "opencode", "project": "x",
              "category": "context", "content": "com chave"},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 200
