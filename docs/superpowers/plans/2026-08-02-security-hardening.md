# Endurecimento de Segurança do EstudioHC Memory Suite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevar a segurança do stack de 3/10 para fail-closed: auth obrigatória, identidade por estação, escopo de dados por owner, XSS do dashboard eliminado e endpoints sensíveis (hermes, relatório, status_md) restritos a master.

**Architecture:** Seis frentes interdependentes: (1) auth fail-closed + comparação constante + rate limiter sempre ativo; (2) identidade por estação via auto-provisionamento (chave gerada na estação, `chave_hash` sha256 no servidor, endpoint `registrar` master-only); (3) escopo de dados por owner nas rotas (agenda, memória, notas, tarefas, projetos); (4) hardening do `/api/hermes` (master-only, env filtrado) + rate limit em projetos + relatório POST-only; (5) XSS do dashboard + envio seguro de chave; (6) endurecimento MCP/ChromaDB/scripts e itens rápidos (CORS, docs, .gitignore, Dockerfile).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async + aiosqlite, Alembic, httpx, Pydantic v2, pytest-asyncio, Shell (setup-machine.sh), vanilla JS (dashboard).

## Global Constraints

- **Workflow de push:** O clone Windows (`C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite`) NÃO tem push. Commits locais são pushados SEMPRE via servidor Contabo `deploy@100.64.117.78` em `~/Apps/EstudioHC-Memory-Suite`. Após push, reconciliar: `git fetch origin && git reset --hard origin/master`.
- **CRLF:** NUNCA `Set-Content` do PowerShell. Para arquivos que irão ao servidor, gerar LF puro via `cmd /c "git -C <repo> show HEAD:<path> > %TEMP%\opencode\lf2\<file>"` (ou usar os arquivos de trabalho com `git diff --stat`), transferir via scp → `/tmp/` → `cp`, e verificar `grep -c $'\r'` = 0.
- **Testes:** workdir `apps\api`, comando `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`. Suíte atual: 8 passed (test_memory 2, test_security 2, test_agenda 4).
- **`curl.exe`** (não `curl`) no PowerShell. Escrever JSON via `[System.IO.File]::WriteAllText` para evitar encoding.
- **Memória:** registrar mudanças via `POST http://100.64.117.78:5050/remember` ao final do deploy.
- **Convenção de commits:** `feat:`, `test:`, `docs:`, `fix:` em português, commits frequentes por task.

---

### Task 1: Frente 1 — Auth fail-closed + comparação constante + rate limiter sempre ativo

**Files:**
- Modify: `apps/api/src/security.py`
- Modify: `apps/api/src/main.py`
- Modify: `apps/api/src/routers/status.py`
- Test: `apps/api/tests/test_security.py`

**Interfaces:**
- Consumes: `settings.API_KEY`, `settings.DEBUG`, `settings.RATE_LIMIT_PER_MIN` (config.py), `request.client.host`.
- Produces: `require_api_key` (falha-closed: sem `API_KEY` configurada → sempre 401; comparação `hmac.compare_digest`); `rate_limiter` (ativo mesmo sem `API_KEY`, evicts IPs inativos). Usado por `main.py` e `status.py`.

- [ ] **Step 1: Escrever testes que falham**

Adicionar a `apps/api/tests/test_security.py` (manter os 2 testes existentes):

```python
import pytest
from time import monotonic
from collections import deque
from fastapi import HTTPException, Request

from src.security import require_api_key, rate_limiter, _requests


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
    from fastapi import Request
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
    from fastapi import Request
    scope = {"type": "http", "method": "POST", "path": "/api/hermes", "headers": [], "client": ("10.0.0.10", 1234)}
    req = Request(scope)
    await rate_limiter(req)
    _requests["10.0.0.10"] = deque([monotonic() - 120])  # envelhece a janela
    await rate_limiter(req)  # evicta o antigo e registra novo -> sem estourar (não deve lançar 429)
    assert len(_requests["10.0.0.10"]) == 1
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_security.py -q`
Expected: os 3 primeiros testes novos falham (fail-open atual aceita sem chave), os 2 últimos falham (rate limiter off sem chave / sem eviction).

- [ ] **Step 3: Implementar `security.py`**

Reescrever `apps/api/src/security.py`:

```python
import hashlib
import hmac
from time import monotonic
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from .config import settings

_SALT = "estudiohc:"


def station_key_hash(chave: str) -> str:
    """Hash de chave de estação — sha256 com salt fixo. Suficiente pois a chave é
    um token aleatório de 256 bits (128 bits de entropia), não uma senha humana."""
    return hashlib.sha256((_SALT + chave).encode("utf-8")).hexdigest()


def require_api_key(x_api_key: str = Header(default="")):
    if not settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


_requests: dict[str, deque[float]] = defaultdict(deque)


async def rate_limiter(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = monotonic()
    dq = _requests[ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= settings.RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    dq.append(now)
```

- [ ] **Step 4: Implementar `main.py` fail-closed + docs/CORS**

Editar `apps/api/src/main.py`:

```python
app = FastAPI(
    title=settings.APP_NAME,
    description=description,
    version="3.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    contact={
        "name": "Helcio O. Costa",
        "url": "https://github.com/helciocosta",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    if not settings.API_KEY and not settings.DEBUG:
        raise RuntimeError("API_KEY é obrigatória em produção (defina API_KEY ou DEBUG=True)")
    await init_db()
```

- [ ] **Step 5: Proteger `status_md`**

Editar `apps/api/src/routers/status.py`:

```python
from fastapi import APIRouter, Depends
from ..security import require_api_key


@router.get("/status_md", dependencies=[Depends(require_api_key)])
async def get_status_md():
    # ... corpo atual inalterado ...
```

- [ ] **Step 6: Rodar suíte completa**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 13 passed (8 antigos + 5 novos). Nenhum teste quebra: conftest define `API_KEY=test-key` e os testes antigos enviam `X-API-Key: test-key`.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/security.py apps/api/src/main.py apps/api/src/routers/status.py apps/api/tests/test_security.py
git commit -m "feat: auth fail-closed + hmac.compare_digest + rate limiter sempre ativo"
```

---

### Task 2: Frente 2 — Modelo: colunas `chave_hash` e `estacao` + migration 002 + schema

**Files:**
- Modify: `apps/api/src/models/estacoes.py`
- Modify: `apps/api/src/models/agent_memory.py`
- Create: `apps/api/alembic/versions/002_identidade_estacao.py`
- Modify: `apps/api/src/schemas/__init__.py`
- Test: `apps/api/tests/test_modelos.py`

**Interfaces:**
- Consumes: `Base`, `Column`, `String` (SQLAlchemy).
- Produces: `Estacao.chave_hash String(64)`; `AgentMemory.estacao String(128)`; schema `EstacaoRegistro{hostname: str, chave: str}`. Migration `002` (revision="002", down_revision="001") adiciona as duas colunas atomicamente.

- [ ] **Step 1: Escrever teste que falha**

Criar `apps/api/tests/test_modelos.py`:

```python
import pytest
from httpx import AsyncClient
from sqlalchemy import inspect

from src.database import engine


@pytest.mark.asyncio
async def test_estacao_tem_chave_hash(client: AsyncClient):
    async with engine.connect() as conn:
        cols = {c["name"] for c in await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("estacoes"))}
    assert "chave_hash" in cols


