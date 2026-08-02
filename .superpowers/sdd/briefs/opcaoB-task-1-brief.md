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

- [ ] **Step 4: Verify local file is LF, deploy to production + restart**

The file at `apps\chromadb-mcp\server.py` (from Step 1 scp) should already be LF (server files are LF). Verify CR count is 0:
```powershell
$c = Get-Content -Raw "C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite\apps\chromadb-mcp\server.py"; [regex]::Matches($c, "`r").Count
```
Expected: `0`. If CR count > 0, strip CR with a byte-safe rewrite, e.g.:
```powershell
$b = [System.IO.File]::ReadAllBytes($p); $s = [System.Text.Encoding]::UTF8.GetString($b) -replace "`r`n", "`n"; [System.IO.File]::WriteAllText($p, $s, (New-Object System.Text.UTF8Encoding $false))
```
Then scp to server, restart service:
```powershell
scp -o ConnectTimeout=10 "C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite\apps\chromadb-mcp\server.py" deploy@100.64.117.78:/tmp/server.py
ssh deploy@100.64.117.78 "cp /tmp/server.py ~/.agents/mcp-servers/chromadb-mcp/server.py && grep -c $'\r' ~/.agents/mcp-servers/chromadb-mcp/server.py; sudo systemctl restart chromadb-mcp.service && sleep 2 && systemctl is-active chromadb-mcp.service"
```
Expected: grep prints `0` (CR count), then `active`.

Verify tools listed via SSE handshake on the server (8 tools: list_collections, create_collection, delete_collection, add_documents, search_documents, get_collection_info, delete_documents, get_documents). A single Python check on the server:
```bash
cd ~/.agents/mcp-servers/chromadb-mcp && ./.venv/bin/python -c "import ast; t=ast.parse(open('server.py').read()); src=open('server.py').read(); assert src.count('delete_documents')>=3 and src.count('get_documents')>=3, 'tools missing'; print('TOOLS_OK')"
```

- [ ] **Step 5: Commit**

```bash
git add apps/chromadb-mcp/server.py
git commit -m "feat(chromadb-mcp): add delete_documents and get_documents tools (versioned copy)"
```

---


