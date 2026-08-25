"""ChromaDB MCP SSE client for the memory server's document layer.

Acts as a long-lived MCP *client* of the chromadb-mcp SSE service
(http://localhost:8765/mcp), storing/searching full documents per project
in ChromaDB collections named docs_<project>.
"""
import asyncio
import json
import os
import random
import re
from datetime import datetime, timezone

from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client

CHROMA_MCP_URL = os.getenv("CHROMA_MCP_URL", "http://localhost:8765/mcp")
SSE_TIMEOUT = float(os.getenv("CHROMA_SSE_TIMEOUT", "10"))
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY", "")


def _collection(project: str) -> str:
    return f"docs_{project}"


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().strip())
    slug = slug[:40].strip("_")
    return slug or "doc"


@asynccontextmanager
async def _session_ctx():
    """Sessao SSE efemera, criada e fechada na MESMA task.

    O mcp-python 1.28.1 tem um bug de teardown (cancel scope cruzado) quando a
    sessao SSE e fechada por uma task diferente da que a criou -- o que
    acontecia com a sessao cacheada global quando o FastMCP cancelava a task
    do handler (doc_add etc.), derrubando o processo inteiro. Sessao por
    chamada elimina o caso.
    """
    streams = sse_client(CHROMA_MCP_URL, timeout=SSE_TIMEOUT)
    async with streams as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session

async def close() -> None:
    """No-op mantido por compatibilidade (sessoes agora sao efemeras)."""
    return None

async def _call_tool(name: str, arguments: dict) -> dict:
    if CHROMA_API_KEY:
        arguments = {**arguments, "api_key": CHROMA_API_KEY}
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            async with _session_ctx() as session:
                async with asyncio.timeout(30):
                    result = await session.call_tool(name, arguments)
            text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
            if getattr(result, "isError", False):
                raise ValueError(text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
        except Exception as e:
            last_err = e
            if attempt < 2:
                await asyncio.sleep(0.5 * (2 ** attempt) + random.uniform(0, 0.3))
    raise last_err if last_err else ValueError(f"tool call failed: {name}")


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
