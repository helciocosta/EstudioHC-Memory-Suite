# 🧠 HANDOFF — EstudioHC Memory Suite (Secretário Digital)

> **Para a próxima estação/agente dar continuidade.** Última atualização: 2026-08-25.
> Repo: `/home/deploy/Apps/EstudioHC-Memory-Suite` (branch `master` → GitHub `helciocosta/EstudioHC-Memory-Suite`).
> Leia também `STATUS_ESTUDIOHC.md` e `README.md`.

## 1. O que é

Cérebro centralizado de IA/produtividade: memória permanente (LTM), working memory (WM),
tarefas, agenda, notas, projetos, documentos (vetorial) — acessível via Tailscale de qualquer estação
(computadores e futuramente celulares). IA primária: **OpenCode**; IA secundária: **Hermes** (OpenRouter);
inferência local llama.cpp em cada estação.

## 2. Arquitetura REAL (verificada) — serviços systemd

| Serviço | Porta | Função | Status |
|---|---|---|---|
| `estudiohc-api` | 5050 (HTTPS/SSL) | FastAPI central, auth X-API-Key, rate limit | ✅ ativo |
| `estudiohc-dashboard` | 8585 | UI web (consome a API) | ✅ ativo |
| `estudiohc-mcp-sse` | 5051 | MCP SSE (12 tools) — via para agentes remotos | ✅ ativo |
| `estudiohc-sync-connect` | 5052 | Bridge integradores (7 rotas) | ✅ ativo |
| `estudiohc-alerts-contabo` | — | timer (19:34) health checks | ⏱ timer |
| `estudiohc-monitor` | — | timer (5min) coleta métricas | ⏱ timer |
| `estudiohc-backup` | — | timer (00:01) backup SQLite+FAISS | ⏱ timer |

Nota: `chromadb-mcp.service` (8765) existe e está ativo (camada docs do MCP).

**Bancos**: `data/estudiohc.db` (SQLite, 151+ memórias, 25 projetos, 12 estações) é o REAL.
`server/estudiohc_memory.db` e `server/memory.db` são LEGADOS — não usar.

## 3. Correções de produção — Fase 1 (2026-08-25, commits `6c48e58`, `d8a5fde`, `af055db`)

### 3.1 Sync-Connect corrigido (bug: chave auto-sync inexistente + schemas errados)
- Antes: systemd `Environment=API_KEY=auto-sync` → 401 em todo sync; rotas chamavam endpoints
  errados (`/api/diarios` POST inexistente; `conteudo` vs `texto`).
- Agora: drop-in systemd `/etc/systemd/system/estudiohc-sync-connect.service.d/override-api-key.conf`
  com a API_KEY real (64 chars). `apps/sync-connect/main.py` reescrito mapeando os schemas REAIS:
  - `/sync/logseq/diario` → `POST /api/nota` `{texto, estacao}`
  - `/sync/joplin/nota` → `POST /api/nota`
  - `/sync/joplin/tarefa` + `/sync/todo/tarefa` → `POST /api/tarefas` (resolve `projeto_id`, cria projeto "geral" se ausente)
  - `/sync/vikunja/projeto` → `POST /api/projetos/sync` `{projetos:[...]}`
  - `/sync/ghost/relatorio` → persistido como **nota** (NÃO usa `/gerar-relatorio` que roda IA e trava)
  - `/sync/agenda` → `POST /api/agenda` `{eventos:[...]}`
- Validado: todos os integradores retornam 200/201 em produção.

### 3.2 FAISS / busca vetorial corrigida (bug: modelo não carregava)
- Antes: `SentenceTransformer` sem cache_folder → tentava download (HF) → timeout 30s → "Vector search disabled".
- Agora: `apps/mcp-memory/src/embedder.py` usa `cache_folder=/home/deploy/.cache/huggingface/hub`
  + `local_files_only=True` (com fallback online). Modelo `all-MiniLM-L6-v2` já em cache.
- Resultado: `[memory] FAISS index rebuilt: 45 vectors` no startup. Índice em `src/.faiss_index.json`.
- ⚠️ NÃO adicionar `HF_HUB_OFFLINE=1` no systemd (conflita com `local_files_only`; causa `LocalEntryNotFoundError`).