@pytest.mark.asyncio
async def test_agent_memory_tem_estacao(client: AsyncClient):
    async with engine.connect() as conn:
        cols = {c["name"] for c in await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("agent_memory"))}
    assert "estacao" in cols
```

Nota: os testes usam a fixture `client` (não usam o client em si) apenas para disparar `_setup_db`/`init_db` no conftest — sem ela, o arquivo rodado isolado falharia com "no such table".

- [ ] **Step 2: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_modelos.py -q`
Expected: FAIL (colunas ainda não existem — `init_db` no conftest cria tabelas a partir dos modelos atuais).

- [ ] **Step 3: Adicionar colunas aos modelos**

`apps/api/src/models/estacoes.py`:

```python
class Estacao(Base):
    __tablename__ = "estacoes"

    hostname = Column(String(128), primary_key=True)
    ip_tailscale = Column(String(64), default="desconhecido")
    ultimo_ping = Column(String(32))
    status = Column(String(32), default="offline")
    chave_hash = Column(String(64), default=None, nullable=True)
```

`apps/api/src/models/agent_memory.py`:

```python
class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(32))
    agent_name = Column(String(128))
    project = Column(String(256))
    category = Column(String(64), default="task")
    content = Column(Text)
    estacao = Column(String(128), default=None, nullable=True)
```

- [ ] **Step 4: Criar migration 002**

Criar `apps/api/alembic/versions/002_identidade_estacao.py`:

```python
"""adiciona identidade por estação (chave_hash + agent_memory.estacao)

Revision ID: 002
Revises: 001
Create Date: 2026-08-02
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("estacoes", sa.Column("chave_hash", sa.String(length=64), nullable=True))
    op.add_column("agent_memory", sa.Column("estacao", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_memory", "estacao")
    op.drop_column("estacoes", "chave_hash")
```

- [ ] **Step 5: Adicionar schema `EstacaoRegistro`**

Em `apps/api/src/schemas/__init__.py`, adicionar:

```python
class EstacaoRegistro(BaseModel):
    hostname: str
    chave: str
```

- [ ] **Step 6: Rodar testes**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_modelos.py -q`
Expected: 2 passed. Depois suíte completa `pytest tests/ -q` → 15 passed.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/models/estacoes.py apps/api/src/models/agent_memory.py apps/api/alembic/versions/002_identidade_estacao.py apps/api/src/schemas/__init__.py apps/api/tests/test_modelos.py
git commit -m "feat: colunas chave_hash (estacoes) e estacao (agent_memory) + migration 002"
```

---

### Task 3: Frente 2 — Identidade `get_current_estacao` + endpoint `registrar` + ping com identidade

**Files:**
- Modify: `apps/api/src/security.py`
- Modify: `apps/api/src/routers/estacoes.py`
- Modify: `apps/api/src/main.py`
- Test: `apps/api/tests/test_identidade.py`

**Interfaces:**
- Consumes: `Estacao` model com `chave_hash`, `station_key_hash(chave)` (Task 1), `get_db`, `EstacaoRegistro`, `rate_limiter`.
- Produces: `Identity(estacao: str, scope: str)` (dataclass); `get_current_estacao(x_api_key, db) -> Identity` (master se bate `API_KEY`, estação se hash bate `chave_hash`, senão 401); `require_master(identity) -> Identity` (403 se scope != master). Endpoint `POST /api/estacoes/registrar` (master-only + rate-limited). `ping` usa identidade (hostname/ip ignorados do payload; `ip_tailscale = request.client.host`). `GET /api/estacoes` filtra IPs para scope=estacao.

- [ ] **Step 1: Escrever testes que falham**

Criar `apps/api/tests/test_identidade.py`:

```python
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
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_identidade.py -q`
Expected: FAIL (registrar 404/405, ping ignora identidade).

- [ ] **Step 3: Implementar `Identity`, `get_current_estacao`, `require_master`**

Em `apps/api/src/security.py`, adicionar:

```python
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models.estacoes import Estacao


@dataclass(frozen=True)
class Identity:
    estacao: str
    scope: str  # "master" | "estacao"


async def get_current_estacao(
    x_api_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> Identity:
    if settings.API_KEY and hmac.compare_digest(x_api_key, settings.API_KEY):
        return Identity(estacao="central", scope="master")
    if x_api_key:
        result = await db.execute(
            select(Estacao).where(Estacao.chave_hash == station_key_hash(x_api_key))
        )
        estacao = result.scalar_one_or_none()
        if estacao:
            return Identity(estacao=estacao.hostname, scope="estacao")
    raise HTTPException(status_code=401, detail="Invalid API key")


async def require_master(identity: Identity = Depends(get_current_estacao)) -> Identity:
    if identity.scope != "master":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return identity
```

- [ ] **Step 4: Implementar rota `registrar` + ping/GET com identidade**

Reescrever `apps/api/src/routers/estacoes.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.estacoes import Estacao
from ..schemas import EstacaoRegistro
from ..security import Identity, get_current_estacao, require_master, rate_limiter, station_key_hash

router = APIRouter(prefix="/api/estacoes", tags=["Estações"])


@router.post("/registrar", dependencies=[Depends(rate_limiter)])
async def registrar_estacao(
    payload: EstacaoRegistro,
    identity: Identity = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    chave_hash = station_key_hash(payload.chave)
    existing = await db.execute(select(Estacao).where(Estacao.hostname == payload.hostname))
    row = existing.scalar_one_or_none()
    if row and row.chave_hash and row.chave_hash != chave_hash:
        raise HTTPException(status_code=409, detail="hostname já registrado com outra chave")
    ts = datetime.now().isoformat()
    if row:
        row.chave_hash = chave_hash
    else:
        db.add(Estacao(hostname=payload.hostname, chave_hash=chave_hash, ultimo_ping=ts, status="offline"))
    await db.commit()
    return {"ok": True}


@router.post("/ping")
async def estacao_ping(
    request: Request,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    hostname = identity.estacao
    ip = request.client.host if request.client else "desconhecido"
    existing = await db.execute(select(Estacao).where(Estacao.hostname == hostname))
    row = existing.scalar_one_or_none()
    ts = datetime.now().isoformat()
    if row:
        row.ip_tailscale = ip
        row.ultimo_ping = ts
        row.status = "online"
    else:
        db.add(Estacao(hostname=hostname, ip_tailscale=ip, ultimo_ping=ts, status="online"))
    await db.commit()
    return {"ok": True}


@router.get("")
async def get_estacoes(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Estacao).order_by(Estacao.hostname.asc()))
    rows = result.scalars().all()
    if identity.scope == "master":
        return [
            {
                "hostname": r.hostname,
                "ip_tailscale": r.ip_tailscale,
                "ultimo_ping": r.ultimo_ping,
                "status": r.status,
            }
            for r in rows
        ]
    return [
        {
            "hostname": r.hostname,
            "ultimo_ping": r.ultimo_ping,
            "status": r.status,
        }
        for r in rows
        if r.hostname == identity.estacao
    ]
```

- [ ] **Step 5: Atualizar `main.py` para usar identidade**

Em `apps/api/src/main.py`, trocar a proteção dos routers de dados:

