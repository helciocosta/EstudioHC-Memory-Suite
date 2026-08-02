# 🧠 EstudioHC — Status do Projeto Central

**Última atualização:** 2026-08-02  
**Estação de origem:** vmi2968998 (Servidor Central)  
**Responsável:** deploy@vmi2968998  
**Versão do stack:** v4.3

---

## 🎯 Meta Principal

**Servir como cérebro centralizado** do ecossistema de AI e produtividade de Helcio O. Costa, usando **OpenCode como IA primária**.

Unificar **memória de agentes AI, agenda, notas/diários, projetos, tarefas, documentos por projeto e estações de trabalho** em um único banco de dados central acessível via Tailscale de qualquer estação — com **inferência local** (llama.cpp) em cada estação.

---

## 🖥️ Inventário de Estações

| Estação | Hostname | Tailscale IP | Sistema | Status |
|---------|----------|--------------|---------|--------|
| Servidor Central | vmi2968998 | 100.64.117.78 | Ubuntu 24.04 | ✅ Online |
| PC Casa / Estúdio | helcio-x99-b | 100.122.75.73 | Linux Mint 22 | ✅ Online |
| Workstation AMD | amd-estudio-c2 | 100.64.211.14 | — | ❌ Offline |
| PC Trabalho/Loja | estudio-x79 | 100.92.94.52 | — | ❌ Offline |

---

## 🏗️ Arquitetura Atual (v4.3)

```
EstudioHC-Memory-Suite/
├── apps/
│   ├── api/                          → FastAPI Central (porta 5050) ✅
│   │   ├── src/main.py               → App principal (auth + rate limit aplicados)
│   │   ├── src/config.py             → Settings (API_KEY, RATE_LIMIT_PER_MIN)
│   │   ├── src/security.py           → require_api_key + rate_limiter
│   │   ├── src/database.py           → SQLAlchemy async
│   │   ├── src/models/               → Modelos ORM
│   │   ├── src/schemas/              → Pydantic v2
│   │   ├── src/routers/              → Routers modulares (8)
│   │   │   ├── memory.py             → /remember, /recall, /status (texto legível)
│   │   │   ├── agenda.py             → /api/agenda
│   │   │   ├── notas.py              → /api/diarios, /api/nota
│   │   │   ├── projetos.py           → /api/projetos, /sync, /relatorio
│   │   │   ├── estacoes.py           → /api/estacoes/ping
│   │   │   ├── hermes.py             → /api/hermes (rate limit)
│   │   │   ├── tarefas.py            → /api/tarefas (CRUD)
│   │   │   └── status.py             → /api/status, /api/status_md (aberto)
│   │   ├── tests/                    → pytest (4 testes)
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── chromadb-mcp/                 → MCP SSE (ChromaDB, porta 8765) ✅
│   │   └── server.py                 → 8 tools (incl. delete/get documents)
│   ├── mcp-memory/                   → MCP Memory Server (12 tools) ✅
│   │   ├── src/memory_server.py      → WM + FAISS + RRF + doc_* tools
│   │   ├── src/chroma_client.py      → Cliente SSE do ChromaDB
│   │   ├── src/summarizer.py         → Sumarização Qwen3-1.7B (11435)
│   │   └── src/embedder.py           → Embeddings + FAISS
│   ├── mcp-stdio/                    → MCP stdio (legado)
│   └── dashboard/                    → Web UI (porta 8585) ✅
├── .github/workflows/ci.yml          → CI (pytest em apps/api) ✅
├── cli/estudio                       → Script de status
├── scripts/                          → backup.sh, monitor.sh, setup-machine.sh, bootstrap-memory-stack.sh
├── docker-compose.yml
├── data/estudiohc.db                 → SQLite persistente
└── .env.example
```

### Stack Tecnológica

| Componente | Tecnologia | Versão |
|-----------|------------|--------|
| API Server | FastAPI + Uvicorn | 3.0.0 |
| ORM | SQLAlchemy 2.0 (async) | 2.0+ |
| Validação | Pydantic v2 | 2.10+ |
| Database | SQLite (aiosqlite) | — |
| MCP SDK | `mcp` | 1.28 |
| ChromaDB | `chromadb` | 1.5.9 |
| FAISS | `faiss-cpu` | 1.9+ |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 3.0+ |
| Frontend | HTML5 + Vanilla CSS/JS | — |
| Container | Docker Compose | — |
| Rede | Tailscale VPN | — |
| IA Primária | OpenCode (via CLI) | — |
| IA Secundária | Hermes CLI (OpenRouter/Nemotron 120B) | — |
| IA Local | llama.cpp (`cybersec-assistant-3b`, 11434) | — |
| Sumarizador | llama.cpp (Qwen3-1.7B, 11435) | — |

---

## 📡 Endpoints da API

> Quando `API_KEY` está configurada, todas as rotas abaixo (exceto `/api/status`
> e `/api/status_md`) exigem o header `X-API-Key`.

