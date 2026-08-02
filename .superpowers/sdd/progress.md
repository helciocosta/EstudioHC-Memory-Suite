# SDD Progress - EstudioHC Memory Stack Fixes

Base: 55e6033
Branch: fix/memory-stack

## Ledger
Task 1: complete (commits 55e6033..332ff13, review clean/Approved)
Task 2: complete (commits 332ff13..41b4295, review clean/Approved)
Task 3: complete (commits 41b4295..eb39ce8, review clean/Approved)

## Minor findings (roll-up p/ final review)
- pyproject.toml declara pytest/pytest-asyncio/httpx como dev deps na Task 6 (esperado, CI cobre). Hoje venv local tem tudo, mas pip install -e limpo quebraria. (T1)
- conftest.py tempfile.mkdtemp nao limpo (hygiene menor). (T1)
- Duplicacao rota /status/{project} top-level + /memory (consistente com /remember e /recall; consolidar em task futura). (T1)
- memory.py e pyproject.toml sem trailing newline (pre-existente, cosmetico). (T1)
- Fallback id FAISS com resolucao de 1s: duas saves no mesmo segundo+categoria geram memory_id identico (prescrito pelo brief, risco de colisao). (T2)
Task 5: complete (commits 50fbf09..d70e647, review clean/Approved)
Minor: rate limiter dict _requests never evicts empty IP deques; timing side-channel x_api_key compare; in-memory per-process rate limit (T5)
Task 6: complete (commits d70e647..cce2467, review clean/Approved)
Minor: Windows temp-dir cleanup no-op (engine lock) — works on CI; pyproject sem trailing newline (T6)

### Final whole-branch review
- Result: READY TO MERGE (no Critical; 2 Important non-blocking for auth-off default deploy, resolve before enabling API_KEY in prod: dashboard static missing X-API-Key header; rate limiter untested + counts before auth)

## Fase 2: Doc Layer via ChromaDB (Opção B)
- Base: 976a763, Branch: feat/doc-layer-chromadb, Plano: docs/superpowers/plans/2026-08-02-doc-layer-chromadb.md

Task 1: complete (commits 976a763..4a11aea, review clean/Approved)
Minor/Important (follow-ups p/ final review): .gitattributes apps/chromadb-mcp/*.py eol=lf (Important, autocrlf=true re-materializa CRLF no Windows); delete_documents reporta deleted=len(ids) mesmo com ids inexistentes (prescrito no brief); get_documents truncates text a 1000 chars sem marker; metadata pode ser null; Chroma get() sem ordenação deterministica; brief assert >=3 insatisfativel (relaxar p/ >=2)

Task 2: complete (commits 4a11aea..c223a36, review clean/Approved)
Important (T2, do plano): _get_session poisons session se __aenter__/initialize falha (if _session is not None shortcut retorna sessao quebrada; close() nao exception-safe); recomendar reset _session/_streams em falha + close seguro. Minor (T2): doc_list traduz not-found so em get_collection_info (race); sem timeout por-request no call_tool; M3 post-reconnect call_tool falha deixa sessao aberta; M4 anotacao -> dict mas json.loads pode retornar list; M6 CRLF-on-checkout sem .gitattributes

Task 3: complete (commits c223a36..ac16b80, review clean/Approved)
Minor (T3): doc_search/doc_list sem clamp inferior de limit (schema-only); erros de colecao inexistente viram 'Error:' generico via except Exception em vez de msg amigavel (comportamento do chroma_client T2)

Task 4: complete (deploy + e2e OK, push 1b5f61a)
Fase 2 all 4 tasks complete: doc layer via ChromaDB deployed + end-to-end verified (doc_add/list/search/delete OK, missing-collection msg NOT_FOUND_OK), completion memory id 31 registered via central API. chromadb-mcp SSE service active (server.py hash-match ~/.agents/mcp-servers/chromadb-mcp/server.py).

### Fase 2 encerrada (final review READY TO MERGE)
- Branch feat/doc-layer-chromadb deletada localmente; master em 1b5f61a = origin/master = producao. 3 follow-ups Important (nao bloqueantes) registrados p/ futuro: I1 _get_session poisoned session, M2 timeout por-request call_tool, M3 clamp inferior de limit.

## Fase 3: Documentacao (02/08/2026)
- README.md v4.3 + STATUS_ESTUDIOHC.md v4.3 + .env.example reescritos (estado real: 12 tools, doc layer ChromaDB, auth, testes/CI).
- Commit 291a85a (push via servidor helciocosta). Clone local reconciliado em 291a85a.
- Memoria #32 registrada.

