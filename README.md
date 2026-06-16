# EstudioHC Memory Suite v3.0

Infraestrutura central de contexto e persistência de memória para o ecossistema de agentes AI de Helcio O. Costa.

> **Documentação principal para coordenação:** [`STATUS_ESTUDIOHC.md`](STATUS_ESTUDIOHC.md)  
> **Repositório:** `github.com/helciocosta/EstudioHC-Memory-Suite.git`

---

## 🏗️ Estrutura

```
EstudioHC-Memory-Suite/
├── apps/
│   ├── api/                    → FastAPI Central (porta 5050)
│   │   ├── src/main.py         → App principal
│   │   ├── src/config.py       → Config (.env)
│   │   ├── src/database.py     → SQLAlchemy async
│   │   ├── src/models/         → 7 modelos ORM
│   │   ├── src/schemas/        → Pydantic v2
│   │   ├── src/routers/        → 7 routers modulares
│   │   ├── alembic/            → Migrations
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── mcp-stdio/              → MCP stdio (agentes locais)
│   │   └── Dockerfile
│   └── dashboard/              → Web UI (porta 8585)
│       ├── static/             → index.html, projeto.html
│       ├── Dockerfile
│       └── pyproject.toml
├── cli/
│   └── estudio                 → CLI de status
├── docker-compose.yml          → api + dashboard
├── data/
│   └── estudiohc.db            → SQLite persistente
├── .env.example
├── .gitignore
├── README.md
└── STATUS_ESTUDIOHC.md         → Plano de ação e coordenação
```

---

## 🚀 Comece por aqui

```bash
# 1. Subir a API
cd apps/api
source .venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 5050

# 2. Testar
curl http://localhost:5050/api/status

# 3. (Opcional) Subir dashboard com proxy
cd apps/dashboard
API_URL=http://localhost:5050 python3 -c "from src import main; main()"

# 4. (Opcional) Docker
docker compose up -d
```

---

## 📡 API

Documentação interativa em `/docs` (Swagger) e `/redoc` (ReDoc) quando a API estiver rodando.

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/remember` | Salva memória de agente |
| GET | `/recall/{project}` | Recupera memórias |
| GET | `/api/agenda` | Lista agenda |
| POST | `/api/agenda` | Salva agenda |
| GET | `/api/diarios` | Lista diários |
| GET | `/api/diario/{data}` | Lê diário |
| POST | `/api/nota` | Adiciona nota |
| GET | `/api/projetos` | Lista projetos |
| POST | `/api/projetos/sync` | Sincroniza projetos |
| POST | `/api/projetos/relatorio` | Relatório IA do projeto |
| GET | `/api/estacoes` | Lista estações |
| POST | `/api/estacoes/ping` | Heartbeat de estação |
| POST | `/api/hermes` | Chat com IA |
| GET | `/api/status` | Health check |
| GET | `/api/status_md` | Status em markdown |

---

## 🔧 Stack

| Componente | Tech |
|-----------|------|
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| Validação | Pydantic v2 |
| DB | SQLite (aiosqlite) |
| Migrações | Alembic |
| Frontend | Vanilla HTML/CSS/JS |
| Container | Docker Compose |
| Rede | Tailscale VPN |
| IA Cloud | Hermes CLI (OpenRouter) |
| IA Local | KoboldCpp (Qwen3 1.7B) |

---

## 📖 Documentos Importantes

- **[STATUS_ESTUDIOHC.md](STATUS_ESTUDIOHC.md)** — Plano de ação completo, tarefas pendentes, arquitetura detalhada. **Leia primeiro.**
- `.env.example` — Exemplo de configuração de ambiente
- `docker-compose.yml` — Orquestração dos serviços

---

*Projeto mantido por Helcio O. Costa. v3.0 — 2026-06-16*