| Método | Rota | Descrição | Status |
|--------|------|-----------|--------|
| POST | `/remember` | Salva memória de agente — retorna `id` | ✅ |
| GET | `/recall/{project}` | Recupera memórias | ✅ |
| GET | `/status/{project}` | Tasks pendentes/concluídas (texto legível) | ✅ |
| GET | `/api/agenda` | Lista eventos | ✅ |
| POST | `/api/agenda` | Substitui agenda | ✅ |
| GET | `/api/diarios` | Lista dias com diário | ✅ |
| GET | `/api/diario/{data}` | Lê diário completo | ✅ |
| POST | `/api/diario/{data}/resumo` | Resumo do diário | ✅ |
| POST | `/api/nota` | Adiciona nota ao diário de hoje | ✅ |
| GET | `/api/projetos` | Lista todos os projetos | ✅ |
| POST | `/api/projetos/sync` | Sincroniza projetos de uma estação | ✅ |
| POST | `/api/projetos/gerar-relatorio` | Relatório IA do projeto | ✅ |
| GET | `/api/estacoes` | Lista estações registradas | ✅ |
| POST | `/api/estacoes/ping` | Heartbeat de estação | ✅ |
| GET | `/api/tarefas` | Lista tarefas | ✅ |
| POST | `/api/tarefas` | Cria tarefa | ✅ |
| PUT | `/api/tarefas/{id}` | Atualiza tarefa | ✅ |
| DELETE | `/api/tarefas/{id}` | Remove tarefa | ✅ |
| POST | `/api/hermes` | Chat IA (com rate limit) | ✅ |
| GET | `/api/status` | Health check | ✅ |
| GET | `/api/status_md` | Retorna este arquivo | ✅ |
| GET | `/docs` | Swagger UI | ✅ |

---

## 🧠 MCP Memory Server — Ferramentas

| Ferramenta | Descrição |
|---|---|
| `add_memory` | Persiste informação no LTM com sumarização opcional |
| `search_memory` | Busca híbrida (keyword + FAISS) com RRF e budget |
| `get_status` | Resumo de tasks pendentes/concluídas |
| `wm_push` | Adiciona item à Working Memory |
| `wm_pop` | Remove item mais recente da WM |
| `wm_list` | Lista WM com token count |
| `wm_clear` | Limpa WM |
| `consolidate` | Move WM → LTM com sumarização |
| `doc_add` | Armazena documento longo no ChromaDB |
| `doc_search` | Busca semântica em documentos do projeto |
| `doc_list` | Lista documentos do projeto |
| `doc_delete` | Remove documento pelo id |

---

## 📊 Estado Atual do Banco

| Tabela | Registros | Status |
|--------|-----------|--------|
| `agent_memory` | ~30 memórias | ✅ Populada |
| `agenda` | Populada | ✅ |
| `projetos` | 13+ | ✅ |
| `tarefas` | Populada | ✅ |
| `notas` | Populada | ✅ |
| `estacoes` | Registradas | ✅ |
| `resumos_diarios` | — | ⚠️ Em uso intermitente |

---

## 🚦 Status do Servidor

| Item | Status | Observação |
|------|--------|------------|
| API (`apps/api`) | ✅ **Systemd ativo** | `estudiohc-api.service` — porta 5050 |
| Dashboard (`apps/dashboard`) | ✅ **Systemd ativo** | `estudiohc-dashboard.service` — porta 8585 |
| ChromaDB MCP | ✅ **Systemd ativo** | `chromadb-mcp.service` — porta 8765 (SSE) |
| Backup | ✅ **Systemd timer** | `estudiohc-backup.timer` — diário 03:00 |
| Monitor | ✅ **Systemd timer** | `estudiohc-monitor.timer` — 5 min |
| OpenCode CLI | ✅ Disponível | `/home/deploy/.opencode/bin/opencode` |
| Hermes CLI | ✅ Disponível | `~/.local/bin/hermes` |
| CI | ✅ GitHub Actions | pytest em `apps/api` |

---

## 📋 Plano de Ação

### ✅ FASE 0 — Concluída (2026-06-17)
- [x] Criado systemd `estudiohc-api.service` para API na porta 5050
- [x] Criado systemd `estudiohc-dashboard.service` para dashboard na porta 8585
- [x] Testado: API, Dashboard, proxy, Swagger
- [x] Chat IA configurado: OpenCode (primário) → Hermes (fallback) → IA local
- [x] Servidor registrado como primeira estação (vmi2968998)
- [x] Agenda, projetos e tarefas populados
- [x] Router de tarefas criado (CRUD completo)

### 🔴 FASE 1 — Conectar Estações
- [x] CLI `estudio` instalado na estação helcio-x99-b
- [x] Dashboard local apontando para `API_URL=http://100.64.117.78:5050`
- [x] Estações registradas via `POST /api/estacoes/ping`