```python
from .security import require_api_key, rate_limiter, get_current_estacao, require_master

for _r in (memory, agenda, notas, projetos, estacoes, tarefas):
    app.include_router(_r.router, dependencies=[Depends(get_current_estacao)])
app.include_router(hermes.router, dependencies=[Depends(get_current_estacao), Depends(rate_limiter)])
app.include_router(status.router)  # status fica aberto (healthcheck); status_md tem require_api_key própria
```

As rotas backward-compat (`/remember`, `/recall/{project}`, `/status/{project}`) ficam com `dependencies=[Depends(require_api_key)]` por enquanto — serão escopadas na Task 5.

- [ ] **Step 6: Rodar suíte completa**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 19 passed (15 + 4 novos de identidade). Os testes antigos usam `test-key` (master) → continuam passando.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/security.py apps/api/src/routers/estacoes.py apps/api/src/main.py apps/api/tests/test_identidade.py
git commit -m "feat: identidade por estação (get_current_estacao) + endpoint registrar master-only + ping com identidade"
```

---

### Task 4: Frente 3 — Escopo da agenda por owner

**Files:**
- Modify: `apps/api/src/routers/agenda.py`
- Test: `apps/api/tests/test_agenda.py`

**Interfaces:**
- Consumes: `Identity`, `get_current_estacao` (Task 3), modelo `Agenda` (já tem `estacao`), `AgendaSavePayload`.
- Produces: `get_agenda` filtra `estacao == identity.estacao` (scope=estacao); `save_agenda` insere com `estacao = identity.estacao` (ignora payload) e upsert com `AND estacao=?`; `delete_evento` com `AND estacao=?`. Master sem restrição.

- [ ] **Step 1: Escrever testes que falham**

Adicionar a `apps/api/tests/test_agenda.py` (manter os 4 existentes; a fixture autouse `_limpa_agenda` já limpa a tabela antes de cada teste):

```python
from src.security import station_key_hash
from src.database import async_session_factory
from src.models.estacoes import Estacao
from sqlalchemy import select

MASTER = {"X-API-Key": "test-key"}


async def _registrar(client, hostname, chave):
    await client.post("/api/estacoes/registrar", json={"hostname": hostname, "chave": chave}, headers=MASTER)


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_estacao_nao_delete_evento_de_outra(client: AsyncClient):
    await _registrar(client, "estacao-x", "chave-x")
    await _registrar(client, "estacao-y", "chave-y")
    await client.post("/api/agenda", json={"eventos": [{"id": "e1", "data": "2026-08-02", "hora": "09:00", "titulo": "original"}]}, headers={"X-API-Key": "chave-x"})
    r = await client.delete("/api/agenda/e1", headers={"X-API-Key": "chave-y"})
    assert r.status_code == 404
    r2 = await client.get("/api/agenda", headers={"X-API-Key": "chave-x"})
    assert len(r2.json()) == 1
```

Nota: os 3 testes novos usam a fixture `client` do conftest (já usada pelos 4 existentes), que dispara `_setup_db` (init_db). Não criar `AsyncClient` manualmente — `ASGITransport` não roda `on_startup`.

- [ ] **Step 2: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_agenda.py -q`
Expected: os 3 novos falham (GET retorna tudo, upsert/DELETE sem filtro de estação).

- [ ] **Step 3: Implementar escopo na `agenda.py`**

Reescrever `apps/api/src/routers/agenda.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agenda import Agenda
from ..schemas import AgendaSavePayload
from ..security import Identity, get_current_estacao

router = APIRouter(prefix="/api/agenda", tags=["Agenda"])


@router.get("")
async def get_agenda(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Agenda).order_by(Agenda.data.asc(), Agenda.hora.asc())
    if identity.scope == "estacao":
        query = query.where(Agenda.estacao == identity.estacao)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "data": r.data,
            "hora": r.hora,
            "titulo": r.titulo,
            "estacao": r.estacao,
            "descricao": r.descricao,
        }
        for r in rows
    ]


@router.post("")
async def save_agenda(
    payload: AgendaSavePayload,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    processados = 0
    for ev in payload.eventos:
        estacao = identity.estacao if identity.scope == "estacao" else (ev.estacao or "central")
        existing = await db.execute(select(Agenda).where(Agenda.id == ev.id))
        row = existing.scalar_one_or_none()
        if identity.scope == "estacao" and row is not None and row.estacao != identity.estacao:
            raise HTTPException(status_code=403, detail="Evento pertence a outra estação")
        if row:
            row.data = ev.data
            row.hora = ev.hora
            row.titulo = ev.titulo
            row.estacao = estacao
            row.descricao = ev.descricao
            row.timestamp = datetime.now().isoformat()
        else:
            db.add(
                Agenda(
                    id=ev.id,
                    data=ev.data,
                    hora=ev.hora,
                    titulo=ev.titulo,
                    estacao=estacao,
                    descricao=ev.descricao,
                    timestamp=datetime.now().isoformat(),
                )
            )
        processados += 1
    await db.commit()
    return {"ok": True, "merge": processados}


@router.delete("/{evento_id}")
async def delete_evento(
    evento_id: str,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Agenda).where(Agenda.id == evento_id)
    if identity.scope == "estacao":
        query = query.where(Agenda.estacao == identity.estacao)
    existing = await db.execute(query)
    row = existing.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 4: Rodar suíte completa**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 22 passed (19 + 3 novos). Os 4 testes antigos de agenda usam master (`test-key`) → sem filtro → continuam passando.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/routers/agenda.py apps/api/tests/test_agenda.py
git commit -m "feat: escopo da agenda por estação (upsert/delete/lista por owner)"
```

---

### Task 5: Frente 3 — Escopo de memória (remember/recall/status) + notas

**Files:**
- Modify: `apps/api/src/routers/memory.py`
- Modify: `apps/api/src/routers/notas.py`
- Modify: `apps/api/src/main.py` (rotas backward-compat)
- Test: `apps/api/tests/test_escopo_memoria.py`

**Interfaces:**
- Consumes: `Identity`, `get_current_estacao`, `AgentMemory.estacao` (Task 2), `Nota` model.
- Produces: `save_memory` grava `estacao = identity.estacao` (agent_name permanece do cliente); `get_memory`/`get_status` filtram `estacao` + `limit Query(10, ge=1, le=200)`; `save_nota` grava `estacao = identity.estacao`; `get_diarios`/`get_diario` filtram por estação (scope=estacao). Nota: `resumos_diarios` (tabela `resumos_diarios`, PK `data`) NÃO tem coluna estacao — resumos permanecem master-gerenciados (documentado).

- [ ] **Step 1: Escrever testes que falham**

Criar `apps/api/tests/test_escopo_memoria.py`:

