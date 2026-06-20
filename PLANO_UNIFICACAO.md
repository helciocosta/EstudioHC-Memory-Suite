# Plano de Unificação e Modernização — EstudioHC Memory Suite v4.0

## Diagnóstico Inicial

O stack de memória e inferência do Estúdio HC evoluiu em paralelo em dois locais:

| Local | Conteúdo | Estado |
|---|---|---|
| `EstudioHC-Memory-Suite/apps/mcp-stdio/` | MCP legado (2 tools, SQLite direto) | Obsoleto |
| `EstudioHC-Memory-Suite/server/mcp_server.py` | FastAPI Central (:5050) | Ativo |
| `~/.config/opencode/mcp/` | MCP moderno (9 tools, FAISS, RRF, budget) | **Fora do repo** |

**Objetivo:** Unificar todo o stack no repositório `EstudioHC-Memory-Suite`,
modernizar a estrutura e garantir que o ecossistema consuma tudo de um lugar só.

---

## Fases

### Fase 1 — Documentação e Planejamento

- [x] Atualizar `README.md` com arquitetura completa do stack
- [x] Criar este `PLANO_UNIFICACAO.md`
- [ ] Commitar documentação no repositório

### Fase 2 — Unificação do Código

Criar `apps/mcp-memory/` com a estrutura moderna:

```
apps/mcp-memory/
├── src/
│   ├── __init__.py
│   ├── memory_server.py    → MCP STDIO server (9 tools)
│   ├── summarizer.py       → Sumarização via llama.cpp
│   └── embedder.py         → FAISS + sentence-transformers
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

**Ações:**
- [ ] Copiar `memory-server.py`, `summarizer.py`, `embedder.py` de `~/.config/opencode/mcp/` para `apps/mcp-memory/src/`
- [ ] Renomear `memory-server.py` → `memory_server.py` (padrão Python)
- [ ] Criar `pyproject.toml` com dependências do MCP
- [ ] Criar `Dockerfile` para deploy conteinerizado
- [ ] Remover `apps/mcp-stdio/` legado (ou manter como referência)

### Fase 3 — Integração com OpenCode

- [ ] Atualizar `~/.config/opencode/opencode.jsonc` para apontar para o novo caminho
- [ ] Criar symlink `~/.config/opencode/mcp/` → `Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src/` para backward compatibility
- [ ] Testar todas as 9 ferramentas MCP via opencode

### Fase 4 — Git e Versionamento

- [ ] Atualizar `.gitignore` se necessário
- [ ] Commitar `apps/mcp-memory/`, `README.md`, `PLANO_UNIFICACAO.md`
- [ ] Push para `github.com/helciocosta/EstudioHC-Memory-Suite.git`
- [ ] Remover `README.md` do home repo (`/home/helcio/README.md`) ou manter como ponte

### Fase 5 — Rotinas Automáticas de Backup

- [ ] Configurar backup periódico do SQLite (`estudiohc_memory.db`)
- [ ] Configurar backup do índice FAISS (`.faiss_index.pkl`)
- [ ] Script systemd timer para backup diário
- [ ] Destino: mesmo repositório ou storage separado

### Fase 6 — Monitoramento Real de RAM/CPU

- [ ] Coletar métricas dos serviços systemd (`llama-server`, `memory-server.py`)
- [ ] Script de log periódico via `journalctl` + `ps`
- [ ] Dashboard de métricas ou integração com ActivityWatch
- [ ] Alertas de uso anormal de memória

---

## Estrutura Final Esperada

```
EstudioHC-Memory-Suite/
├── apps/
│   ├── api/                      → FastAPI Central (:5050)
│   ├── mcp-memory/               → MCP Memory Server (unificado)
│   │   ├── src/
│   │   │   ├── memory_server.py  → 9 tools, WM, FAISS, RRF, budget
│   │   │   ├── summarizer.py     → Sumarização LLM
│   │   │   └── embedder.py       → Embeddings FAISS
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── mcp-stdio/                → (legado, manter como ref)
│   └── dashboard/                → Web UI (:8585)
├── server/
│   ├── mcp_server.py             → FastAPI hub central
│   ├── mcp_stdio_server.py       → (legado)
│   └── requirements.txt
├── cli/
│   └── estudio
├── scripts/
│   ├── backup.sh                 → Backup automático
│   └── monitor.sh                → Coleta de métricas
├── README.md
├── PLANO_UNIFICACAO.md
└── STATUS_ESTUDIOHC.md
```

---

## Critérios de Sucesso

- [ ] Todas as ferramentas MCP funcionando a partir do repositório
- [ ] OpenCode consumindo `memory_server.py` do caminho unificado
- [ ] Symlink funcional mantendo compatibilidade com configs existentes
- [ ] Push bem-sucedido para GitHub
- [ ] Backup automático rodando via systemd timer
- [ ] Métricas de RAM/CPU coletadas periodicamente

---

*Helcio O. Costa — 2026-06-20*
