# ?? EstudioHC ? Status do Projeto Central

**?ltima atualiza??o:** 2026-10-30  
**Maestro Prim?rio (24/7):** `vmi2968998` (`100.64.117.78` / `hub.estudiohc`)  
**Servidor Local (R?plica & Failover):** `estudiohc` (`100.107.208.50`)  
**Vers?o do stack:** v4.7.1 (`commit 9531e69+` - Failover Autom?tico Windows)  
**Failover Autom?tico Windows:** `scripts/failover_monitor.py` + tarefa agendada `EstudioHC-FailoverMonitor`
---

## ?? Meta Principal

**Servir como c?rebro centralizado 24/7** do ecossistema de IA e produtividade de Helcio O. Costa, integrando **OMP (`oh-my-pi`), Google Antigravity (`agy`), OpenCode, Claude Code, PandaCode e Obsidian**.

Unificar **mem?ria sem?ntica de agentes (Hy-Memory RRF + versionamento), working memory, cadeias de evolu??o de c?digo (Diff-Chain), agenda, notas/di?rios do Obsidian, projetos, tarefas, documentos vetoriais (ChromaDB) e telemetria de esta??es** sob a malha Tailscale.

---

## ??? Invent?rio Atualizado de N?s e Esta??es (Tailscale Mesh)

| N? / Esta??o | Hostname | Tailscale IP | Sistema Operacional | Papel no Ecossistema | Status |
|---|---|---|---|---|---|
| **Maestro Central 24/7** | `vmi2968998` | `100.64.117.78` | Ubuntu 24.04 LTS | Hub Central (`hub.estudiohc`), API `:5050`, MCP `:5051`, Chroma `:8765`, Sync `:5052`, Dashboard `:8585` | ? Online |
| **Servidor Local 32GB** | `estudiohc` | `100.107.208.50` | Ubuntu 24.04 LTS | Lab IA Sob Demanda + R?plica Quente (15 min) + Failover Imediato | ? Online |
| **Workstation Principal** | `WIN-X99` | `100.81.219.127` | Windows 11 Pro 26H2 | Esta??o Di?ria + Gateway LiteLLM (`:4000`) + Obsidian Collector v2.0 | ? Online |
| **Workstation Linux** | `linux-i5` | `100.71.137.21` | Debian 13 (Trixie) 30GB | Esta??o Secund?ria Linux + Cofre Obsidian Espelhado | ? Sob Demanda |

---

## ??? Arquitetura em Produ??o (v4.7.0)

```
EstudioHC-Memory-Suite/
??? apps/
?   ??? api/                          ? FastAPI Central HTTPS (porta 5050) ? [33/33 testes pytest]
?   ?   ??? src/main.py               ? App principal + rotas /remember, /recall, /status
?   ?   ??? src/security.py           ? Identidade Master e por Esta??o + Rate Limiter
?   ?   ??? src/models/               ? ORM (AgentMemory v4.6, Nota, Tarefa, Agenda, Projeto, Estacao)
?   ?   ??? src/routers/              ? memory, notas, agenda, projetos, tarefas, estacoes, hermes, status
?   ??? mcp-memory/                   ? MCP Memory Server SSE (porta 5051, 14 tools + /api/index-doc) ?
?   ?   ??? src/memory_server_sse.py  ? Servidor SSE + RRF + Working Memory + endpoint /api/index-doc
?   ?   ??? src/rrf.py                ? Fus?o H?brida RRF (Vetorial + L?xico + Rec?ncia)
?   ?   ??? src/coding_chain.py       ? Version-Evolution Chain (Diff-Chain em SQLite)
?   ?   ??? src/chroma_client.py      ? Cliente ass?ncrono do ChromaDB MCP
?   ?   ??? src/embedder.py           ? Embeddings all-MiniLM-L6-v2 + FAISS
?   ??? chromadb-mcp/                 ? ChromaDB MCP SSE (porta 8765, suporte a upsert) ?
?   ??? sync-connect/                 ? Bridge Integrador (porta 5052) ?
?   ??? dashboard/                    ? Web UI Operacional (porta 8585) ?
??? scripts/
?   ??? obsidian_collector.py         ? Coletor Local v2.0 (Tripla Ingest?o, Debounce 15s, Failover) ?
?   ??? agenda_sync.py                ? Sincronizador de Agenda v2.0 ?
?   ??? station_bootstrap_win.ps1     ? Bootstrap e Watchdog para Windows 11 ?
?   ??? failover_monitor.py           ? Failover Autom?tico do Windows (hosts DNS) ?
?   ??? start_failover_monitor.bat    ? Inicializador do Failover Monitor ?
?   ??? switch-to-contabo.cmd         ? Comutador DNS can?nico para Maestro Contabo ?
?   ??? switch-to-local.cmd           ? Comutador DNS can?nico para Failover Local ?
?   ??? replicate_to_local.sh         ? Replica??o quente SQLite WAL + ChromaDB (15 min) ?
??? data/
?   ??? estudiohc.db                  ? Banco SQLite Mestre (WAL ativo)
?   ??? coding_memory_cv.db           ? Banco Diff-Chain de evolu??o de c?digo
?   ??? chroma_data/                  ? Base documental vetorial ChromaDB
??? README.md
??? HANDOFF.md
??? STATUS_ESTUDIOHC.md
??? progress.md
```

---

## ?? Resumo das Entregas Recentes (2026-10-29 ? v4.7.0)

1. **Coletor Obsidian v2.0 (`scripts/obsidian_collector.py`)**:
   - Ingest?o tripla autom?tica (`/api/nota` + `/remember` com `supersedes_id` + `:5051/api/index-doc` para ChromaDB e FAISS).
   - Monitoramento de `00 - Painel`, `01 - Notas` e `02 - Di?rio` com filtro r?pido `mtime/size`, debounce de 15s, Mutex de inst?ncia ?nica, log rotacionado e failover autom?tico.
   - Gera??o bidirecional autom?tica da nota `00 - Painel/Status Ecossistema EstudioHC.md`.
2. **Preserva??o de Identidade de Esta??o (`notas.py`, `memory.py`, `estacoes.py`)**:
   - Preserva??o de `estacao` e `hostname` reais para chamadas administrativas (`scope="master"`), mantendo prote??o anti-spoofing para chaves de esta??o (`scope="estacao"`).
   - Backfill de 84 notas hist?ricas (`WIN-X99` e `linux-i5`) e limpeza de registros de smoke-test na tabela `estacoes`.
3. **Gateway LiteLLM + OMP na Esta??o `WIN-X99`**:
   - Gateway LiteLLM (`127.0.0.1:4000`) restaurado e blindado contra corrida de inicializa??o no logon.
   - `litellm/modelo-free-prioritario` fixado como modelo padr?o persistente em todos os `modelRoles` do OMP (`~/.omp/agent/config.yml`), com fallback para `litellm/modelo-deepseek-barato` e `mcp.startupTimeoutMs: 5000`.
