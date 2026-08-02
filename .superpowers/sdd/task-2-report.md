# Task 2 Report: MCP `memory_server.py` usa o `id` real no indice FAISS

## Status: DONE

## What I implemented

Followed the task brief exactly (Steps 1 and 2), modifying only `apps/mcp-memory/src/memory_server.py`.

**Step 1 — `add_memory` (real id + safe fallback):**

Replaced the `memory_id` construction to use the real id returned by `/remember`, with a safe fallback if the API does not return one:

```python
result = await call_api("POST", "/remember", json=payload)
mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
memory_id = f"{mem_id}|{category}"
vec_text = summary or content
await asyncio.to_thread(vec_store.add, vec_text, memory_id)
```

**Step 2 — `consolidate` (also index FAISS):**

The loop body that previously only POSTed to `/remember` now also indexes into FAISS with the real id:

```python
try:
    result = await call_api("POST", "/remember", json=payload)
    mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    await asyncio.to_thread(vec_store.add, content, f"{mem_id}|{item['category']}")
    saved += 1
except Exception as e:
    print(f"[memory] consolidate save failed: {e}", file=sys.stderr)
```

Consumed Task 1's `/remember` response (`{"status","id"}`) and produced `vec_store.add(text, memory_id)` with `memory_id = "{id}|{category}"`, consistent with `search_memory` and `rebuild_vector_index`.

## What I tested and test results

- `py_compile` (compile-only, avoids the heavy sentence-transformers import):
  - Command: `.\.venv\Scripts\python.exe -m py_compile apps/mcp-memory/src/memory_server.py`
  - Result: **EXIT=0** (no syntax errors)
  - Note: the brief's suggested path `..\..\.venv\Scripts\python.exe` was wrong for this checkout; the venv lives inside the repo at `.venv\Scripts\python.exe`.
- Manual diff review of `git diff` before commit confirmed both changes match the brief verbatim (5 insertions, 3 deletions).
- No pytest exists for this task (avoids sentence-transformers dependency), per the brief.

## Files changed

- `apps/mcp-memory/src/memory_server.py` (only file)

## Self-review findings

- `datetime`/`timezone` already imported at top (`from datetime import datetime, timezone`) — no import changes needed, no new dependencies added.
- `memory_id` format `"{id}|{category}"` is consistent with `search_memory` (lines ~318/350) and `rebuild_vector_index` (line ~503), so hybrid RRF vector lookup will now match entries created by both `add_memory` and `consolidate`.
- `consolidate` indexes the (possibly LLM-summarized) `content` variable, per the brief; the original raw text remains available via `item['content']` in the `r` field of the payload.
- Fallback id format `local_YYYYMMDDHHMMSS` is applied identically in both places.
- No other behavior touched; no refactoring.

## Issues or concerns

- LSP diagnostics surfaced (e.g. `Server.list_tools` unknown, `inputSchema` param) but these are **pre-existing** type-stub noise from the `mcp` package and `WorkingMemory` typing — none are on the edited lines and all exist before this change. No impact on runtime; py_compile passes.
- The `.venv` is inside the repo (`EstudioHC-Memory-Suite/.venv`), not at the path in the task description; used the correct path for verification.