```python
import pytest
from httpx import AsyncClient

from src.main import app

MASTER = {"X-API-Key": "test-key"}


async def _registrar(client, hostname, chave):
    await client.post("/api/estacoes/registrar", json={"hostname": hostname, "chave": chave}, headers=MASTER)


@pytest.mark.asyncio
async def test_recall_escopo_por_estacao(client: AsyncClient):
    await _registrar(client, "est-mx", "chave-mx")
    await _registrar(client, "est-my", "chave-my")
    await client.post("/remember", json={"agent_name": "opencode", "project": "proj1", "content": "memoria de x"}, headers={"X-API-Key": "chave-mx"})
    r = await client.get("/recall/proj1", headers={"X-API-Key": "chave-my"})
    assert r.status_code == 200
    assert r.json() == []
    r2 = await client.get("/recall/proj1", headers={"X-API-Key": "chave-mx"})
    assert len(r2.json()) == 1
    assert r2.json()[0]["estacao"] == "est-mx"


@pytest.mark.asyncio
async def test_recall_limit_com_teto(client: AsyncClient):
    await _registrar(client, "est-mx", "chave-mx")
    for i in range(3):
        await client.post("/remember", json={"agent_name": "a", "project": "proj1", "content": f"m{i}"}, headers={"X-API-Key": "chave-mx"})
    r = await client.get("/recall/proj1?limit=2", headers={"X-API-Key": "chave-mx"})
    assert len(r.json()) == 2
    r_inv = await client.get("/recall/proj1?limit=-1", headers={"X-API-Key": "chave-mx"})
    assert r_inv.status_code == 422


@pytest.mark.asyncio
async def test_nota_grava_estacao_da_identidade(client: AsyncClient):
    await _registrar(client, "est-mx", "chave-mx")
    await client.post("/api/nota", json={"texto": "nota de x", "estacao": "central"}, headers={"X-API-Key": "chave-mx"})
    r = await client.get("/api/diarios", headers={"X-API-Key": "chave-mx"})
    assert r.status_code == 200
    # diários de x contêm o dia de hoje
    dias = [d["data"] for d in r.json()]
    assert any(d >= "2026-01-01" for d in dias)
```

Nota: os nomes de hostname/chave em test_escopo_memoria usam prefixo `m` (est-mx/chave-mx) porque o DB de teste é session-scoped e compartilhado entre arquivos — chaves devem ser únicas no namespace global da suíte (est-x/chave-x já são usados por test_agenda).

