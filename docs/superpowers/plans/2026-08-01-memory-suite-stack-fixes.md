# EstudioHC Memory Suite — Stack Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 critical/major bugs in the memory stack (FAISS ID mismatch, backup path, summarizer endpoint, get_status readability), add API authentication + rate limiting, and set up pytest + CI.

**Architecture:** Fix the API (`apps/api`) to be the source of truth for memory IDs and readable status text; fix the MCP client (`apps/mcp-memory`) to use those IDs for the FAISS index; fix operational scripts (`scripts/backup.sh`, `apps/mcp-memory/src/summarizer.py`); add an optional `X-API-Key` auth layer and an in-memory rate limiter for the cost-bearing `/api/hermes` endpoint; bootstrap pytest infra and a GitHub Actions workflow.

**Tech Stack:** Python 3.11+ (prod), Python 3.13 local, FastAPI, SQLAlchemy async/aiosqlite, MCP SDK, httpx, pytest, GitHub Actions.

## Global Constraints

- Repo root is `apps/api` (API) and `apps/mcp-memory` (MCP) within `EstudioHC-Memory-Suite`.
- Local clone path: `C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite`; production at `deploy@100.64.117.78:~/Apps/EstudioHC-Memory-Suite` (branch `master`, remote `https://github.com/helciocosta/EstudioHC-Memory-Suite.git`).
- Do NOT introduce new heavy runtime dependencies. chromadb stays OUT (Opção B paused).
- API is consumed by: `memory_server.py` (MCP, no API key today), dashboard (static, same-origin), stations via `MEMORY_API_URL=http://100.64.117.78:5050`.
- Auth MUST be optional via env (`API_KEY`); when unset, behavior is unchanged (dev-mode allow) so stations/status checks keep working until keys are distributed.
- Keep the SQLite schema unchanged; existing `data/estudiohc.db` must remain valid.
- Tests must not require network, llama.cpp, or sentence-transformers.

---

### Task 1: API `/remember` retorna `id` (raiz do bug FAISS)

**Files:**
- Modify: `apps/api/src/routers/memory.py:14-25`
- Test: `apps/api/tests/test_memory.py` (create)

**Interfaces:**
- Consumes: `AgentMemory` model, `MemoryEntry` schema, `get_db` (all exist).
- Produces: `save_memory()` returns `{"status": "success", "id": int}` — the persisted row id. `get_status()` returns readable text (summaries), not raw JSON.

- [ ] **Step 1: Escrever o teste que falha**

```python
# apps/api/tests/test_memory.py
import json
from httpx import AsyncClient


async def test_remember_returns_id(client: AsyncClient):
    resp = await client.post("/remember", json={
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
    await client.post("/remember", json={
        "agent_name": "opencode",
        "project": "opencode",
        "category": "task_pending",
        "content": json.dumps({"s": "Tarefa pendente legível", "r": None, "c": True}),
    })
    resp = await client.get("/status/opencode")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending"] == ["Tarefa pendente legível"]
```

- [ ] **Step 2: Rodar e confirmar falha**

Run (na pasta `apps/api`): `python -m pytest tests/test_memory.py -v`
Expected: FAIL — `body["id"]` ausente (KeyError) e `body["pending"]` contém o JSON bruto `{"s": "Tarefa pendente..."}`.

- [ ] **Step 3: Implementar o fix**

```python
# apps/api/src/routers/memory.py — save_memory
@router.post("/remember")
async def save_memory(entry: MemoryEntry, db: AsyncSession = Depends(get_db)):
    mem = AgentMemory(
        timestamp=datetime.now().isoformat(),
        agent_name=entry.agent_name,
        project=entry.project,
        category=entry.category,
        content=entry.content,
    )
    db.add(mem)
    await db.commit()
    return {"status": "success", "id": mem.id}
```

```python
# apps/api/src/routers/memory.py — get_status (extrair texto legível)
import json

def _readable(content: str) -> str:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and parsed.get("s"):
            return parsed["s"]
    except (json.JSONDecodeError, TypeError):
        pass
    return content

@router.get("/status/{project}")
async def get_status(project: str, db: AsyncSession = Depends(get_db)):
    result_pending = await db.execute(
        select(AgentMemory.content)
        .where(AgentMemory.project == project, AgentMemory.category == "task_pending")
        .order_by(AgentMemory.timestamp.desc())
        .limit(5)
    )
    result_completed = await db.execute(
        select(AgentMemory.content)
        .where(AgentMemory.project == project, AgentMemory.category == "task_completed")
        .order_by(AgentMemory.timestamp.desc())
        .limit(3)
    )
    return {
        "project": project,
        "pending": [_readable(r[0]) for r in result_pending.fetchall()],
        "completed": [_readable(r[0]) for r in result_completed.fetchall()],
    }
```

- [ ] **Step 4: Rodar e confirmar passagem**

