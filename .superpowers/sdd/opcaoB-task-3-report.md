# Task 3 Report: doc_add/doc_search/doc_list/doc_delete tools

## Status

DONE

## Commit

- Hash: `ac16b80`
- Message: `feat(mcp-memory): doc_add/doc_search/doc_list/doc_delete tools backed by ChromaDB`
- Branch: `feat/doc-layer-chromadb`

## Changes

`apps/mcp-memory/src/memory_server.py` (+97 lines, transcribed verbatim from the brief):

1. **Import** — added `import chroma_client as chroma` immediately after `import embedder as vec_store` (line 17).
2. **`handle_list_tools`** — added 4 `Tool` definitions (`doc_add`, `doc_search`, `doc_list`, `doc_delete`) after the `consolidate` entry, before the closing `]`.
3. **`handle_call_tool`** — added 4 `elif` branches (`doc_add`, `doc_search`, `doc_list`, `doc_delete`) before the final `else: raise ValueError(...)`.

The 6 existing tools (add_memory, search_memory, get_status, wm_push/pop/list/clear, consolidate) are untouched.

## Verification

- **COMPILE_OK** — copied `chroma_client.py` + `memory_server.py` to server via scp, ran `py_compile src/chroma_client.py src/memory_server.py` in the mcp-memory venv: `COMPILE_OK` confirmed. No service restarted.
- **CR count = 0** — normalized working file to LF before commit; `[regex]::Matches(..., "`r").Count` = 0; committed blob (`git show HEAD:...`) also has 0 CR bytes.
- Diff contains only the 97 added lines (no modifications to existing code).
- Working tree untracked remains only `.superpowers/` and `docs/` (not committed).

## Concerns

- Pre-existing pyright diagnostics (`inputSchema` vs `input_schema`, `Server.list_tools` attribute) appear for existing AND new tools; they predate this change and are irrelevant to `py_compile`/runtime.
- Git warns "LF will be replaced by CRLF the next time Git touches it" — expected with `core.autocrlf=true`; committed blob is LF.
- The server's `src/` now contains copies of `chroma_client.py` and the modified `memory_server.py` (identical to the repo). Nothing was restarted; Task 4 deploys cleanly.
