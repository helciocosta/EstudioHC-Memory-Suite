# 🧠 EstudioHC — Status do Projeto Central

**Última atualização:** 2026-06-16  
**Responsável:** deploy@vmi2968998 (Contabo)  
**Repositório:** `git@github.com:helciocosta/EstudioHC-Memory-Suite.git`

---

## 🎯 Meta Principal

**Servir como cérebro centralizado** do ecossistema de AI e produtividade de Helcio O. Costa.

Unificar **memória de agentes AI, agenda, notas/diários, projetos, tarefas e estações de trabalho** em um único banco de dados central acessível via Tailscale de qualquer estação.

---

## 🖥️ Inventário de Estações

| Estação | Hostname | Tailscale IP | Sistema | Status |
|---------|----------|--------------|---------|--------|
| Servidor Central | vmi2968998 | 100.64.117.78 | Ubuntu 24.04 | ✅ Online |
| PC Casa / Estúdio | helcio-x99-b | 100.122.75.73 | Linux Mint 22 | ✅ Online |
| Workstation AMD | amd-estudio-c2 | 100.64.211.14 | — | ❌ Offline |
| PC Trabalho/Loja | estudio-x79 | 100.92.94.52 | — | ❌ Offline |

---

## 🏗️ Arquitetura Atual (v3.0)

```
EstudioHC-Memory-Suite/
├── apps/
│   ├── api/                          → FastAPI Central (porta 5050)
│   │   ├── src/main.py               → App principal (FastAPI)
│   │   ├── src/config.py             → Settings via .env
│   │   ├── src/database.py           → SQLAlchemy async + init_db
│   │   ├── src/models/               → 7 modelos ORM
│   │   │   ├── agent_memory.py       → Memória persistente de agentes
│   │   │   ├── agenda.py             → Eventos de agenda
│   │   │   ├── projetos.py           → Projetos mapeados
│   │   │   ├── tarefas.py            → Tarefas por projeto
│   │   │   ├── notas.py              → Notas/diário central
│   │   │   ├── estacoes.py           → Registro de estações
│   │   │   └── resumos_diarios.py    → Cache de resumos de IA
│   │   ├── src/schemas/              → Schemas Pydantic v2
│   │   ├── src/routers/              → 7 routers modulares
│   │   │   ├── memory.py             → /remember, /recall
│   │   │   ├── agenda.py             → /api/agenda
│   │   │   ├── notas.py              → /api/diarios, /api/nota
│   │   │   ├── projetos.py           → /api/projetos, /sync, /relatorio
│   │   │   ├── estacoes.py           → /api/estacoes/ping
│   │   │   ├── hermes.py             → /api/hermes (chat IA)
│   │   │   └── status.py             → /api/status, /api/status_md
│   │   ├── alembic/                  → Migrations versionadas
│   │   ├── Dockerfile
│   │   └── pyproject.toml            → Python packaging
│   ├── mcp-stdio/                    → MCP stdio server (agentes locais)
│   │   └── Dockerfile
│   └── dashboard/                    → Web UI (porta 8585)
│       ├── static/
│       │   ├── index.html            → SPA (agenda, diário, projetos, chat)
│       │   └── projeto.html          → Visualizador de relatórios
│       ├── src/__init__.py           → FastAPI + proxy para API
│       ├── Dockerfile
│       └── pyproject.toml
├── cli/
│   └── estudio                       → Script de status do terminal
├── docker-compose.yml                → api + dashboard
├── data/
│   └── estudiohc.db                  → SQLite (persistente)
├── .env.example
├── .gitignore
└── README.md
```

### Stack Tecnológica

| Componente | Tecnologia | Versão |
|-----------|------------|--------|
| API Server | FastAPI + Uvicorn | 0.136+ / 0.46+ |
| ORM | SQLAlchemy 2.0 (async) | 2.0+ |
| Validação | Pydantic v2 | 2.13+ |
| Migrations | Alembic | — |
| Database | SQLite (aiosqlite) | — |
| Frontend | HTML5 + Vanilla CSS/JS | — |
| Container | Docker Compose | — |
| Rede | Tailscale VPN | 1.98+ |
| IA Cloud | Hermes CLI (OpenRouter) | — |
| IA Local | KoboldCpp (Qwen3 1.7B) | — |

---

## 📡 Endpoints da API

### Rotas Originais (MCP - backward compatible)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/remember` | Salva memória de agente |
| GET | `/recall/{project}` | Recupera memórias recentes |
| GET | `/status/{project}` | Status de tarefas do projeto |

