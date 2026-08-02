### Task 5: Autenticacao via API key + rate limit em /api/hermes

**Files:**
- Create: `apps/api/src/security.py`
- Modify: `apps/api/src/config.py`, `apps/api/src/main.py`, `apps/api/src/routers/hermes.py`, `apps/api/tests/conftest.py`, `apps/mcp-memory/src/memory_server.py`
- Test: `apps/api/tests/test_security.py` (create)

**Interfaces:**
- Consumes: `settings.API_KEY`, `settings.RATE_LIMIT_PER_MIN` (novos).
- Produces: dependencia FastAPI `require_api_key` (Header `X-API-Key`) e `rate_limiter` (por IP). MCP manda a chave via env `MEMORY_API_KEY`.

- [ ] **Step 1: conftest.py define API_KEY de teste**

Em `apps/api/tests/conftest.py`, adicionar `os.environ["API_KEY"] = "test-key"` LOGO APOS a linha 6 (`os.environ["DATABASE_URL"] = ...`), ANTES de qualquer import de src.*. Sem isso, `require_api_key` fica desabilitado e o teste de 401 falha.

```python
_tmp = tempfile.mkdtemp(prefix="estudiohc_test_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["API_KEY"] = "test-key"
```

- [ ] **Step 2: Teste que falha**

```python
# apps/api/tests/test_security.py
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
```

- [ ] **Step 3: config.py — novos settings**

Adicionar ao final da classe Settings, ANTES de `settings = Settings()`:

```python
    # Auth
    API_KEY: str = ""  # vazio = auth desabilitado (dev)
    RATE_LIMIT_PER_MIN: int = 10
```

- [ ] **Step 4: security.py — dependencias**

```python
# apps/api/src/security.py
from time import monotonic
from collections import defaultdict, deque
from fastapi import Header, HTTPException, Request

from .config import settings


def require_api_key(x_api_key: str = Header(default="")):
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


_requests: dict[str, deque[float]] = defaultdict(deque)


async def rate_limiter(request: Request):
    if not settings.API_KEY:
        return
    ip = request.client.host if request.client else "unknown"
    now = monotonic()
    dq = _requests[ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= settings.RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    dq.append(now)
```

- [ ] **Step 5: Aplicar em main.py**

Em `apps/api/src/main.py`: adicionar import `from fastapi import Depends` (se ainda nao importado), `from .security import require_api_key, rate_limiter`, e SUBSTITUIR os include_router atuais por:

```python
from .routers import memory, agenda, notas, projetos, estacoes, status, hermes, tarefas

for _r in (memory, agenda, notas, projetos, estacoes, tarefas):
    app.include_router(_r.router, dependencies=[Depends(require_api_key)])
app.include_router(hermes.router, dependencies=[Depends(require_api_key), Depends(rate_limiter)])
app.include_router(status.router)  # status fica aberto (healthcheck)
```

IMPORTANTE: as rotas top-level backward-compat de main.py (POST /remember, GET /recall/{project}, GET /status/{project}) chamam funcoes do router memory direto. Elas NAO passam pelas dependencias de include_router (que so cobrem rotas registradas via router). Portanto, adicione `dependencies=[Depends(require_api_key)]` nesses 3 decorators top-level tambem, para que /remember e /recall fiquem protegidos (mesma protecao das rotas do router). NAO altere a logica dos handlers.

- [ ] **Step 6: MCP envia a chave — memory_server.py**

Em `apps/mcp-memory/src/memory_server.py`, adicionar `MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "")` junto das outras constantes, e ajustar `call_api`:

```python
MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "")

async def call_api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    if MEMORY_API_KEY:
        headers["X-API-Key"] = MEMORY_API_KEY
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.request(method, f"{MEMORY_API_URL}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 7: Rodar testes**

Run (a partir de `apps/api`): `..\..\.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: PASS — `test_security.py` usa `client` com `API_KEY="test-key"` (conftest). Sem header -> 401; com header -> 200. Tambem devem continuar passando os 2 testes de test_memory.py.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/security.py apps/api/src/config.py apps/api/src/main.py apps/api/src/routers/hermes.py apps/mcp-memory/src/memory_server.py apps/api/tests/test_security.py apps/api/tests/conftest.py
git commit -m "feat(api): optional API key auth + rate limit on /api/hermes"
```

---
