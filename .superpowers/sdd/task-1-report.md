# Task 1 Report: API `/remember` retorna `id` + `get_status` legível

## What I implemented

1. **`apps/api/src/routers/memory.py`**
   - `save_memory()` now returns `{"status": "success", "id": mem.id}` instead of `{"status": "success"}`. This is the root fix for the FAISS bug: the MCP memory server can now index with a real persisted row id. `mem.id` is populated after `commit()` because the session factory uses `expire_on_commit=False`.
   - Added `_readable(content)` helper that JSON-parses content and returns the `s` (summary) field, falling back to raw content for non-JSON or non-dict.
   - `get_status()` now returns `pending`/`completed` as readable summary text via `_readable()` instead of raw JSON strings.
   - Added `import json`.

2. **`apps/api/src/main.py`**
   - Added backward-compat top-level route `GET /status/{project}` delegating to `memory.get_status(project, db)`, mirroring the existing `/remember` and `/recall/{project}` backward-compat routes. Required because the memory router is prefix-mounted at `/memory`, but the brief's test (and the top-level API contract) hits `/status/{project}`.

3. **`apps/api/pyproject.toml`**
   - Added `[tool.pytest.ini_options] asyncio_mode = "auto"`. Without it, pytest-asyncio runs in STRICT mode and the async test functions error with "async def functions are not natively supported" instead of executing — the meaningful RED failure was impossible.

4. **`apps/api/tests/conftest.py`** (exact content from brief)
   - Sets `DATABASE_URL` env var to a temp sqlite file BEFORE importing `src.database`/`src.main`, provides session-scoped `_setup_db` (runs `init_db()`) and per-test `client` fixture (httpx `ASGITransport`).

5. **`apps/api/tests/test_memory.py`** (exact content from brief, ASCII-only literals)

## What I tested and results

- Focused: `..\..\.venv\Scripts\python.exe -m pytest tests/test_memory.py -v` → **2 passed**
- Full api suite: `..\..\.venv\Scripts\python.exe -m pytest -v` → **2 passed** (only these 2 tests exist)
- Manual smoke: `/remember` returns `{"status":"success","id":1}`; `/status/opencode` and `/memory/status/p` both return readable text; `/recall/p` and `/memory/recall/p` still return full rows including `id`. No regressions.

## TDD Evidence

### RED (first attempt — asyncio STRICT mode, wrong reason)
Command: `..\..\.venv\Scripts\python.exe -m pytest tests/test_memory.py -v`
```
tests/test_memory.py::test_remember_returns_id FAILED
tests/test_memory.py::test_status_returns_readable_text FAILED
Error: async def functions are not natively supported.
```
Expected: meaningful KeyError/raw-JSON failures. Actual: pytest-asyncio STRICT mode refused to run async tests. Root cause: no `asyncio_mode` config. Fixed by adding `asyncio_mode = "auto"` to pyproject.toml.

### RED (after config fix — correct reason)
Command: `..\..\.venv\Scripts\python.exe -m pytest tests/test_memory.py -v`
```
tests/test_memory.py::test_remember_returns_id FAILED  -> KeyError: 'id'
tests/test_memory.py::test_status_returns_readable_text FAILED -> assert 404 == 200
```
- `KeyError: 'id'`: expected — old `save_memory` returned no id.
- `404`: route `/status/opencode` did not exist (router is `/memory`-prefixed); the brief's router-only code would NOT satisfy its own test at the top-level path. Resolved by adding the backward-compat route in `main.py`.

### GREEN
Command: `..\..\.venv\Scripts\python.exe -m pytest tests/test_memory.py -v`
```
2 passed, 2 warnings in 0.17s
```

## Files changed (commit 332ff13)

- `apps/api/src/routers/memory.py` (fix)
- `apps/api/src/main.py` (backward-compat `/status/{project}` route)
- `apps/api/pyproject.toml` (`asyncio_mode = "auto"`)
- `apps/api/tests/conftest.py` (new)
- `apps/api/tests/test_memory.py` (new)

## Self-review findings

- `mem.id` is read after `commit()`; correct because `expire_on_commit=False` in `database.py` (`async_sessionmaker(..., expire_on_commit=False)`).
- `_readable` handles malformed JSON via `json.JSONDecodeError`/`TypeError` catch and returns raw content — no crash on legacy rows.
- Backward-compat routes still pass `db` positionally, matching `save_memory(entry, db)` / `get_memory(project, limit, db)` / `get_status(project, db)` signatures.
- `import json` added at top of `memory.py`; no unused-import regressions introduced by me (`HTTPException` unused import is pre-existing).
- Tests use a temp DB (mkdtemp); the real `~/Apps/EstudioHC-Memory-Suite/data/estudiohc.db` is never touched. Verified.
- DeprecationWarning on `@app.on_event("startup")` is pre-existing, unrelated.

## Concerns

- **Deviation from brief's file list:** I committed `main.py` and `pyproject.toml` in addition to the brief's `memory.py` + `tests/`. Both were strictly required: without `asyncio_mode=auto` the tests cannot execute (STRICT mode), and without the top-level `/status/{project}` route the brief's own test hits a 404 (brief's router code mounts `/memory/status/{project}`). Both changes follow existing repo patterns.
- **Route duplication:** `/status/{project}` now exists both at top level (main.py) and under `/memory` (router). Intentional — primary API under `/memory/*`, top-level for backward compatibility, same as `/remember`/`/recall`. A later consolidation task may want to dedupe.
- Later task will expand conftest (API_KEY auth + CI); I intentionally did NOT add those (YAGNI per brief).