Run: `python -m pytest tests/test_memory.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/routers/memory.py apps/api/tests/test_memory.py
git commit -m "fix(api): return memory id from /remember and readable status text"
```

---

### Task 2: MCP `memory_server.py` usa o `id` real no índice FAISS

**Files:**
- Modify: `apps/mcp-memory/src/memory_server.py:295-299` (`add_memory`) e `:452-482` (`consolidate`)
- Test: verificação manual no servidor (sem pytest — evita dep. de sentence-transformers)

**Interfaces:**
- Consumes: `/remember` agora retorna `{"status","id"}` (Task 1).
- Produces: `vec_store.add(text, memory_id)` com `memory_id = "{id}|{category}"` consistente com `search_memory`/`rebuild_vector_index`.

- [ ] **Step 1: `add_memory` — fallback seguro se API antiga não retornar id**

```python
# memory_server.py add_memory (substituir a linha memory_id)
result = await call_api("POST", "/remember", json=payload)
mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
memory_id = f"{mem_id}|{category}"
vec_text = summary or content
await asyncio.to_thread(vec_store.add, vec_text, memory_id)
```

- [ ] **Step 2: `consolidate` — também indexar no FAISS (hoje esquece!)**

```python
# memory_server.py consolidate (dentro do loop for item in to_persist)
try:
    result = await call_api("POST", "/remember", json=payload)
    mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    await asyncio.to_thread(vec_store.add, content, f"{mem_id}|{item['category']}")
    saved += 1
except Exception as e:
    print(f"[memory] consolidate save failed: {e}", file=sys.stderr)
```

- [ ] **Step 3: Commit**

```bash
git add apps/mcp-memory/src/memory_server.py
git commit -m "fix(mcp-memory): index FAISS with real memory id on add and consolidate"
```

---

### Task 3: Corrigir caminho do DB no `backup.sh`

**Files:**
- Modify: `scripts/backup.sh:14`

- [ ] **Step 1: Trocar o path errado**

```bash
# de
DB="$REPO_DIR/server/estudiohc_memory.db"
# para
DB="$REPO_DIR/data/estudiohc.db"
```

- [ ] **Step 2: Validar dry-run no servidor**

Run (via SSH em deploy@100.64.117.78):
```bash
cd ~/Apps/EstudioHC-Memory-Suite && bash scripts/backup.sh --dry-run
```
Expected: `[backup] OK memory-db → memory-db.<timestamp>` (não mais SKIP)

- [ ] **Step 3: Commit**

```bash
git add scripts/backup.sh
git commit -m "fix(scripts): correct DB path in backup.sh"
```

---

### Task 4: Corrigir endpoint do sumarizador (porta 11435 + modelo Qwen3-1.7B)

**Files:**
- Modify: `apps/mcp-memory/src/summarizer.py:6-7`

- [ ] **Step 1: Tornar configurável via env com default correto**

```python
import os

SUMMARIZER_API = os.getenv("SUMMARIZER_API", "http://localhost:11435/v1/chat/completions")
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "Qwen3-1.7B")
```

Substituir uso de `KOBOLD_API` por `SUMMARIZER_API` e `"model": "koboldcpp"` por `"model": SUMMARIZER_MODEL`.

- [ ] **Step 2: Validar no servidor**

Run:
```bash
curl -s http://localhost:11435/v1/models
```
Expected: servidor Qwen3 ativo (porta 11435). Se a porta não responder, documentar para ajuste no deploy (Task 8).

- [ ] **Step 3: Commit**

```bash
git add apps/mcp-memory/src/summarizer.py
git commit -m "fix(mcp-memory): point summarizer at Qwen3-1.7B on port 11435"
```

---

### Task 5: Autenticação via API key + rate limit em `/api/hermes`

**Files:**
- Create: `apps/api/src/security.py`
- Modify: `apps/api/src/config.py`, `apps/api/src/main.py`, `apps/api/src/routers/hermes.py`
- Test: `apps/api/tests/test_security.py` (create)

**Interfaces:**
- Consumes: `settings.API_KEY`, `settings.RATE_LIMIT_PER_MIN` (novos).
- Produces: dependência FastAPI `require_api_key` (Header `X-API-Key`) e `rate_limiter` (por IP). MCP manda a chave via env `MEMORY_API_KEY`.

- [ ] **Step 1: Teste que falha**

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

- [ ] **Step 2: `config.py` — novos settings**

```python
    # Auth
    API_KEY: str = ""  # vazio = auth desabilitado (dev)
    RATE_LIMIT_PER_MIN: int = 10
```

- [ ] **Step 3: `security.py` — dependências**

```python
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

- [ ] **Step 4: Aplicar em `main.py` e `hermes.py`**

```python
# main.py — importar
from .security import require_api_key, rate_limiter

# main.py — aplicar nas rotas de dados (memory, agenda, notas, projetos, estacoes, tarefas)
from .routers import memory, agenda, notas, projetos, estacoes, status, hermes, tarefas
from fastapi import Depends

