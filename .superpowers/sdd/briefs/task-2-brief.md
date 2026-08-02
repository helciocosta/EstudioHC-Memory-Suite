### Task 2: MCP `memory_server.py` usa o `id` real no indice FAISS

**Files:**
- Modify: `apps/mcp-memory/src/memory_server.py` (`add_memory`) e (`consolidate`)
- Test: verificacao manual no servidor (sem pytest - evita dep. de sentence-transformers)

**Interfaces:**
- Consumes: `/remember` agora retorna `{"status","id"}` (Task 1).
- Produces: `vec_store.add(text, memory_id)` com `memory_id = "{id}|{category}"` consistente com `search_memory`/`rebuild_vector_index`.

**IMPORTANTE (global constraints):** o arquivo `memory_server.py` ja importa `from datetime import datetime, timezone`. Verifique os imports antes de usar. Nao altere mais nada alem do escopo desta task. Nao introduza dependencias novas.

- [ ] **Step 1: `add_memory` - fallback seguro se API antiga nao retornar id**

Substitua a linha que monta `memory_id` dentro de `add_memory` (hoje algo como `memory_id = f"{result.get('id','')}|{category}"`) por:

```python
result = await call_api("POST", "/remember", json=payload)
mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
memory_id = f"{mem_id}|{category}"
vec_text = summary or content
await asyncio.to_thread(vec_store.add, vec_text, memory_id)
```

- [ ] **Step 2: `consolidate` - tambem indexar no FAISS (hoje esquece!)**

Dentro do loop `for item in to_persist` no `consolidate`, substitua o bloco que faz POST /remember (que hoje nao indexa no FAISS) por:

```python
try:
    result = await call_api("POST", "/remember", json=payload)
    mem_id = result.get("id") or f"local_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    await asyncio.to_thread(vec_store.add, content, f"{mem_id}|{item['category']}")
    saved += 1
except Exception as e:
    print(f"[memory] consolidate save failed: {e}", file=sys.stderr)
```

- [ ] **Step 3: Commit**

```bash
git add apps/mcp-memory/src/memory_server.py
git commit -m "fix(mcp-memory): index FAISS with real memory id on add and consolidate"
```
