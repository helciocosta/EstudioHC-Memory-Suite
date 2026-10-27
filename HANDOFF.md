# 🧠 HANDOFF — EstudioHC Memory Suite (Secretário Digital)

> **Documento de Continuidade Operacional para Equipes e Agentes de Engenharia.**  
> **Última Atualização:** 2026-10-27 | **Versão:** 4.6.0  
> **Repositório:** `https://github.com/helciocosta/EstudioHC-Memory-Suite` (branch `master`)  
> **Leituras Obrigatórias Complementares:** `README.md`, `STATUS_ESTUDIOHC.md` e o plano em `docs/superpowers/plans/2026-10-26-orquestrador-central-failover-contingencia.md`.

---

## 1. Visão Geral da Arquitetura

O **EstudioHC Memory Suite** é o nó central de persistência cognitiva e inteligência da rede Tailscale. Ele unifica:
* **Memória Permanente (LTM):** SQLite mestre (`data/estudiohc.db`) com versionamento, reconciliação de fatos e linhagem (`superseded_by`).
* **Working Memory (WM):** Armazenamento volátil com persistência em disco (`src/.working_memory.json`).
* **Documentos Vetoriais:** ChromaDB isolado por coleções de projeto (`docs_<project>`).
* **Busca Híbrida Inteligente:** Fusão por Postos Recíprocos (RRF) combinando vetores FAISS (`all-MiniLM-L6-v2`), sobreposição léxica BM25 e frescor temporal.
* **Coding Chain Store:** Rastreamento de diffs de código (`data/coding_memory_cv.db`) com custo zero de LLM.
* **Bridge de Integradores:** Sync Connect mapeando Logseq, Joplin, Vikunja, Ghost e Obsidian Agenda.

---

## 2. Inventário de Serviços Systemd em Produção

| Serviço | Porta / Protocolo | Função | Verificação de Saúde |
|---|---|---|---|
| `estudiohc-api` | `5050` (HTTPS/TLS) | FastAPI central, auth `X-API-Key`, CRUD de entidades | `curl -sk https://127.0.0.1:5050/api/status` |
| `estudiohc-mcp-sse` | `5051` (HTTP/SSE) | Servidor MCP SSE com 14 ferramentas | `curl -s http://127.0.0.1:5051/sse` |
| `chromadb-mcp` | `8765` (HTTP/SSE) | Servidor MCP SSE para busca em documentos inteiros | `curl -s http://127.0.0.1:8765/sse` |
| `estudiohc-sync-connect` | `5052` (HTTP) | Bridge integrador para 7 serviços externos | `curl -s http://127.0.0.1:5052/health` |
| `estudiohc-dashboard` | `8585` (HTTP) | Interface web operacional de gestão | `curl -s http://127.0.0.1:8585/` |
| `estudiohc-monitor` | Timer (5 min) | Coleta de métricas e status | `systemctl list-timers estudiohc-monitor` |
| `estudiohc-backup` | Timer (00:01) | Snapshot e backup do SQLite WAL + FAISS | `systemctl list-timers estudiohc-backup` |

---

## 3. Bancos de Dados Reais vs Legados

* ✅ **BANCO ATIVO E VERDADEIRO:** `data/estudiohc.db` (SQLite em modo WAL com tabelas `agent_memory`, `notas`, `tarefas`, `agenda`, `projetos`, `estacoes`).
* ✅ **BANCO DE DIFFS DE CÓDIGO:** `data/coding_memory_cv.db` (tabelas `coding_thread` e `coding_round`).
* ❌ **BANCOS LEGADOS (NÃO UTILIZAR):** `server/estudiohc_memory.db` e `server/memory.db`.

---

## 4. Evoluções Recentes de Produção (Versão 4.6.0)

### 4.1 Busca Híbrida RRF (Reciprocal Rank Fusion)
* Arquivo: `apps/mcp-memory/src/rrf.py`
* Substituiu a soma ingênua de scores pelo algoritmo oficial do Tencent Hy-Memory (Cormack et al., 2009).
* A ferramenta `search_memory` avalia 3 canais simultâneos (`vec` ponderado 1.2, `kw` ponderado 1.0, `recency` ponderado 0.4) com constante $k=60$.

### 4.2 Reconciliação e Versionamento na Tabela `agent_memory`
* Colunas adicionadas: `status` (`active` | `superseded`), `version` (inteiro incremental) e `superseded_by` (chave estrangeira autorreferencial).
* `POST /remember` com `supersedes_id` marca a memória anterior como `superseded` e gera nova versão.
* `GET /recall/{project}` filtra por padrão apenas registros `status='active'`, evitando que decisões técnicas obsoletas gerem alucinações nos agentes.

### 4.3 Coding Chain Store
* Arquivo: `apps/mcp-memory/src/coding_chain.py`
* Ferramentas MCP expostas: `code_record_change` e `code_get_history`.
* Permite que agentes OMP, OpenCode e Jarvis gravem o histórico exato de diffs aplicados no repositório.

---

## 5. Procedimento de Contingência e Failover

Se a VPS Contabo (`100.64.117.78`) estiver indisponível:
1. Ligar o **Servidor Local EstudioHC** (`100.107.208.50`).
2. O servidor local sobe os 5 serviços systemd automaticamente no boot.
3. No Windows ou Linux, executar o script de comutação de DNS canônico:
   ```cmd
   C:\Users\helcio\scripts\switch-to-local.cmd
   ```
   Isso altera a resolução de `hub.estudiohc` no arquivo `hosts` para `100.107.208.50`.
4. Todos os agentes (OMP, OpenCode, Obsidian) são redirecionados instantaneamente sem reconfiguração de portas ou chaves.
5. Quando a VPS retornar:
   - Executar o script de failback reverso para replicar os deltas de SQLite via WAL/rsync.
   - Executar `switch-to-contabo.cmd` e desligar o Servidor Local para retorno ao consumo zero de energia.

---

## 6. Cuidados e Armadilhas Conhecidas (Pitfalls)

1. **FAISS em Cache Local:**
   - O arquivo `apps/mcp-memory/src/embedder.py` utiliza `local_files_only=True` com fallback dinâmico. O modelo `all-MiniLM-L6-v2` deve estar no cache Hugging Face (`~/.cache/huggingface/hub`). **NUNCA** adicionar `HF_HUB_OFFLINE=1` nas unidades systemd, pois isso causa falha de carregamento (`LocalEntryNotFoundError`).
2. **FastAPI Booleanos em Chamadas Internas:**
   - Em `apps/api/src/routers/memory.py`, se um endpoint aceitar parâmetros com `Query(False)` e for chamado diretamente por funções internas de `main.py`, o valor padrão recebido será a instância do objeto `Query` (que em Python avalia para `True`). Mantenha os defaults de funções internas como booleanos literais (`include_superseded: bool = False`).
3. **Certificados TLS:**
   - A API na porta `5050` roda estritamente sob HTTPS. Requisições em plain HTTP retornam `Empty reply from server (code 52)`. Use sempre `curl -k` ou HTTPS.