- [ ] **Step 2: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_escopo_memoria.py -q`
Expected: falham (recall sem filtro de estação; limit sem teto; nota grava estacao do payload).

- [ ] **Step 3: Implementar escopo em `memory.py`**

Reescrever `apps/api/src/routers/memory.py`:

```python
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agent_memory import AgentMemory
from ..schemas import MemoryEntry
from ..security import Identity, get_current_estacao

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/remember")
async def save_memory(
    entry: MemoryEntry,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    mem = AgentMemory(
        timestamp=datetime.now().isoformat(),
        agent_name=entry.agent_name,
        estacao=identity.estacao,
        project=entry.project,
        category=entry.category,
        content=entry.content,
    )
    db.add(mem)
    await db.commit()
    return {"status": "success", "id": mem.id}


@router.get("/recall/{project}")
async def get_memory(
    project: str,
    limit: int = Query(10, ge=1, le=200),
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(AgentMemory).where(AgentMemory.project == project)
    if identity.scope == "estacao":
        query = query.where(AgentMemory.estacao == identity.estacao)
    query = query.order_by(AgentMemory.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "agent_name": r.agent_name,
            "project": r.project,
            "category": r.category,
            "content": r.content,
            "estacao": r.estacao,
        }
        for r in rows
    ]


def _readable(content: str) -> str:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and parsed.get("s"):
            return parsed["s"]
    except (json.JSONDecodeError, TypeError):
        pass
    return content


@router.get("/status/{project}")
async def get_status(
    project: str,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    base = select(AgentMemory.content).where(AgentMemory.project == project)
    if identity.scope == "estacao":
        base = base.where(AgentMemory.estacao == identity.estacao)
    result_pending = await db.execute(
        base.where(AgentMemory.category == "task_pending").order_by(AgentMemory.timestamp.desc()).limit(5)
    )
    result_completed = await db.execute(
        base.where(AgentMemory.category == "task_completed").order_by(AgentMemory.timestamp.desc()).limit(3)
    )
    return {
        "project": project,
        "pending": [_readable(r[0]) for r in result_pending.fetchall()],
        "completed": [_readable(r[0]) for r in result_completed.fetchall()],
    }
```

- [ ] **Step 4: Atualizar rotas backward-compat em `main.py`**

Em `apps/api/src/main.py`:

```python
from .security import rate_limiter, get_current_estacao, require_master, Identity


@app.post("/remember", dependencies=[Depends(get_current_estacao)])
async def remember_backward(entry: MemoryEntry, identity: Identity = Depends(get_current_estacao), db=Depends(get_db)):
    return await memory.save_memory(entry, identity, db)


@app.get("/recall/{project}", dependencies=[Depends(get_current_estacao)])
async def recall_backward(project: str, limit: int = Query(10, ge=1, le=200), identity: Identity = Depends(get_current_estacao), db=Depends(get_db)):
    return await memory.get_memory(project, limit, identity, db)


@app.get("/status/{project}", dependencies=[Depends(get_current_estacao)])
async def status_backward(project: str, identity: Identity = Depends(get_current_estacao), db=Depends(get_db)):
    return await memory.get_status(project, identity, db)
```

(Adicionar `Query` ao import de `fastapi` em `main.py`.)

- [ ] **Step 5: Implementar escopo em `notas.py`**

Editar `apps/api/src/routers/notas.py` (assinaturas + filtros):

```python
from ..security import Identity, get_current_estacao

@router.get("/diarios")
async def get_diarios(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            func.substr(Nota.timestamp, 1, 10).label("data_dia"),
            func.sum(func.length(Nota.texto)).label("tamanho"),
        )
        .group_by(func.substr(Nota.timestamp, 1, 10))
        .order_by(func.substr(Nota.timestamp, 1, 10).desc())
    )
    if identity.scope == "estacao":
        query = query.where(Nota.estacao == identity.estacao)
    result = await db.execute(query)
    diarios = [{"data": r[0], "tamanho": r[1] or 0} for r in result.fetchall()]

    hoje = datetime.now().strftime("%Y-%m-%d")
    if not any(x["data"] == hoje for x in diarios):
        diarios.insert(0, {"data": hoje, "tamanho": 0})
    return diarios


@router.get("/diario/{data}")
async def get_diario(
    data: str,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Nota).where(func.substr(Nota.timestamp, 1, 10) == data)
    if identity.scope == "estacao":
        query = query.where(Nota.estacao == identity.estacao)
    query = query.order_by(Nota.timestamp.asc())
    result = await db.execute(query)
    rows = result.scalars().all()
    # ... resto do corpo inalterado (resumo, montagem do markdown) ...
```

E no `save_nota`, trocar `estacao=payload.estacao` por:

```python
@router.post("/nota")
async def save_nota(
    payload: NotaEntry,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    nota = Nota(
        estacao=identity.estacao,
        texto=payload.texto,
        timestamp=datetime.now().isoformat(),
    )
    db.add(nota)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 6: Rodar suíte completa**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 25 passed (22 + 3 novos). `test_memory.py` e `test_security.py` usam master → sem filtro → continuam passando.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/routers/memory.py apps/api/src/routers/notas.py apps/api/src/main.py apps/api/tests/test_escopo_memoria.py
git commit -m "feat: escopo de memória e notas por estação + limit com teto no recall"
```

---

### Task 6: Frente 3/4 — Escopo de tarefas e projetos + relatório POST-only

**Files:**
- Modify: `apps/api/src/routers/tarefas.py`
- Modify: `apps/api/src/routers/projetos.py`
- Modify: `apps/api/src/main.py` (rate limiter em projetos)
- Test: `apps/api/tests/test_escopo_tarefas.py`

**Interfaces:**
- Consumes: `Identity`, `get_current_estacao`, `require_master`, modelo `Projeto` (tem `estacao`), `Tarefa`.
- Produces: `listar_tarefas` escopa por projeto da estação (join `Projeto.estacao == identity.estacao` quando scope=estacao); `criar_tarefa` exige projeto da estação; `atualizar_tarefa`/`deletar_tarefa` validam ownership do projeto; `sync_projetos` força `estacao = identity.estacao` (scope=estacao); `gerar_relatorio` master-only; `GET /api/projetos/relatorio` → 405 (POST-only). `main.py` adiciona `rate_limiter` ao router `projetos`.

- [ ] **Step 1: Escrever testes que falham**

Criar `apps/api/tests/test_escopo_tarefas.py`:
```python
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
```

Nota: chaves de estação de test_escopo_tarefas usam prefixo `t` (chave-tx/chave-ty) — únicas no namespace global da suíte (DB session-scoped compartilhado).

- [ ] **Step 2: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_escopo_tarefas.py -q`
Expected: falham (tarefas sem escopo; GET relatorio responde 200; POST sem master responde 200).

- [ ] **Step 3: Implementar escopo em `tarefas.py`**

Editar `apps/api/src/routers/tarefas.py`:

```python
from ..models.projetos import Projeto
from ..security import Identity, get_current_estacao


async def _projeto_da_estacao(db, projeto_id: int, identity: Identity):
    result = await db.execute(select(Projeto).where(Projeto.id == projeto_id))
    projeto = result.scalar_one_or_none()
    if projeto is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if identity.scope == "estacao" and projeto.estacao != identity.estacao:
        raise HTTPException(status_code=403, detail="Projeto pertence a outra estação")
    return projeto


@router.get("")
async def listar_tarefas(
    projeto_id: int | None = None,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Tarefa).join(Projeto, Tarefa.projeto_id == Projeto.id)
    if identity.scope == "estacao":
        query = query.where(Projeto.estacao == identity.estacao)
    if projeto_id is not None:
        query = query.where(Tarefa.projeto_id == projeto_id)
    query = query.order_by(Tarefa.prioridade.asc(), Tarefa.id.desc())
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "projeto_id": r.projeto_id,
            "titulo": r.titulo,
            "status": r.status,
            "prioridade": r.prioridade,
            "data_limite": r.data_limite,
        }
        for r in rows
    ]


@router.post("")
async def criar_tarefa(
    payload: TarefaCreate,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    await _projeto_da_estacao(db, payload.projeto_id, identity)
    tarefa = Tarefa(
        projeto_id=payload.projeto_id,
        titulo=payload.titulo,
        status=payload.status,
        prioridade=payload.prioridade,
        data_limite=payload.data_limite,
    )
    db.add(tarefa)
    await db.commit()
    await db.refresh(tarefa)
    return {
        "id": tarefa.id,
        "projeto_id": tarefa.projeto_id,
        "titulo": tarefa.titulo,
        "status": tarefa.status,
        "prioridade": tarefa.prioridade,
        "data_limite": tarefa.data_limite,
    }


@router.put("/{tarefa_id}")
async def atualizar_tarefa(
    tarefa_id: int,
    payload: TarefaUpdate,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tarefa).where(Tarefa.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    await _projeto_da_estacao(db, tarefa.projeto_id, identity)
    # ... atualiza campos e retorna igual ao original ...
```

(Manter o corpo de atualização e `deletar_tarefa` com a mesma validação `_projeto_da_estacao`.)

- [ ] **Step 4: Implementar escopo em `projetos.py`**

Editar `apps/api/src/routers/projetos.py`:

```python
from ..security import Identity, get_current_estacao, require_master


@router.get("")
async def get_projetos(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Projeto).order_by(Projeto.nome.asc())
    if identity.scope == "estacao":
        query = query.where(Projeto.estacao == identity.estacao)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "nome": r.nome,
            "local": r.local_caminho,
            "preview": r.readme_preview,
            "status": r.status,
            "tags": r.tags,
            "estacao": r.estacao,
        }
        for r in rows
    ]


@router.post("/sync")
async def sync_projetos(
    payload: ProjetosSyncPayload,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    count = 0
    for p in payload.projetos:
        estacao = identity.estacao if identity.scope == "estacao" else p.estacao
        existing = await db.execute(
            select(Projeto).where(
                Projeto.nome == p.nome,
                Projeto.estacao == estacao,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.local_caminho = p.local_caminho
            row.readme_preview = p.readme_preview
            row.status = p.status
            row.tags = p.tags
            row.ultima_atualizacao = datetime.now().isoformat()
        else:
            db.add(
                Projeto(
                    nome=p.nome,
                    local_caminho=p.local_caminho,
                    status=p.status,
                    tags=p.tags,
                    readme_preview=p.readme_preview,
                    estacao=estacao,
                    ultima_atualizacao=datetime.now().isoformat(),
                )
            )
        count += 1
    await db.commit()
    return {"ok": True, "count": count}


@router.get("/relatorio", status_code=405)
async def gerar_relatorio_get(nome: str):
    return {"detail": "Use POST /api/projetos/gerar-relatorio"}


@router.post("/gerar-relatorio")
async def gerar_relatorio(
    payload: ProjetoRelatorioPayload,
    identity: Identity = Depends(require_master),
):
    # ... corpo atual inalterado (prompt, subprocess, parse) ...
```

**Importante:** ao trocar o decorator de `gerar_relatorio` para `identity: Identity = Depends(require_master)`, remover a antiga função `gerar_relatorio_get` que chamava `gerar_relatorio(payload)` e substituir pela versão 405 acima.

- [ ] **Step 5: Rate limiter em projetos**

Em `apps/api/src/main.py`, no loop de routers:

```python
for _r in (memory, agenda, notas, estacoes, tarefas):
    app.include_router(_r.router, dependencies=[Depends(get_current_estacao)])
app.include_router(projetos.router, dependencies=[Depends(get_current_estacao), Depends(rate_limiter)])
app.include_router(hermes.router, dependencies=[Depends(get_current_estacao), Depends(rate_limiter)])
```

- [ ] **Step 6: Rodar suíte completa**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 28 passed (25 + 3 novos).

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/routers/tarefas.py apps/api/src/routers/projetos.py apps/api/src/main.py apps/api/tests/test_escopo_tarefas.py
git commit -m "feat: escopo de tarefas e projetos por estação + relatório master-only/POST-only"
```

---

### Task 7: Frente 4 — Hardening do `/api/hermes` (master-only + env filtrado)

**Files:**
- Modify: `apps/api/src/routers/hermes.py`
- Test: `apps/api/tests/test_hermes.py`

**Interfaces:**
- Consumes: `require_master` (Task 3), `ChatPayload`, `settings.HERMES_TIMEOUT`, `settings.HERMES_CLI`.
- Produces: `chat_ia` exige master (403 para estação); `_call_opencode`/`_call_hermes` usam env filtrado (`PATH`, `HOME`, `OPENROUTER_API_KEY` — sem `**os.environ`); `_call_hermes` não ecoa exceção crua no `resposta`.

- [ ] **Step 1: Escrever teste que falha**

Criar `apps/api/tests/test_hermes.py`:

```python
import pytest
from httpx import AsyncClient

from src.main import app

MASTER = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_hermes_estacao_403(client: AsyncClient):
    await client.post("/api/estacoes/registrar", json={"hostname": "est-hx", "chave": "chave-hx"}, headers=MASTER)
    r = await client.post("/api/hermes", json={"mensagem": "oi"}, headers={"X-API-Key": "chave-hx"})
    assert r.status_code == 403
```

Nota: chave `chave-hx` (prefixo h) — única no namespace global da suíte (DB session-scoped compartilhado).

- [ ] **Step 2: Rodar e verificar que falha**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_hermes.py -q`
Expected: FAIL (hoje estação com chave válida passa).

- [ ] **Step 3: Implementar hardening em `hermes.py`**

Editar `apps/api/src/routers/hermes.py`:

```python
import os
import json
import subprocess

from fastapi import APIRouter, Depends

from ..config import settings
from ..schemas import ChatPayload
from ..security import Identity, require_master

router = APIRouter(prefix="/api", tags=["Chat IA"])

OPENCODE_CLI = "/home/deploy/.opencode/bin/opencode"
HERMES_CLI = settings.HERMES_CLI


def _env_filtrado() -> dict:
    """Somente as variáveis mínimas necessárias — não vaza todo o os.environ."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    if os.environ.get("OPENROUTER_API_KEY"):
        env["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    env["PYTHONUNBUFFERED"] = "1"
    return env


async def _call_opencode(prompt: str) -> dict | None:
    try:
        resultado = subprocess.run(
            [OPENCODE_CLI, "run", "--format", "json", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            env=_env_filtrado(),
        )
        # ... parse idêntico ao atual (eventos JSON) ...
    except Exception:
        return None


async def _call_hermes(prompt: str) -> dict:
    try:
        resultado = subprocess.run(
            [HERMES_CLI, "-z", prompt, "chat"],
            capture_output=True,
            text=True,
            timeout=settings.HERMES_TIMEOUT,
            env=_env_filtrado(),
        )
        saida = resultado.stdout.strip()
        erro = resultado.stderr.strip() if resultado.stderr else ""
        if resultado.returncode != 0:
            return {"resposta": f"Erro Hermes CLI ({resultado.returncode})", "agente": "hermes-error"}
        return {"resposta": saida, "agente": "hermes"}
    except subprocess.TimeoutExpired:
        return {"resposta": "Falha ao chamar Hermes: timeout", "agente": "hermes-failed"}
    except Exception:
        return {"resposta": "Falha ao chamar Hermes", "agente": "hermes-failed"}


@router.post("/hermes")
async def chat_ia(
    payload: ChatPayload,
    identity: Identity = Depends(require_master),
):
    prompt = payload.mensagem
    if payload.contexto:
        prompt = f"[Contexto EstudioHC: {payload.contexto}]\n\n{payload.mensagem}"

    result = await _call_opencode(prompt)
    if result:
        return result

    return await _call_hermes(prompt)
```

- [ ] **Step 4: Rodar suíte completa**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: 29 passed. Não há teste antigo de hermes com resposta real (o teste novo só checa 403).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/routers/hermes.py apps/api/tests/test_hermes.py
git commit -m "feat: hermes master-only + env filtrado + sem eco de exceção"
```

---

### Task 8: Frente 5 — Dashboard: XSS + envio de chave + path traversal legado

**Files:**
- Modify: `apps/dashboard/static/index.html`
- Modify: `apps/dashboard/static/projeto.html`
- Modify: `apps/dashboard/src/__init__.py`
- Modify: `dashboard/server.py` (legado)

**Interfaces:**
- Consumes: padrão seguro já existente no dashboard (`textContent` em `diario-content`/`addMsg`).
- Produces: nenhum `innerHTML` com dado da API não sanitizado; dashboard envia `X-API-Key` lida de `window.__ESTUDIOHC_KEY__`; proxy `apps/dashboard/src/__init__.py` injeta header `X-API-Key` quando `DASHBOARD_API_KEY` env presente; `dashboard/server.py` valida `data` com regex antes de montar caminho.

- [ ] **Step 1: Verificar estado atual (sem teste automatizado — inspeção + commit)**

Leia `apps/dashboard/static/index.html` linhas 324-337 (renderEventosDia), 394/413/514 (respostas IA) e `projeto.html` 473/477/488.

- [ ] **Step 2: Corrigir XSS em `index.html`**

Em `apps/dashboard/static/index.html`, substituir a função `renderEventosDia()` (que monta `lista.innerHTML = evsDia.map(...)`) por construção segura com `createElement` + `textContent`:

```javascript
function renderEventosDia() {
    const evs = agenda
        .filter(e => e.data === dataSelecionada())
        .sort((a, b) => (a.hora || '').localeCompare(b.hora || ''));
    const lista = document.getElementById('lista-eventos');
    if (!lista) return;
    lista.innerHTML = '';
    if (evs.length === 0) {
        const li = document.createElement('li');
        li.className = 'lista-vazia';
        li.textContent = 'Nenhum evento para este dia.';
        lista.appendChild(li);
        return;
    }
    evs.forEach(ev => {
        const li = document.createElement('li');
        const hora = document.createElement('span');
        hora.className = 'evento-hora';
        hora.textContent = ev.hora || '';
        const titulo = document.createElement('span');
        titulo.className = 'evento-titulo';
        titulo.textContent = ev.titulo || '';
        const btn = document.createElement('button');
        btn.className = 'btn-remover';
        btn.textContent = 'Remover';
        btn.addEventListener('click', () => removerEvento(ev.id));
        li.appendChild(hora);
        li.appendChild(titulo);
        li.appendChild(btn);
        lista.appendChild(li);
    });
}
```

**Nota:** ajuste `dataSelecionada()` e os nomes de id/classes às classes reais do CSS existente (mantenha o layout atual); o essencial é `textContent`, nunca `innerHTML` com `ev.titulo`/`ev.hora`/`ev.id`.

Para as respostas de IA (`index.html` ~394/413/514, ex.: `d.resumo`, `d.resposta` renderizados com `innerHTML` após `replace(/\n/g,'<br>')`), substituir por `textContent`:

```javascript
// Antes (exemplo):
// el.innerHTML = (d.resumo || '').replace(/\n/g, '<br>');
// Depois:
el.textContent = d.resumo || '';
```

E para `projeto.html` 473/477/488 (`marked.parse(data.relatorio)` etc.), usar sanitização com DOMPurify OU texto simples. Como o dashboard é servido estaticamente, verificar se existe `DOMPurify` local em `static/vendor/`; se existir:

```javascript
document.getElementById('report-rendered').innerHTML = DOMPurify.sanitize(marked.parse(data.relatorio || ''));
```

Se não houver asset local de DOMPurify, usar `textContent` (perde formatação markdown, mas elimina XSS):

```javascript
document.getElementById('report-rendered').textContent = data.relatorio || '';
```

- [ ] **Step 3: Injetar chave no dashboard (proxy) e no client**

Em `apps/dashboard/src/__init__.py`, no `proxy_api`, adicionar header quando `DASHBOARD_API_KEY` estiver definida:

```python
import os

DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")


@registry.get("/api/estacion-key")
async def estacion_key():
    # Serve a chave da estação local para o JS (mesma origem, uso local).
    return {"chave": DASHBOARD_API_KEY}


@router.api_route("/api/{path:path}", methods=[GET, POST, PUT, DELETE, OPTIONS])
async def proxy_api(request: Request, path: str):
    url = f"{API_URL}/api/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    if DASHBOARD_API_KEY:
        headers["X-API-Key"] = DASHBOARD_API_KEY
    # ... resto do proxy inalterado ...
```

(Se o proxy já monta `/api/{path:path}`, o `estacion_key` deve ser registrado como rota `@app.get("/api/estacion-key")` no mesmo objeto FastAPI — ajustar conforme a estrutura real de `apps/dashboard/src/__init__.py`.)

Em `apps/dashboard/static/index.html`, no topo (após `const API = ...`), carregar a chave e usá-la em todos os fetch:

```javascript
const API = window.location.origin + '/api';
let ESTUDIOHC_KEY = '';
async function carregarChave() {
    try {
        const r = await fetch(API + '/estacion-key');
        if (r.ok) ESTUDIOHC_KEY = (await r.json()).chave || '';
    } catch (e) { ESTUDIOHC_KEY = ''; }
}
function headersComChave(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    if (ESTUDIOHC_KEY) h['X-API-Key'] = ESTUDIOHC_KEY;
    return h;
}
carregarChave();
```

Substituir cada `fetch(...)` das funções que chamam a API (`salvarAgenda`, `removerEvento`, `chamarIA`, `carregarDiario`, etc.) para incluir `{ method, headers: headersComChave(), body }`.

- [ ] **Step 4: Corrigir path traversal no hub legado**

Em `dashboard/server.py`, na função que monta o caminho do diário (linha 43):

```python
import re

def get_diario(data: str):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data or ""):
        raise HTTPException(status_code=400, detail="data inválida")
    caminho = f"{DIARIO_DIR}/{data}_COMPLETO.txt"
    # ... resto inalterado ...
```

- [ ] **Step 5: Verificação manual e commit**

Sem harness JS automatizado no repo, validar por inspeção: nenhum `innerHTML` com dado da API permanece em `index.html`/`projeto.html`. Commit:

```bash
git add apps/dashboard/static/index.html apps/dashboard/static/projeto.html apps/dashboard/src/__init__.py dashboard/server.py
git commit -m "fix: dashboard sem XSS + envio de chave via proxy + path traversal legado"
```

---

### Task 9: Frente 6 — Endurecimento MCP/ChromaDB/scripts + itens rápidos

**Files:**
- Modify: `apps/chromadb-mcp/server.py`
- Modify: `apps/mcp-memory/src/memory_server.py`
- Modify: `apps/mcp-memory/src/chroma_client.py`
- Modify: `apps/mcp-stdio/src/main.py`
- Modify: `scripts/setup-machine.sh`
- Modify: `.gitignore`
- Modify: `apps/api/Dockerfile`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `CHROMA_API_KEY` (novo env), `CHROMA_HOST` default `127.0.0.1`, `AGENT_NAME`, `project` validation regex `^[a-z0-9_-]{1,64}$`.
- Produces: ChromaDB MCP com token em `call_tool`; `project` validado antes de URL/coleção; `doc_delete` checa owner; `doc_add`/`wm_push` com limites; `limit` clamp 1-50 (mcp-stdio e memory_server); `chroma_client` com `asyncio.wait_for` + backoff; `setup-machine.sh` bind `127.0.0.1` no llama-server, chave por estação no registro, hostname escapado em JSON; `.gitignore` com `.matrixx/` e `*.pkl`; Dockerfile `USER` não-root; docker-compose com `API_KEY` obrigatória/Tailscale-only.

- [ ] **Step 1: ChromaDB MCP — token em `call_tool` + bind local + hash → uuid5**

Em `apps/chromadb-mcp/server.py`:

```python
import os
import uuid
import hashlib

CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_API_KEY = os.environ.get("CHROMA_API_KEY", "")


def _check_auth(arguments: dict) -> None:
    token = arguments.get("api_key") or ""
    if CHROMA_API_KEY and token != CHROMA_API_KEY:
        raise ValueError("Unauthorized")


# Em cada tool handler de `call_tool`, na primeira linha:
#   _check_auth(arguments)
```

Em `add_documents`, trocar `hash(d['text'][:50])` por id determinístico:

```python
import uuid as _uuid
# dentro do loop de add_documents:
doc_id = d.get("id") or str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{collection}:{d['text'][:200]}"))
```

- [ ] **Step 2: `filter_metadata` allowlist em `search_documents`**

Em `apps/chromadb-mcp/server.py`, no `search_documents`, substituir o repasse verbatim:

```python
ALLOWED_META = {"title", "tags", "project", "ts"}

def _sanitizar_where(raw):
    if not isinstance(raw, dict):
        return None
    out = {}
    for k, v in raw.items():
        if k in ALLOWED_META:
            out[k] = v
        elif k in ("$and", "$or") and isinstance(v, list):
            out[k] = [_sanitizar_where(item) for item in v]
    return out or None
```

E usar `where=_sanitizar_where(arguments.get("filter_metadata"))` na chamada `col.query`.

- [ ] **Step 3: `memory_server.py` — validar `project` + doc_delete owner + limites + clamp**

Em `apps/mcp-memory/src/memory_server.py`:

```python
import re
PROJECT_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def _validar_project(project: str) -> str:
    if not project or not PROJECT_RE.fullmatch(project):
        raise ValueError(f"project inválido: {project!r}")
    return project
```

- Chamar `_validar_project(project)` no início de `search_memory`, `get_status`, `doc_add`, `doc_search`, `doc_list`, `doc_delete`.
- Em `doc_add`: rejeitar `content` com mais de 1MB e `tags` com mais de 50 itens:

```python
content = arguments.get("content", "")
if len(content) > 1024 * 1024:
    raise ValueError("content muito grande (máx 1MB)")
tags = arguments.get("tags") or []
if len(tags) > 50:
    raise ValueError("tags demais (máx 50)")
```

- Em `doc_delete`: checar ownership antes de apagar:

```python
meta = arguments.get("metadata", {})
if meta.get("owner") and meta["owner"] != AGENT_NAME:
    raise ValueError("Sem permissão para apagar este documento")
```

- Em `search_memory` e `wm_push`: clamp de tamanho/limit. Para `limit`, usar `min(max(int(arguments.get("limit", 10)), 1), 50)`.

- [ ] **Step 4: `chroma_client.py` — timeout por request + backoff**

Em `apps/mcp-memory/src/chroma_client.py`, envolver `session.call_tool` com `asyncio.wait_for` e retry com backoff exponencial:

```python
import asyncio
import random

async def _call_tool(self, name: str, arguments: dict) -> dict:
    if CHROMA_API_KEY and arguments:
        arguments = {**arguments, "api_key": CHROMA_API_KEY}
    last_err = None
    for attempt in range(3):
        try:
            async with self._get_session() as session:
                result = await asyncio.wait_for(
                    session.call_tool(name, arguments),
                    timeout=30,
                )
                return self._parse(result)
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.5 * (2 ** attempt) + random.uniform(0, 0.3))
    raise last_err
