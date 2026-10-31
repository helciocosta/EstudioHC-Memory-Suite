# EstudioHC Memory Suite v4.7.1

**Secretário Digital e Orquestrador Central de Inteligência** ? Coordena, comanda e gerencia memória permanente, working memory, agenda, projetos, notas do Obsidian, documentos vetoriais e cadeias de evolução de código para todos os agentes de IA na malha Tailscale.

![Versão](https://img.shields.io/badge/versão-4.7.1-00e5ff)
![Python](https://img.shields.io/badge/python-3.12-7000ff)
![Licença](https://img.shields.io/badge/licença-Apache--2.0-4c6ef5)
![MCP](https://img.shields.io/badge/mcp-14%20ferramentas-00ff9d)
![Rede](https://img.shields.io/badge/rede-Tailscale%20Mesh-ffae00)

---

## ??? Topologia e Arquitetura do Ecossistema

O **EstudioHC Memory Suite** foi arquitetado sob princípios de alta resiliência, baixa latência e eficiência energética:

```
                            ??????????????????????????????????????????
                            ?      Agentes de IA & Clientes          ?
                            ?  (OMP, Antigravity, OpenCode, Claude)  ?
                            ??????????????????????????????????????????
                                                ?
                          ?????????????????????????????????????????????
                          ?     Rede Tailscale (WireGuard Mesh)       ?
                          ?        hub.estudiohc (DNS Canônico)       ?
                          ?????????????????????????????????????????????
                                        ?                 ?
               [Maestro Primário 24/7]  ?                 ?  [Nó Reserva / Lab Dev]
                                        ?                 ?
             ?????????????????????????????????   ?????????????????????????????????
             ?       VPS Contabo (24/7)      ?   ?     Servidor Local (32GB)     ?
             ?         100.64.117.78         ?   ?        100.107.208.50         ?
             ? ????????????????????????????? ?   ? ????????????????????????????? ?
             ? ? API Central (:5050 HTTPS)   ?????? Replicação WAL SQLite & Git  ?
             ? ? MCP SSE Server (:5051)      ?   ? ? API Central (:5050 HTTPS)   ?
             ? ? ChromaDB SSE (:8765)        ?   ? ? MCP SSE Server (:5051)      ?
             ? ? Sync Connect (:5052)        ?   ? ? Sync Connect (:5052)        ?
             ? ? Dashboard Web (:8585)       ?   ? ? Dashboard Web (:8585)       ?
             ? ? SQLite Master (estudiohc.db)?   ? ? SQLite Réplica Quente       ?
             ? ? Coding Chain (Diff-Chain)   ?   ? ? Coding Chain (Diff-Chain)   ?
             ?????????????????????????????????   ?????????????????????????????????
                               ?                                 ?
                               ???????????????????????????????????
                                                 ? Coleta Tripla + Pull Bidirecional
                                 ?????????????????????????????????
                                 ?      Estações de Trabalho     ?
                                 ?   ? WIN-X99 (Windows 11 Pro)  ?
                                 ?   ? linux-i5 (Debian 13)      ?
                                 ? (Obsidian Collector v2.0)     ?
                                 ?????????????????????????????????
```

1. **Hub Central / Maestro 24/7 (VPS Contabo `100.64.117.78`)**:
   - Nó permanente que mantém os 5 serviços systemd e os 4 timers operacionais ativos ininterruptamente para consumo local, móvel e remoto.

2. **Laboratório Sob Demanda & Reserva Imediata (Servidor Local 32GB `100.107.208.50`)**:
   - Ambiente de computação pesada (Ollama, fine-tuning, Vane AI). Recebe snapshots quentes do SQLite WAL e ChromaDB a cada 15 minutos via `estudiohc-replicate.timer` e assume automaticamente a carga em caso de contingência na VPS.

3. **Coletores Locais Obsidian v2.0 nas Estações (WIN-X99 e linux-i5)**:
   - Monitoram `00 - Painel`, `01 - Notas` e `02 - Diário` com filtro rápido de metadados (`mtime`/`size`), debounce de escrita de 15s, trava de instância única (Mutex/flock), log rotacionado (`~/.estudiohc/logs/obsidian_collector.log`) e failover automático (`EndpointRouter`).
   - Executam **Ingestão Semântica Tripla**:
     1. `POST /api/nota` (diário cronológico com preservação da estação de origem).
     2. `POST /remember` (memória estruturada na tabela `agent_memory` com versionamento **Hy-Memory v4.6** via `supersedes_id`).
     3. `POST :5051/api/index-doc` (upsert documental completo na coleção `docs_obsidian` do **ChromaDB** + indexação vetorial imediata no **FAISS**).
   - Executam **Heartbeat automático** (`POST /api/estacoes/ping`), **Sincronização de Agenda** (`POST /api/agenda`) e **Pull Bidirecional** (`00 - Painel/Status Ecossistema EstudioHC.md`).

---

## ?? Failover Automático Windows (Failover Monitor)

A estação Windows (`WIN-X99`) agora conta com **failover automático de DNS** para o arquivo `hosts`. Quando o Maestro Contabo fica inacessível, o `failover_monitor.py` detecta a falha e redireciona automaticamente `hub.estudiohc` para o Servidor Local (`100.107.208.50`). Quando o Contabo volta, o failback é feito automaticamente.

### Como funciona

1. O `failover_monitor.py` faz `probe` contínuo na API Central (`https://hub.estudiohc:5050/api/status`).
2. Após `FAILURE_THRESHOLD` (3) falhas consecutivas, ele altera `C:\Windows\System32\drivers\etc\hosts` para apontar `hub.estudiohc` para `100.107.208.50` (Servidor Local).
3. Quando o Contabo volta (verificado após `RECOVERY_THRESHOLD` (2) sucessos consecutivos), o failback é feito automaticamente de volta para `100.64.117.78`.
4. Todo o processo é logado em `C:\Users\helcio\.estudiohc\logs\failover_monitor.log`.

### Instalação no Windows

```powershell
# Executar como Administrador no PowerShell:
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File C:\Users\helcio\scripts\start_failover_monitor.bat'
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName 'EstudioHC-FailoverMonitor' -Action $action -Trigger $trigger -Description 'Failover automático do hub.estudiohc para o Servidor Local'
```

Ou iniciar manualmente:

```bash
cd C:\Users\helcio\scripts
python failover_monitor.py
```

### Arquivos da estação Windows

| Arquivo | Função |
|---------|--------|
| `scripts/failover_monitor.py` | Monitora Contabo e altera `hosts` automaticamente |
| `scripts/start_failover_monitor.bat` | Script batch para iniciar o monitor |
| `scripts/switch-to-contabo.cmd` | Comutador manual para Contabo |
| `scripts/switch-to-local.cmd` | Comutador manual para Servidor Local |
| `C:\Users\helcio\.estudiohc_collector_state.json` | Estado de sincronização do coletor |

---

## ??? Catálogo de Ferramentas MCP (14 Ferramentas Ativas)

O servidor MCP SSE na porta `5051/sse` serve 14 ferramentas estruturadas para agentes autônomos (OMP, Antigravity, OpenCode, Claude Code):

| Categoria | Ferramenta | Descrição e Parâmetros |
|---|---|---|
| **Working Memory** | `wm_push` | Insere item na memória de trabalho volátil/sessão (`content`, `category`). |
| | `wm_pop` | Remove e retorna o último item da memória de trabalho. |
| | `wm_list` | Lista todos os itens da memória de trabalho da sessão atual. |
| | `wm_clear` | Limpa a memória de trabalho (com filtro opcional por `category`). |
| | `wm_consolidate` | Promove itens da working memory para a memória permanente central. |
| **Long-Term Memory** | `add_memory` | Grava memória permanente no SQLite e atualiza o índice FAISS em tempo real. Suporta `supersedes_id` para substituição e versionamento lógico. |
| | `search_memory` | **Busca Híbrida RRF (Reciprocal Rank Fusion)** multi-canal (Vetorial FAISS + Léxico BM25 + Recência). |
| | `get_status` | Retorna o sumário de tarefas pendentes e concluídas de um projeto. |
| **Engenharia de Código** | `code_record_change` | Registra diffs Git e motivos de alteração na **Version-Evolution Chain** (custo zero de LLM). |
| | `code_get_history` | Recupera a linha do tempo de alterações, versões e diffs de arquivos/projetos. |
| **Documentos Vetoriais** | `doc_add` | Indexa/atualiza (`upsert`) documentos completos no ChromaDB por coleção (`project`, `documents` ou `title`/`content`/`tags`). |
| | `doc_search` | Realiza busca semântica em documentos inteiros no ChromaDB com metadados. |
| | `doc_list` | Lista documentos e metadados armazenados em uma coleção. |
| | `doc_delete` | Remove um documento específico do ChromaDB por ID. |

> **Endpoint HTTP Auxiliar de Indexação (`:5051/api/index-doc`)**: Além do transporte MCP SSE (`/sse`), o servidor `:5051` expõe `POST /api/index-doc` (autenticado via `X-API-Key`) para ingestão direta pelo `obsidian_collector.py` em ChromaDB + FAISS.

---

## ?? Inovações Algorítmicas Incorporadas (Tencent Hy-Memory + Collector v2.0)

### 1. Fusão Híbrida Multi-Canal (RRF)

Em vez de misturar distâncias vetoriais com scores de texto empíricos, o `search_memory` implementa a fórmula de Cormack et al. (2009):

$$\text{score}(d) = \sum_{c} \frac{w_c}{60 + \text{rank}_c(d)}$$

* **Canal Vetorial ($w=1.2$):** Similaridade de cosseno via FAISS com modelo `all-MiniLM-L6-v2` (reconstruído no boot a partir dos projetos `opencode`, `EstudioHC` e `obsidian`, e atualizado incrementalmente a cada novo registro).
* **Canal Léxico ($w=1.0$):** Sobreposição exata de tokens da query e bônus de categoria.
* **Canal Temporal ($w=0.4$):** Freshness score baseado no timestamp cronológico.

### 2. Reconciliador de Fatos e Versionamento (`supersedes_id`)

A tabela `agent_memory` rastreia a evolução do conhecimento:
* Novas memórias ou edições de notas do Obsidian que substituem versões anteriores recebem `supersedes_id` (rastreado localmente em `~/.estudiohc_collector_state.json`).
* O fato antigo é marcado como `status='superseded'` e apontado para o novo ID (`superseded_by`).
* Consultas padrão retornam estritamente fatos `status='active'`, evitando que agentes usem credenciais, arquiteturas ou portas obsoletas.

### 3. Coding Chain Store (Diff-Chain em SQLite)

Rastreia a evolução do código em `data/coding_memory_cv.db` sem gastar tokens de contexto:
* Cada alteração gera uma rodada (`round`) vinculada ao branch, arquivo e função.
* Preserva os patches Git reais e os motivos declarados pelo usuário, viabilizando auditoria de reversões.

---

## ?? Configuração de Estações Coletoras (Windows 11 e Linux Desktop)

### 1. Arquivo de Ambiente da Estação (`~/.estudiohc/.env`)

Em cada estação de trabalho (`WIN-X99` ou `linux-i5`), crie `~/.estudiohc/.env`:

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

### 2. Scripts da Estação (`scripts/`)

* `scripts/obsidian_collector.py`: Daemon coletor v2.0 (Ingestão Tripla + Heartbeat + Agenda + Pull Bidirecional + Failover Automático).
* `scripts/agenda_sync.py`: Sincronizador de checkboxes `- [ ]` / `- [x]` de `00 - Painel/Agenda.md` e `02 - Diário/<YYYY-MM-DD>.md` com `/api/agenda`.
* `scripts/station_bootstrap_win.ps1`: Script de inicialização no Windows (acionado pela Tarefa Agendada `\EstudioHC-StationSync` via `pythonw.exe`).
* `scripts/failover_monitor.py`: Monitora Contabo e altera `hosts` automaticamente para failover/failback.
* `scripts/start_failover_monitor.bat`: Script batch para iniciar o Failover Monitor.
* `scripts/switch-to-contabo.cmd` e `scripts/switch-to-local.cmd`: Comutadores manuais do DNS canônico `hub.estudiohc` no arquivo `hosts`.

---

## ?? Guia de Implantação em Novos Servidores (Onboarding)

Siga este procedimento passo a passo para instalar e executar o **EstudioHC Memory Suite** em um servidor Linux (Ubuntu 24.04 ou Debian 13):

### 1. Pré-Requisitos do Sistema
```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip sqlite3 curl ufw
```

### 2. Clonagem do Repositório
```bash
mkdir -p ~/Apps && cd ~/Apps
git clone https://github.com/helciocosta/EstudioHC-Memory-Suite.git
cd EstudioHC-Memory-Suite
```

### 3. Estruturação dos Ambientes Virtuais (Venvs)
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

### 4. Validação de Saúde Operacional e Testes Automatizados
```bash
# 1. Executar suíte de testes da API Central (33 testes)
cd apps/api && PYTHONPATH=. .venv/bin/pytest -q

# 2. Testar API Central HTTPS
curl -sk https://127.0.0.1:5050/api/status

# 3. Testar MCP SSE Server
curl -s http://127.0.0.1:5051/sse | head -n 3

# 4. Testar ChromaDB Server
curl -s http://127.0.0.1:8765/mcp | head -n 3
```

---

## ?? Licença

Distribuído sob a licença **Apache-2.0**. Consulte `LICENSE` para mais detalhes.