### 3.3 Working Memory persistente (bug: volátil)
- Antes: `wm = WorkingMemory()` lista em RAM — perdida em restart.
- Agora: `apps/mcp-memory/src/memory_server_sse.py` persiste em `src/.working_memory.json`
  (load no `__init__`, save em push/pop/clear/consolidate). Validado: wm_push → restart → wm_list mantém.

### 3.4 Sanitização de dados (bug: nomes sujos)
- `apps/api/src/routers/memory.py`: `agent_name/project/category` com `.strip()` em `/memory/remember`.
- 14 registros existentes corrigidos no banco. Validado com memória id 154.

## 4. Autenticação (como funciona)

- `get_current_estacao`: `X-API-Key` = API_KEY global → scope `master`; OU chave de estação (hash) → scope `estacao`.
- `require_master` para rotas administrativas.
- API: env `apps/api/.env` (`API_KEY`, `MEMORY_API_KEY`). MCP read da mesma env via EnvironmentFile do systemd.
- Rotas abertas (sem auth): `/api/status` (healthcheck). Todo o resto exige key.

## 5. Como dar continuidade (Fase 2+)

Próximos passos priorizados (sem pressa, com aprovação):

1. **Backup distribuído**: servidor `estudiohc` (100.107.208.50) será o espelho/backup quando
   estiver online (hoje timeout de rede). Configurar: rsync/restic do `data/estudiohc.db` + `.env` →
   ou replicação. Validar quando o host responder.
2. **Teste de restore**: restaurar `backups/memory-db.*` em outro path e validar integridade SQLite.
3. **Migração SQLite → Postgres** quando >1 estação escrever simultaneamente (concorrência).
4. **Chave por estação**: criar chaves de estação dedicadas (hash) para celulares/dispositivos,
   em vez de todos usarem a master. Endpoint `/api/estacoes` + `EstacaoRegistro`.
5. **Dashboard hardcoded paths**: `apps/dashboard/static/*.html` usam `API` fixo — parametrizar por env.
6. **Rota `/docs` (Swagger)**: retorna 404 — reabilitar ou remover da doc.
7. **`gerar-relatorio`** gera IA e trava (lento) — tornar assíncrono/opcional.
8. **Camada docs ChromaDB**: validar `doc_add/search` end-to-end (rota 8765 ativa).

## 6. Erros conhecidos / armadilhas

- **MCP `/mcp` path dá `TypeError: NoneType not callable`** (404 no log) — o caminho REAL é `/sse`.
  Ignorar 404 de `/mcp`; não "corrigir" mexendo no routing sem testar o SSE.
- **`gerar-relatorio`** da API pode travar (chama IA) — não usar em sync; timeout 40s+.
- **Não editar `apps/`** (minúscula) — não existe mais; tudo em `Apps/`.
- **Backup diário existe mas RESTORE NÃO TESTADO** — testar antes de confiar.
- **Repos em branch `master`** (Memory-Suite) e `main` (server-setup): cada um no seu.

## 7. Comandos úteis

```bash
# health API (https)
curl -sk https://127.0.0.1:5050/api/status
# tools MCP (via cliente)
cd apps/mcp-memory && .venv/bin/python - <<EOF
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
async def m():
    async with sse_client("http://127.0.0.1:5051/sse") as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print((await s.list_tools()).tools)
asyncio.run(m())
EOF
# testes API
cd apps/api && K=$(grep -m1 "^API_KEY=" .env|cut -d= -f2)
curl -sk -H "X-API-Key: $K" https://127.0.0.1:5050/memory/remember -X POST -d "{\"agent_name\":\"x\",\"project\":\"x\",\"category\":\"fact\",\"content\":\"teste\"}" -H "Content-Type: application/json"
# sync teste
curl -s -X POST http://127.0.0.1:5052/sync/joplin/nota -H "Content-Type: application/json" -d "{\"titulo\":\"t\",\"conteudo\":\"c\"}"
```

## 8. Estado do banco (2026-08-25)

- `agent_memory`: 151 → 153+ (memórias reais; testes de auditoria removidos).
- Projetos: 25; Estações: 12 (nós Tailscale legítimos — NÃO remover).
- Distribuição: EstudioHC 53, opencode 45, CGDOC 24; agentes: opencode 61, Antigravity 30, Dashboard_Terminal 21.
- Últimas escritas reais: 19/08 — o stack estava com sync quebrado; após Fase 1, integradores voltam a escrever.

*Documento mantido no repo. Próxima estação: siga este handoff + STATUS_ESTUDIOHC.md.*
