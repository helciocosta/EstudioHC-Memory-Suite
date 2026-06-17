# 🧠 EstudioHC — Status do Projeto Central

**Última atualização:** 2026-06-17  
**Estação de origem:** vmi2968998 (Servidor Central)  
**Responsável:** deploy@vmi2968998

---

## 🎯 Meta Principal

**Servir como cérebro centralizado** do ecossistema de AI e produtividade de Helcio O. Costa, usando **OpenCode como IA primária**.

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
│   ├── api/                          → FastAPI Central (porta 5050) ✅
│   │   ├── src/main.py               → App principal
│   │   ├── src/config.py             → Settings
│   │   ├── src/database.py           → SQLAlchemy async
│   │   ├── src/models/               → 7 modelos ORM
│   │   ├── src/schemas/              → Pydantic v2
│   │   ├── src/routers/              → 8 routers modulares
│   │   │   ├── memory.py             → /remember, /recall
│   │   │   ├── agenda.py             → /api/agenda
│   │   │   ├── notas.py              → /api/diarios, /api/nota
│   │   │   ├── projetos.py           → /api/projetos, /sync, /relatorio
│   │   │   ├── estacoes.py           → /api/estacoes/ping
│   │   │   ├── hermes.py             → /api/hermes (OpenCode → Hermes → KoboldCpp)
│   │   │   ├── tarefas.py            → /api/tarefas (CRUD) ✅ NOVO
│   │   │   └── status.py             → /api/status, /api/status_md
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── mcp-stdio/                    → MCP stdio (agentes locais)
│   └── dashboard/                    → Web UI (porta 8585) ✅
│       ├── static/
│       │   ├── index.html            → SPA atualizado (OpenCode + Hermes + KoboldCpp)
│       │   └── projeto.html
│       ├── src/__init__.py           → FastAPI + proxy para API
│       └── pyproject.toml
├── cli/estudio                       → Script de status
├── docker-compose.yml
├── data/estudiohc.db                 → SQLite persistente
└── .env.example
```

### Stack Tecnológica

| Componente | Tecnologia | Versão |
|-----------|------------|--------|
| API Server | FastAPI + Uvicorn | 0.137+ |
| ORM | SQLAlchemy 2.0 (async) | 2.0+ |
| Validação | Pydantic v2 | 2.13+ |
| Database | SQLite (aiosqlite) | — |
| Frontend | HTML5 + Vanilla CSS/JS | — |
| Container | Docker Compose | — |
| Rede | Tailscale VPN | — |
| IA Primária | OpenCode (via CLI) | — |
| IA Secundária | Hermes CLI (OpenRouter/Nemotron 120B) | — |
| IA Local | KoboldCpp (Qwen3 1.7B, porta 11434) | — |

---

## 📡 Endpoints da API

| Método | Rota | Descrição | Status |
|--------|------|-----------|--------|
| POST | `/remember` | Salva memória de agente | ✅ |
| GET | `/recall/{project}` | Recupera memórias | ✅ |
| GET | `/api/agenda` | Lista eventos | ✅ Com dados |
| POST | `/api/agenda` | Substitui agenda | ✅ |
| GET | `/api/diarios` | Lista dias com diário | ✅ |
| GET | `/api/diario/{data}` | Lê diário completo | ✅ |
| POST | `/api/nota` | Adiciona nota ao diário de hoje | ✅ |
| GET | `/api/projetos` | Lista todos os projetos | ✅ 13 projetos |
| POST | `/api/projetos/sync` | Sincroniza projetos de uma estação | ✅ |
| GET | `/api/projetos/relatorio` | Relatório IA do projeto | ✅ |
| GET | `/api/estacoes` | Lista estações registradas | ✅ 1 estação |
| POST | `/api/estacoes/ping` | Heartbeat de estação | ✅ |
| **GET** | **`/api/tarefas`** | **Lista tarefas** | ✅ **NOVO** |
| **POST** | **`/api/tarefas`** | **Cria tarefa** | ✅ **NOVO** |
| **PUT** | **`/api/tarefas/{id}`** | **Atualiza tarefa** | ✅ **NOVO** |
| **DELETE** | **`/api/tarefas/{id}`** | **Remove tarefa** | ✅ **NOVO** |
| POST | `/api/hermes` | Chat IA (OpenCode → Hermes → KoboldCpp) | ✅ |
| GET | `/api/status` | Health check | ✅ |
| GET | `/api/status_md` | Retorna este arquivo | ✅ |
| GET | `/docs` | Swagger UI | ✅ |

---

## 📊 Estado Atual do Banco

| Tabela | Registros | Status |
|--------|-----------|--------|
| `agent_memory` | 1 (teste) | ✅ |
| `agenda` | 7 eventos | ✅ Populada |
| `projetos` | 13 (5 servidor + 8 estação) | ✅ |
| `tarefas` | 4 (3 pendentes) | ✅ NOVA |
| `notas` | 2 entradas | ✅ |
| `estacoes` | 1 (vmi2968998) | ✅ |
| `resumos_diarios` | 0 | ⚠️ Vazia |

---

## 🚦 Status do Servidor

| Item | Status | Observação |
|------|--------|------------|
| API (`apps/api`) | ✅ **Systemd ativo** | `estudiohc-api.service` — porta 5050 |
| Dashboard (`apps/dashboard`) | ✅ **Systemd ativo** | `estudiohc-dashboard.service` — porta 8585 |
| OpenCode CLI | ✅ Disponível | `/home/deploy/.opencode/bin/opencode` |
| Hermes CLI | ✅ Disponível | `~/.local/bin/hermes` |
| Docker Compose | ✅ Configurado | `docker compose up -d` |
| CLI (`estudio`) | ⚠️ Script existe | Aponta para dashboard local |

---

## 📋 Plano de Ação

### ✅ FASE 0 — Concluída (2026-06-17)
- [x] Criado systemd `estudiohc-api.service` para API na porta 5050
- [x] Criado systemd `estudiohc-dashboard.service` para dashboard na porta 8585
- [x] Testado: API, Dashboard, proxy, Swagger
- [x] Chat IA configurado: OpenCode (primário) → Hermes (fallback) → KoboldCpp (GPU local)
- [x] Servidor registrado como primeira estação (vmi2968998)
- [x] Projetos do servidor sincronizados (5 projetos)
- [x] Agenda populada com eventos
- [x] Router de tarefas criado (CRUD completo)
- [x] Diário atualizado com notas da sessão

### 🔴 FASE 1 — Conectar Estações
- [ ] Instalar CLI `estudio` na estação helcio-x99-b
- [ ] Configurar dashboard local apontando para `API_URL=http://100.64.117.78:5050`
- [ ] Criar systemd `estudiohc-hub` na estação local
- [ ] Registrar estação via `POST /api/estacoes/ping`

