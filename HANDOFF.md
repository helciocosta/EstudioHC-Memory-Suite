# ?? HANDOFF ? EstudioHC Memory Suite (Secret?rio Digital)

> **Documento de Continuidade Operacional para Equipes e Agentes de Engenharia.**  
> **?ltima Atualiza??o:** 2026-10-29 | **Vers?o:** 4.7.0  
> **Reposit?rio:** `https://github.com/helciocosta/EstudioHC-Memory-Suite` (branch `master`)  
> **Leituras Obrigat?rias Complementares:** `README.md`, `STATUS_ESTUDIOHC.md` e `progress.md`.

---

## 1. Vis?o Geral da Arquitetura

O **EstudioHC Memory Suite** ? o n? central de persist?ncia cognitiva e intelig?ncia da rede Tailscale, tendo a **VPS Contabo (`100.64.117.78` / `vmi2968998`)** como **Maestro 24/7** e o **Servidor Local (`100.107.208.50` / `estudiohc`)** como **R?plica Quente e Failover**. Ele unifica:
* **Mem?ria Permanente (LTM):** SQLite mestre (`data/estudiohc.db`) com versionamento, reconcilia??o de fatos e linhagem (`superseded_by`).
* **Working Memory (WM):** Armazenamento vol?til com persist?ncia em disco (`apps/mcp-memory/src/.working_memory.json`).
* **Documentos Vetoriais:** ChromaDB isolado por cole??es de projeto (`docs_<project>`, incluindo `docs_obsidian` alimentado continuamente pelo coletor do Obsidian).
* **Busca H?brida Inteligente:** Fus?o por Postos Rec?procos (RRF) combinando vetores FAISS (`all-MiniLM-L6-v2`), sobreposi??o l?xica BM25 e frescor temporal.
* **Coding Chain Store:** Rastreamento de diffs de c?digo (`data/coding_memory_cv.db`) com custo zero de LLM.
* **Obsidian Collector v2.0 nas Esta??es (`WIN-X99`, `linux-i5`):** Coletor ativo com ingest?o tripla (`/api/nota` + `/remember` com `supersedes_id` + `:5051/api/index-doc` para ChromaDB/FAISS), debounce de escrita (15s), sincroniza??o de agenda, heartbeat e painel bidirecional.

---

## 2. Invent?rio de Servi?os Systemd em Produ??o (Maestro Contabo & Espelho Local)

| Servi?o / Timer | Porta / Ciclo | Fun??o | Verifica??o de Sa?de |
|---|---|---|---|
| `estudiohc-api.service` | `5050` (HTTPS/TLS) | FastAPI central, auth `X-API-Key`, CRUD de entidades | `curl -sk https://127.0.0.1:5050/api/status` |
| `estudiohc-mcp-sse.service` | `5051` (HTTP/SSE) | Servidor MCP SSE (14 tools) + `POST /api/index-doc` | `curl -s http://127.0.0.1:5051/sse` |
| `chromadb-mcp.service` | `8765` (HTTP/SSE) | Servidor MCP SSE para documentos vetoriais (`upsert`) | `curl -s http://127.0.0.1:8765/mcp` |
| `estudiohc-sync-connect.service` | `5052` (HTTP) | Bridge integrador para servi?os externos | `curl -s http://127.0.0.1:5052/health` |
| `estudiohc-dashboard.service` | `8585` (HTTP) | Interface web operacional de gest?o | `curl -s http://127.0.0.1:8585/` |
| `estudiohc-replicate.timer` | Timer (15 min) | Replica??o quente SQLite `.backup` + `rsync` ChromaDB (Contabo ? Local) | `systemctl list-timers estudiohc-replicate.timer` |
| `estudiohc-monitor.timer` | Timer (5 min) | Coleta de m?tricas e status | `systemctl list-timers estudiohc-monitor.timer` |
| `estudiohc-alerts-contabo.timer` | Timer (10 min) | Monitoramento de alertas na VPS | `systemctl list-timers estudiohc-alerts-contabo.timer` |
| `estudiohc-backup.timer` | Timer (00:01) | Snapshot di?rio do SQLite WAL + FAISS | `systemctl list-timers estudiohc-backup.timer` |

---

## 3. Bancos de Dados Reais vs Legados

* ? **BANCO ATIVO E VERDADEIRO:** `data/estudiohc.db` (SQLite em modo WAL com tabelas `agent_memory`, `notas`, `tarefas`, `agenda`, `projetos`, `estacoes`, `resumos_diarios`).
* ? **BANCO DE DIFFS DE C?DIGO:** `data/coding_memory_cv.db` (tabelas `coding_thread` e `coding_round`).
* ? **BANCO DOCUMENTAL CHROMADB:** `data/chroma_data/chroma.sqlite3` (cole??es `docs_obsidian`, `docs_opencode`, `docs_EstudioHC`).
* ? **BANCOS LEGADOS (N?O UTILIZAR):** `server/estudiohc_memory.db` e `server/memory.db`.

---

## 4. Evolu??es Recentes de Produ??o (Vers?es 4.6.0 e 4.7.0)

### 4.1 Busca H?brida RRF (Reciprocal Rank Fusion)
* Arquivo: `apps/mcp-memory/src/rrf.py`
* A ferramenta `search_memory` avalia 3 canais simult?neos (`vec` ponderado 1.2, `kw` ponderado 1.0, `recency` ponderado 0.4) com constante $k=60$.

