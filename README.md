# EstudioHC Memory Suite v4.6

**Secretário Digital e Orquestrador Central de Inteligência** — Coordena, comanda e gerencia memória permanente, working memory, agenda, projetos, notas do Obsidian, documentos vetoriais e cadeias de evolução de código para todos os agentes de IA na malha Tailscale.

![Versão](https://img.shields.io/badge/versão-4.6.0-00e5ff)
![Python](https://img.shields.io/badge/python-3.12-7000ff)
![Licença](https://img.shields.io/badge/licença-Apache--2.0-4c6ef5)
![MCP](https://img.shields.io/badge/mcp-14%20ferramentas-00ff9d)
![Rede](https://img.shields.io/badge/rede-Tailscale%20Mesh-ffae00)

---

## 🏛️ Topologia e Arquitetura do Ecossistema

O **EstudioHC Memory Suite** foi arquitetado sob princípios de alta resiliência, baixa latência e eficiência energética:

```
                            ┌────────────────────────────────────────┐
                            │      Agentes de IA & Clientes          │
                            │  (OMP, OpenCode, Jarvis, Claude Code)  │
                            └───────────────────┬────────────────────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          │     Rede Tailscale (WireGuard Mesh)       │
                          │        hub.estudiohc (DNS Canônico)       │
                          └─────────────┬─────────────────┬───────────┘
                                        │                 │
               [Nó Primário 24/7]       │                 │  [Nó Reserva / Lab Dev]
                                        ▼                 ▼
             ┌───────────────────────────────┐   ┌───────────────────────────────┐
             │       VPS Contabo (24/7)      │   │     Servidor Local (32GB)     │
             │         100.64.117.78         │   │        100.107.208.50         │
             │ ───────────────────────────── │   │ ───────────────────────────── │
             │ • API Central (:5050 HTTPS)   │◄──┼─ Replicação WAL SQLite & Git  │
             │ • MCP SSE Server (:5051)      │   │ • API Central (:5050 HTTPS)   │
             │ • ChromaDB SSE (:8765)        │   │ • MCP SSE Server (:5051)      │
             │ • Sync Connect (:5052)        │   │ • ChromaDB SSE (:8765)        │
             │ • Dashboard Web (:8585)       │   │ • Sync Connect (:5052)        │
             │ • SQLite Master (estudiohc.db)│   │ • Dashboard Web (:8585)       │
             │ • Coding Chain (Diff-Chain)   │   │ • Coding Chain (Diff-Chain)   │
             └───────────────────────────────┘   └───────────────────────────────┘
                               ▲                                 ▲
                               └─────────────────┬───────────────┘
                                                 │ Coleta Contínua
                                 ┌───────────────┴───────────────┐
                                 │      Estações de Trabalho     │
                                 │   • win-x99 (Windows 11)      │
                                 │   • linux-i5 (Debian 13)      │
                                 │ (Obsidian + Watchdog + Git)   │
                                 └───────────────────────────────┘
```

1. **Hub Central 24/7 (VPS Contabo `100.64.117.78`)**:
   - Nó permanente que mantém os serviços ativos ininterruptamente para consumo móvel e remoto.
2. **Laboratório Sob Demanda & Reserva Imediata (Servidor Local 32GB `100.107.208.50`)**:
   - Ambiente de computação pesada (Ollama, fine-tuning). Permanece desligado na maior parte do tempo para economia de energia.
   - Ao ser inicializado, possui paridade total de serviços e assume a rede em caso de contingência na VPS.
3. **Coletores Locais Obsidian nas Estações**:
   - Os cofres pessoais do Obsidian sincronizam notas técnicas e diários automaticamente via `estudiohc-collector.service` com a API (`POST /api/nota`) e ChromaDB (`doc_add`).

---

## 🛠️ Catálogo de Ferramentas MCP (14 Ferramentas Ativas)

O servidor MCP SSE na porta `5051/sse` serve 14 ferramentas estruturadas para agentes autônomos:

| Categoria | Ferramenta | Descrição e Parâmetros |
|---|---|---|
| **Working Memory** | `wm_push` | Insere item na memória de trabalho volátil/sessão (`content`, `category`). |
| | `wm_pop` | Remove e retorna o último item da memória de trabalho. |
| | `wm_list` | Lista todos os itens da memória de trabalho da sessão atual. |
| | `wm_clear` | Limpa a memória de trabalho (com filtro opcional por `category`). |
| | `wm_consolidate` | Promove itens da working memory para a memória permanente central. |
| **Long-Term Memory** | `add_memory` | Grava memória permanente no SQLite. Suporta `supersedes_id` para substituição e versionamento lógico. |
| | `search_memory` | **Busca Híbrida RRF (Reciprocal Rank Fusion)** multi-canal (Vetorial FAISS + Léxico BM25 + Recência). |
| | `get_status` | Retorna o sumário de tarefas pendentes e concluídas de um projeto. |
| **Engenharia de Código** | `code_record_change` | Registra diffs Git e motivos de alteração na **Version-Evolution Chain** (custo zero de LLM). |
| | `code_get_history` | Recupera a linha do tempo de alterações, versões e diffs de arquivos/projetos. |
| **Documentos Vetoriais** | `doc_add` | Indexa documentos completos no ChromaDB por coleção (`project`, `documents`). |
| | `doc_search` | Realiza busca semântica em documentos inteiros no ChromaDB com metadados. |
| | `doc_list` | Lista documentos e metadados armazenados em uma coleção. |
| | `doc_delete` | Remove um documento específico do ChromaDB por ID. |

---

## 🔬 Inovações Algorítmicas Incorporadas (Tencent Hy-Memory)

### 1. Fusão Híbrida Multi-Canal (RRF)
Em vez de misturar distâncias vetoriais com scores de texto empíricos, o `search_memory` implementa a fórmula de Cormack et al. (2009):
$$\text{score}(d) = \sum_{c} \frac{w_c}{60 + \text{rank}_c(d)}$$
* **Canal Vetorial ($w=1.2$):** Similaridade de cosseno via FAISS com modelo `all-MiniLM-L6-v2`.
* **Canal Léxico ($w=1.0$):** Sobreposição exata de tokens da query e bônus de categoria.
* **Canal Temporal ($w=0.4$):** Freshness score baseado no timestamp cronológico.

### 2. Reconciliador de Fatos e Versionamento
A tabela `agent_memory` rastreia a evolução do conhecimento:
* Novas memórias que substituem parâmetros antigos recebem `supersedes_id`.
* O fato antigo é marcado como `status='superseded'` e apontado para o novo ID.
* Consultas padrão retornam estritamente fatos `status='active'`, evitando que agentes usem credenciais ou portas antigas.

### 3. Coding Chain Store (Diff-Chain em SQLite)
Rastreia a evolução do código em `data/coding_memory_cv.db` sem gastar tokens de contexto:
* Cada alteração gera uma rodada (`round`) vinculada ao branch, arquivo e função.
* Preserva os patches Git reais e os motivos declarados pelo usuário, viabilizando auditoria de reversões.

---

## 🚀 Guia de Implantação em Novas Máquinas (Onboarding)

Siga este procedimento passo a passo para instalar e executar o **EstudioHC Memory Suite** em um novo servidor Linux (Ubuntu 24.04 ou Debian 13):

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
O projeto utiliza ambientes virtuais isolados por serviço:

```bash
# A. API Central
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install --upgrade pip
apps/api/.venv/bin/pip install -r apps/api/requirements.txt

# B. MCP Memory SSE
python3 -m venv apps/mcp-memory/.venv
apps/mcp-memory/.venv/bin/pip install --upgrade pip
apps/mcp-memory/.venv/bin/pip install -r apps/mcp-memory/requirements.txt

# C. ChromaDB MCP
python3 -m venv apps/chromadb-mcp/.venv
apps/chromadb-mcp/.venv/bin/pip install --upgrade pip
apps/chromadb-mcp/.venv/bin/pip install -r apps/chromadb-mcp/requirements.txt
```

### 4. Configuração de Variáveis de Ambiente e Certificados TLS
```bash
# Configurar API Central
cp apps/api/.env.example apps/api/.env
# Definir API_KEY segura de 64 caracteres em apps/api/.env

# Gerar Certificado SSL Autoassinado para a porta 5050 HTTPS
sudo mkdir -p /etc/estudiohc/ssl
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/estudiohc/ssl/estudiohc.key \
  -out /etc/estudiohc/ssl/estudiohc.crt \
  -subj "/C=BR/ST=SP/L=Local/O=EstudioHC/CN=hub.estudiohc"
sudo chmod 600 /etc/estudiohc/ssl/estudiohc.key
```

### 5. Inicialização do Banco de Dados SQLite Mestre
```bash
mkdir -p data
sqlite3 data/estudiohc.db < config/schema.sql
# Ativar modo WAL para alta concorrência
sqlite3 data/estudiohc.db "PRAGMA journal_mode=WAL;"
```

### 6. Instalação e Ativação dos Serviços Systemd
Copie os arquivos de unidade para o systemd do host:

```bash
sudo cp config/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now estudiohc-api.service
sudo systemctl enable --now estudiohc-mcp-sse.service
sudo systemctl enable --now chromadb-mcp.service
sudo systemctl enable --now estudiohc-sync-connect.service
sudo systemctl enable --now estudiohc-dashboard.service
```

### 7. Validação de Saúde Operacional
```bash
# 1. Testar API Central HTTPS
curl -sk https://127.0.0.1:5050/api/status

# 2. Testar MCP SSE Server
curl -s http://127.0.0.1:5051/sse | head -n 3

# 3. Testar ChromaDB Server
curl -s http://127.0.0.1:8765/sse | head -n 3
```

---

## 📄 Licença
Distribuído sob a licença **Apache-2.0**. Consulte `LICENSE` para mais detalhes.
