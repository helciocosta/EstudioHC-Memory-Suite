# EstudioHC Memory Suite v4.5

**Secretário Digital e Orquestrador Central de Inteligência** — Coordena, comanda e gerencia todas as notas, memórias, tarefas, agendas, documentos vetoriais e dados dos agentes locais e remotos em toda a rede Tailscale.

---

## 🏛️ Topologia e Diretrizes de Engenharia (2026-10-26)

O **EstudioHC Memory Suite** opera sob uma arquitetura de alta resiliência e eficiência energética:

1. **Hub Central 24/7 (VPS Contabo `100.64.117.78`)**:
   - **Servidor Principal Absoluto**: opera de forma ininterrupta provendo a API Central (:5050 HTTPS), MCP SSE (:5051), ChromaDB (:8765), Sync-Connect (:5052), Dashboard (:8585) e o banco mestre SQLite (`data/estudiohc.db`).
2. **Laboratório Sob Demanda & Reserva Imediata (Servidor Local 32GB `100.107.208.50`)**:
   - **Economia de Energia**: Opera como ambiente de desenvolvimento e processamento pesado local (Ollama, fine-tuning). Permanece desligado a maior parte do tempo, sendo ligado sob demanda por poucas horas.
   - **Reserva de Contingência Total (Cold Standby com Auto-Boot)**: Ao ser inicializado, se a VPS Contabo estiver offline, assume 100% da stack e rede com sincronização reversa (failback) sem perda de dados.
3. **Coletores Locais Obsidian nas Estações de Trabalho**:
   - As estações (`win-x99` e `linux-i5`) utilizam o **Obsidian** como coletor ativo de conhecimento, notas diárias e telemetria (ActivityWatch + Git commits).
   - Ingestão contínua para a API (`POST /api/nota`) e ChromaDB (`doc_add`).
   - Sincronização e atualização contínua das **Agendas Locais das Estações** (`00 - Painel/Agenda.md` e diários) com `/api/agenda`.
4. **Ciclo de Vida de Tarefas Automatizado no Repositório (Ledger Git)**:
   - Todo início (`[IN_PROGRESS]`), progresso e conclusão (`[COMPLETED]`) de tarefas executadas por equipes e agentes é versionado com commits e pushes automáticos para o GitHub (`origin master`).

> **Plano Completo de Implementação:** Consulte `docs/superpowers/plans/2026-10-26-orquestrador-central-failover-contingencia.md`.  
> **Guia de Continuidade:** Consulte `HANDOFF.md` e `STATUS_ESTUDIOHC.md`.

---

## Componentes

### 1. API Central (5050 HTTPS)
FastAPI + Uvicorn com SSL/TLS. Rotas: `/api/diarios`, `/api/nota`, `/api/tarefas`, `/api/agenda`, `/api/projetos`, `/api/estacoes`, `/api/hermes`, `/api/status`.
Autenticação via `X-API-Key`.

### 2. MCP SSE Server (5051 SSE)
Bridge SSE (FastMCP) para agentes remotos (OMP, Antigravity CLI `agy`, OpenCode, Claude Code) consumirem e registrarem memórias de longo prazo, working memory e pesquisa semântica.

### 3. ChromaDB MCP Server (8765 SSE)
Camada documental vetorial isolada por coleções de projeto (`docs_<project>`), exposta via MCP SSE para busca semântica em documentos inteiros.

### 4. Sync Connect (5052 HTTP)
Bridge unificadora entre os serviços do ecossistema e a API central:
- `POST /sync/logseq/diario` <- Logseq
- `POST /sync/joplin/nota` <- Joplin
- `POST /sync/joplin/tarefa` <- Joplin
- `POST /sync/vikunja/projeto` <- Vikunja
- `POST /sync/ghost/relatorio` <- Ghost
- `POST /sync/todo/tarefa` <- Microsoft To Do
- `POST /sync/agenda` <- Calendários / Obsidian Agenda
- `GET /health` <- Healthcheck

### 5. Dashboard (8585 HTTP)
UI web moderna de visualização e gestão operacional de memórias, notas, tarefas e estações conectadas.

---

## Estações Tailscale Gerenciadas (Nós)

| Estação | IP Tailscale | Sistema | Papel |
| :--- | :---: | :---: | :--- |
| **vmi2968998 (Contabo)** | `100.64.117.78` | Linux | **Hub Central 24/7 (Principal)** |
| **estudiohc (Local 32GB)** | `100.107.208.50` | Linux | **Laboratório Dev / Reserva Imediata** |
| **win-x99** | `100.81.219.127` | Windows | Estação Dev / Obsidian Coletor Local / OMP |
| **linux-i5** | `100.71.137.21` | Linux | Estação Dev / Obsidian Coletor Local / Agy |

---

## Como Acessar via Tailscale

```bash
# Apontamento Canônico Universal (hosts):
100.64.117.78 hub.estudiohc

# Healthcheck da API (HTTPS):
curl -sk https://hub.estudiohc:5050/api/status

# Endpoint MCP SSE para Agentes:
http://hub.estudiohc:5051/sse
```

---

## Licença
MIT — Helcio O. Costa
