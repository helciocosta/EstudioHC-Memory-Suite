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

Expect `estudiohc-memory âœ“ connected` and `chromadb-contabo âœ“ connected`. A fresh opencode session's memory server now lists 12 tools (8 + 4 new doc_*).

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