### 🟡 FASE 2 — Popular Dados Reais
- [ ] Inserir tarefas reais nos projetos
- [ ] Usar diário diariamente via `POST /api/nota`
- [ ] Sincronizar projetos da estação helcio-x99-b

### 🟢 FASE 3 — Frontend
- [ ] Banner de boas-vindas com tarefas do dia
- [ ] Filtro agenda: "Todos" vs "Esta estação"
- [ ] Corrigir timezone (eventos salvos em UTC)

### 🔵 FASE 4 — Segurança e Melhorias
- [ ] Adicionar autenticação (API Key/JWT)
- [ ] Testes automatizados (pytest)
- [ ] Rate limiting no `/api/hermes`
- [ ] Backup automático do SQLite (cron diário)
- [ ] Logs rotacionados

---

## 🛠️ Comandos Úteis

```bash
# Acessar servidor
ssh deploy@100.64.117.78

# Status dos serviços
sudo systemctl status estudiohc-api
sudo systemctl status estudiohc-dashboard

# Logs
sudo journalctl -u estudiohc-api -n 30 --no-pager
sudo journalctl -u estudiohc-dashboard -n 30 --no-pager

# Testar API
curl http://localhost:5050/api/status
curl http://localhost:8585/api/status  # via dashboard proxy

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
| Acesso SSH | `ssh deploy@100.64.117.78` |
| Repositório | `github.com/helciocosta/EstudioHC-Memory-Suite.git` |

---

## ⚠️ Riscos e Alertas

1. **Zero autenticação** — qualquer um na Tailscale pode acessar/modificar dados
2. **SQLite não é cluster** — apenas um servidor, sem replicação
3. **OpenCode depende do modelo configurado** — verificar provider/model antes de usar
4. **Hermes depende de OpenRouter** — sem internet ou sem crédito, chat quebra
5. **Dashboard com paths hardcoded** — verificar ao rodar em outra estação
6. **Banco com dados iniciais** — schema ok, mas precisa de uso contínuo

---

*Documento mantido no servidor central. Atualizado em 2026-06-17.*