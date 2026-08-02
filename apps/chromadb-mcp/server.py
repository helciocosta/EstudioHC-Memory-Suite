"""ChromaDB MCP Server - stdio (local) or SSE (remote/Tailscale).
   Set CHROMA_TRANSPORT=sse to run in SSE mode on a port."""
import json
import os
import sys
from typing import Any

import chromadb
from chromadb.utils import embedding_functions
from importlib.metadata import version as _pkg_version
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, ServerCapabilities, TextContent, Tool

DATA_DIR = os.environ.get("CHROMA_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_data"))
HOST = os.environ.get("CHROMA_HOST", "0.0.0.0")
PORT = int(os.environ.get("CHROMA_PORT", "8765"))

_mcp_ver = _pkg_version("mcp")
MCP_MAJOR = int(_mcp_ver.split(".")[0])
MCP_MINOR = int(_mcp_ver.split(".")[1])
MCP_NEW_API = (MCP_MAJOR, MCP_MINOR) >= (1, 28)

os.makedirs(DATA_DIR, exist_ok=True)
client = chromadb.PersistentClient(path=DATA_DIR)

server = Server("chromadb-mcp")

if MCP_NEW_API:
    from mcp.server.models import InitializationOptions
    _init_options = InitializationOptions(
        server_name="chromadb-mcp",
        server_version=_pkg_version("mcp"),
        capabilities=ServerCapabilities(),
    )
else:
    _init_options = None

COLLECTIONS_FILE = os.path.join(DATA_DIR, "collections.json")


def _load_meta() -> dict:
    if os.path.exists(COLLECTIONS_FILE):
        with open(COLLECTIONS_FILE) as f:
            return json.load(f)
    return {}


def _save_meta(data: dict) -> None:
    with open(COLLECTIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@server.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(tools=[
        Tool(name="list_collections", description="List all collections",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="create_collection", description="Create a new collection",
             inputSchema={"type": "object", "properties": {
                 "name": {"type": "string", "description": "Collection name"},
                 "metadata": {"type": "object", "description": "Optional metadata"},
             }, "required": ["name"]}),
        Tool(name="delete_collection", description="Delete a collection",
             inputSchema={"type": "object", "properties": {
                 "name": {"type": "string", "description": "Collection name"},
             }, "required": ["name"]}),
        Tool(name="add_documents", description="Add documents to a collection",
             inputSchema={"type": "object", "properties": {
                 "collection": {"type": "string"},
                 "documents": {"type": "array", "items": {"type": "object",
                     "properties": {
                         "text": {"type": "string"},
                         "id": {"type": "string"},
                         "metadata": {"type": "object"},
                     }, "required": ["text"]}},
             }, "required": ["collection", "documents"]}),
        Tool(name="search_documents", description="Search documents by semantic similarity",
             inputSchema={"type": "object", "properties": {
                 "collection": {"type": "string"},
                 "query": {"type": "string"},
                 "n_results": {"type": "integer", "default": 5},
                 "filter_metadata": {"type": "object"},
             }, "required": ["collection", "query"]}),
        Tool(name="get_collection_info", description="Get collection info",
             inputSchema={"type": "object", "properties": {
                 "name": {"type": "string"},
             }, "required": ["name"]}),
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
    ])


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    try:
        if name == "list_collections":
            cols = client.list_collections()
            meta = _load_meta()
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps([{"name": c.name, "count": c.count(), "metadata": meta.get(c.name, {})}
                                 for c in cols], indent=2))])

        elif name == "create_collection":
            n = arguments["name"]
            m = arguments.get("metadata", {})
            client.create_collection(name=n, metadata=m)
            meta = _load_meta()
            meta[n] = m
            _save_meta(meta)
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps({"status": "created", "name": n}))])

        elif name == "delete_collection":
            client.delete_collection(arguments["name"])
            meta = _load_meta()
            meta.pop(arguments["name"], None)
            _save_meta(meta)
            return CallToolResult(content=[TextContent(type="text",
                text=f"Deleted '{arguments['name']}'")])

        elif name == "add_documents":
            col = client.get_collection(name=arguments["collection"])
            docs = arguments["documents"]
            ids = [d.get("id", f"doc_{i}_{hash(d['text'][:50])}") for i, d in enumerate(docs)]
            texts = [d["text"] for d in docs]
            metas = [d.get("metadata", {}) for d in docs]
            col.add(documents=texts, ids=ids, metadatas=metas)
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps({"added": len(docs), "ids": ids}))])

        elif name == "search_documents":
            col = client.get_collection(name=arguments["collection"])
            r = col.query(query_texts=[arguments["query"]],
                          n_results=min(arguments.get("n_results", 5), 50),
                          where=arguments.get("filter_metadata"))
            out = [{"id": r["ids"][0][i], "text": r["documents"][0][i][:500],
                    "metadata": r["metadatas"][0][i] if r["metadatas"] else {},
                    "score": float(r["distances"][0][i]) if r["distances"] else None}
                   for i in range(len(r["ids"][0]))]
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps(out, indent=2, ensure_ascii=False))])

        elif name == "get_collection_info":
            col = client.get_collection(name=arguments["name"])
            return CallToolResult(content=[TextContent(type="text",
                text=json.dumps({"name": arguments["name"], "count": col.count()}, indent=2))])

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

        else:
            return CallToolResult(content=[TextContent(type="text", text=f"Unknown: {name}")], isError=True)
    except ValueError as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Not found: {e}")], isError=True)
    except Exception as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {e}")], isError=True)


# ---- STDIO mode (default) ----
async def run_stdio():
    async with stdio_server() as streams:
        if MCP_NEW_API:
            read_stream, write_stream = streams
            await server.run(read_stream, write_stream, _init_options)
        else:
            await server.run(streams)


# ---- SSE mode (for Tailscale/Contabo) ----
def run_sse():
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from mcp.server.sse import SseServerTransport

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            if MCP_NEW_API:
                read_stream, write_stream = streams
                await server.run(read_stream, write_stream, _init_options)
            else:
                await server.run(streams)

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)

    app = Starlette(debug=False, routes=[
        Route("/mcp", endpoint=handle_sse),
        Mount("/messages/", routes=[Route("/", endpoint=handle_messages, methods=["POST"])]),
    ])

    import uvicorn
    print(f"ChromaDB MCP SSE listening on {HOST}:{PORT}/mcp  (Tailscale: 100.64.117.78:{PORT}/mcp)")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    import anyio

    transport = os.environ.get("CHROMA_TRANSPORT", "stdio")
    if transport == "sse":
        run_sse()
    else:
        anyio.run(run_stdio)
