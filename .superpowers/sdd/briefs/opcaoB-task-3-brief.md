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


