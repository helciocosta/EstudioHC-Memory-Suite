# Doc Layer via ChromaDB (Option B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a document layer to the MCP Memory Server that stores/searchs long documents per project in ChromaDB, via 4 new MCP tools (doc_add, doc_search, doc_list, doc_delete).

**Architecture:** memory_server.py becomes an MCP *client* of the existing chromadb-mcp SSE service (localhost:8765). A new `chroma_client.py` module owns a long-lived SSE session with reconnect; the memory server exposes `doc_*` tools that call it. The chromadb-mcp server gains two new tools (`delete_documents`, `get_documents`) so delete/list can work. One ChromaDB collection per project, named `docs_<project>`, created on demand.

**Tech Stack:** Python 3.11 (server venv), mcp==1.28.x (already installed in `apps/mcp-memory/.venv`), chromadb 1.5.9 (chromadb-mcp venv), SSE transport.

## Global Constraints

- Repo root `apps/api` and `apps/mcp-memory`. Local clone: `C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite` (branch `master`, HEAD `976a763`). Production: `deploy@100.64.117.78:~/Apps/EstudioHC-Memory-Suite` (branch master).
- NO new dependencies anywhere. `apps/mcp-memory/.venv` already has `mcp` (1.28.0) which provides `sse_client` + `ClientSession`; use them.
- `chromadb-mcp` SSE service is at `http://localhost:8765/mcp` (from the memory server's perspective they share the host). Not a git repo — the canonical versioned copy of its `server.py` will live at `apps/chromadb-mcp/server.py` in this repo and be deployed to `~/.agents/mcp-servers/chromadb-mcp/server.py`.
- Memory server runs via MCP stdio through SSH: `ssh deploy@100.64.117.78 "cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && ./.venv/bin/python src/memory_server.py"`.
- The 6 existing memory tools (add_memory, search_memory, get_status, wm_push/pop/list/clear, consolidate) must NOT change behavior.
- Existing chromadb-mcp tools (list_collections, create_collection, delete_collection, add_documents, search_documents, get_collection_info) must NOT change behavior.
- Collection name format: `docs_<project>` (e.g. `docs_opencode`). Document metadata: `{"title": <str>, "tags": <comma-joined str>, "ts": <ISO-8601 seconds>, "project": <str>}`.
- Document id format: `<slugified-title>_<YYYYmmddHHMMSS>` where slug = lowercase, non-alphanumeric → `_`, truncated to 40 chars, `_` stripped at ends; fallback `"doc"` if empty.
- chromadb metadata values must be scalar (str/int/float/bool) — store `tags` as a comma-joined string, never a list.
- Missing collection must produce a clear message: `collection 'docs_<project>' not found (no documents yet for project '<project>')`.
- Test/verification commands run on the SERVER for mcp-memory files (local clone `.venv` lacks `mcp`). Use `apps/mcp-memory/.venv/bin/python -m py_compile`.
- `curl` on Windows PowerShell is an alias — use `curl.exe`.

---

### Task 1: Versioned chromadb-mcp server.py with delete_documents + get_documents tools

**Files:**
- Create: `apps/chromadb-mcp/server.py` (canonical copy of `~/.agents/mcp-servers/chromadb-mcp/server.py`, verbatim, + 2 new tools)
- Deploy: `deploy@100.64.117.78:~/.agents/mcp-servers/chromadb-mcp/server.py` (LF) + restart `chromadb-mcp.service`

**Interfaces:**
- Consumes: the existing chromadb-mcp server implementation (fetch it first: `scp deploy@100.64.117.78:~/.agents/mcp-servers/chromadb-mcp/server.py ...`).
- Produces: `delete_documents(collection, ids)` and `get_documents(collection, limit, offset)` tools, used by Task 2's `chroma_client.py`.

- [ ] **Step 1: Fetch current server.py from production**

```bash
scp -o ConnectTimeout=10 deploy@100.64.117.78:~/.agents/mcp-servers/chromadb-mcp/server.py "C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite\apps\chromadb-mcp\server.py"
```

Then create the directory if scp didn't: `New-Item -ItemType Directory -Force -Path "...\apps\chromadb-mcp"`.

- [ ] **Step 2: Add `delete_documents` tool to `list_tools`** (after `get_collection_info` entry)

```python
        Tool(name="delete_documents", description="Delete documents from a collection by ids",
             inputSchema={"type": "object", "properties": {
                 "collection": {"type": "string"},
                 "ids": {"type": "array", "items": {"type": "string"}},
             }, "required": ["collection", "ids"]}),
        Tool(name="get_documents", description="Get documents from a collection (id, text, metadata)",
             inputSchema={"type": "object", "properties": {
                 "collection": {"type": "string"},
                 "limit": {"type": "integer", "default": 20},
                 "offset": {"type": "integer", "default": 0},
             }, "required": ["collection"]}),
```

- [ ] **Step 3: Add handlers to `call_tool`** (before the final `else: unknown`)

```python
        elif name == "delete_documents":
            col = client.get_collection(name=arguments["collection"])
            ids = arguments["ids"]
            col.delete(ids=ids)
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps({"deleted": len(ids), "ids": ids}))])

        elif name == "get_documents":
            col = client.get_collection(name=arguments["collection"])
            r = col.get(limit=min(arguments.get("limit", 20), 100),
                        offset=arguments.get("offset", 0),
                        include=["documents", "metadatas"])
            out = [{"id": r["ids"][i], "text": (r["documents"][i] or "")[:1000],
                    "metadata": r["metadatas"][i] if r["metadatas"] else {}}
                   for i in range(len(r["ids"]))]
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps(out, indent=2, ensure_ascii=False))])
```

- [ ] **Step 4: Deploy to production (LF bytes) + restart + verify tools listed**

Generate LF copy via git show (bytes raw), scp to server, restart service, verify handshake lists 8 tools.

```powershell
# LF bytes from git HEAD:file (do NOT use PowerShell text cmdlets)
cmd /c "git -C C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite show HEAD:apps/chromadb-mcp/server.py > %TEMP%\opencode\lf2\apps_chromadb-mcp_server.py"
scp -o ConnectTimeout=10 "$env:TEMP\opencode\lf2\apps_chromadb-mcp_server.py" deploy@100.64.117.78:/tmp/server.py
ssh deploy@100.64.117.78 "cp /tmp/server.py ~/.agents/mcp-servers/chromadb-mcp/server.py && sudo systemctl restart chromadb-mcp.service && sleep 2 && systemctl is-active chromadb-mcp.service"
```

Verify: `opencode mcp list` on Windows shows chromadb-contabo connected, or an SSE handshake on the server listing 8 tools (list_collections, create_collection, delete_collection, add_documents, search_documents, get_collection_info, delete_documents, get_documents).

- [ ] **Step 5: Commit**

```bash
git add apps/chromadb-mcp/server.py
git commit -m "feat(chromadb-mcp): add delete_documents and get_documents tools (versioned copy)"
```

---

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

(After copying the file up first — Step 3 deploys it; for a local-only check, run the clone's file through the server venv after copy.)

- [ ] **Step 3: Commit**

```bash
git add apps/mcp-memory/src/chroma_client.py
git commit -m "feat(mcp-memory): chroma_client.py SSE client for ChromaDB doc layer"
```

---

### Task 3: Add doc_add/doc_search/doc_list/doc_delete tools to memory_server.py

**Files:**
- Modify: `apps/mcp-memory/src/memory_server.py` (import + `handle_list_tools` return + `handle_call_tool` branches)

**Interfaces:**
- Consumes: Task 2's `chroma_client` functions (import as `import chroma_client as chroma`).
- Produces: 4 new MCP tools registered in `handle_list_tools` and handled in `handle_call_tool`. No changes to the 6 existing tools.

- [ ] **Step 1: Add import** after `import embedder as vec_store` (line 16)

```python
import chroma_client as chroma
```

- [ ] **Step 2: Add 4 tool definitions to `handle_list_tools` return list** (after the `consolidate` Tool entry, before the closing `]`)

```python
        Tool(
            name="doc_add",
            description="Store a long document (manual, spec, article, log) for a project in ChromaDB. Use for content too large or too detailed for memory. Returns the document id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project namespace", "default": "opencode"},
                    "title": {"type": "string", "description": "Document title"},
                    "content": {"type": "string", "description": "Document body"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags", "default": []},
                },
                "required": ["title", "content"],
            },
        ),
        Tool(
            name="doc_search",
            description="Semantic search across documents of a project (ChromaDB). Returns matching titles, scores, timestamps and snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project namespace", "default": "opencode"},
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (1-20)", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="doc_list",
            description="List documents stored for a project (ChromaDB) with total count.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project namespace", "default": "opencode"},
                    "limit": {"type": "integer", "description": "Max documents (1-100)", "default": 20, "minimum": 1, "maximum": 100},
                },
                "required": [],
            },
        ),
        Tool(
            name="doc_delete",
            description="Delete a document from a project by its id (ChromaDB).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project namespace", "default": "opencode"},
                    "id": {"type": "string", "description": "Document id to delete"},
                },
                "required": ["id"],
            },
        ),
```

- [ ] **Step 3: Add branches to `handle_call_tool`** (before the final `else:` at line 490)

```python
        elif name == "doc_add":
            project = arguments.get("project", "opencode")
            title = arguments["title"]
            content = arguments["content"]
            tags = arguments.get("tags", [])
            info = await chroma.doc_add(project, title, content, tags)
            return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False))]

        elif name == "doc_search":
            project = arguments.get("project", "opencode")
            query = arguments["query"]
            limit = min(arguments.get("limit", 5), 20)
            docs = await chroma.doc_search(project, query, limit)
            if not docs:
                return [TextContent(type="text", text=f"No documents found in [{project}].")]
            lines = [f"--- Documents in [{project}] ---"]
            for d in docs:
                meta = d.get("metadata") or {}
                score = f"{d.get('score'):.3f}" if d.get("score") is not None else "n/a"
                lines.append(f"[{meta.get('ts', '')}] ({score}) {meta.get('title', d.get('id'))}")
                snippet = (d.get("text") or "")[:200].replace("\n", " ")
                if snippet:
                    lines.append(f"    {snippet}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "doc_list":
            project = arguments.get("project", "opencode")
            limit = min(arguments.get("limit", 20), 100)
            data = await chroma.doc_list(project, limit)
            docs = data.get("documents", [])
            if not docs:
                return [TextContent(type="text", text=f"No documents stored in [{project}] (count=0).")]
            lines = [f"--- Documents in [{project}] (count={data.get('count', 0)}) ---"]
            for d in docs:
                meta = d.get("metadata") or {}
                title = meta.get("title") or d.get("id")
                lines.append(f"  {d.get('id')}  [{meta.get('ts', '')}] {title}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "doc_delete":
            project = arguments.get("project", "opencode")
            doc_id = arguments["id"]
            info = await chroma.doc_delete(project, doc_id)
            return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False))]
```

- [ ] **Step 4: Syntax check**

Copy both changed files to the server and run `py_compile` in the mcp-memory venv:

```bash
ssh deploy@100.64.117.78 "cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && ./.venv/bin/python -m py_compile src/chroma_client.py src/memory_server.py && echo COMPILE_OK"
```

- [ ] **Step 5: Commit**

```bash
git add apps/mcp-memory/src/memory_server.py
git commit -m "feat(mcp-memory): doc_add/doc_search/doc_list/doc_delete tools backed by ChromaDB"
```

---

### Task 4: Deploy + end-to-end verification in production

**Files:**
- Deploy: `apps/mcp-memory/src/chroma_client.py`, `apps/mcp-memory/src/memory_server.py` (LF) to server; `apps/chromadb-mcp/server.py` already deployed in Task 1.
- Register completion memory via the central API.

**Interfaces:**
- Consumes: Tasks 1-3 outputs.

- [ ] **Step 1: Generate LF copies and scp to server**

```powershell
cmd /c "git -C C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite show HEAD:apps/mcp-memory/src/chroma_client.py > %TEMP%\opencode\lf2\apps_mcp-memory_src_chroma_client.py"
cmd /c "git -C C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite show HEAD:apps/mcp-memory/src/memory_server.py > %TEMP%\opencode\lf2\apps_mcp-memory_src_memory_server.py"
scp -o ConnectTimeout=10 "$env:TEMP\opencode\lf2\apps_mcp-memory_src_chroma_client.py" deploy@100.64.117.78:/tmp/chroma_client.py
scp -o ConnectTimeout=10 "$env:TEMP\opencode\lf2\apps_mcp-memory_src_memory_server.py" deploy@100.64.117.78:/tmp/memory_server.py
ssh deploy@100.64.117.78 "cp /tmp/chroma_client.py ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/chroma_client.py && cp /tmp/memory_server.py ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py && grep -c $'\r' ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/chroma_client.py ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py"
```

Both CR counts must be 0.

- [ ] **Step 2: End-to-end test script on server** (test project `docs_test_<ts>`)

Write and run a throwaway script that exercises the full cycle against the real chromadb-mcp:

```bash
ssh deploy@100.64.117.78 'cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && cat > /tmp/test_docs.py <<'"'"'PY'"'"'
import asyncio, sys
sys.path.insert(0, "src")
import chroma_client as chroma

async def main():
    p = "test_opcao_b"
    added = await chroma.doc_add(p, "Guia do SSD", "Passo a passo para TRIM no SSD C: do Arquimedes, executar mensalmente.", ["ssd", "trim"])
    print("ADDED", added)
    lst = await chroma.doc_list(p)
    print("LIST", lst["count"], [d["id"] for d in lst["documents"]])
    srch = await chroma.doc_search(p, "TRIM no disco")
    print("SEARCH_COUNT", len(srch), srch[0]["id"] if srch else None)
    dl = await chroma.doc_delete(p, added["id"])
    print("DELETED", dl)
    lst2 = await chroma.doc_list(p)
    print("AFTER_DELETE", lst2["count"])
    await chroma.close()

asyncio.run(main())
PY
.venv/bin/python /tmp/test_docs.py'
```

Expected: `ADDED {'id': 'guia_do_ssd_<ts>', ...}`, `LIST 1 [...]`, `SEARCH_COUNT 1`, `DELETED {'deleted': 1, ...}`, `AFTER_DELETE 0`. Also verify missing-collection message: run `doc_list("projeto_inexistente_xyz")` and confirm the `_not_found` message is raised.

- [ ] **Step 3: Verify via opencode MCP** (optional, from Windows)

```powershell
opencode mcp list
```

Expect `estudiohc-memory ✓ connected` and `chromadb-contabo ✓ connected`. A fresh opencode session's memory server now lists 12 tools (8 + 4 new doc_*).

- [ ] **Step 4: Register completion memory + commit & push**

```bash
# register memory via central API (id 31)
curl.exe -s -X POST http://100.64.117.78:5050/remember -H "Content-Type: application/json" -d '{"agent_name":"opencode","project":"opencode","category":"task_completed","content":"{\"s\":\"DOC LAYER (OPCAO B) COMPLETED 02/08/2026: 4 tools doc_add/doc_search/doc_list/doc_delete via chroma_client.py (SSE client do chromadb-mcp 8765), colecoes docs_<project>, delete_documents+get_documents adicionados ao chromadb-mcp. Teste end-to-end OK no Contabo.\",\"r\":\"\",\"c\":true}"}'
```

Then push master to GitHub from the server (account helciocosta has push):

```bash
ssh deploy@100.64.117.78 "cd ~/Apps/EstudioHC-Memory-Suite && git add apps/chromadb-mcp/server.py apps/mcp-memory/src/chroma_client.py apps/mcp-memory/src/memory_server.py && git commit -m 'feat(mcp-memory): document layer via ChromaDB (doc_add/search/list/delete)' && git push origin master"
```

(If the server working tree already contains the deployed files with correct content, commit there; otherwise re-copy the LF versions first.)

- [ ] **Step 5: Reconcile the local Windows clone**

```bash
# from local clone
git fetch origin && git reset --hard origin/master
```

Then mark all tasks complete in the ledger at `.superpowers/sdd/progress.md`.