### 🟡 FASE 2 — Popular Dados Reais
- [x] Tarefas reais nos projetos
- [x] Diário via `POST /api/nota`
- [x] Projetos sincronizados da estação helcio-x99-b

### 🟢 FASE 3 — Frontend
- [ ] Banner de boas-vindas com tarefas do dia
- [ ] Filtro agenda: "Todos" vs "Esta estação"
- [ ] Corrigir timezone (eventos salvos em UTC)

### 🔵 FASE 4 — Segurança e Melhorias ✅ Concluída (2026-08-02)
- [x] **Autenticação por API Key** — `API_KEY` opcional (vazia = aberto; configurada = exige `X-API-Key`)
- [x] **Testes automatizados (pytest)** — 4 testes: id no remember, status legível, auth 401/200
- [x] **Rate limiting no `/api/hermes`** — janela 60s por IP, `RATE_LIMIT_PER_MIN=10`
- [x] **Backup automático do SQLite + FAISS** — `scripts/backup.sh` + timer diário 03:00
- [ ] Logs rotacionados (pendente)

### 🟣 FASE 5 — Camada de Documentos (ChromaDB) ✅ Concluída (2026-08-02)
- [x] `apps/chromadb-mcp/server.py` versionado (8 tools, SSE 8765)
- [x] `apps/mcp-memory/src/chroma_client.py` — cliente SSE com reconnect
- [x] 4 tools `doc_add`/`doc_search`/`doc_list`/`doc_delete` no MCP Memory Server
- [x] Coleção por projeto `docs_<project>` criada on-demand
- [x] Teste end-to-end validado em produção (ADDED/LIST/SEARCH/DELETE/NOT_FOUND_OK)
- [x] Memória #31 registrada — "DOC LAYER (OPCAO B) COMPLETED"

### 🟠 Correções do Stack (2026-08-02)
- [x] FAISS indexado com **id real** da API (antes `"|category"` nunca casava → RRF vetorial zero)
- [x] `consolidate` agora indexa no FAISS
- [x] `scripts/backup.sh` aponta para `data/estudiohc.db` (antes `server/...` inexistente)
- [x] Sumarizador aponta para **11435 / Qwen3-1.7B** (antes 11434/koboldcpp)
- [x] `get_status` retorna **texto legível** (antes JSON interno `{"s":...}`)
- [x] Testes pytest + CI restaurados no versionamento

---

## 🛠️ Comandos Úteis

```bash
# Acessar servidor
ssh deploy@100.64.117.78

# Status dos serviços
sudo systemctl status estudiohc-api
sudo systemctl status estudiohc-dashboard
sudo systemctl status chromadb-mcp

# Logs
sudo journalctl -u estudiohc-api -n 30 --no-pager
sudo journalctl -u chromadb-mcp -n 30 --no-pager

# Testar API
curl http://localhost:5050/api/status
curl http://localhost:8765/mcp  # SSE handshake (Accept: text/event-stream)

# Testes (com API_KEY=test-key)
cd apps/api && python -m pytest -v

# Backup (dry-run)
cd ~/Apps/EstudioHC-Memory-Suite && bash scripts/backup.sh --dry-run

# Migrations
cd ~/Apps/EstudioHC-Memory-Suite/apps/api
alembic upgrade head
alembic revision --autogenerate -m "descricao"

# Git
cd ~/Apps/EstudioHC-Memory-Suite
git status && git add . && git commit -m "mensagem" && git push
```

---

## 🔗 Informações de Rede

| Item | Valor |
|------|-------|
| Servidor Tailscale IP | 100.64.117.78 |
| Hostname | vmi2968998 |
| Porta API | 5050 |
| Porta Dashboard | 8585 |
| Porta ChromaDB MCP | 8765 |
| Acesso SSH | `ssh deploy@100.64.117.78` |
| Repositório | `github.com/helciocosta/EstudioHC-Memory-Suite.git` |

---

## ⚠️ Riscos e Alertas

1. **Auth opcional** — com `API_KEY` vazia, qualquer um na Tailscale acessa os dados. **Ativar `API_KEY` antes de expor** (e enviar header `X-API-Key` no dashboard).
2. **Dashboard sem header de auth** — se `API_KEY` for ativada, o dashboard estático precisa enviar `X-API-Key` (pendência documentada).
3. **SQLite não é cluster** — apenas um servidor, sem replicação
4. **OpenCode depende do modelo configurado** — verificar provider/model antes de usar
5. **Hermes depende de OpenRouter** — sem internet ou sem crédito, chat quebra
6. **Dashboard com paths hardcoded** — verificar ao rodar em outra estação
7. **`server/`, `dashboard/` (raiz) e `apps/mcp-stdio/` são legados** — não são usados pelos serviços ativos
8. **Llama-servers não rodam no servidor central** — inferência local é provisionada por `setup-machine.sh` nas estações

---

*Documento mantido no servidor central. Atualizado em 2026-08-02.*
