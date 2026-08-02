# Task 5 Report: Autenticacao via API key + rate limit em /api/hermes

**Status:** DONE

**Commit:** `d70e647` — `feat(api): optional API key auth + rate limit on /api/hermes` (branch `fix/memory-stack`, local only, not pushed)

## Test command and output

Command (from `apps/api`):
```
..\..\.venv\Scripts\python.exe -m pytest tests/ -v
```

Result: **4 passed, 2 warnings** (`DeprecationWarning` on `@app.on_event` — pre-existing).

TDD flow:
1. Wrote `tests/test_security.py` + added `API_KEY=test-key` to `conftest.py`. Ran: **1 failed, 3 passed** — `test_api_key_required_when_configured` failed with `assert 200 == 401` (RED, as expected).
2. Implemented Steps 3-6, re-ran: `test_security.py` passed but the two pre-existing `test_memory.py` tests failed (got 401 — they did not send the header).
3. Added `X-API-Key: test-key` headers to the two `test_memory.py` tests (required by the brief's Step 7 expectation that they keep passing). Re-ran: **4 passed**.

## Changes per file

- **`apps/api/src/security.py`** (created): `require_api_key` dependency (Header `X-API-Key`, 401 on mismatch when `settings.API_KEY` set) and `rate_limiter` dependency (per-IP sliding window, 429 when exceeding `settings.RATE_LIMIT_PER_MIN` in 60s). Verbatim from brief.
- **`apps/api/src/config.py`**: added `API_KEY: str = ""` and `RATE_LIMIT_PER_MIN: int = 10` to `Settings`. Verbatim.
- **`apps/api/src/main.py`**: imported `require_api_key, rate_limiter`; replaced the 8 `include_router` calls with the dependency-annotated loop from the brief (`memory/agenda/notas/projetos/estacoes/tarefas` get `require_api_key`; `hermes` gets `require_api_key + rate_limiter`; `status` stays open). Added `dependencies=[Depends(require_api_key)]` to the 3 top-level backward-compat decorators (`POST /remember`, `GET /recall/{project}`, `GET /status/{project}`). Handler logic unchanged.
- **`apps/api/tests/conftest.py`**: added `os.environ["API_KEY"] = "test-key"` right after `DATABASE_URL`. Verbatim.
- **`apps/api/tests/test_security.py`** (created): the 2 tests from the brief verbatim.
- **`apps/mcp-memory/src/memory_server.py`**: added `MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "")`; updated `call_api` to inject `headers["X-API-Key"]` when set. Verbatim.
- **`apps/api/tests/test_memory.py`** (deviation): added `HEADERS = {"X-API-Key": "test-key"}` and passed it to the POST/GET calls. NOT in the brief's file list, but required — the brief's Step 7 demands these 2 tests keep passing, and with `API_KEY=test-key` in conftest they now need the header. Handler/source logic untouched.
- **`apps/api/src/routers/hermes.py`**: listed in the brief but required no change — rate limiting is applied via `include_router` dependencies in `main.py`.

## Concerns

1. **test_memory.py update (minor deviation)**: the brief's Step 8 commit command did not include `test_memory.py`, but its Step 7 expectation ("tambem devem continuar passando os 2 testes de test_memory.py") is only satisfiable if those tests send the API key. I added the header to them and included the file in the commit. Flag for reviewer awareness.
2. Pre-existing LSP errors (mcp package stubs in `memory_server.py`, sqlalchemy import resolution, `pytest_asyncio` resolution) remain and are out of scope.
3. `rate_limiter`/`_requests` is in-memory per-process — not shared across workers/restarts. Acceptable for this stack, noted for completeness.