### 4.2 Reconcilia??o e Versionamento na Tabela `agent_memory`
* Colunas: `status` (`active` | `superseded`), `version` (inteiro incremental) e `superseded_by`.
* `POST /remember` com `supersedes_id` marca a mem?ria anterior como `superseded` e gera nova vers?o.
* `GET /recall/{project}` filtra por padr?o apenas registros `status='active'`.

### 4.3 Coding Chain Store
* Arquivo: `apps/mcp-memory/src/coding_chain.py`
* Ferramentas MCP expostas: `code_record_change` e `code_get_history`.

### 4.4 Obsidian Collector v2.0 e Pipeline Triplo de Ingest?o (2026-10-29 ? v4.7.0)
* Arquivos: `scripts/obsidian_collector.py`, `scripts/agenda_sync.py`, `scripts/station_bootstrap_win.ps1`.
* **Ingest?o Tripla**: Cada nota criada ou modificada em `00 - Painel`, `01 - Notas` ou `02 - Di?rio` no cofre do Obsidian ? sincronizada simultaneamente em:
  1. `POST /api/nota` (di?rio cronol?gico com `estacao` real).
  2. `POST /remember` (mem?ria sem?ntica em `agent_memory` com `supersedes_id` persistido em `~/.estudiohc_collector_state.json`).
  3. `POST :5051/api/index-doc` (indexa??o documental com `upsert` na cole??o `docs_obsidian` do ChromaDB + indexa??o vetorial imediata no FAISS).
* **Otimiza??es de Esta??o**:
  - Filtro r?pido de metadados (`st_mtime`, `st_size`) evitando leitura desnecess?ria de disco.
  - Debounce de escrita (`COLLECTOR_DEBOUNCE_SEC=15`) evitando envios parciais enquanto o usu?rio ou agente digita no Obsidian.
  - Trava de inst?ncia ?nica (`CreateMutexW` no Windows / `fcntl.flock` no Linux) e logs rotacionados (`~/.estudiohc/logs/obsidian_collector.log`).
  - `EndpointRouter` com failover autom?tico transparente entre Maestro Contabo (`https://hub.estudiohc:5050`) e Servidor Local (`https://100.107.208.50:5050`).
  - Pull bidirecional peri?dico gerando `00 - Painel/Status Ecossistema EstudioHC.md` no cofre local.

### 4.5 Preserva??o de Identidade de Esta??o e Corre??o Ass?ncrona do ChromaDB (2026-10-29 ? v4.7.0)
* Arquivos: `apps/api/src/routers/notas.py`, `apps/api/src/routers/memory.py`, `apps/api/src/routers/estacoes.py`, `apps/mcp-memory/src/memory_server_sse.py`, `apps/chromadb-mcp/server.py`.
* Quando autenticado com escopo `master`, a API agora preserva `payload.estacao` (em `/api/nota` e `/remember`) e `payload.hostname` / `payload.ip` (em `/api/estacoes/ping`). Quando autenticado com chave restrita de esta??o (`scope == "estacao"`), mant?m o bloqueio anti-spoofing for?ando `identity.estacao`.
* Corrigidas as chamadas ass?ncronas `await chroma.doc_add`, `await chroma.doc_search`, `await chroma.doc_list` e `await chroma.doc_delete` em `memory_server_sse.py` e alterado `col.add` para `col.upsert` em `apps/chromadb-mcp/server.py`.

---

## 5. Procedimento de Conting?ncia e Failover

1. **Autom?tico no Coletor (`obsidian_collector.py` v2.0)**:
   - Ap?s 3 falhas consecutivas no Maestro Contabo (`100.64.117.78`), o `EndpointRouter` comuta automaticamente para `https://100.107.208.50:5050` (Servidor Local) e realiza failback autom?tico assim que a VPS voltar a responder `200 OK` em `/api/status`.
2. **Comuta??o Global de Esta??o (Agentes MCP + Navegador)**:
   - Caso a VPS Contabo fique indispon?vel por per?odo prolongado, execute como Administrador no Windows:
     ```cmd
     C:\Users\helcio\scripts\switch-to-local.cmd
     ```
   - Quando a VPS retornar, execute:
     ```cmd
     C:\Users\helcio\scripts\switch-to-contabo.cmd
     ```

---

## 6. Pr?ximos Passos Recomendados para a Equipe (Roadmap v4.8+)

1. **Atualiza??o do Coletor na Esta??o `linux-i5` (`100.71.137.21`)**:
   - Quando a esta??o `linux-i5` estiver ligada, executar `git pull origin master` em `/home/helcioc/Projetos/EstudioHC-Memory-Suite`, criar `~/.estudiohc/.env` com `ESTUDIOHC_STATION_NAME=linux-i5` e reiniciar o servi?o do coletor local para usar o `obsidian_collector.py` v2.0.
2. **Chaves Individuais por Esta??o (`scope="estacao"` vs `scope="master"`)**:
   - Caso deseje isolar permiss?es por m?quina, emitir chaves individuais via `POST /api/estacoes/registrar` para cada esta??o e configurar `ESTUDIOHC_API_KEY` no respectivo `~/.estudiohc/.env`.
3. **Chunking Sem?ntico por Cabe?alhos Markdown (`## `)**:
   - Para notas t?cnicas muito extensas (>10 KB), evoluir o endpoint `:5051/api/index-doc` para dividir o documento por se??es `## ` antes do `upsert` no ChromaDB, aumentando a precis?o de trechos retornados pelo `doc_search`.
4. **Migra??o de `@app.on_event("startup")` para Lifespan Context Manager**:
   - Atualizar `apps/api/src/main.py` para usar `lifespan` do FastAPI moderno, eliminando os dois warnings de depreca??o na su?te `pytest`.
