"""EstudioHC Memory MCP Server — SSE/HTTP Transport (for remote omp/clients)."""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
import httpx
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from summarizer import summarize as llm_summarize
import embedder as vec_store
import chroma_client as chroma

# ─── Config ──────────────────────────────────────────────────────────────
MEMORY_API_URL = os.getenv("MEMORY_API_URL", "https://127.0.0.1:5050")
MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "")
AGENT_NAME = os.getenv("AGENT_NAME", "opencode")
SUMMARIZE_THRESHOLD = int(os.getenv("MEMORY_SUMMARIZE_THRESHOLD", "60"))
MAX_INJECT = int(os.getenv("MEMORY_MAX_INJECT", "3"))
DECAY_DAYS = int(os.getenv("MEMORY_DECAY_DAYS", "30"))
HYBRID_RRF_K = int(os.getenv("HYBRID_RRF_K", "60"))
PROJECT_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
MEMORY_MAX_TOKENS = int(os.getenv("MEMORY_MAX_TOKENS", "2048"))
MEMORY_INJECT_TOKENS = int(os.getenv("MEMORY_INJECT_TOKENS", "1024"))

HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "5051"))

def _validar_project(project: str) -> str:
    if not project or not PROJECT_RE.fullmatch(project):
        raise ValueError(f"project inválido: {project!r}")
    return project

def count_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)

# ─── MCP Server ──────────────────────────────────────────────────────────
server = Server("estudiohc-memory")