### Rotas da Central API
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/agenda` | Lista eventos de agenda |
| POST | `/api/agenda` | Substitui agenda completa |
| GET | `/api/diarios` | Lista dias com diário |
| GET | `/api/diario/{data}` | Lê diário completo |
| POST | `/api/diario/{data}/resumo` | Salva resumo de IA do diário |
| POST | `/api/nota` | Adiciona nota ao diário de hoje |
| GET | `/api/projetos` | Lista todos os projetos |
| POST | `/api/projetos/sync` | Sincroniza projetos de uma estação |
| GET | `/api/projetos/relatorio` | Gera relatório de IA do projeto |
| GET | `/api/estacoes` | Lista estações registradas |
| POST | `/api/estacoes/ping` | Registra heartbeat de estação |
| POST | `/api/hermes` | Chat com Hermes AI |
| GET | `/api/status` | Health check do servidor |
| GET | `/api/status_md` | Retorna STATUS_ESTUDIOHC.md |
| GET | `/docs` | Swagger UI (documentação interativa) |
| GET | `/redoc` | Redoc UI |

---

## 📊 Estado Atual do Banco

| Tabela | Colunas | Registros | Status |
|--------|---------|-----------|--------|
| `agent_memory` | id, timestamp, agent_name, project, category, content | 1 (teste) | ✅ |
| `agenda` | id, data, hora, titulo, estacao, descricao, timestamp | 0 | ⚠️ Vazia |
| `projetos` | id, nome, local_caminho, status, tags, readme_preview, estacao, ultima_atualizacao | 11 (seed) | ✅ |
| `tarefas` | id, projeto_id, titulo, status, prioridade, data_limite | 0 | ⚠️ Vazia |
| `notas` | id, estacao, texto, timestamp | 0 | ⚠️ Vazia |
| `estacoes` | hostname, ip_tailscale, ultimo_ping, status | 0 | ⚠️ Vazia |
| `resumos_diarios` | data, resumo, agente, timestamp | 0 | ⚠️ Vazia |

**Banco de dados funcional mas sem dados operacionais — precisa de uso real para ser útil.**

---

## 🚦 Status do Servidor

| Item | Status | Observação |
|------|--------|------------|
| API (`apps/api`) | ✅ **Funcional** | Testado — sobe, responde `/api/status`, `/docs` |
| Dashboard (`apps/dashboard`) | 🟡 **Estrutura pronta** | Proxy para API configurado, precisa de deploy |
| MCP stdio (`apps/mcp-stdio`) | 🟡 **Código pronto** | Usado por agentes locais, não roda como serviço |
| Docker Compose | ✅ **Configurado** | `docker compose up -d` sobe api + dashboard |
| Systemd service | ❌ **Não instalado** | Precisa criar e habilitar o serviço |
| CLI (`estudio`) | ✅ **Script existente** | Aponta para `100.64.117.78:8585` (dashboard) |
| Vagas removidas | ✅ | aionui, antigravity, gemini, waveterm |

---

## 📋 Plano de Ação — O QUE A PRÓXIMA EQUIPE PRECISA FAZER

### 🔴 FASE 0 — URGENTE (colocar no ar AGORA)

- [ ] **Criar serviço systemd** (`/etc/systemd/system/estudiohc-api.service`):
  ```ini
  [Unit]
  Description=EstudioHC Central API
  After=network.target tailscaled.service

  [Service]
  Type=simple
  User=deploy
  WorkingDirectory=/home/deploy/Apps/EstudioHC-Memory-Suite/apps/api
  ExecStart=/home/deploy/Apps/EstudioHC-Memory-Suite/apps/api/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 5050
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] `sudo systemctl daemon-reload && sudo systemctl enable --now estudiohc-api`
- [ ] **Verificar:** `curl http://localhost:5050/api/status` → deve retornar 200
- [ ] **Subir dashboard via Docker ou systemd** similar

### 🟡 FASE 1 — Conectar Estações

- [ ] **Instalar CLI `estudio`** em cada estação local:
  ```bash
  sudo cp cli/estudio /usr/local/bin/estudio
  ```
- [ ] **Configurar dashboard local** em cada estação (helcio-x99-b, etc):
  - Clonar repositório
  - Rodar dashboard apontando para `API_URL=http://100.64.117.78:5050`
  - Criar serviço systemd `estudiohc-hub` porta 8585
