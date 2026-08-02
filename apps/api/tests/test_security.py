import pytest
from time import monotonic
from collections import deque
from fastapi import HTTPException, Request

from src.security import require_api_key, rate_limiter, _requests

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


def test_require_api_key_fail_closed_sem_chave_configurada(monkeypatch):
    monkeypatch.setattr("src.security.settings.API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        require_api_key("")
    assert exc.value.status_code == 401


def test_require_api_key_rejeita_chave_errada(monkeypatch):
    monkeypatch.setattr("src.security.settings.API_KEY", "segredo")
    with pytest.raises(HTTPException) as exc:
        require_api_key("errada")
    assert exc.value.status_code == 401


def test_require_api_key_aceita_chave_correta(monkeypatch):
    monkeypatch.setattr("src.security.settings.API_KEY", "segredo")
    assert require_api_key("segredo") is True


async def test_rate_limiter_ativo_sem_api_key(monkeypatch):
    monkeypatch.setattr("src.security.settings.API_KEY", "")
    monkeypatch.setattr("src.security.settings.RATE_LIMIT_PER_MIN", 2)
    _requests.clear()
    scope = {"type": "http", "method": "POST", "path": "/api/hermes", "headers": [], "client": ("10.0.0.9", 1234)}
    req = Request(scope)
    await rate_limiter(req)
    await rate_limiter(req)
    with pytest.raises(HTTPException) as exc:
        await rate_limiter(req)
    assert exc.value.status_code == 429


async def test_rate_limiter_evicta_ips_inativos(monkeypatch):
    monkeypatch.setattr("src.security.settings.API_KEY", "")
    monkeypatch.setattr("src.security.settings.RATE_LIMIT_PER_MIN", 2)
    _requests.clear()
    scope = {"type": "http", "method": "POST", "path": "/api/hermes", "headers": [], "client": ("10.0.0.10", 1234)}
    req = Request(scope)
    await rate_limiter(req)
    _requests["10.0.0.10"] = deque([monotonic() - 120])  # envelhece a janela
    await rate_limiter(req)  # evicta o antigo e registra novo -> sem estourar (não deve lançar 429)
    assert len(_requests["10.0.0.10"]) == 1
