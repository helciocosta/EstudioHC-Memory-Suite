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
from mcp.server.stdio import stdio_server

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from summarizer import summarize as llm_summarize
import embedder as vec_store

MEMORY_API_URL = os.getenv("MEMORY_API_URL", "http://localhost:5050")
MEMORY_API_KEY = os.getenv("MEMORY_API_KEY", "")
SUMMARIZE_THRESHOLD = int(os.getenv("MEMORY_SUMMARIZE_THRESHOLD", "60"))
MAX_INJECT = int(os.getenv("MEMORY_MAX_INJECT", "3"))
DECAY_DAYS = int(os.getenv("MEMORY_DECAY_DAYS", "30"))
HYBRID_RRF_K = int(os.getenv("HYBRID_RRF_K", "60"))

# Token budget enforcement
MEMORY_MAX_TOKENS = int(os.getenv("MEMORY_MAX_TOKENS", "2048"))
MEMORY_INJECT_TOKENS = int(os.getenv("MEMORY_INJECT_TOKENS", "1024"))


def count_tokens(text: str) -> int:
    """Estimate token count. Uses ~4 chars/token heuristic (no heavy deps)."""
    if not text:
        return 0
    # Conservative estimate for mixed PT/EN text: ~4 chars per token
    return max(1, len(text) // 4)

server = Server("opencode-memory")


class WorkingMemory:
    def __init__(self):
        self._items = []

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
            print(f"[memory] WM budget {MEMORY_MAX_TOKENS} exceeded, dropped oldest ({removed['tokens']} tok)",
                  file=sys.stderr)
        return len(self._items)

    def _total_tokens(self) -> int:
        return sum(i.get("tokens", count_tokens(i["content"])) for i in self._items)

    def pop(self) -> dict:
        return self._items.pop() if self._items else None

    def list(self) -> list:
        return list(self._items)

    def clear(self, category: str = "") -> int:
        if category:
            before = len(self._items)
            self._items = [i for i in self._items if i["category"] != category]
            return before - len(self._items)
        else:
            count = len(self._items)
            self._items = []
            return count

    def consolidate(self, category: str = "") -> list:
        to_persist = self._items[:]
        if category:
            to_persist = [i for i in to_persist if i["category"] == category]
        self._items = [i for i in self._items if i not in to_persist]
        return to_persist


wm = WorkingMemory()


def extract_text(m: dict) -> str:
    raw = m.get("content", "")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "s" in parsed:
            return parsed["s"]
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


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
        terms = [t for t in query.lower().split() if len(t) > 2]
        if terms:
            matches = sum(1 for t in terms if t in text)
            kw_score = matches / len(terms)

    cat_score = 1.0
    if category_filter and category_filter != "context":
        cat_score = 3.0 if cat == category_filter else 0.5

    score = decay * 0.4 + kw_score * 0.35 + cat_score * 0.25
    return round(score, 4)


async def call_api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    if MEMORY_API_KEY:
        headers["X-API-Key"] = MEMORY_API_KEY
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.request(method, f"{MEMORY_API_URL}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()


def summarize_blocking(text: str) -> str:
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(llm_summarize, text)
            return future.result(timeout=35)
    except Exception as e:
        print(f"[memory] summarize failed: {e}", file=sys.stderr)
        return text


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="add_memory",
            description="Store persistent information. Use to remember decisions, user preferences, or project context between sessions. Content is automatically compressed via LLM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The information to remember"},
                    "project": {"type": "string", "description": "Project context", "default": "opencode"},
                    "category": {
                        "type": "string",
                        "description": "Category: task_pending, task_completed, decision, preference, context, note",
                        "default": "context",
                    },
                    "skip_summarize": {
                        "type": "boolean",
                        "description": "If true, stores raw content without LLM summarization",
                        "default": False,
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="search_memory",
            description="Search persistent memories by project. Results are ranked by recency and relevance to query. Only top-ranked entries are returned.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project to search", "default": "opencode"},
                    "query": {"type": "string", "description": "Keywords to match in memories for relevance ranking", "default": ""},
                    "category": {"type": "string", "description": "Filter by category (task_pending, task_completed, decision, preference, context, note)", "default": ""},
                    "limit": {"type": "integer", "description": "Max results (1-15)", "default": 3, "minimum": 1, "maximum": 15},
                    "include_raw": {"type": "boolean", "description": "Include full original content if available", "default": False},
                    "days": {"type": "integer", "description": "Only memories newer than this many days", "default": 0},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_status",
            description="Get summarized status of pending and completed tasks for a project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project to check", "default": "opencode"},
                },
                "required": [],
            },
        ),
        Tool(
            name="wm_push",
            description="Add an item to volatile working memory (session-scoped, not persistent). Use for current task context that doesn't need permanent storage yet.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Working memory content"},
                    "category": {"type": "string", "description": "Category", "default": "context"},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="wm_pop",
            description="Remove and return the most recent item from working memory.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="wm_list",
            description="List all items currently in working memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category", "default": ""},
                },
                "required": [],
            },
        ),
        Tool(
            name="wm_clear",
            description="Clear working memory. Optionally filter by category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Only clear items of this category", "default": ""},
                },
                "required": [],
            },
        ),
        Tool(
            name="consolidate",
            description="Move items from working memory to persistent long-term memory. Items are summarized via LLM before storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Target project", "default": "opencode"},
                    "category": {"type": "string", "description": "Only consolidate items of this category", "default": ""},
                    "skip_summarize": {"type": "boolean", "description": "Skip LLM summarization", "default": False},
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "add_memory":
            content = arguments["content"]
            project = arguments.get("project", "opencode")
            category = arguments.get("category", "context")
            skip_summarize = arguments.get("skip_summarize", False)

            if skip_summarize or len(content) < SUMMARIZE_THRESHOLD:
                summary = content
                raw = ""
            else:
                summary = await asyncio.to_thread(summarize_blocking, content)
                raw = content if len(content) > len(summary) * 1.3 else ""

            payload = {
                "agent_name": "opencode",
                "project": project,
                "category": category,
                "content": json.dumps({
                    "s": summary,
                    "r": raw if raw else None,
                    "c": True,
                }, ensure_ascii=False),
            }
            result = await call_api("POST", "/remember", json=payload)
            mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            memory_id = f"{mem_id}|{category}"
            vec_text = summary or content
            await asyncio.to_thread(vec_store.add, vec_text, memory_id)

            suffix = f" (summarized: {len(summary)} vs {len(content)} chars)" if raw else ""
            return [TextContent(type="text", text=f"Memory saved in [{project}]{suffix}")]

        elif name == "search_memory":
            project = arguments.get("project", "opencode")
            query = arguments.get("query", "")
            category_filter = arguments.get("category", "")
            limit = min(arguments.get("limit", MAX_INJECT), 15)
            include_raw = arguments.get("include_raw", False)
            max_days = arguments.get("days", 0)

            result = await call_api("GET", f"/recall/{project}?limit=50")
            if not result:
                return [TextContent(type="text", text=f"No memories found for [{project}].")]

            mem_by_id = {}
            for m in result:
                mem_id = f"{m.get('id', '')}|{m.get('category', '')}"
                mem_by_id[mem_id] = m

            if category_filter:
                result = [m for m in result if m.get("category", "") == category_filter]

            filtered = []
            for m in result:
                if max_days > 0:
                    try:
                        ts = m.get("timestamp", "")
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00") if "Z" in ts else ts)
                        age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
                        if age > max_days:
                            continue
                    except (ValueError, TypeError):
                        pass
                kw_score = score_memory(m, query, category_filter)
                if kw_score > 0:
                    filtered.append((kw_score, m))

            if not filtered:
                return [TextContent(type="text", text=f"No matching memories for [{project}].")]

            filtered.sort(key=lambda x: x[0], reverse=True)
            kw_ranked = [m for _, m in filtered]

            vec_ranked = await asyncio.to_thread(vec_store.search, query, len(filtered))
            vec_rank_map = {mid: rank for rank, (mid, _) in enumerate(vec_ranked)}

            scored = []
            for rank_kw, m in enumerate(kw_ranked):
                mem_id = f"{m.get('id', '')}|{m.get('category', '')}"
                rrf_kw = 1.0 / (HYBRID_RRF_K + rank_kw + 1)
                if mem_id in vec_rank_map:
                    rrf_vec = 1.0 / (HYBRID_RRF_K + vec_rank_map[mem_id] + 1)
                else:
                    rrf_vec = 0.0
                rrf_score = rrf_kw * 0.4 + rrf_vec * 0.6
                scored.append((rrf_score, m))

            scored.sort(key=lambda x: x[0], reverse=True)

            # Budget-aware truncation: include top result always, then fill within budget
            top = []
            tok_budget = MEMORY_INJECT_TOKENS
            for rrf_score, m in scored:
                text = extract_text(m)
                tok = count_tokens(text)
                if not top:
                    # Always include the top-ranked result
                    top.append((rrf_score, m))
                    tok_budget -= tok
                elif tok <= tok_budget:
                    top.append((rrf_score, m))
                    tok_budget -= tok
                else:
                    continue
                if len(top) >= limit:
                    break

            total_tok = sum(count_tokens(extract_text(m)) for _, m in top)
            lines = [f"--- Top {len(top)}/{len(filtered)} memories for [{project}] ({total_tok}/{MEMORY_INJECT_TOKENS} tok) ---"]
            if query:
                kw_mode = "keyword only" if not vec_ranked else "hybrid (keyword+vector)"
                lines.append(f"    (query: '{query}', mode: {kw_mode})")
            for rrf_score, m in top:
                ts = m["timestamp"][:19]
                cat = m["category"]
                text = extract_text(m)

                if include_raw:
                    raw = m.get("content", "")
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict) and parsed.get("r"):
                            lines.append(f"[{ts}] ({cat}) [{rrf_score:.3f}]\n    {text}\n    raw: {parsed['r']}")
                            continue
                    except (json.JSONDecodeError, TypeError):
                        pass

                lines.append(f"[{ts}] ({cat}) [{rrf_score:.3f}] {text}")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_status":
            project = arguments.get("project", "opencode")
            result = await call_api("GET", f"/status/{project}")
            parts = [f"--- Status for [{project}] ---"]
            if result.get("pending"):
                parts.append("\nPending:")
                for p in result["pending"]:
                    parts.append(f"  * {p}")
            if result.get("completed"):
                parts.append("\nCompleted:")
                for c in result["completed"]:
                    parts.append(f"  / {c}")
            if not result.get("pending") and not result.get("completed"):
                parts.append("No tasks found.")
            return [TextContent(type="text", text="\n".join(parts))]

        elif name == "wm_push":
            content = arguments["content"]
            category = arguments.get("category", "context")
            size = wm.push(content, category)
            return [TextContent(type="text", text=f"Working memory: {size} items now.")]

        elif name == "wm_pop":
            item = wm.pop()
            if item:
                return [TextContent(type="text", text=f"Popped: [{item['category']}] {item['content']}")]
            return [TextContent(type="text", text="Working memory is empty.")]

        elif name == "wm_list":
            category = arguments.get("category", "")
            items = wm.list()
            if category:
                items = [i for i in items if i["category"] == category]
            if not items:
                return [TextContent(type="text", text="Working memory is empty.")]
            total = sum(i.get("tokens", count_tokens(i["content"])) for i in items)
            budget = MEMORY_MAX_TOKENS
            lines = [f"--- Working memory ({len(items)} items, {total}/{budget} tok) ---"]
            for i, item in enumerate(items, 1):
                tok = item.get("tokens", count_tokens(item["content"]))
                lines.append(f"  {i}. [{item['category']}] ({tok} tok) {item['content']}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "wm_clear":
            category = arguments.get("category", "")
            count = wm.clear(category)
            suffix = f" (category: {category})" if category else ""
            return [TextContent(type="text", text=f"Cleared {count} items from working memory{suffix}.")]

        elif name == "consolidate":
            project = arguments.get("project", "opencode")
            category = arguments.get("category", "")
            skip_summarize = arguments.get("skip_summarize", False)

            to_persist = wm.consolidate(category)
            if not to_persist:
                return [TextContent(type="text", text="No items to consolidate.")]

            saved = 0
            for item in to_persist:
                content = item["content"]
                if not skip_summarize and len(content) >= SUMMARIZE_THRESHOLD:
                    content = await asyncio.to_thread(summarize_blocking, content)
                payload = {
                    "agent_name": "opencode",
                    "project": project,
                    "category": item["category"],
                    "content": json.dumps({
                        "s": content,
                        "r": item["content"] if len(item["content"]) > len(content) * 1.3 else None,
                        "c": True,
                    }, ensure_ascii=False),
                }
                try:
                    result = await call_api("POST", "/remember", json=payload)
                    mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                    await asyncio.to_thread(vec_store.add, content, f"{mem_id}|{item['category']}")
                    saved += 1
                except Exception as e:
                    print(f"[memory] consolidate save failed: {e}", file=sys.stderr)

            return [TextContent(type="text", text=f"Consolidated {saved}/{len(to_persist)} items to [{project}].")]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except httpx.HTTPStatusError as e:
        return [TextContent(type="text", text=f"Memory API error: {e.response.status_code} - {e.response.text}")]
    except httpx.RequestError as e:
        return [TextContent(type="text", text=f"Memory API unavailable ({MEMORY_API_URL}). Is EstudioHC Memory Suite running? Error: {e}")]
    except asyncio.TimeoutError:
        return [TextContent(type="text", text=f"Operation timed out while connecting to Memory API ({MEMORY_API_URL}).")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


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
        print(f"[memory] FAISS rebuild skipped: {e}", file=sys.stderr)


async def main():
    try:
        await asyncio.wait_for(rebuild_vector_index(), timeout=30)
    except asyncio.TimeoutError:
        print("[memory] FAISS rebuild timed out (30s) — vector search disabled. Memory API still works.", file=sys.stderr)
    except Exception as e:
        print(f"[memory] FAISS rebuild failed: {e} — vector search disabled. Memory API still works.", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="opencode-memory",
                server_version="1.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