for _r in (memory, agenda, notas, projetos, estacoes, tarefas):
    app.include_router(_r.router, dependencies=[Depends(require_api_key)])
app.include_router(hermes.router, dependencies=[Depends(require_api_key), Depends(rate_limiter)])
app.include_router(status.router)  # status fica aberto (healthcheck)
```

```python
# hermes.py — nada muda na lógica; o rate limit vem da dependência da rota
```

- [ ] **Step 5: MCP envia a chave — `memory_server.py`**

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

- [ ] **Step 6: Rodar testes**

Run: `python -m pytest tests/ -v`
Expected: PASS — `test_security.py` usa `client` com `API_KEY="test-key"` (conftest). Quando `API_KEY` setada, chamada sem header → 401; com header → 200. Rate limit: 11ª chamada rápida ao `/api/hermes` → 429.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/security.py apps/api/src/config.py apps/api/src/main.py apps/api/src/routers/hermes.py apps/mcp-memory/src/memory_server.py apps/api/tests/test_security.py
git commit -m "feat(api): optional API key auth + rate limit on /api/hermes"
```

---

### Task 6: Infra de testes (pytest + conftest) e CI

**Files:**
- Create: `apps/api/tests/conftest.py`, `.github/workflows/ci.yml`
- Modify: `apps/api/pyproject.toml` (dev deps + pytest config)

- [ ] **Step 1: conftest.py (banco temporário + client autenticado)**

```python
# apps/api/tests/conftest.py
import os
import tempfile

# Deve ser definido ANTES de importar o app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["API_KEY"] = "test-key"

import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.database import init_db


@pytest.fixture(scope="session", autouse=True)
async def _setup_db():
    await init_db()
    yield
    _tmp.close()
    if os.path.exists(_tmp.name):
        os.unlink(_tmp.name)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 2: pytest asyncio config no pyproject**

```toml
# apps/api/pyproject.toml — adicionar
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [master]
  pull_request:

jobs:
  test-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        working-directory: apps/api
        run: pip install -e ".[dev]"
      - name: Run tests
        working-directory: apps/api
        run: python -m pytest -v
```

- [ ] **Step 4: Rodar testes localmente**

Run (na pasta `apps/api`, com venv com deps instaladas):
```bash
pip install -e ".[dev]"
python -m pytest -v
```
Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/conftest.py apps/api/pyproject.toml .github/workflows/ci.yml
git commit -m "test(api): pytest harness + CI workflow"
```

---

### Task 7: Deploy e verificação em produção

- [ ] **Step 1: Push**

```bash
git push origin master
```

- [ ] **Step 2: Pull + restart no servidor**

```bash
ssh deploy@100.64.117.78 "cd ~/Apps/EstudioHC-Memory-Suite && git pull && sudo systemctl restart estudiohc-api.service"
```

- [ ] **Step 3: Verificar API + /remember retorna id**

```bash
curl -s -X POST http://localhost:5050/remember -H 'Content-Type: application/json' \
  -d '{"agent_name":"teste","project":"opencode","category":"context","content":"{\"s\":\"verificacao deploy\",\"r\":null,\"c\":true}"}'
```
Expected: `{"status":"success","id":<int>}`

- [ ] **Step 4: Verificar get_status legível**

```bash
curl -s http://localhost:5050/status/opencode
```
Expected: textos legíveis (sem `{"s":` bruto).

- [ ] **Step 5: Verificar backup.sh**

```bash
cd ~/Apps/EstudioHC-Memory-Suite && bash scripts/backup.sh --dry-run
```
Expected: `OK memory-db`.

- [ ] **Step 6: (Opcional) Ativar auth**

Criar `~/Apps/EstudioHC-Memory-Suite/.env` com `API_KEY=<chave>` e `MEMORY_API_KEY=<chave>` no comando do MCP no `opencode.json`. Reiniciar API e testar 401 sem chave.

- [ ] **Step 7: Registrar memória de conclusão**

Via MCP `add_memory` no opencode (projeto opencode, category task_completed), documentando a correção dos 4 bugs + auth + testes.

---

## Self-Review

- **Spec coverage:** bugs 1-4 (Tasks 1-4), segurança auth+rate-limit (Task 5), testes+CI (Task 6), deploy (Task 7). Todos os achados da revisão priorizados estão cobertos. Opção B (ChromaDB) permanece fora — planejada à parte.
- **Placeholder scan:** todos os passos têm código/commands concretos. Nenhum "TBD".
- **Type consistency:** `require_api_key` e `rate_limiter` usam `settings.API_KEY`/`RATE_LIMIT_PER_MIN` definidos no Task 5 Step 2; `call_api` envia `X-API-Key`; conftest define `API_KEY=test-key` casando com os testes. `_readable` é usado no get_status. Consistentes entre tasks.

