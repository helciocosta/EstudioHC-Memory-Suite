# Task 4 Report — Deploy + end-to-end verification (Doc Layer via ChromaDB, Opção B)

Status: DONE_WITH_CONCERNS

## Step 1 — LF copies + scp (OK)
- Generated LF copies from `git show HEAD:` via `cmd /c` redirection (no CR bytes locally: both files CR=0).
- scp to `/tmp/chroma_client.py`, `/tmp/memory_server.py`; copied into server repo and re-checked:
  - `~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/chroma_client.py` CR=0
  - `~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py` CR=0
- SHA256 match with local repo files: chroma_client `BEF70854...`, memory_server `588F45CA...`.

## Step 2 — End-to-end test (OK, all markers)
Wrote `/tmp/test_docs.py` locally (LF, scp) with sys.path.insert(0,"src") + extra missing-collection check. Ran `cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && .venv/bin/python /tmp/test_docs.py`:

```
ADDED {'id': 'guia_do_ssd_20260802104718', 'collection': 'docs_test_opcao_b', 'added': 1, 'ids': ['guia_do_ssd_20260802104718']}
LIST 1 ['guia_do_ssd_20260802104718']
SEARCH_COUNT 1 guia_do_ssd_20260802104718
DELETED {'deleted': 1, 'collection': 'docs_test_opcao_b', 'id': 'guia_do_ssd_20260802104718'}
AFTER_DELETE 0
NOT_FOUND_OK collection 'docs_projeto_inexistente_xyz' not found (no documents yet for project 'projeto_inexistente_xyz')
```

All expected markers present. Missing-collection message matches the brief's expected wording.

## Step 3 — opencode MCP check (optional, FAILED — non-blocking)
`opencode mcp list` errored: `opencode.exe` at `C:\Users\helci\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe` is "not a valid application for this OS platform" (likely a mismatched npm-shipped binary). Skipped per brief (non-blocking). The real end-to-end proof is Step 2 against the live chromadb-mcp SSE service.

## Step 4 — Memory registration + commit/push (OK)
- Memory registered via `curl.exe --data-binary @file` (direct `-d` was mangled by PowerShell quoting): **id 31**.
- Push from server:
  - Branch `master`, commit `1b5f61a` — `feat(mcp-memory): document layer via ChromaDB (doc_add/search/list/delete)`
  - `3 files changed, 472 insertions(+)` (create chroma_client.py, memory_server.py +97, create apps/chromadb-mcp/server.py)
  - `976a763..1b5f61a master -> master` (remote `git@github.com:helciocosta/EstudioHC-Memory-Suite.git`)

## Step 5 — Reconcile local clone (OK)
- `git fetch origin && git reset --hard origin/master` → local clone now at `1b5f61a`.
- Ledger `.superpowers/sdd/progress.md` appended: `Task 4: complete (deploy + e2e OK, push 1b5f61a)` + all 4 Fase 2 tasks marked complete.

## Concerns
1. **chromadb-mcp not in server repo path**: `~/Apps/EstudioHC-Memory-Suite/apps/chromadb-mcp/` did not exist. The live SSE service runs from `~/.agents/mcp-servers/chromadb-mcp/server.py` (byte-identical to our repo version, SHA `504DC23A...`, service `chromadb-mcp.service` active). I created the repo dir and committed the LF copy so the brief's commit includes it, but the repo now tracks a duplicate of the actually-deployed file. Future maintenance should keep both in sync or move the service to read from the repo.
2. **Step 3 (opencode mcp list) not verifiable** from this Windows shell (binary mismatch). Non-blocking.
3. First `curl -d` attempt returned JSON decode error due to PowerShell argument mangling; resolved with `--data-binary @payload-file` (id 31 registered successfully).