class WorkingMemory:
    """Working Memory persistida em disco (JSON) para sobreviver a restarts."""
    WM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".working_memory.json")

    def __init__(self):
        self._items = []
        self._load()

    def _load(self):
        try:
            with open(self.WM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._items = data
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[memory] WM load falhou (usa vazia): {e}", file=sys.stderr)

    def _persist(self):
        try:
            with open(self.WM_FILE, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"[memory] WM persist falhou: {e}", file=sys.stderr)

    def push(self, content: str, category: str = "context") -> int:
        tokens = count_tokens(content)
        self._items.append({
            "content": content,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat()[:19],
            "tokens": tokens,
        })
        total = self._total_tokens()
        while total > MEMORY_MAX_TOKENS and len(self._items) > 1:
            removed = self._items.pop(0)
            total -= removed["tokens"]
            print(f"[memory] WM budget {MEMORY_MAX_TOKENS} exceeded, dropped oldest ({removed[tokens]} tok)", file=sys.stderr)
        self._persist()
        return len(self._items)

    def _total_tokens(self) -> int:
        return sum(i.get("tokens", count_tokens(i["content"])) for i in self._items)

    def pop(self):
        item = self._items.pop() if self._items else None
        self._persist()
        return item

    def list(self) -> list:
        return list(self._items)

    def clear(self, category: str = "") -> int:
        if category:
            before = len(self._items)
            self._items = [i for i in self._items if i["category"] != category]
            removed = before - len(self._items)
        else:
            removed = len(self._items)
            self._items = []
        self._persist()
        return removed

    def consolidate(self, category: str = "") -> list:
        to_persist = self._items[:]
        if category:
            to_persist = [i for i in to_persist if i["category"] == category]
        self._items = [i for i in self._items if i not in to_persist]
        self._persist()
        return to_persist


wm = WorkingMemory()

# ─── Helpers (copied from stdio version) ────────────────────────────────
def extract_text(m: dict) -> str:
    raw = m.get("content", "")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "s" in parsed:
            return parsed["s"]
    except (json.JSONDecodeError, TypeError):
        pass
    return raw

async def call_api(method: str, path: str, json_data: dict | None = None) -> dict | list:
    headers = {}
    if MEMORY_API_KEY:
        headers["X-API-Key"] = MEMORY_API_KEY
    async with httpx.AsyncClient(base_url=MEMORY_API_URL, timeout=30.0, verify=False) as client:
        resp = await client.request(method, path, json=json_data, headers=headers)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

def score_memory(m: dict, query: str = "", category_filter: str = "") -> float:
    ts_str = m.get("timestamp", "")
    cat = m.get("category", "")
    try:
        ts_fixed = ts_str.replace("Z", "+00:00") if "Z" in ts_str else ts_str
        if "." in ts_fixed and ts_fixed.count(":") == 1:
            ts_fixed = ts_fixed.replace(" ", "T")
        dt = datetime.fromisoformat(ts_fixed)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    age_days = (now - dt).total_seconds() / 86400
    if age_days > DECAY_DAYS * 2:
        decay = 0.0
    elif age_days > DECAY_DAYS:
        decay = 0.3 * (1 - (age_days - DECAY_DAYS) / DECAY_DAYS)
    else:
        decay = 1.0 - (age_days / DECAY_DAYS) * 0.4
    text = extract_text(m).lower()
    kw_score = 0.0
    if query:
        q_terms = set(query.lower().split())
        t_terms = set(text.split())
        if q_terms:
            kw_score = len(q_terms & t_terms) / len(q_terms)
    cat_score = 1.0 if not category_filter or cat == category_filter else 0.0
    return (0.4 * (1 - decay)) + (0.35 * kw_score) + (0.25 * cat_score)

# ─── Tool Definitions ────────────────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # Working Memory
        Tool(name="wm_push", description="Push item to working memory (volatile, session-scoped)",
             inputSchema={"type": "object", "properties": {
                 "content": {"type": "string", "description": "Content to store"},
                 "category": {"type": "string", "description": "Category (default: context)", "default": "context"},
             }, "required": ["content"]}),
        Tool(name="wm_pop", description="Pop last item from working memory",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="wm_list", description="List all working memory items",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="wm_clear", description="Clear working memory (optionally by category)",
             inputSchema={"type": "object", "properties": {
                 "category": {"type": "string", "description": "Optional category to clear"},
             }}),
        Tool(name="wm_consolidate", description="Move working memory items to long-term memory (persist)",
             inputSchema={"type": "object", "properties": {
                 "category": {"type": "string", "description": "Optional category to consolidate"},
             }}),
        # Long-term Memory (via API)
        Tool(name="add_memory", description="Add a long-term memory entry (persists to central API)",
             inputSchema={"type": "object", "properties": {
                 "content": {"type": "string", "description": "Memory content"},
                 "project": {"type": "string", "description": "Project name", "default": "opencode"},
                 "category": {"type": "string", "description": "Category", "default": "context"},
             }, "required": ["content"]}),
        Tool(name="search_memory", description="Search long-term memories (hybrid: recency + keyword + FAISS)",
             inputSchema={"type": "object", "properties": {
                 "query": {"type": "string", "description": "Search query"},
                 "project": {"type": "string", "description": "Project name", "default": "opencode"},
                 "limit": {"type": "integer", "description": "Max results", "default": 10},
                 "category": {"type": "string", "description": "Optional category filter"},
             }, "required": ["query"]}),
        Tool(name="get_status", description="Get project status (pending/completed tasks)",
             inputSchema={"type": "object", "properties": {
                 "project": {"type": "string", "description": "Project name", "default": "opencode"},
             }}),
        # Vector/Document tools (ChromaDB)
        Tool(name="doc_add", description="Add document to vector store (ChromaDB)",
             inputSchema={"type": "object", "properties": {
                 "project": {"type": "string", "description": "Project/collection name", "default": "opencode"},
                 "documents": {"type": "array", "items": {"type": "object", "properties": {
                     "text": {"type": "string"},
                     "id": {"type": "string"},
                     "metadata": {"type": "object"},
                 }, "required": ["text"]}},
             }, "required": ["documents"]}),
        Tool(name="doc_search", description="Search documents by semantic similarity",
             inputSchema={"type": "object", "properties": {
                 "project": {"type": "string", "description": "Project/collection name", "default": "opencode"},
                 "query": {"type": "string", "description": "Search query"},
                 "n_results": {"type": "integer", "default": 5},
                 "filter_metadata": {"type": "object"},
             }, "required": ["project", "query"]}),
        Tool(name="doc_list", description="List documents in a project",
             inputSchema={"type": "object", "properties": {
                 "project": {"type": "string", "description": "Project name", "default": "opencode"},
                 "limit": {"type": "integer", "default": 20},
             }}),
        Tool(name="doc_delete", description="Delete a document by ID",
             inputSchema={"type": "object", "properties": {
                 "project": {"type": "string", "description": "Project name", "default": "opencode"},
                 "id": {"type": "string"},
                 "metadata": {"type": "object"},
             }, "required": ["id"]}),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    if arguments is None:
        arguments = {}
    try:
        # ─── Working Memory ──────────────────────────────────────────────
        if name == "wm_push":
            cnt = wm.push(arguments["content"], arguments.get("category", "context"))
            return [TextContent(type="text", text=f"Working memory: {cnt} items (pushed)")]
        elif name == "wm_pop":
            item = wm.pop()
            if item is None:
                return [TextContent(type="text", text="Working memory empty.")]
            return [TextContent(type="text", text=json.dumps(item, ensure_ascii=False))]
        elif name == "wm_list":
            items = wm.list()
            if not items:
                return [TextContent(type="text", text="Working memory empty.")]
            lines = [f"[{i['timestamp']}] ({i['category']}) {i['content'][:120]}" for i in items]
            return [TextContent(type="text", text="\n".join(lines))]
        elif name == "wm_clear":
            count = wm.clear(arguments.get("category", ""))
            return [TextContent(type="text", text=f"Cleared {count} items.")]
        elif name == "wm_consolidate":
            items = wm.consolidate(arguments.get("category", ""))
            if not items:
                return [TextContent(type="text", text="Nothing to consolidate.")]
            for it in items:
                await call_api("POST", "/remember", {
                    "agent_name": AGENT_NAME,
                    "project": "opencode",
                    "category": it.get("category", "context"),
                    "content": it["content"],
                })
            return [TextContent(type="text", text=f"Consolidated {len(items)} items to long-term memory.")]

        # ─── Long-term Memory (API) ─────────────────────────────────────
        elif name == "add_memory":
            project = _validar_project(arguments.get("project", "opencode"))
            await call_api("POST", "/remember", {
                "agent_name": AGENT_NAME,
                "project": project,
                "category": arguments.get("category", "context"),
                "content": arguments["content"],
            })
            return [TextContent(type="text", text=f"Memory added to [{project}].")]
        elif name == "search_memory":
            project = _validar_project(arguments.get("project", "opencode"))
            query = arguments["query"]
            limit = min(arguments.get("limit", 10), 50)
            category = arguments.get("category", "")
            data = await call_api("GET", f"/recall/{project}?limit={limit * 3}")
            if not data:
                return [TextContent(type="text", text=f"No memories in [{project}].")]
            scored = [(m, score_memory(m, query, category)) for m in data]
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:limit]
            if not top:
                return [TextContent(type="text", text="No matching memories.")]
            lines = [f"--- Top {len(top)} memories for '{query}' in [{project}] ---"]
            for m, sc in top:
                cat = m.get("category", "")
                ts = m.get("timestamp", "")
                txt = extract_text(m)[:200].replace("\n", " ")
                lines.append(f"[{ts}] ({cat}) score={sc:.3f} {txt}")
            return [TextContent(type="text", text="\n".join(lines))]
        elif name == "get_status":
            project = _validar_project(arguments.get("project", "opencode"))
            data = await call_api("GET", f"/memory/status/{project}")
            pending = data.get("pending", ["Nenhuma"])
            completed = data.get("completed", ["Nenhuma"])
            return [TextContent(type="text", text=(
                f"Status do Projeto {project}:\n"
                f"- Pendentes: {', '.join(pending)}\n"
                f"- Concluídas: {', '.join(completed)}"
            ))]

        # ─── Vector/Doc Tools (ChromaDB) ────────────────────────────────
        elif name == "doc_add":
            project = _validar_project(arguments.get("project", "opencode"))
            docs = arguments["documents"]
            await asyncio.to_thread(chroma.doc_add, project, docs)
            return [TextContent(type="text", text=f"Added {len(docs)} documents to [{project}].")]
        elif name == "doc_search":
            project = _validar_project(arguments.get("project", "opencode"))
            data = await asyncio.to_thread(chroma.doc_search, project, arguments["query"],
                                           arguments.get("n_results", 5), arguments.get("filter_metadata", {}))
            docs = data.get("documents", [])
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
            project = _validar_project(arguments.get("project", "opencode"))
            limit = min(arguments.get("limit", 20), 100)
            data = await asyncio.to_thread(chroma.doc_list, project, limit)
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
            project = _validar_project(arguments.get("project", "opencode"))
            doc_id = arguments["id"]
            meta = arguments.get("metadata", {}) or {}
            if meta.get("owner") and meta["owner"] != AGENT_NAME:
                raise ValueError("Sem permissão para apagar este documento")
            info = await asyncio.to_thread(chroma.doc_delete, project, doc_id)
            return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False))]
        else:
            raise ValueError(f"Unknown tool: {name}")

    except httpx.HTTPStatusError as e:
        return [TextContent(type="text", text=f"Memory API error: {e.response.status_code} - {e.response.text}")]
    except httpx.RequestError as e:
        return [TextContent(type="text", text=f"Memory API unavailable ({MEMORY_API_URL}). Is EstudioHC Memory Suite running?")]
    except asyncio.TimeoutError:
        return [TextContent(type="text", text=f"Operation timed out while connecting to Memory API ({MEMORY_API_URL}).")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]

