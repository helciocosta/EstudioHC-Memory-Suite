# EstudioHC Memory Suite v4.7

**Secret?rio Digital e Orquestrador Central de Intelig?ncia** ? Coordena, comanda e gerencia mem?ria permanente, working memory, agenda, projetos, notas do Obsidian, documentos vetoriais e cadeias de evolu??o de c?digo para todos os agentes de IA na malha Tailscale.

![Vers?o](https://img.shields.io/badge/vers?o-4.7.0-00e5ff)
![Python](https://img.shields.io/badge/python-3.12-7000ff)
![Licen?a](https://img.shields.io/badge/licen?a-Apache--2.0-4c6ef5)
![MCP](https://img.shields.io/badge/mcp-14%20ferramentas-00ff9d)
![Rede](https://img.shields.io/badge/rede-Tailscale%20Mesh-ffae00)

---

## ??? Topologia e Arquitetura do Ecossistema

O **EstudioHC Memory Suite** foi arquitetado sob princ?pios de alta resili?ncia, baixa lat?ncia e efici?ncia energ?tica:

```
                            ??????????????????????????????????????????
                            ?      Agentes de IA & Clientes          ?
                            ?  (OMP, Antigravity, OpenCode, Claude)  ?
                            ??????????????????????????????????????????
                                                ?
                          ?????????????????????????????????????????????
                          ?     Rede Tailscale (WireGuard Mesh)       ?
                          ?        hub.estudiohc (DNS Can?nico)       ?
                          ?????????????????????????????????????????????
                                        ?                 ?
               [Maestro Prim?rio 24/7]  ?                 ?  [N? Reserva / Lab Dev]
                                        ?                 ?
             ?????????????????????????????????   ?????????????????????????????????
             ?       VPS Contabo (24/7)      ?   ?     Servidor Local (32GB)     ?
             ?         100.64.117.78         ?   ?        100.107.208.50         ?
             ? ????????????????????????????? ?   ? ????????????????????????????? ?
             ? ? API Central (:5050 HTTPS)   ?????? Replica??o WAL SQLite & Git  ?
             ? ? MCP SSE Server (:5051)      ?   ? ? API Central (:5050 HTTPS)   ?
             ? ? ChromaDB SSE (:8765)        ?   ? ? MCP SSE Server (:5051)      ?
             ? ? Sync Connect (:5052)        ?   ? ? ChromaDB SSE (:8765)        ?
             ? ? Dashboard Web (:8585)       ?   ? ? Sync Connect (:5052)        ?
             ? ? SQLite Master (estudiohc.db)?   ? ? Dashboard Web (:8585)       ?
             ? ? Coding Chain (Diff-Chain)   ?   ? ? Coding Chain (Diff-Chain)   ?
             ?????????????????????????????????   ?????????????????????????????????
                               ?                                 ?
                               ???????????????????????????????????
                                                 ? Coleta Tripla + Pull Bidirecional
                                 ?????????????????????????????????
                                 ?      Esta??es de Trabalho     ?
                                 ?   ? WIN-X99 (Windows 11 Pro)  ?
                                 ?   ? linux-i5 (Debian 13)      ?
                                 ? (Obsidian Collector v2.0)     ?
                                 ?????????????????????????????????
```

1. **Hub Central / Maestro 24/7 (VPS Contabo `100.64.117.78`)**:
   - N? permanente que mant?m os 5 servi?os systemd e os 4 timers operacionais ativos ininterruptamente para consumo local, m?vel e remoto.
2. **Laborat?rio Sob Demanda & Reserva Imediata (Servidor Local 32GB `100.107.208.50`)**:
   - Ambiente de computa??o pesada (Ollama, fine-tuning, Vane AI). Recebe snapshots quentes do SQLite WAL e ChromaDB a cada 15 minutos via `estudiohc-replicate.timer` e assume automaticamente a carga em caso de conting?ncia na VPS.
3. **Coletores Locais Obsidian v2.0 nas Esta??es (`WIN-X99` e `linux-i5`)**:
   - Monitoram `00 - Painel`, `01 - Notas` e `02 - Di?rio` com filtro r?pido de metadados (`mtime`/`size`), debounce de escrita de 15s, trava de inst?ncia ?nica (Mutex/flock), log rotacionado (`~/.estudiohc/logs/obsidian_collector.log`) e failover autom?tico (`EndpointRouter`).
   - Executam **Ingest?o Sem?ntica Tripla**:
     1. `POST /api/nota` (di?rio cronol?gico com preserva??o da esta??o de origem).
     2. `POST /remember` (mem?ria estruturada na tabela `agent_memory` com versionamento **Hy-Memory v4.6** via `supersedes_id`).
     3. `POST :5051/api/index-doc` (upsert documental completo na cole??o `docs_obsidian` do **ChromaDB** + indexa??o vetorial imediata no **FAISS**).
   - Executam **Heartbeat autom?tico** (`POST /api/estacoes/ping`), **Sincroniza??o de Agenda** (`POST /api/agenda`) e **Pull Bidirecional** (`00 - Painel/Status Ecossistema EstudioHC.md`).

---

## ??? Cat?logo de Ferramentas MCP (14 Ferramentas Ativas)

O servidor MCP SSE na porta `5051/sse` serve 14 ferramentas estruturadas para agentes aut?nomos (OMP, Antigravity, OpenCode, Claude Code):

| Categoria | Ferramenta | Descri??o e Par?metros |
|---|---|---|
| **Working Memory** | `wm_push` | Insere item na mem?ria de trabalho vol?til/sess?o (`content`, `category`). |
| | `wm_pop` | Remove e retorna o ?ltimo item da mem?ria de trabalho. |
| | `wm_list` | Lista todos os itens da mem?ria de trabalho da sess?o atual. |
| | `wm_clear` | Limpa a mem?ria de trabalho (com filtro opcional por `category`). |
| | `wm_consolidate` | Promove itens da working memory para a mem?ria permanente central. |
| **Long-Term Memory** | `add_memory` | Grava mem?ria permanente no SQLite e atualiza o ?ndice FAISS em tempo real. Suporta `supersedes_id` para substitui??o e versionamento l?gico. |
| | `search_memory` | **Busca H?brida RRF (Reciprocal Rank Fusion)** multi-canal (Vetorial FAISS + L?xico BM25 + Rec?ncia). |
| | `get_status` | Retorna o sum?rio de tarefas pendentes e conclu?das de um projeto. |
| **Engenharia de C?digo** | `code_record_change` | Registra diffs Git e motivos de altera??o na **Version-Evolution Chain** (custo zero de LLM). |
| | `code_get_history` | Recupera a linha do tempo de altera??es, vers?es e diffs de arquivos/projetos. |
| **Documentos Vetoriais** | `doc_add` | Indexa/atualiza (`upsert`) documentos completos no ChromaDB por cole??o (`project`, `documents` ou `title`/`content`/`tags`). |
| | `doc_search` | Realiza busca sem?ntica em documentos inteiros no ChromaDB com metadados. |
| | `doc_list` | Lista documentos e metadados armazenados em uma cole??o. |
| | `doc_delete` | Remove um documento espec?fico do ChromaDB por ID. |

> **Endpoint HTTP Auxiliar de Indexa??o (`:5051/api/index-doc`)**: Al?m do transporte MCP SSE (`/sse`), o servidor `:5051` exp?e `POST /api/index-doc` (autenticado via `X-API-Key`) para ingest?o direta pelo `obsidian_collector.py` em ChromaDB + FAISS.

---

## ?? Inova??es Algor?tmicas Incorporadas (Tencent Hy-Memory + Collector v2.0)

### 1. Fus?o H?brida Multi-Canal (RRF)
Em vez de misturar dist?ncias vetoriais com scores de texto emp?ricos, o `search_memory` implementa a f?rmula de Cormack et al. (2009):
$$\text{score}(d) = \sum_{c} \frac{w_c}{60 + \text{rank}_c(d)}$$
* **Canal Vetorial ($w=1.2$):** Similaridade de cosseno via FAISS com modelo `all-MiniLM-L6-v2` (reconstru?do no boot a partir dos projetos `opencode`, `EstudioHC` e `obsidian`, e atualizado incrementalmente a cada novo registro).
* **Canal L?xico ($w=1.0$):** Sobreposi??o exata de tokens da query e b?nus de categoria.
* **Canal Temporal ($w=0.4$):** Freshness score baseado no timestamp cronol?gico.

### 2. Reconciliador de Fatos e Versionamento (`supersedes_id`)
A tabela `agent_memory` rastreia a evolu??o do conhecimento:
* Novas mem?rias ou edi??es de notas do Obsidian que substituem vers?es anteriores recebem `supersedes_id` (rastreado localmente em `~/.estudiohc_collector_state.json`).
* O fato antigo ? marcado como `status='superseded'` e apontado para o novo ID (`superseded_by`).
* Consultas padr?o retornam estritamente fatos `status='active'`, evitando que agentes usem credenciais, arquiteturas ou portas obsoletas.

### 3. Coding Chain Store (Diff-Chain em SQLite)
Rastreia a evolu??o do c?digo em `data/coding_memory_cv.db` sem gastar tokens de contexto:
* Cada altera??o gera uma rodada (`round`) vinculada ao branch, arquivo e fun??o.
* Preserva os patches Git reais e os motivos declarados pelo usu?rio, viabilizando auditoria de revers?es.

---

## ?? Configura??o de Esta??es Coletoras (Windows 11 e Linux Desktop)

### 1. Arquivo de Ambiente da Esta??o (`~/.estudiohc/.env`)
Em cada esta??o de trabalho (`WIN-X99` ou `linux-i5`), crie `~/.estudiohc/.env`:
```ini
ESTUDIOHC_HUB=hub.estudiohc
ESTUDIOHC_API_URL=https://hub.estudiohc:5050
ESTUDIOHC_MCP_URL=http://hub.estudiohc:5051
ESTUDIOHC_FALLBACK_API_URL=https://100.107.208.50:5050
ESTUDIOHC_FALLBACK_MCP_URL=http://100.107.208.50:5051
ESTUDIOHC_API_KEY=<CHAVE_API_OU_ESTACAO>
ESTUDIOHC_STATION_NAME=WIN-X99
OBSIDIAN_VAULT=C:\Users\helcio\Documents\Notas
COLLECTOR_INTERVAL=5
COLLECTOR_DEBOUNCE_SEC=15
```

### 2. Scripts da Esta??o (`scripts/`)
* `scripts/obsidian_collector.py`: Daemon coletor v2.0 (Ingest?o Tripla + Heartbeat + Agenda + Pull Bidirecional + Failover Autom?tico).
* `scripts/agenda_sync.py`: Sincronizador de checkboxes `- [ ]` / `- [x]` de `00 - Painel/Agenda.md` e `02 - Di?rio/<YYYY-MM-DD>.md` com `/api/agenda`.
* `scripts/station_bootstrap_win.ps1`: Script de inicializa??o no Windows (acionado pela Tarefa Agendada `\EstudioHC-StationSync` via `pythonw.exe`).
* `scripts/switch-to-contabo.cmd` e `scripts/switch-to-local.cmd`: Comutadores manuais do DNS can?nico `hub.estudiohc` no arquivo `hosts`.

---

## ?? Guia de Implanta??o em Novos Servidores (Onboarding)

Siga este procedimento passo a passo para instalar e executar o **EstudioHC Memory Suite** em um servidor Linux (Ubuntu 24.04 ou Debian 13):

### 1. Pr?-Requisitos do Sistema
```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip sqlite3 curl ufw
```

### 2. Clonagem do Reposit?rio
```bash
mkdir -p ~/Apps && cd ~/Apps
git clone https://github.com/helciocosta/EstudioHC-Memory-Suite.git
cd EstudioHC-Memory-Suite
```

### 3. Estrutura??o dos Ambientes Virtuais (Venvs)
```bash
# A. API Central
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install --upgrade pip
apps/api/.venv/bin/pip install -e apps/api

# B. MCP Memory SSE
python3 -m venv apps/mcp-memory/.venv
apps/mcp-memory/.venv/bin/pip install --upgrade pip
apps/mcp-memory/.venv/bin/pip install -e apps/mcp-memory

# C. ChromaDB MCP
python3 -m venv apps/chromadb-mcp/.venv
apps/chromadb-mcp/.venv/bin/pip install --upgrade pip
apps/chromadb-mcp/.venv/bin/pip install chromadb mcp starlette uvicorn
```

### 4. Valida??o de Sa?de Operacional e Testes Automatizados
```bash
# 1. Executar su?te de testes da API Central (33 testes)
cd apps/api && PYTHONPATH=. .venv/bin/pytest -q

# 2. Testar API Central HTTPS
curl -sk https://127.0.0.1:5050/api/status

# 3. Testar MCP SSE Server
curl -s http://127.0.0.1:5051/sse | head -n 3

# 4. Testar ChromaDB Server
curl -s http://127.0.0.1:8765/mcp | head -n 3
```

---

## ?? Licen?a
Distribu?do sob a licen?a **Apache-2.0**. Consulte `LICENSE` para mais detalhes.