- [ ] **Registrar estação via API:** `POST /api/estacoes/ping?hostname=helcio-x99-b`
- [ ] **Sincronizar projetos locais:** `POST /api/projetos/sync` com lista de projetos

### 🟢 FASE 2 — Popular Dados Reais

- [ ] **Inserir agenda real:** eventos, compromissos, prazos via `POST /api/agenda`
- [ ] **Criar tarefas nos projetos:** `POST /api/tarefas` (endpoint existe no model, falta router)
- [ ] **Usar diário:** postar notas do dia a dia via `POST /api/nota`
- [ ] **Configurar Hermes AI:** garantir que `~/.local/bin/hermes` existe e tem chave OpenRouter

### 🔵 FASE 3 — Frontend (index.html)

**Arquivo:** `apps/dashboard/static/index.html`

- [ ] **Chat IA:** trocar `/api/kobold` → `/api/hermes` (nuvem primeiro, fallback local)
- [ ] **Resumir Diario:** trocar `/api/kobold` → `/api/hermes`
- [ ] **Status bar:** adicionar dots de Hermes + Central (hoje só mostra KoboldCpp)
- [ ] **Corrigir bug timezone:** eventos salvos em UTC mas exibidos como local
- [ ] **Renomear aba** "IA Local" → "Chat IA"
- [ ] **Adicionar indicador de estação** no header (via `localStorage`)
- [ ] **Banner de boas-vindas:** tarefas do dia ao abrir
- [ ] **Filtro agenda:** "Todos os PCs" vs "Esta estação"

### 🟣 FASE 4 — Melhorias e Segurança

- [ ] **Autenticação:** adicionar API Key ou JWT (hoje CORS aberto `*`)
- [ ] **Endpoint de tarefas:** criar router `tarefas.py` (modelo e schema já existem)
- [ ] **Testes automatizados:** pytest nos routers
- [ ] **Rate limiting** no `/api/hermes` (previne abuso)
- [ ] **Logs rotacionados:** configurar logrotate para logs da API
- [ ] **Monitoramento:** healthcheck no docker-compose (já configurado)
- [ ] **Backup automático do SQLite** (cron diário)

---

## 🛠️ Comandos Úteis

```bash
# Acessar servidor
ssh deploy@100.64.117.78

# Rodar API manualmente
cd ~/Apps/EstudioHC-Memory-Suite/apps/api
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 5050

# Testar API
curl http://localhost:5050/api/status
curl -X POST http://localhost:5050/remember \
  -H "Content-Type: application/json" \
  -d '{"agent_name":"test","project":"EstudioHC","content":"hello","category":"task"}'

# Migrations
cd ~/Apps/EstudioHC-Memory-Suite/apps/api
alembic upgrade head
alembic revision --autogenerate -m "descricao"

# Docker
cd ~/Apps/EstudioHC-Memory-Suite
docker compose up -d
docker compose logs -f

# Git
cd ~/Apps/EstudioHC-Memory-Suite
git status
git add . && git commit -m "mensagem" && git push
```

---

## 🔗 Informações de Rede

| Item | Valor |
|------|-------|
| Servidor Tailscale IP | 100.64.117.78 |
| Hostname | vmi2968998 |
| Porta API | 5050 |
| Porta Dashboard | 8585 |
| Acesso SSH | `ssh deploy@100.64.117.78` |
| Repositório | `github.com/helciocosta/EstudioHC-Memory-Suite.git` |
| Branch | `master` |

---

## 📁 Projetos Relacionados

| Projeto | Localização | Descrição |
|---------|-------------|-----------|
| **pc_local_config** | `~/Apps/pc_local_config/` | DNA de config do desktop + script update.sh (alimenta esta API) |
| **Hermes Agent** | `~/.hermes/` | Agente AI principal (OpenRouter, Nemotron 120B) |
| **KoboldCpp** | systemd local | IA local (Qwen3 1.7B, porta 11434) |

---

## ⚠️ Riscos e Alertas

1. **Zero autenticação** — qualquer um na Tailscale pode acessar/modificar dados
2. **SQLite não é cluster** — apenas um servidor, sem replicação
3. **Hermes depende de OpenRouter** — sem internet ou sem crédito, chat quebra
4. **Dashboard com paths hardcoded** (`/home/helcio/`) — não funciona se executado como deploy
5. **Banco vazio** — schema ok, mas sem dados úteis até estações conectarem

---

*Documento mantido para coordenação da equipe. Atualizado em 2026-06-16.*