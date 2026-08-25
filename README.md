# EstudioHC Memory Suite v4.4

**Secretario Digital Pessoal** — Coordena, comanda e gerencia todas as notas,
memorias, tarefas, agendas, correcoes e dados dos agentes locais e remotos.
Projetado como um secretario profissional, moderno e totalmente funcional.

## Arquitetura



## Componentes

### 1. API Central (5050)
FastAPI + Uvicorn com SSL. Rotas: /api/diarios, /api/nota, /api/tarefas,
/api/agenda, /api/projetos, /api/estacoes, /api/hermes.
Memoria vetorial: ChromaDB + Qdrant + Ollama. Autenticacao via X-API-Key.

### 2. Sync Connect (5052) — NOVO
Bridge entre os 5 servicos do stack e a API central.
- POST /sync/logseq/diario  <- Logseq
- POST /sync/joplin/nota    <- Joplin
- POST /sync/joplin/tarefa  <- Joplin
- POST /sync/vikunja/projeto <- Vikunja
- POST /sync/ghost/relatorio <- Ghost
- POST /sync/todo/tarefa    <- Microsoft To Do
- POST /sync/agenda         <- Qualquer servico
- GET /health               <- Healthcheck

### 3. MCP SSE (5051)
Bridge para agentes OMP consultarem/escreverem memoria persistente.
Suporte a memoria com decay temporal (30 dias).

### 4. Dashboard (8585)
UI web de gerenciamento com visualizacao de memoria, notas e tarefas.

## Stack de Servicos (Secretario Digital)

| Servico | Funcao | Sincroniza em |
|---------|--------|---------------|
| Logseq | Memoria, diario, tarefas, agenda | /sync/logseq/diario |
| Joplin | Notas, tarefas, calendario, lembretes | /sync/joplin/nota e /sync/joplin/tarefa |
| Vikunja | Projetos, tarefas, agenda | /sync/vikunja/projeto |
| Ghost | Blog, relatorios, pagina web | /sync/ghost/relatorio |
| Microsoft To Do | Tarefas diarias | /sync/todo/tarefa |

## Integracao Microsoft To Do
Ver: docs/microsoft-todo-integration.md

## Gerenciamento de Projetos
Ver: docs/project-management.md

## Estacoes Tailscale Gerenciadas (8 nos)

| Estacao | IP | Sistema | Status |
|---------|-----|---------|--------|
| esutdiohc-i5-1 | 100.97.90.121 | Windows | Ativa |
| estudiohc (Contabo) | 100.107.208.50 | Linux | Ativa |
| vmi2968998 (Contabo) | 100.64.117.78 | Linux | Ativa |
| estudio-x79 | 100.64.48.115 | Windows | Offline |
| estudiohc-x79g | 100.94.239.93 | Linux | Offline |
| helcio-x99-b | 100.122.75.73 | Linux | Offline |
| luizanoot | 100.97.197.7 | Windows | Offline |
| pc062858521 | 100.72.65.78 | Linux | Offline |

## Docker (17 containers ativos)
- Studyield (backend + frontend + postgres + redis + clickhouse)
- Omniroute
- Qdrant
- Beszel + Beszel Agent (monitoramento)
- Netdata (monitoramento)
- Portainer (gerenciamento)
- Coolify (PaaS) + Coolify DB + Redis + Realtime + Proxy (Traefik)

## Licenca
MIT — Helcio O. Costa