```

(Adicionar `CHROMA_API_KEY = os.getenv("CHROMA_API_KEY", "")` e injetar `api_key` em todos os `_call_tool(...)` existentes.)

- [ ] **Step 5: `mcp-stdio/src/main.py` — clamp limit**

Em `apps/mcp-stdio/src/main.py`, em `recall_memory`:

```python
try:
    limit = int(arguments.get("limit", 10))
except (TypeError, ValueError):
    limit = 10
limit = max(1, min(limit, 50))
```

- [ ] **Step 6: `setup-machine.sh` — bind local + chave por estação + escape JSON**

Editar `scripts/setup-machine.sh`:

1. Llama-server bind loopback (linha ~155): `--host 127.0.0.1 --port 11434`.
2. Gerar chave da estação e registrar na central (substituir o bloco final de ping):

```bash
CHAVE_ESTACAO="${CHAVE_ESTACAO:-$(openssl rand -hex 32)}"

# Registrar a estação na central (endpoint master-only) com a chave gerada
MASTER_KEY="${ESTUDIOHC_API_KEY:-}"
if [ -n "${MASTER_KEY}" ]; then
  PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"hostname": sys.argv[1], "chave": sys.argv[2]}))' "$(hostname)" "${CHAVE_ESTACAO}")
  curl -s -X POST "http://${SERVIDOR_CENTRAL}:5050/api/estacoes/registrar" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${MASTER_KEY}" \
    -d "${PAYLOAD}" || echo "Aviso: falha ao registrar estação (verifique ESTUDIOHC_API_KEY)"
