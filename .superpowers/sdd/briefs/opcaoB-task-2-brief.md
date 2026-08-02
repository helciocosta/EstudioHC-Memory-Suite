### Task 2: Create chroma_client.py (SSE client with reconnect)

**Files:**
- Create: `apps/mcp-memory/src/chroma_client.py`

**Interfaces:**
- Consumes: Task 1's `delete_documents`/`get_documents` and existing chromadb-mcp tools over SSE at `CHROMA_MCP_URL` (default `http://localhost:8765/mcp`).
- Produces: `ensure_collection(project)`, `doc_add(project, title, content, tags)`, `doc_search(project, query, limit)`, `doc_list(project, limit)`, `doc_delete(project, doc_id)`, `close()`. Used by Task 3.

- [ ] **Step 1: Write the module** (`apps/mcp-memory/src/chroma_client.py`)

```python
"""ChromaDB MCP SSE client for the memory server's document layer.

Acts as a long-lived MCP *client* of the chromadb-mcp SSE service
(http://localhost:8765/mcp), storing/searching full documents per project
in ChromaDB collections named docs_<project>.
"""
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

CHROMA_MCP_URL = os.getenv("CHROMA_MCP_URL", "http://localhost:8765/mcp")
SSE_TIMEOUT = float(os.getenv("CHROMA_SSE_TIMEOUT", "10"))

_session: ClientSession | None = None
_streams: Any | None = None
_lock = asyncio.Lock()


def _collection(project: str) -> str:
    return f"docs_{project}"


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().strip())
    slug = slug[:40].strip("_")
    return slug or "doc"


async def _get_session() -> ClientSession:
    global _session, _streams
    async with _lock:
        if _session is not None:
            return _session
        _streams = sse_client(CHROMA_MCP_URL, timeout=SSE_TIMEOUT)
        read_stream, write_stream = await _streams.__aenter__()
        _session = ClientSession(read_stream, write_stream)
        await _session.__aenter__()
        await _session.initialize()
        return _session


async def close() -> None:
    global _session, _streams
    async with _lock:
        if _session is not None:
            await _session.__aexit__(None, None, None)
            _session = None
        if _streams is not None:
            await _streams.__aexit__(None, None, None)
            _streams = None


async def _call_tool(name: str, arguments: dict) -> dict:
    session = await _get_session()
    try:
        result = await session.call_tool(name, arguments)
    except Exception:
        await close()
        session = await _get_session()
        result = await session.call_tool(name, arguments)
    text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    if getattr(result, "isError", False):
        raise ValueError(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _not_found(project: str) -> ValueError:
    return ValueError(
        f"collection '{_collection(project)}' not found (no documents yet for project '{project}')"
    )


async def ensure_collection(project: str) -> str:
    name = _collection(project)
    cols = await _call_tool("list_collections", {})
    names = [c.get("name") for c in cols] if isinstance(cols, list) else []
    if name not in names:
        await _call_tool("create_collection", {"name": name, "metadata": {"project": project}})
    return name


async def doc_add(project: str, title: str, content: str, tags: list | None = None) -> dict:
    name = await ensure_collection(project)
    now = datetime.now(timezone.utc)
    doc_id = f"{_slugify(title)}_{now.strftime('%Y%m%d%H%M%S')}"
    tags_str = ",".join(tags) if tags else ""
    metadata = {
        "title": title,
        "tags": tags_str,
        "ts": now.isoformat()[:19],
        "project": project,
    }
    res = await _call_tool("add_documents", {
        "collection": name,
        "documents": [{"text": content, "id": doc_id, "metadata": metadata}],
    })
    return {"id": doc_id, "collection": name, **res}


async def doc_search(project: str, query: str, limit: int = 5) -> list:
    name = _collection(project)
    try:
        res = await _call_tool("search_documents", {
            "collection": name, "query": query, "n_results": limit,
        })
    except ValueError as e:
        if "not found" in str(e) or "does not exist" in str(e):
            raise _not_found(project)
        raise
    return res if isinstance(res, list) else []


async def doc_list(project: str, limit: int = 20) -> dict:
    name = _collection(project)
    try:
        info = await _call_tool("get_collection_info", {"name": name})
    except ValueError as e:
        if "not found" in str(e) or "does not exist" in str(e):
            raise _not_found(project)
        raise
    docs = await _call_tool("get_documents", {"collection": name, "limit": limit, "offset": 0})
    return {
        "count": info.get("count", 0),
        "documents": docs if isinstance(docs, list) else [],
    }


async def doc_delete(project: str, doc_id: str) -> dict:
    name = _collection(project)
    try:
        res = await _call_tool("delete_documents", {"collection": name, "ids": [doc_id]})
    except ValueError as e:
        if "not found" in str(e) or "does not exist" in str(e):
            raise _not_found(project)
        raise
    return {"deleted": res.get("deleted", 1), "collection": name, "id": doc_id}
```

- [ ] **Step 2: Syntax check on server venv**

```bash
ssh deploy@100.64.117.78 "cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && ./.venv/bin/python -m py_compile /tmp/chroma_client.py"
```

(After copying the file up first â€” Step 3 deploys it; for a local-only check, run the clone's file through the server venv after copy.)

- [ ] **Step 3: Commit**

```bash
git add apps/mcp-memory/src/chroma_client.py
git commit -m "feat(mcp-memory): chroma_client.py SSE client for ChromaDB doc layer"
```

---


