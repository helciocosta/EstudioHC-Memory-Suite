# EstudioHC Memory Suite v4.0

Infraestrutura central de contexto, persistência de memória e inferência local
para o ecossistema de agentes AI de Helcio O. Costa.

> **Repositório:** `github.com/helciocosta/EstudioHC-Memory-Suite.git`
> **Stack:** Intel Haswell · CPU-only · Linux · Python 3.12 · llama.cpp b8763

---

## Sumário

- [Arquitetura](#arquitetura)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Serviços Systemd](#serviços-systemd)
- [API REST (porta 5050)](#api-rest-porta-5050)
- [MCP Memory Server](#mcp-memory-server)
- [Infraestrutura de Inferência](#infraestrutura-de-inferência)
- [Integrações](#integrações)
- [Monitoramento](#monitoramento)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Plano de Modernização](#plano-de-modernização)

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│                    WORKING MEMORY (MCP Tools)                     │
│  Volátil · sessão-escopo · wm_push/pop/list/clear/consolidate    │
│  Budget: MEMORY_MAX_TOKENS = 2048 · overflow: drop + log         │
└──────────────────────────┬───────────────────────────────────────┘
                           │ consolidate()
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    LONG-TERM MEMORY (API :5050)                   │
│  Persistente · FastAPI · SQLite · Decaimento temporal            │
│  • 0-30 dias:  peso normal (1.0 → 0.6)                          │
│  • 30-60 dias: peso reduzido (0.3 → 0.0)                        │
│  • >60 dias:   arquivada/excluída                                │
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
│                    INFERÊNCIA LOCAL (llama.cpp)                    │
│  llama-server.service  :11434 → cybersec-assistant-3b             │
│  llama-server-summarizer :11435 → Qwen3-1.7B                      │
│  Flash Attention · KV Cache Shift · CPU-only (Haswell)          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Estrutura do Projeto

```
EstudioHC-Memory-Suite/
├── apps/
│   ├── api/                      → FastAPI Central (porta 5050)
│   │   ├── src/                  → main, config, database, models, routers
│   │   ├── alembic/              → Migrations
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── mcp-stdio/                → MCP stdio legado (2 tools)
│   │   └── Dockerfile
│   ├── mcp-memory/               → MCP Memory Server moderno
│   │   ├── src/
│   │   │   ├── memory_server.py  → WM + FAISS + RRF + budget
│   │   │   ├── summarizer.py     → Sumarização via llama.cpp:11435
│   │   │   └── embedder.py       → Embeddings + índice FAISS
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── dashboard/                → Web UI (porta 8585)
│       ├── static/               → index.html, projeto.html
│       ├── Dockerfile
│       └── pyproject.toml
├── cli/
│   └── estudio                   → CLI de status
├── server/
│   ├── mcp_server.py             → FastAPI hub central (5050)
│   ├── mcp_stdio_server.py       → MCP stdio legado
│   └── requirements.txt
├── docker-compose.yml            → api + dashboard
├── .env.example
├── .gitignore
├── README.md
├── STATUS_ESTUDIOHC.md
└── PLANO_UNIFICACAO.md           → Roteiro de modernização
```

---

## Serviços Systemd

| Serviço | Porta | Modelo | Contexto | Threads | Função |
|---|---|---|---|---|---|
| `llama-server.service` | 11434 (0.0.0.0) | `cybersec-assistant-3b-Q4_K_M` | 4096 | 6 | Inferência principal |
| `llama-server-summarizer.service` | 11435 (127.0.0.1) | `Qwen3-1.7B-Q4_K_M` | 2048 | 4 | Sumarização de memória |

Flags comuns a ambos:
```
--flash-attn auto --cache-reuse 256 --keep -1
--device none --no-kv-offload --cont-batching
```

### KV Cache Shift — Ganho Mensurado

| Cenário | Prompt ms | Cached tokens | Ganho |
|---|---|---|---|
| Cold start | 662ms | 3 | — |
| Com cache | 99ms | 25 | **6.7x** |

---

## API REST (porta 5050)

FastAPI Central — servidor HTTP de persistência e coordenação.

| Método | Rota | Descrição |
|---|---|---|
| POST | `/remember` | Salva memória de agente |
| GET | `/recall/{project}` | Recupera memórias |
| GET | `/status/{project}` | Tasks pendentes/concluídas |
| GET | `/api/agenda` | Lista agenda |
| POST | `/api/agenda` | Salva agenda |
| GET | `/api/diarios` | Lista diários |
| GET | `/api/diario/{data}` | Lê diário |
| POST | `/api/nota` | Adiciona nota |
| GET | `/api/projetos` | Lista projetos |
| POST | `/api/projetos/sync` | Sincroniza projetos |
| POST | `/api/projetos/gerar-relatorio` | Relatório IA do projeto |
| GET | `/api/estacoes` | Lista estações |
| POST | `/api/estacoes/ping` | Heartbeat de estação |
| POST | `/api/hermes` | Chat com IA (Hermes CLI) |
| GET | `/api/status` | Health check |
| GET | `/api/status_md` | Status em markdown |

Docs interativos: `/docs` (Swagger) e `/redoc` (ReDoc).

---

## MCP Memory Server

O `apps/mcp-memory/` implementa o servidor MCP STDIO com 9 ferramentas
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

### Ranking Híbrido (search_memory)

```
score = decay(recência) × 0.4 + keyword_match × 0.35 + categoria × 0.25
RRF   = keyword_rank × 0.4 + vector_rank × 0.6
```

- Decaimento: 30 dias para início, 60 dias para exclusão
- FAISS IndexFlatIP (all-MiniLM-L6-v2, dim 384)
- Budget: `MEMORY_INJECT_TOKENS` (1024) — top-1 sempre incluso

### Integração OpenCode

Registrado em `~/.config/opencode/opencode.jsonc`:

```json
{
  "mcp": {
    "memory": {
      "type": "local",
      "command": ["python3", "/caminho/para/apps/mcp-memory/src/memory_server.py"],
      "enabled": true
    }
  }
}
```

---

## Infraestrutura de Inferência

### Migração: KoboldCpp → llama.cpp nativo (2026-06-20)

| Componente | Antes | Depois |
|---|---|---|
| Binário | `koboldcpp-linux-x64` | `msty-llama-server` v8763 |
| Backend CPU | Genérico | `libggml-cpu-haswell.so` |
| Flash Attention | ❌ | ✅ `--flash-attn auto` |
| KV Cache Shift | ❌ | ✅ `--cache-reuse 256 + --keep -1` |
| Prompt Caching | ❌ | ✅ `--cache-prompt` (default on) |
| Continuous Batching | ❌ | ✅ `--cont-batching` |

### Flags Críticas

| Flag | Efeito |
|---|---|
| `--flash-attn auto` | Reduz largura de banda da atenção ~2x |
| `--cache-reuse 256` | KV Cache Shift — reaproveita prefixo em chamadas repetidas |
| `--keep -1` | System prompt nunca sai do cache |
| `--device none` | Força CPU-only (evita falha de VRAM em GPU limitada) |
| `--no-kv-offload` | KV cache 100% em RAM (0 latência de transferência) |

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

## Integrações

### Odysseus

```env
LLM_HOST=localhost  →  http://localhost:11434/v1/chat/completions
```

- Compatível com formato OpenAI de mensagens
- Embeddings via `/v1/embeddings` ou fallback fastembed local

### Agentes OpenCode

Todos os agentes configurados (Morpheus, Merovingian, Trinity, etc.)
consomem as ferramentas MCP de memória diretamente via STDIO.

---

## Monitoramento

### Logs

```bash
# Servidor principal
journalctl -u llama-server.service -f --no-hostname -o cat

# Summarizer
journalctl -u llama-server-summarizer.service -f --no-hostname -o cat
```

### Healthcheck

```bash
# Disponibilidade
curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/v1/models

# Inferência
curl -s http://localhost:11434/v1/chat/completions \
  -d '{"model":"llama","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'

# KV Cache Hit
curl -s ... | python3 -c "
import sys,json; d=json.load(sys.stdin)
t = d['usage']['prompt_tokens_details']
print(f'Cache: {t[\"cached_tokens\"]} tok, Prompt: {d[\"timings\"][\"prompt_ms\"]:.0f}ms')"
```

### Recursos

```bash
# Memória
ps -o pid,rss,comm -p $(pgrep -d',' -f msty-llama-server) \
  | awk 'NR>1 {printf "%s: %.1f GiB\n", $3, $2/1024/1024}'

# Portas
ss -tlnp | grep -E "1143[4-5]|5050"

# Logs de erro
journalctl -u llama-server.service --no-pager | grep -i "error\|fail\|warn"
```

### Gerenciamento

```bash
sudo systemctl restart llama-server.service
sudo systemctl restart llama-server-summarizer.service
```

---

## Variáveis de Ambiente

| Variável | Default | Serviço | Descrição |
|---|---|---|---|
| `MEMORY_MAX_TOKENS` | 2048 | memory-server.py | Budget total da Working Memory |
| `MEMORY_INJECT_TOKENS` | 1024 | memory-server.py | Budget por chamada de search_memory |
| `MEMORY_SUMMARIZE_THRESHOLD` | 60 | memory-server.py | Tamanho mínimo (chars) para sumarizar |
| `MEMORY_MAX_INJECT` | 3 | memory-server.py | Máximo de itens injetados |
| `MEMORY_DECAY_DAYS` | 30 | memory-server.py | Dias para início do decaimento |
| `HYBRID_RRF_K` | 60 | memory-server.py | Constante K do RRF ranking |
| `MEMORY_API_URL` | http://localhost:5050 | memory-server.py | Endpoint de persistência LTM |
| `CUDA_VISIBLE_DEVICES` | "" | systemd services | Força CPU-only |

---

## Plano de Modernização

Consulte [`PLANO_UNIFICACAO.md`](PLANO_UNIFICACAO.md) para o roteiro completo
de unificação, atualização e modernização deste stack.

---

*Projeto mantido por Helcio O. Costa. v4.0 — 2026-06-20*
