### Task 4: Corrigir endpoint do sumarizador (porta 11435 + modelo Qwen3-1.7B)

**Files:**
- Modify: `apps/mcp-memory/src/summarizer.py` (as linhas que definem a URL da API e o modelo)

**Contexto:** o `summarizer.py` apontava para `http://localhost:11434/v1/chat/completions` com model `"koboldcpp"` (LLM principal). O correto e o servidor dedicado na porta **11435** (Qwen3-1.7B, servico `llama-server-summarizer`). Tornar configuravel via env com default correto.

- [ ] **Step 1: Tornar configuravel via env com default correto**

No arquivo `apps/mcp-memory/src/summarizer.py`, substituir a definicao da URL/constante da API (hoje `KOBOLD_API = "http://localhost:11434/v1/chat/completions"` ou similar) por:

```python
import os

SUMMARIZER_API = os.getenv("SUMMARIZER_API", "http://localhost:11435/v1/chat/completions")
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "Qwen3-1.7B")
```

Substituir todos os usos de `KOBOLD_API` por `SUMMARIZER_API` e `"model": "koboldcpp"` por `"model": SUMMARIZER_MODEL`. Garantir que `import os` esteja presente (pode ja existir). Nao altere MAX_OUTPUT_TOKENS/TIMEOUT ou a logica de chamada.

- [ ] **Step 2: Validar sintaxe**

```bash
../../.venv/Scripts/python.exe -m py_compile apps/mcp-memory/src/summarizer.py
```

Esperado: exit 0, sem output. (Validacao real do servidor Qwen3 na porta 11435 fica para a Task 7 de deploy.)

- [ ] **Step 3: Commit**

```bash
git add apps/mcp-memory/src/summarizer.py
git commit -m "fix(mcp-memory): point summarizer at Qwen3-1.7B on port 11435"
```
