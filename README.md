# EstudioHC Memory Suite v4.3

Infraestrutura centralizada de memória, contexto e inferência local para o
ecossistema de agentes AI de Helcio O. Costa — com **servidor central
orquestrando múltiplas estações** na rede Tailscale.

> **Repositório:** `github.com/helciocosta/EstudioHC-Memory-Suite.git`
> **Servidor Central:** `vmi2968998` (Contabo) · Tailscale `100.64.117.78` · API na porta 5050
> **Stack:** CPU-only · Ubuntu 24.04 · Python 3.11 · FastAPI 3.0 · mcp 1.28

---

## Sumário

- [Quickstart](#quickstart)
- [Arquitetura Multi-Máquina](#arquitetura-multi-máquina)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Serviços por Máquina](#serviços-por-máquina)
- [API Central (porta 5050)](#api-central-porta-5050)
- [MCP Memory Server](#mcp-memory-server)
- [Documentos por Projeto (ChromaDB)](#documentos-por-projeto-chromadb)
- [Memória Multi-Agente e Continuidade de Tarefas](#memória-multi-agente-e-continuidade-de-tarefas)
- [Conectando Agentes ao Stack de Memória](#conectando-agentes-ao-stack-de-memória)
- [Autenticação e Rate Limiting](#autenticação-e-rate-limiting)
- [Testes e CI](#testes-e-ci)
- [Local Memory Stack (WAL de Sobrevivência)](#local-memory-stack-wal-de-sobrevivência)
- [Modelos de Inferência Local](#modelos)
- [Provisionamento de Novas Estações](#provisionamento-de-novas-estações)
- [Monitoramento](#monitoramento)
- [Variáveis de Ambiente](#variáveis-de-ambiente)

---

## Quickstart

Como colocar o stack no ar em menos de 5 minutos, seja no servidor central ou
numa máquina de desenvolvimento.

### 1. Rodar a API Central localmente

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 5050
```

Teste:

```bash
curl -s http://localhost:5050/api/status
# {"status":"online","servidor":"central","hermes":true,"opencode":true,"database":"SQLite",...}
```

> O `DATABASE_URL` default aponta para `~/Apps/EstudioHC-Memory-Suite/data/estudiohc.db`.
> Para isolar em outro caminho, exporte `DATABASE_URL` antes de subir.

### 2. Rodar o MCP Memory Server localmente

```bash
cd apps/mcp-memory
python3 -m venv .venv
.venv/bin/pip install -e .
MEMORY_API_URL=http://localhost:5050 .venv/bin/python src/memory_server.py
```

O servidor inicia no modo MCP STDIO (fica aguardando o cliente). Para testar
como *cliente*, use o `OpenCode` ou um script de handshake MCP apontando para
o mesmo binário.

### 3. Rodar os testes

```bash
cd apps/api
.venv/bin/python -m pytest -v     # 4 testes: id do /remember, status legível, auth
```

### 4. Gravar a primeira memória

```bash
curl -s -X POST http://localhost:5050/remember \
  -H "Content-Type: application/json" \
  -d '{"agent_name":"opencode","project":"opencode","category":"context","content":"{\"s\":\"Hello World\",\"r\":null,\"c\":true}"}'
# {"status":"success","id":1}

curl -s http://localhost:5050/recall/opencode
# [{"id":1,"timestamp":"...","agent_name":"opencode","project":"opencode",...}]
```

### 5. Testar a camada de documentos (ChromaDB)

O `chromadb-mcp` precisa estar ativo (porta 8765). Nos testes locais, suba
primeiro o servidor SSE:

```bash
# no servidor central (ou estação com o serviço instalado)
sudo systemctl start chromadb-mcp.service
curl -s -H "Accept: text/event-stream" http://localhost:8765/mcp   # deve abrir stream SSE
```

Depois use as tools `doc_add` / `doc_search` do MCP Memory Server — elas
criam a coleção `docs_<project>` automaticamente no primeiro `doc_add`.

---


## Arquitetura Multi-Máquina

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        REDE TAILSCALE (100.x.x.x)                        │
│  Conexão direta entre estações e servidor central (p2p, criptografado)  │
└──────────────────────────────────────────────────────────────────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  SERVIDOR    │   │  ESTAÇÃO 1   │   │  ESTAÇÃO N        │
│  (Contabo)   │   │  (helcio-x99)│   │  (qualquer PC)    │
│              │   │              │   │                   │
│  API :5050   │   │  llama.cpp   │   │  llama.cpp        │
│  SQLite ÚNICO│   │  :11434      │   │  :11434           │
│  ChromaDB    │   │  :11435      │   │  :11435           │
│  :8765 (SSE) │   │  MCP → API   │   │  MCP → API        │
│  Agenda/Proj │   │  (dev/lab)   │   │  (dev/lab)        │
│  Backup diário│  │              │   │                   │
│  Dashboard   │   │              │   │                   │
└──────────────┘   └──────────────┘   └──────────────────┘
       ▲                    ▲                    ▲
       │                    │                    │
       └───────── MEMORY_API_URL=http://100.64.117.78:5050 ─────────┘
                          (todas as estações)

┌──────────────────────────────────────────────────────────────────┐
│                    WORKING MEMORY (MCP Tools)                     │
│  Volátil · sessão-escopo · wm_push/pop/list/clear/consolidate    │
│  Budget: MEMORY_MAX_TOKENS = 2048 · overflow: drop + log         │
└──────────────────────────┬───────────────────────────────────────┘
                           │ consolidate() → MEMORY_API_URL
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│            LONG-TERM MEMORY (SERVIDOR CENTRAL :5050)              │
│  Persistente · FastAPI · SQLite único · Decaimento temporal      │
│  • 0-30 dias:  peso normal (1.0 → 0.6)                          │
│  • 30-60 dias: peso reduzido (0.3 → 0.0)                        │
│  • >60 dias:   arquivada/excluída                                │
│  • Acessível por todas as estações via Tailscale                 │
└──────────────────────────┬───────────────────────────────────────┘
                           │ search_memory()
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    RANKING HÍBRIDO (FAISS + RRF)                  │
│  Recência (40%) + Keyword Match (35%) + Categoria (25%)          │
│  + RRF: keyword rank (40%) + vector rank (60%)                   │
│  Injeção budget-aware: top-1 sempre, demais até 1024 tok         │
└──────────────────────────┬───────────────────────────────────────┘
                           │ /v1/chat/completions
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    INFERÊNCIA LOCAL (cada estação)                │
│  llama-server.service  :11434 → cybersec-assistant-3b            │
│  llama-server-summarizer :11435 → Qwen3-1.7B                     │
│  Flash Attention · KV Cache Shift · CPU-only                     │
│  Cada estação tem seu próprio LLM (sem latência de rede)          │
└──────────────────────────────────────────────────────────────────┘
```

A camada de **documentos por projeto** (ChromaDB) é uma via paralela à memória:
documentos longos (manuais, specs, logs, artigos) são armazenados por
similaridade semântica e buscados com as tools `doc_*`, sem competir com o
fluxo de memória resumida do SQLite.

---

## Estrutura do Projeto

```
EstudioHC-Memory-Suite/
├── apps/
│   ├── api/                      → FastAPI Central (porta 5050)
│   │   ├── src/                  → main, config, security, database, models, routers
│   │   ├── tests/                → pytest (conftest, test_memory, test_security)
│   │   ├── alembic/              → Migrations
│   │   ├── Dockerfile
│   │   └── pyproject.toml        → deps + dev extra + pytest config
│   ├── chromadb-mcp/             → MCP SSE server (ChromaDB, porta 8765)
│   │   └── server.py             → 8 tools (list/create/delete collection, add/search/get/delete documents, info)
│   ├── mcp-stdio/                → MCP stdio legado
│   │   └── Dockerfile
│   ├── mcp-memory/               → MCP Memory Server moderno (12 tools)
│   │   ├── src/
│   │   │   ├── memory_server.py  → WM + FAISS + RRF + budget + doc_* tools
│   │   │   ├── chroma_client.py  → Cliente SSE do ChromaDB (camada de documentos)
│   │   │   ├── summarizer.py     → Sumarização via llama.cpp:11435 (Qwen3-1.7B)
│   │   │   └── embedder.py       → Embeddings + índice FAISS
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── dashboard/                → Web UI (porta 8585)
│       ├── static/               → index.html, projeto.html, agenda.json
│       ├── Dockerfile
│       └── pyproject.toml
├── cli/
│   └── estudio                   → CLI de status
├── config/                        → Configurações locais da estação
│   ├── skills/
│   │   └── journal_recovery/
│   │       └── SKILL.md          → Skill de WAL textual pós-queda
│   └── tmux/
│       └── .tmux.conf            → history-limit 50000 + remain-on-exit
├── .github/
│   └── workflows/
│       └── ci.yml                → CI: pytest no apps/api (push master + PR)
├── orchestrator/                  → Orquestração de agentes (agent_orchestrator.py, dashboard.py)
├── scripts/
│   ├── backup.sh                 → Backup diário SQLite + FAISS
│   ├── bootstrap-memory-stack.sh → Instala journal_recovery + configs locais
│   ├── monitor.sh                → Coleta métricas RAM/CPU/cache
│   └── setup-machine.sh          → Provisionamento completo de estação
├── docker-compose.yml            → api + dashboard
├── .env.example
├── .gitignore
├── README.md
├── STATUS_ESTUDIOHC.md
└── PLANO_UNIFICACAO.md           → Roteiro de modernização
```

> `server/` e `dashboard/` (raiz) e `apps/mcp-stdio/` são **legados** e não são
> usados pelos serviços ativos.

---

## Serviços por Máquina

### Servidor Central (Contabo — `100.64.117.78`)

| Serviço | Porta | Função |
|---|---|---|
| `estudiohc-api.service` | 5050 (0.0.0.0) | API Central — FastAPI, SQLite único, agenda, projetos, memória |
| `estudiohc-dashboard.service` | 8585 (0.0.0.0) | Web UI de administração |
| `chromadb-mcp.service` | 8765 (0.0.0.0) | MCP SSE server do ChromaDB (camada de documentos) |
| `llama-server.service` | 11434 (0.0.0.0) | LLM principal (cybersec-assistant-3b) — opcional no servidor |
| `llama-server-summarizer.service` | 11435 (127.0.0.1) | Sumarizador (Qwen3-1.7B) — opcional no servidor |
| `estudiohc-backup.timer` | — | Backup diário do SQLite + FAISS às 03:00 |
| `estudiohc-monitor.timer` | — | Coleta de métricas RAM/CPU/cache a cada 5 min |

### Estações (qualquer PC na Tailscale)

| Serviço | Porta | Função |
|---|---|---|
| `llama-server.service` | 11434 (0.0.0.0) | LLM principal — inferência local rápida |
| `llama-server-summarizer.service` | 11435 (127.0.0.1) | Sumarizador local |
| MCP memory (STDIO) | — | Conecta ao servidor central via `MEMORY_API_URL` |

> **Nas estações, a API NÃO roda localmente.** O MCP memory aponta para
> `http://100.64.117.78:5050` (servidor central) via variável de ambiente.
> Isso garante que agenda, projetos e tarefas sejam compartilhados entre
> todas as máquinas.

Flags comuns do llama.cpp em todas as máquinas:
```
--flash-attn auto --cache-reuse 256 --keep -1
--device none --no-kv-offload --cont-batching
```

---

## API Central (porta 5050)

FastAPI Central — servidor HTTP de persistência e coordenação.
Versão 3.0.0 · autenticação opcional por API Key (ver [Autenticação](#autenticação-e-rate-limiting)).

| Método | Rota | Descrição |
|---|---|---|
| POST | `/remember` | Salva memória de agente — retorna `{"status":"success","id":N}` |
| GET | `/recall/{project}` | Recupera memórias |
| GET | `/status/{project}` | Tasks pendentes/concluídas (texto legível) |
| GET | `/api/agenda` | Lista agenda |
| POST | `/api/agenda` | Salva agenda (merge/upsert por `id`) |
| DELETE | `/api/agenda/{id}` | Remove um evento da agenda |
| GET | `/api/diarios` | Lista diários |
| GET | `/api/diario/{data}` | Lê diário |
| POST | `/api/diario/{data}/resumo` | Resumo do diário |
| POST | `/api/nota` | Adiciona nota |
| GET | `/api/projetos` | Lista projetos |
| POST | `/api/projetos/sync` | Sincroniza projetos |
| POST | `/api/projetos/gerar-relatorio` | Relatório IA do projeto |
| GET | `/api/estacoes` | Lista estações |
| POST | `/api/estacoes/ping` | Heartbeat de estação |
| POST | `/api/hermes` | Chat com IA (OpenCode → Hermes) — com rate limit |
| GET | `/api/tarefas` | Lista tarefas |
| POST | `/api/tarefas` | Cria tarefa |
| PUT | `/api/tarefas/{id}` | Atualiza tarefa |
| DELETE | `/api/tarefas/{id}` | Remove tarefa |
| GET | `/api/status` | Health check (aberto) |
| GET | `/api/status_md` | Status em markdown (aberto) |

Docs interativos: `/docs` (Swagger) e `/redoc` (ReDoc).

> **Autenticação:** quando `API_KEY` está configurada, todas as rotas acima
> (exceto `/api/status` e `/api/status_md`) exigem o header `X-API-Key`.
> Com `API_KEY` vazia (default), a API fica aberta — modo desenvolvimento.

### Payloads e Exemplos

Exemplos de integração (agenda, notas, diários, projetos, tarefas, estações e Hermes).
Autenticação via header `X-API-Key` quando ativa.

**Agenda** — `GET /api/agenda` lista todos os eventos.
`POST /api/agenda` faz **merge/upsert por `id`**: insere eventos novos, atualiza
os que já existem e **preserva eventos não enviados** (não é mais destrutivo).
`DELETE /api/agenda/{id}` remove um único evento.

```bash
curl -X POST "http://100.64.117.78:5050/api/agenda" \
  -H "Content-Type: application/json" \
  -d '{"eventos": [
    {"id": "a1", "data": "2026-08-03", "hora": "09:00", "titulo": "Reunião equipe", "estacao": "central", "descricao": "Check-in semanal"},
    {"id": "a2", "data": "2026-08-04", "hora": "14:30", "titulo": "Deploy", "estacao": "central"}
  ]}'

# Remove um evento específico
curl -X DELETE "http://100.64.117.78:5050/api/agenda/a1"
```

**Notas** — `POST /api/nota` adiciona uma nota à estação informada.

```bash
curl -X POST "http://100.64.117.78:5050/api/nota" \
  -H "Content-Type: application/json" \
  -d '{"texto": "Ideia para o módulo de memória", "estacao": "central"}'
```

**Diários** — `GET /api/diarios` lista os diários; `GET /api/diario/{data}` lê o
diário de `YYYY-MM-DD`; `POST /api/diario/{data}/resumo` salva/atualiza o resumo.

```bash
curl -X POST "http://100.64.117.78:5050/api/diario/2026-08-02/resumo" \
  -H "Content-Type: application/json" \
  -d '{"resumo": "Dia de manutenção do servidor", "agente": "opencode"}'
```

**Projetos** — `GET /api/projetos` lista; `POST /api/projetos/sync` cria/atualiza em lote.

```bash
curl -X POST "http://100.64.117.78:5050/api/projetos/sync" \
  -H "Content-Type: application/json" \
  -d '{"projetos": [
    {"nome": "EstudioHC-Memory-Suite", "local_caminho": "~/Apps/EstudioHC-Memory-Suite", "status": "ativo", "tags": "memoria,ia", "estacao": "central"}
  ]}'

curl -X POST "http://100.64.117.78:5050/api/projetos/gerar-relatorio" \
  -H "Content-Type: application/json" \
  -d '{"nome": "EstudioHC-Memory-Suite", "estacao": "central"}'
```

**Tarefas** — CRUD completo.

```bash
curl -X POST "http://100.64.117.78:5050/api/tarefas" \
  -H "Content-Type: application/json" \
  -d '{"projeto_id": 1, "titulo": "Documentar payloads da API", "status": "pendente", "prioridade": "media", "data_limite": "2026-08-10"}'

curl -X PUT "http://100.64.117.78:5050/api/tarefas/1" \
  -H "Content-Type: application/json" \
  -d '{"status": "concluida", "prioridade": "alta"}'
```

**Estações** — `GET /api/estacoes` lista as estações conhecidas.
`POST /api/estacoes/ping` aceita **query string** OU **body JSON**:

```bash
# Via query string
curl -X POST "http://100.64.117.78:5050/api/estacoes/ping?hostname=pc-arquimedes&ip=100.64.117.5"

# Via body JSON
curl -X POST "http://100.64.117.78:5050/api/estacoes/ping" \
  -H "Content-Type: application/json" \
  -d '{"hostname": "pc-arquimedes", "ip": "100.64.117.5"}'
```

**Hermes** — `POST /api/hermes` chat com a IA central (OpenCode → Hermes).
Rate limit de 10 req/min por IP.

```bash
curl -X POST "http://100.64.117.78:5050/api/hermes" \
  -H "Content-Type: application/json" \
  -d '{"mensagem": "Resuma o estado do projeto", "contexto": "README do EstudioHC"}'
```

---

## MCP Memory Server

O `apps/mcp-memory/` implementa o servidor MCP STDIO com **12 ferramentas**
registradas no OpenCode.

### Ferramentas

| Ferramenta | Descrição |
|---|---|
| `add_memory` | Persiste informação no LTM com sumarização opcional |
| `search_memory` | Busca híbrida (keyword + FAISS) com RRF e budget |
| `get_status` | Resumo de tasks pendentes/concluídas do projeto |
| `wm_push` | Adiciona item à Working Memory (budget-aware) |
| `wm_pop` | Remove item mais recente da WM |
| `wm_list` | Lista WM com token count (ex: `3 items, 512/2048 tok`) |
| `wm_clear` | Limpa WM (opcional: filtro por categoria) |
| `consolidate` | Move WM → LTM com sumarização LLM |
| `doc_add` | Armazena documento longo de um projeto no ChromaDB |
| `doc_search` | Busca semântica em documentos do projeto (ChromaDB) |
| `doc_list` | Lista documentos do projeto com contagem total |
| `doc_delete` | Remove um documento pelo id |

### Ranking Híbrido (search_memory)

```
score = decay(recência) × 0.4 + keyword_match × 0.35 + categoria × 0.25
RRF   = keyword_rank × 0.4 + vector_rank × 0.6
```

- Decaimento: 30 dias para início, 60 dias para exclusão
- FAISS IndexFlatIP (all-MiniLM-L6-v2, dim 384)
- Budget: `MEMORY_INJECT_TOKENS` (1024) — top-1 sempre incluso
- Cada memória é indexada no FAISS com o **id real** retornado pela API
  (`{id}|{category}`), garantindo que o ranking vetorial contribua de fato.

### Resiliência e Timeouts

O MCP Memory Server incorpora proteções contra falhas de inicialização
para garantir que o servidor nunca bloqueie o cliente (OpenCode):

| Camada | Timeout | Comportamento em Falha |
|---|---|---|
| **Modelo de Embeddings** (`embedder.py`) | 30s | `SentenceTransformer("all-MiniLM-L6-v2")` é carregado em thread separada. Se o download do HuggingFace exceder 30s, o modelo é abortado e a busca vetorial (FAISS) é desabilitada. A memória API (keyword) continua funcionando. |
| **FAISS Rebuild** (`memory_server.py:main()`) | 30s | `asyncio.wait_for()` no startup. Se o rebuild exceder 30s (ex.: modelo não disponível, API central offline), o servidor MCP **ainda inicializa** normalmente — apenas vetor search fica temporariamente indisponível. |
| **API Central** (`handle_call_tool`) | 10s (httpx) | `asyncio.TimeoutError` capturado e retornado como mensagem de texto ao cliente, sem crash. |

> **Efeito colateral:** Se o modelo de embeddings não carregar, o `search_memory`
> opera apenas com ranking por keyword (recência + matching textual). O registro
> `[embedder] Model load timed out` aparece no stderr do servidor.

### Integração OpenCode (em Estações)

Registrado em `~/.config/opencode/opencode.jsonc`, apontando para o servidor central:

```json
{
  "mcp": {
    "memory": {
      "type": "local",
      "command": [
        "env",
        "MEMORY_API_URL=http://100.64.117.78:5050",
        "python3", "/caminho/para/apps/mcp-memory/src/memory_server.py"
      ],
      "enabled": true
    }
  }
}
```

> A variável `MEMORY_API_URL` redireciona a persistência para o servidor central.
> Em estações novas, use `scripts/setup-machine.sh` para configurar automaticamente.

---

## Documentos por Projeto (ChromaDB)

A camada de documentos armazena conteúdo longo (manuais, specs, logs,
artigos) com **busca semântica por similaridade**, de forma independente da
memória resumida do SQLite.

### Arquitetura

```
MCP Memory Server (memory_server.py)
   │  tools doc_add / doc_search / doc_list / doc_delete
   ▼
chroma_client.py  (cliente MCP via SSE, reconnect automático)
   │  sse_client → http://localhost:8765/mcp
   ▼
chromadb-mcp server (porta 8765, SSE)  →  ChromaDB PersistentClient
   ├── add_documents      → coleta `docs_<project>` (criada on-demand)
   ├── search_documents   → busca semântica com score
   ├── get_documents      → paginação (limit/offset)
   ├── delete_documents   → remove por ids
   ├── get_collection_info / list_collections / create_collection / delete_collection
```

### Modelo de Dados

- **Coleção por projeto:** `docs_<project>` (ex: `docs_opencode`), criada
  automaticamente no primeiro `doc_add`.
- **id:** `<slug>_<YYYYmmddHHMMSS>` — slug = título em minúsculas,
  não-alfanumérico → `_`, truncado em 40 chars (fallback `doc`).
- **metadata:** `{title, tags, ts, project}` — `tags` é string separada por
  vírgula (nunca lista); `ts` é ISO em segundos.

### Ferramentas

| Tool | Parâmetros | Retorno |
|---|---|---|
| `doc_add` | `project` (default `opencode`), `title`, `content`, `tags[]` | `{"id","collection","added"}` |
| `doc_search` | `query` (obrigatório), `project`, `limit` (1-20, default 5) | linhas `[ts] (score) title` + snippet |
| `doc_list` | `project`, `limit` (1-100, default 20) | linhas `id [ts] title` |
| `doc_delete` | `id` (obrigatório), `project` | `{"deleted","collection","id"}` |

Se a coleção de um projeto ainda não existe, as tools retornam a mensagem
`collection 'docs_<project>' not found (no documents yet for project '<project>')`.

### Integração OpenCode (no servidor)

O memory server em produção roda via SSH do opencode.json do Windows:

```json
"estudiohc-memory": {
  "type": "local",
  "command": ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
    "deploy@100.64.117.78",
    "cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && ./.venv/bin/python src/memory_server.py"]
}
```

O `chromadb-mcp` também é registrado como servidor MCP remoto (`chromadb-contabo`,
SSE em `http://100.64.117.78:8765/mcp`) para acesso direto às tools do ChromaDB.

---

## Memória Multi-Agente e Continuidade de Tarefas

O EstudioHC é **agnóstico de agente**: qualquer agente de IA que suporte o
protocolo MCP (OpenCode, Claude Code, Codex, Gemini/Antigravity, Mistral,
OMP e outros) grava e lê memória no **mesmo** servidor central, sem
adaptação de código. A única exigência é registrar o `memory_server.py`
como servidor MCP e apontar `MEMORY_API_URL` para o central.

### Como a memória é gravada (fluxo em qualquer estação)

```
Agente (OpenCode/Claude/Codex/...)
   │  1. wm_push → Working Memory local (volátil, budget 2048 tok)
   │  2. consolidate ou add_memory
   ▼
memory_server.py (MCP stdio, roda local na estação)
   │  3. content ≥ 60 chars? → summarizer.py → llama.cpp :11435 (Qwen3-1.7B)
   │  4. POST /remember  {agent_name, project, category, content}
   ▼
API Central (100.64.117.78:5050)
   │  5. SQLite (data/estudiohc.db) — fonte única de verdade
   │  6. retorna id real (ex: 28)
   ▼
memory_server.py
   │  7. FAISS.add(texto, f"{id}|{category}") — índice vetorial local
```

- **`agent_name`** identifica a origem da memória (`AGENT_NAME` env, default
  `opencode`) — cada agente registrado com seu próprio valor.
- **`project`** agrupa memórias por contexto de trabalho (ex: `opencode`,
  `claude`, `estudiohc`).
- **`category`** orienta a busca: `task_pending`, `task_completed`,
  `decision`, `preference`, `context`, `note`.
- A **Working Memory** é local e volátil; o `consolidate` a move para o LTM
  central. Para não perder contexto em queda, use o `journal_recovery`
  (ver [Local Memory Stack](#local-memory-stack-wal-de-sobrevivência)).

### Continuidade: estação A desligada → estação B retoma

O cenário que a suite resolve:

```
Estação A (membro X)                          Estação B (membro Y)
  tarefa iniciada  ──────────────────────────▶  mesma tarefa retomada
  add_memory/consolidate                         search_memory / get_status
        │                                                │
        ▼                                                ▼
  SQLite central (5050) ◀─── dados persistentes ────►  SQLite central (5050)
  + FAISS index (local da estação A)                   + FAISS index (local da estação B)
```

1. **Membro X** inicia a tarefa na Estação A e chama `add_memory` (ou
   `consolidate`). A memória vai para o SQLite central e o FAISS local da A.
2. **A é desligada.** Nada se perde: os dados já estão no servidor central.
3. **Membro Y** abre a Estação B, registra o MCP apontando para
   `100.64.117.78:5050` e pergunta ao agente "retome a tarefa X".
4. O agente chama `search_memory(project, "tarefa X")` → o MCP da B busca
   no SQLite (keyword) e, ao subir, **rebuild_vector_index** reconstrói o
   FAISS local da B via `GET /recall/{project}?limit=200`.
5. `get_status(project)` mostra as tasks pendentes em texto legível.
6. A tarefa continua de onde parou — com o histórico da A.

> **Nota de design:** o índice FAISS é **local por estação** e reconstruído
> no startup do MCP (30s de tolerância). O SQLite central é a verdade;
> o FAISS é apenas aceleração de ranking vetorial. Qualquer estação nova
> reconstrói seu índice sozinha.

### Projeto vs. Agente — como separar contextos

Use **`project`** para separar linhas de trabalho, não o agente:

| Projeto | Conteúdo típico |
|---|---|
| `opencode` | Memórias das sessões OpenCode |
| `claude` | Memórias das sessões Claude Code |
| `estudiohc` | Contexto de manutenção/evolução do próprio stack |
| `cliente-X` | Projeto de um cliente específico |

O mesmo agente pode operar em vários projetos; o mesmo projeto pode ser
continuado por qualquer agente/estação.

---

## Conectando Agentes ao Stack de Memória

Todos os agentes conectam da **mesma forma**: registrando `memory_server.py`
como servidor MCP STDIO, com `MEMORY_API_URL` apontando para o central e
`AGENT_NAME` identificando o agente. Os arquivos de configuração mudam de
acordo com a ferramenta, mas o payload é idêntico.

### Opções de conexão

| Opção | Quando usar | Comando/env |
|---|---|---|
| **MCP STDIO local** | Agente roda na mesma máquina do repo (estação) | `python3 src/memory_server.py` + `MEMORY_API_URL` |
| **MCP via SSH** | Agente numa máquina **sem** o repo (ex: Windows → central) | `ssh deploy@100.64.117.78 "cd ... && ./.venv/bin/python src/memory_server.py"` |
| **MCP STDIO com env** | Passar `AGENT_NAME`/`API_KEY` sem editar código | prefixar `env VAR=val` no comando |

### OpenCode

`~/.config/opencode/opencode.json` (Windows aponta via SSH para o central):

```json
{
  "mcp": {
    "estudiohc-memory": {
      "type": "local",
      "command": ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
        "deploy@100.64.117.78",
        "cd ~/Apps/EstudioHC-Memory-Suite/apps/mcp-memory && ./.venv/bin/python src/memory_server.py"]
    }
  }
}
```

Na estação (com o repo presente), direto:

```json
{
  "mcp": {
    "memory": {
      "type": "local",
      "command": ["env", "MEMORY_API_URL=http://100.64.117.78:5050",
        "AGENT_NAME=opencode", "python3", "/home/USER/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py"]
    }
  }
}
```

> O `setup-machine.sh` gera essa configuração automaticamente nas estações.

### Claude Code

`.mcp.json` na raiz do projeto:

```json
{
  "mcpServers": {
    "estudiohc-memory": {
      "command": "env",
      "args": ["MEMORY_API_URL=http://100.64.117.78:5050",
        "AGENT_NAME=claude",
        "python3", "/home/USER/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py"]
    }
  }
}
```

### Codex (OpenAI)

```bash
codex mcp add estudiohc-memory -- \
  env MEMORY_API_URL=http://100.64.117.78:5050 \
  AGENT_NAME=codex \
  python3 /home/USER/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py
```

### Gemini CLI / Antigravity (Google)

```bash
gemini mcp add --tool estudiohc-memory --command \
  "env MEMORY_API_URL=http://100.64.117.78:5050 AGENT_NAME=gemini python3 /home/USER/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/memory_server.py"
```

### Mistral, OMP e outros agentes MCP

Qualquer agente com cliente MCP registra o mesmo servidor. O padrão é
sempre:

```
command: env MEMORY_API_URL=<central> AGENT_NAME=<nome> python3 <repo>/apps/mcp-memory/src/memory_server.py
```

Se o agente não suporta MCP, use a **API REST diretamente**:

```bash
# gravar
curl -s -X POST http://100.64.117.78:5050/remember \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <chave se configurada>" \
  -d '{"agent_name":"mistral","project":"meuprojeto","category":"context","content":"{\"s\":\"...\",\"r\":null,\"c\":true}"}'

# ler
curl -s "http://100.64.117.78:5050/recall/meuprojeto?limit=10"
```

### Verificação rápida de conexão

```bash
# 1. API central acessível?
curl -s http://100.64.117.78:5050/api/status

# 2. Agente enxerga as tools?
#   Em cada cliente MCP: listar tools → deve aparecer add_memory, search_memory,
#   get_status, wm_*, consolidate, doc_* (12 tools)

# 3. Escrever e ler
#   add_memory → GET /recall/{project} confirma a memória com agent_name correto
```

---

## Autenticação e Rate Limiting

Implementado em `apps/api/src/security.py` e aplicado em `apps/api/src/main.py`.

### API Key opcional

- Configuração: variável de ambiente `API_KEY` (vazia = auth **desabilitado**).
- Quando configurada, toda rota protegida exige header `X-API-Key`.
- O `memory_server.py` envia a chave automaticamente via `MEMORY_API_KEY`.

### Rate Limiting

- Aplicado ao `/api/hermes` (rota que consome LLM).
- Janela deslizante de 60s por IP; `RATE_LIMIT_PER_MIN` (default 10).
- Excesso retorna HTTP 429.

> **Dashboard:** ao ativar `API_KEY`, o dashboard estático (`apps/dashboard/static/`)
> precisa enviar o header `X-API-Key` nas chamadas — pendência documentada antes
> de habilitar auth em produção.

---

## Testes e CI

### Testes locais (pytest)

```bash
cd apps/api
pip install -e ".[dev]"
python -m pytest -v
```

| Teste | Verifica |
|---|---|
| `test_remember_returns_id` | POST `/remember` retorna `id` inteiro > 0 |
| `test_status_returns_readable_text` | GET `/status/{project}` retorna texto legível |
| `test_api_key_required_when_configured` | Sem `X-API-Key` → 401 |
| `test_api_key_accepted` | Com `X-API-Key` correta → 200 |

### CI (GitHub Actions)

`.github/workflows/ci.yml` roda em push para `master` e PRs: instala
`apps/api` com dev deps (Python 3.11) e executa `pytest -v`.

---

## Local Memory Stack (WAL de Sobrevivência)

Complemento offline ao MCP Memory Server — um **append-only journal** local
que preserva o contexto da sessão mesmo em caso de queda de energia.

### Motivação

O MCP Memory Server persiste memória no servidor central (Contabo :5050).
Se a energia cai durante uma tarefa, o contexto da conversa atual se perde.
O journal local preenche esta lacuna: cada turno é anexado a um arquivo de
texto antes do próximo turno começar.

### Componentes

| Componente | Local | Função |
|---|---|---|
| `config/skills/journal_recovery/SKILL.md` | `~/.agents/skills/` | Skill do agente que lê o journal na inicialização e faz append a cada turno |
| `config/tmux/.tmux.conf` | `~/.tmux.conf` | Backup textual bruto via histórico do tmux (50000 linhas) |
| `.matrixx/journal.md` | `./.matrixx/` ou `/tmp/.matrixx/` | Append log Markdown — atômico, sobrevive a queda |
| `.matrixx/journal.yaml` | `./.matrixx/` ou `/tmp/.matrixx/` | Structured snapshot para parsing programático |

### Fluxo

```
Nova sessão → journal_recovery skill lê .matrixx/journal.md
           → extrai últimas 15 entradas como contexto
           → agente opera com continuidade
           → cada turno: append no journal.md (>> atômico)
           → task complete: memória consolidada no servidor central
           → queda de energia? journal.md sobrevive
```

### Integração com o restante da Suite

| Camada | Dependência | Função |
|---|---|---|
| `journal_recovery` (local) | Nenhuma — funciona offline | WAL textual pós-queda |
| MCP Memory Server | Servidor central :5050 | Memória remota compartilhada entre estações |
| Documentos (ChromaDB) | chromadb-mcp :8765 | Busca semântica de documentos longos por projeto |

As camadas são independentes e complementares.

### Instalação

```bash
# Na estação já clonada:
./scripts/bootstrap-memory-stack.sh
```

O script copia o skill para `~/.agents/skills/`, instala o `.tmux.conf`,
e cria o diretório `.matrixx/` com os arquivos iniciais.

---

## Provisionamento de Novas Estações

Para adicionar um novo PC à rede, execute o script de provisionamento:

```bash
# Na máquina nova (deve ter Tailscale instalado e conectado):
curl -sL https://raw.githubusercontent.com/helciocosta/EstudioHC-Memory-Suite/master/scripts/setup-machine.sh | bash
```

O script `scripts/setup-machine.sh` faz automaticamente:

| Etapa | Descrição |
|---|---|
| ✅ Pré-requisitos | Verifica git, python3, node, tailscale |
| ✅ Ping servidor | Testa conexão com `100.64.117.78:5050` |
| ✅ Git clone | Clona ou atualiza o repositório |
| ✅ Modelos GGUF | Baixa cybersec-assistant-3b e Qwen3-1.7B do Hugging Face |
| ✅ Python venv | Cria ambiente virtual com MCP, sentence-transformers, FAISS |
| ✅ OpenCode | Instala opencode-matrixx e config com MCP → servidor central |
| ✅ Systemd | Cria `llama-server.service` e `llama-server-summarizer.service` |
| ✅ Registro | Registra a estação na API central (`/api/estacoes/ping`) |

> **Nota:** O binário `msty-llama-server` precisa ser copiado de uma estação já
> configurada (`rsync -avz user@estacao:~/.config/MstyStudio/llama-cpp/ ...`)
> pois é um binário proprietário da Msty Studio não disponível publicamente.

> Após o setup-machine.sh, execute também o bootstrap do stack local:
> ```bash
> cd ~/Apps/EstudioHC-Memory-Suite && ./scripts/bootstrap-memory-stack.sh
> ```
> Isso instala o skill `journal_recovery` e o `.tmux.conf` para proteção
> contra queda de energia durante sessões do agente.

### Workflow de Desenvolvimento

```
1. Estação A inicia tarefa  →  MCP salva no servidor central
2. Estação B continua       →  MCP lê do servidor central
3. Código versionado        →  git push/pull (qualquer estação)
4. Deploy no servidor       →  Quando estiver pronto
```

Cada estação é um **laboratório de desenvolvimento** com inferência local
rápida. O servidor central mantém a **fonte única de verdade** para dados
persistentes (agenda, projetos, tarefas, memória de longo prazo).

### Migração: KoboldCpp → llama.cpp nativo (2026-06-20)

| Componente | Antes | Depois |
|---|---|---|
| Binário | `koboldcpp-linux-x64` | `msty-llama-server` v8763 |
| Backend CPU | Genérico | `libggml-cpu-haswell.so` |
| Flash Attention | ❌ | ✅ `--flash-attn auto` |
| KV Cache Shift | ❌ | ✅ `--cache-reuse 256 + --keep -1` |
| Prompt Caching | ❌ | ✅ `--cache-prompt` (default on) |
| Continuous Batching | ❌ | ✅ `--cont-batching` |

### Modelos

| Modelo | Arquivo | Quantização | Uso |
|---|---|---|---|
| cybersec-assistant-3b | `cybersec-assistant-3b-Q4_K_M.gguf` | Q4_K_M | Inferência principal |
| Qwen3-1.7B | `Qwen3-1.7B-Q4_K_M.gguf` | Q4_K_M | Sumarização |
| all-MiniLM-L6-v2 | — (sentence-transformers) | FP32 | Embeddings FAISS |

### Compatibilidade CLI (Ollama Mock)

`~/.local/bin/ollama` redireciona para a API OpenAI do llama.cpp:

```bash
ollama list   → GET /v1/models → cybersec-assistant-3b-Q4_K_M.gguf:latest
ollama run    → echo "llama-server rodando na porta 11434"
```

---

## Monitoramento

### Logs

```bash
# Servidor principal
journalctl -u llama-server.service -f --no-hostname -o cat

# Summarizer
journalctl -u llama-server-summarizer.service -f --no-hostname -o cat

# API central
journalctl -u estudiohc-api.service -f --no-hostname -o cat

# ChromaDB MCP
journalctl -u chromadb-mcp.service -f --no-hostname -o cat
```

### Healthcheck

```bash
# Disponibilidade da API
curl -s http://localhost:5050/api/status

# Disponibilidade do ChromaDB MCP (SSE)
curl -s -H "Accept: text/event-stream" http://localhost:8765/mcp

# Inferência
curl -s http://localhost:11434/v1/chat/completions \
  -d '{"model":"llama","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
```

### Gerenciamento

```bash
sudo systemctl restart estudiohc-api.service
sudo systemctl restart chromadb-mcp.service
sudo systemctl restart llama-server.service
sudo systemctl restart llama-server-summarizer.service
```

---

## Variáveis de Ambiente

### API Central (`apps/api`)

| Variável | Default | Descrição |
|---|---|---|
| `APP_NAME` | `EstudioHC Central API` | Nome da aplicação |
| `DEBUG` | `false` | Modo debug |
| `API_PORT` | `5050` | Porta da API |
| `DATABASE_URL` | `sqlite+aiosqlite:///${HOME}/Apps/EstudioHC-Memory-Suite/data/estudiohc.db` | Conexão SQLite (ou PostgreSQL asyncpg) |
| `CORS_ORIGINS` | `["*"]` | Origens permitidas |
| `DASHBOARD_PATH` | `./apps/dashboard/static` | Caminho do dashboard estático |
| `HERMES_CLI` | `${HOME}/.local/bin/hermes` | Binário do Hermes CLI |
| `HERMES_TIMEOUT` | `120` | Timeout do Hermes (s) |
| `API_KEY` | *(vazio)* | Chave de API — vazio desabilita auth; configurado, exige `X-API-Key` |
| `RATE_LIMIT_PER_MIN` | `10` | Máximo de chamadas por IP/min no `/api/hermes` |

### MCP Memory Server (`apps/mcp-memory`)

| Variável | Default | Descrição |
|---|---|---|
| `MEMORY_API_URL` | `http://localhost:5050` | Endpoint de persistência LTM no servidor central |
| `MEMORY_API_KEY` | *(vazio)* | Chave para o header `X-API-Key` nas chamadas à API |
| `AGENT_NAME` | `opencode` | Identifica a origem da memória (`agent_name` gravado no `/remember`) |
| `MEMORY_MAX_TOKENS` | `2048` | Budget total da Working Memory |
| `MEMORY_INJECT_TOKENS` | `1024` | Budget por chamada de search_memory |
| `MEMORY_SUMMARIZE_THRESHOLD` | `60` | Tamanho mínimo (chars) para sumarizar |
| `MEMORY_MAX_INJECT` | `3` | Máximo de itens injetados |
| `MEMORY_DECAY_DAYS` | `30` | Dias para início do decaimento |
| `HYBRID_RRF_K` | `60` | Constante K do RRF ranking |
| `CHROMA_MCP_URL` | `http://localhost:8765/mcp` | Endpoint SSE do chromadb-mcp (camada de documentos) |
| `CHROMA_SSE_TIMEOUT` | `10` | Timeout de conexão SSE (s) |
| `SUMMARIZER_API` | `http://localhost:11435/v1/chat/completions` | Endpoint do sumarizador (Qwen3-1.7B) |
| `SUMMARIZER_MODEL` | `Qwen3-1.7B` | Modelo do sumarizador |

---

> **Stack concluído.** Consulte [`PLANO_UNIFICACAO.md`](PLANO_UNIFICACAO.md) para o histórico
> de modernização.

*Projeto mantido por Helcio O. Costa. v4.3 — 2026-08-02*
