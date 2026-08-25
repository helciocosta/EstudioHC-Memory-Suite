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

## Estacoes Tailscale Gerenciadas (nós)

> Registradas no banco (2026-08-25): **12 nós** (vmi2968998, estudiohc, esutdiohc-i5-1,
> HELCIO-X99-B, Esteção X79G, mais registros antigos/smoke).
> Cada estação é um nó Tailscale legítimo — NÃO remover sem confirmação.

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

## Producao — 2026-08-25 (Fase 1)

Auditoria completa para producao real. 4 bugs de integracao corrigidos e versionados:

1. **Sync-Connect** (5052): chave real no systemd (drop-in) + mapeamento correto dos schemas
   da API. Todos os 6 integradores validados (200/201). Ver HANDOFF.md §3.1.
2. **FAISS/busca vetorial**: embedder com cache local + local_files_only → rebuild com
   **45 vetores** no startup (antes desabilitado por timeout de download).
3. **Working Memory persistente**: salva em `.working_memory.json` (sobrevive a restarts).
4. **Sanitizacao**: `agent_name/project/category` com strip no `/memory/remember` + dados existentes corrigidos.

Commits: `6c48e58`, `d8a5fde`, `af055db`, `eff5e28`.
Leia **`HANDOFF.md`** (continuidade/operacao) e **`STATUS_ESTUDIOHC.md`** (estado detalhado).

## Docker (22 containers ativos)
- Studyield (backend + frontend + postgres + redis + clickhouse)
- Omniroute
- Qdrant
- Beszel + Beszel Agent (monitoramento)
- Netdata (monitoramento)
- Portainer (gerenciamento)
- Coolify (PaaS) + Coolify DB + Redis + Realtime + Proxy (Traefik)

## Licenca
MIT — Helcio O. Costa

---
## Infraestrutura Final (Contabo)

| Subdomínio | Porta | Serviço | Status |
|-----------|-------|---------|--------|
| http://logseq.estudiohc.dns | 5053 | Logseq (memória/diário) | ✅ |
| http://joplin.estudiohc.dns | 5054 | Joplin (notas/tarefas) | ✅ |
| http://vikunja.estudiohc.dns | 5055 | Vikunja (projetos) | ✅ |
| http://ghost.estudiohc.dns | 5056 | Ghost (blog) | ✅ |
| http://todo.estudiohc.dns | 5057 | MS To Do sync | ✅ |

## Como Acessar (Tailscale)
100.64.117.78 logseq.estudiohc.dns joplin.estudiohc.dns vikunja.estudiohc.dns ghost.estudiohc.dns todo.estudiohc.dns

## Stack Completo — Secretário Digital
- 5 serviços rodando em Docker no Contabo
- Traefik reverse proxy com subdomínios
- PC local zero — tudo no servidor
- Quando PC desligar: Contabo mantém tudo