fi
```

3. Gravar `MEMORY_API_KEY=${CHAVE_ESTACAO}` no config MCP e usar a chave no ping:

```bash
# no opencode.jsonc do MCP memory, adicionar MEMORY_API_KEY=${CHAVE_ESTACAO}
curl -s -X POST "http://${SERVIDOR_CENTRAL}:5050/api/estacoes/ping" \
  -H "X-API-Key: ${CHAVE_ESTACAO}" || true
```

- [ ] **Step 7: `.gitignore`, Dockerfile, docker-compose**

`.gitignore` — adicionar:

```
.matrixx/
*.pkl
```

`apps/api/Dockerfile` — adicionar usuário não-root antes do `CMD`:

```dockerfile
RUN useradd --create-home --uid 1000 appuser
USER appuser
```

`docker-compose.yml` — api: adicionar `API_KEY: ${API_KEY:?API_KEY é obrigatória}` e mudar ports para só Tailscale (ou remover publish e usar network do host):

```yaml
environment:
  - API_KEY=${API_KEY:?defina API_KEY}
  # remover "5050:5050" do ports; usar rede interna ou bind 100.x
```

- [ ] **Step 8: Verificação e commit**

Rodar suíte da API (inalterada — itens MCP não têm testes): `..\..\.venv\Scripts\python.exe -m pytest tests/ -q` → 29 passed. Commit:

```bash
git add apps/chromadb-mcp/server.py apps/mcp-memory/src/memory_server.py apps/mcp-memory/src/chroma_client.py apps/mcp-stdio/src/main.py scripts/setup-machine.sh .gitignore apps/api/Dockerfile docker-compose.yml
git commit -m "feat: endurecimento MCP/ChromaDB/scripts + CORS/docs/Dockerfile/.gitignore"
```

---

### Task 10: Deploy via servidor + smoke tests + reconcile + memória

**Files:** nenhum novo (deploy operacional).

**Interfaces:** consome todo o trabalho das Tasks 1-9 (HEAD local com 10 commits).

- [ ] **Step 1: Verificar suíte e git status**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q` → 29 passed.
Run: `git status --short` e `git log --oneline -12` no clone.

