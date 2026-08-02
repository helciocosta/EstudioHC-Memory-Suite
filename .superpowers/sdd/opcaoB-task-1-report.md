# Task 1 Report: Versioned chromadb-mcp server.py + delete_documents / get_documents

**Status:** DONE

## Summary

Created the canonical copy of the production chromadb-mcp server at `apps/chromadb-mcp/server.py`, verified the 2 new tools are present and working, deployed to Contabo, restarted the service, and committed.

## Steps performed

### Step 1 — Fetch production server.py
- `scp deploy@100.64.117.78:~/.agents/mcp-servers/chromadb-mcp/server.py → apps/chromadb-mcp/server.py` (10,038 bytes).
- **Note:** the fetched production file *already contained* both new tools (8 tools total in `list_tools`, both `elif` branches present). The task notes claimed production had 6 tools — either a prior run already applied this change or the note was stale. The fetched content matched the brief's Step 2/Step 3 code **verbatim**, so no edits were needed; the deliverable state was already correct.

### Steps 2/3 — Tools present (verified, no edits needed)
- `Tool(name="delete_documents", ...)` and `Tool(name="get_documents", ...)` after `get_collection_info` in `list_tools` (lines 89–99).
- `elif name == "delete_documents"` and `elif name == "get_documents"` branches before the final `else: unknown` in `call_tool` (lines 158–174).
- All four code blocks byte-identical to the brief.

### Step 4 — LF check, deploy, restart, verify
- Working-tree CR count = **0** (LF).
- Deployed: `scp` → `/tmp/server.py` → `cp` to server path → `sudo systemctl restart chromadb-mcp.service` → `systemctl is-active` → **`active`**.
- Deployed file CR count = **0** (checked on server).
- `md5sum` deployed == `/tmp/server.py` == repo blob == `f4d75b762feb0fdc97795f99bfb9369e`.
- Full MCP stdio handshake via the server venv: `TOOLS(8): ['list_collections','create_collection','delete_collection','add_documents','search_documents','get_collection_info','delete_documents','get_documents']` → `HANDSHAKE_OK`.
- SSE endpoint responds (`event: endpoint` at `http://127.0.0.1:8765/mcp`).

### Step 5 — Commit
- `4a11aea feat(chromadb-mcp): add delete_documents and get_documents tools (versioned copy)`
- Only `apps/chromadb-mcp/server.py` added (230 insertions). `.superpowers/` and `docs/` left untracked, as instructed.

## Verification summary
Tools deployed (8, incl. `delete_documents` + `get_documents`, confirmed via MCP `tools/list`) + service `active` + CR count 0 (working tree, git blob, and deployed file).

## Concerns
1. **Brief's own verification assert was wrong for this code:** the brief's server-side check uses `src.count('delete_documents') >= 3`. The brief's own Step 2/3 code yields exactly **2** occurrences per tool (tool declaration + `elif` branch) — the description text uses "Delete documents"/"Get documents" (no underscore), so `>= 3` can never pass. I used the corrected equivalent: 8 `Tool(name=` declarations + ≥2 occurrences each + `ast.parse`, plus a real JSON-RPC `tools/list` handshake. If later tasks rely on that exact `>=3` assertion, it will fail and should be relaxed to `>= 2`.
2. **`core.autocrlf=true` in the repo:** git emits a warning ("LF will be replaced by CRLF") on checkout for this file. The committed blob is LF (0 CR, md5 matches deployed), which is what the requirement demands, but on a Windows checkout the working copy will come back CRLF. Consider adding a `.gitattributes` (`apps/chromadb-mcp/*.py text eol=lf`) in a future task if Windows working copies must stay LF.
3. **Source-of-truth discrepancy:** production already had the 8-tool file; this task redeployed the identical file and confirmed it's now tracked in the repo. Worth confirming with the orchestrator that no other change (e.g. an earlier partial run) introduced the 2 tools before this task.