# ─── SSE App ─────────────────────────────────────────────────────────────
sse = SseServerTransport("/messages/")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        read_stream, write_stream = streams
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="estudiohc-memory",
                server_version="4.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

async def handle_messages(scope, receive, send):
    # handle_post_message envia a resposta ASGI internamente (retorna None);
    # registrado como app ASGI cru (Mount), nao como endpoint HTTP.
    await sse.handle_post_message(scope, receive, send)

app = Starlette(debug=False, routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=handle_messages),
])

# ─── Startup: rebuild FAISS index ───────────────────────────────────────
async def rebuild_vector_index():
    try:
        result = await call_api("GET", "/recall/opencode?limit=200")
        if result:
            texts = []
            for m in result:
                mid = f"{m.get('id', '')}|{m.get('category', '')}"
                text = extract_text(m)
                if text:
                    texts.append((mid, text))
            if texts:
                await asyncio.to_thread(vec_store.rebuild, texts)
                vs = vec_store.status()
                print(f"[memory] FAISS index rebuilt: {vs['index_size']} vectors", file=sys.stderr)
    except Exception as e:
        print(f"[memory] FAISS rebuild skipped: {e} — vector search disabled. Memory API still works.", file=sys.stderr)

# ─── Entry Point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    # Run index rebuild before starting server
    asyncio.run(rebuild_vector_index())
    print(f"[memory] Starting EstudioHC MCP SSE on {HOST}:{PORT}/sse", file=sys.stderr)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