- [ ] **Step 2: Extrair arquivos alterados em LF puro**

Para cada arquivo alterado desde `9da3e67`, gerar LF via:
`cmd /c "git -C <repo> show HEAD:<path> > %TEMP%\opencode\lf2\<file>"`

Arquivos a transferir (resumo): `apps/api/src/security.py`, `apps/api/src/main.py`, `apps/api/src/config.py` (se alterado), `apps/api/src/routers/*.py` (estacoes, agenda, memory, notas, tarefas, projetos, hermes, status), `apps/api/src/models/*.py` (estacoes, agent_memory), `apps/api/src/schemas/__init__.py`, `apps/api/alembic/versions/002_identidade_estacao.py`, `apps/api/tests/*.py`, `apps/dashboard/static/index.html`, `apps/dashboard/static/projeto.html`, `apps/dashboard/src/__init__.py`, `dashboard/server.py`, `apps/chromadb-mcp/server.py`, `apps/mcp-memory/src/memory_server.py`, `apps/mcp-memory/src/chroma_client.py`, `apps/mcp-stdio/src/main.py`, `scripts/setup-machine.sh`, `.gitignore`, `apps/api/Dockerfile`, `docker-compose.yml`.

- [ ] **Step 3: Transferir via scp e aplicar no servidor**

```bash
scp <arquivos> deploy@100.64.117.78:/tmp/hardening/
# no servidor:
cp /tmp/hardening/* apps/api/src/routers/  # conforme a árvore de destino
grep -c $'\r' <arquivo>   # deve ser 0 para todos
```

- [ ] **Step 4: Commit e push no servidor**

No servidor `~/Apps/EstudioHC-Memory-Suite`:
```bash
git add -A
git commit -m "feat: endurecimento de segurança (6 frentes)"
git push origin master
```

- [ ] **Step 5: Aplicar migration e reiniciar API**

```bash
cd apps/api
source ~/.venv/bin/activate  # ou .venv conforme o servidor
alembic upgrade head
sudo systemctl restart estudiohc-api
# healthcheck:
curl -s http://127.0.0.1:5050/api/status
```

(Se systemctl indisponível: `pkill -f uvicorn` e relançar via systemd user ou nohup.)

- [ ] **Step 6: Smoke tests na API real**

```bash
# sem chave -> 401
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5050/api/agenda          # 401
# master -> 200
curl -s -H "X-API-Key: $MASTER_KEY" http://127.0.0.1:5050/api/status
# registrar estação de teste + ping + GET escopado
curl -s -X POST -H "X-API-Key: $MASTER_KEY" -d '{"hostname":"smoke","chave":"chave-smoke"}' http://127.0.0.1:5050/api/estacoes/registrar
curl -s -H "X-API-Key: chave-smoke" -X POST http://127.0.0.1:5050/api/estacoes/ping
curl -s -H "X-API-Key: chave-smoke" http://127.0.0.1:5050/api/estacoes
# hermes com estação -> 403; relatorio GET -> 405
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: chave-smoke" -X POST -d '{"mensagem":"oi"}' http://127.0.0.1:5050/api/hermes   # 403
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5050/api/projetos/relatorio?nome=x" -H "X-API-Key: $MASTER_KEY"   # 405
```

- [ ] **Step 7: Reconciliar clone local + registrar memória**

No Windows:
```bash
git fetch origin && git reset --hard origin/master
```
`POST http://100.64.117.78:5050/remember` (agente `opencode`, project `EstudioHC`, category `task_completed`): "Hardening de segurança aplicado e deployado: auth fail-closed, identidade por estação (registrar master-only), escopo por owner, hermes master-only, dashboard sem XSS, endurecimento MCP/ChromaDB. Nota de segurança: 3/10 → fail-closed."
