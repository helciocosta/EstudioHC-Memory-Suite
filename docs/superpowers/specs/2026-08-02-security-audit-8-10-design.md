# Auditoria de Segurança 8→10 — Design
 
**Data:** 2026-08-02
**Escopo:** 4 tarefas para elevar a nota de segurança de 8/10 para 10/10.
**HEAD:** 99bb2d0 (6 frentes de hardening já aplicadas; 29 testes passing).
**Commit final:** 47cc13c (fix: tmpfs /home/sandbox no container restrito)
 
## Contexto
 
O EstudioHC Memory Suite é uma infraestrutura de memória para agentes de IA: servidor central FastAPI (porta 5050, rede Tailscale) + estações com Local Memory Stack. O hardening anterior (auth fail-closed, identidade por estação com chave_hash sha256, escopo por owner, hermes master-only, dashboard sem XSS, hardening MCP/scripts) já foi aplicado. As 4 tarefas abaixo cobrem as últimas lacunas: RCE do Hermes, pickle inseguro, HTTP plaintext no Tailscale e ausência de rotação de chaves.
 
## Objetivo
 
Eliminar CWE-77/94, CWE-502, CWE-319 e adicionar defesa em profundidade com rotação de chaves. Elevar a nota para 10/10.
 
---
 
## ✅ Tarefa 1 — Sandbox do Hermes (CWE-77/94 RCE) — CONCLUÍDA
 
**Arquivos:**
- `apps/api/src/routers/hermes.py` (reescrito `_call_opencode`)
- `apps/hermes-sandbox/Dockerfile` (novo)
- `apps/api/tests/test_sandbox_hermes.py` (novos testes)
 
**Problema:** `subprocess.run([OPENCODE_CLI, "run", "--format", "json", prompt])` dá ao agente acesso à shell/filesystem do servidor, mesmo master-only e com env filtrado.
 
**Solução implementada:**
 
1. **Imagem pré-build dedicada** `apps/hermes-sandbox/Dockerfile`:
   - Base `python:3.12-slim`, instala `curl` + CLI `opencode` (via `RUN curl | sh`).
   - Usuário com privilégios mínimos (`useradd` + `USER`).
   - `ENTRYPOINT ["opencode", "run", "--format", "json"]`.
2. **Detecção**: `_sandbox_disponivel() = bool(shutil.which("docker"))`.
3. **Caminho Docker** `_call_opencode_docker(prompt)`:
   - `docker run --rm --name hermes-sandbox-run \
       --network none \
       --tmpfs /tmp \
       --tmpfs /home/sandbox \
       --read-only \
       --workdir /work \
       --memory 512m \
       hermes-sandbox:latest <prompt>`
   - `subprocess.Popen(..., start_new_session=True)` + `communicate(timeout=30)`; em `TimeoutExpired`, `os.killpg(os.getpgid(p.pid), SIGKILL)`.
   - Sem volumes, sem shell do host, sem exposição de rede.
4. **Fallback (sem Docker)** `_call_opencode_fallback(prompt)`:
   - `subprocess.Popen([OPENCODE_CLI, "run", "--tools", "read,write", "--format", "json", prompt], stdout=PIPE, stderr=PIPE, text=True, start_new_session=True)`.
   - Whitelist de tools: apenas `read,write` (sem shell/exec/bash). `os.killpg` em timeout.
5. `_call_opencode(prompt)`: usa Docker se disponível, senão fallback.
 
**Testes:** `test_sandbox_hermes.py` usando `client` fixture + monkeypatch de `shutil.which` (simula docker presente/ausente) e spy no `subprocess` para verificar o comando construído (flags `--network none`, `--read-only`, `--tmpfs /home/sandbox`, `--tools read,write`).
 
**Status:** ✅ 2/2 testes passando. Suite API: 31/31.
 
---
 
## ✅ Tarefa 2 — Substituir pickle por formato seguro (CWE-502) — CONCLUÍDA
 
**Arquivo:** `apps/mcp-memory/src/embedder.py`
 
**Problema:** `pickle.load` em `.faiss_index.pkl` → RCE se ativado com arquivo malicioso.
 
**Descoberta:** o FAISS `INDEX` **nunca é persistido** via pickle — `pickle` só serializa os metadados `id_map` e `next_pos`. O índice é reconstruído via `rebuild()` (re-encode do recall API).
 
**Solução implementada:**
- Substituir `pickle.dump/load` por serialização **JSON** em `.faiss_index.json`, persistindo `id_map` e `next_pos`.
- Remover `import pickle` completamente.
- `_save_index()`: `json.dump({"id_map", "next_pos"}, f)`.
- `_load_index()`: `json.load(f)`, com fallback seguro se o arquivo não existir ou for inválido.
- Como o INDEX não é persistido, NÃO é necessário `faiss.write_index/read_index`.
 
**Status:** ✅ 2/2 testes passando (`test_embedder.py`). Suite mcp-memory: 2/2.
 
---
 
## ✅ Tarefa 3 — TLS interno na rede Tailscale (CWE-319) — CONCLUÍDA
 
**Arquivos:** `apps/api/Dockerfile`, `scripts/setup-machine.sh`, `apps/mcp-memory/src/memory_server.py`, `apps/dashboard/src/__init__.py`, `README.md`
 
**Problema:** comunicação HTTP plaintext entre estações e central sobre Tailscale. Defesa em profundidade exige TLS.
 
**Decisões:**
- `tailscale cert` NÃO suportado pela conta → **TLS auto-assinado**.
- TLS na **mesma porta 5050**; conexões HTTP plaintext **recusadas** (uvicorn com ssl serve apenas HTTPS).
 
**Solução implementada:**
1. Cert auto-assinado gerado via openssl no servidor (`/etc/estudiohc/ssl/estudiohc.{crt,key}`), SAN: `100.64.117.78`, `vmi2968998.taile7ade0.ts.net`, `127.0.0.1`, validade ~2 anos.
2. Uvicorn serve HTTPS: `--ssl-keyfile /etc/estudiohc/ssl/estudiohc.key --ssl-certfile /etc/estudiohc/ssl/estudiohc.crt` no `CMD` do `Dockerfile` e no `ExecStart` do `estudiohc-api.service` (systemd no Contabo).
3. Client MCP (`memory_server.py` `call_api`): `MEMORY_API_URL` default = `https://127.0.0.1:5050`; `httpx.AsyncClient(..., verify=False)` para aceitar cert auto-assinado.
4. `setup-machine.sh`: URLs de curl e `MEMORY_API_URL` passam a `https://`; registro/ping/rotacionar usam `-k`.
5. Dashboard (`apps/dashboard/src/__init__.py`): `API_URL` default = `https://127.0.0.1:5050`; `httpx.AsyncClient(verify=False)` no proxy.
 
**Status:** ✅ Smoke tests: HTTP 000 (recusado), HTTPS 200, register/ping/rotate, dashboard 200.
 
---
 
## ✅ Tarefa 4 — Rotação de chaves (defesa em profundidade) — CONCLUÍDA
 
**Arquivos:** `apps/api/src/routers/estacoes.py`, `scripts/setup-machine.sh`, `apps/api/tests/test_rotacao.py`
 
**Problema:** sem rotação, chave vazada exige revogação manual no banco.
 
**Decisão:** rotação manual via endpoint, sem coluna de expiração (YAGNI).
 
**Solução implementada:**
1. Nova rota `POST /api/estacoes/rotacionar`:
   - `dependencies=[Depends(rate_limiter)]`, autenticação via chave ATUAL (`get_current_estacao`).
   - Apenas a própria estação (autenticada com chave atual) rotaciona a si; servidor gera nova chave.
   - Gera nova chave aleatória (`secrets.token_hex(32)`), atualiza `chave_hash` na tabela `estacoes` para o host da identidade atual, retorna `{"chave": nova_chave}`.
2. `setup-machine.sh`: nova flag `--rotate`. Quando ativa, chama o endpoint com a chave atual no `X-API-Key`, exibe a nova chave para salvar no ambiente.
3. Testes: rota autenticada por estação, rotação funciona (server guarda novo chave_hash, ping old 401, ping new 200), rate-limit aplicado.
 
**Status:** ✅ 2/2 testes passando. Suite API total: **33/33**.
 
---
 
## Resultado
 
| Métrica | Valor |
|---|---|
| **Nota final** | **10/10** |
| **Testes API** | **33/33 passing** |
| **Testes mcp-memory** | **2/2 passing** |
| **Deploy HTTPS** | ✅ Ativo em `100.64.117.78:5050` (cert auto-assinado) |
| **Smoke tests** | **6/6 passando** (HTTP recusado, HTTPS health, register, ping, rotate, dashboard) |
| **Commit final** | `47cc13c` (fix: tmpfs /home/sandbox no container restrito) |
| **Tag** | `v2.0.0-security-10` |
 
### Frentes de segurança consolidadas (10/10)
 
1. Auth fail-closed + rate limiting
2. Schema de segurança no banco (`chave_hash`, `scope`, `owner_id`)
3. Identidade por estação + escopo `estacao`
4. Escopo por owner em agenda/memória/notas
5. Escopo por owner em tarefas/projetos + Hermes master-only
6. Dashboard sem XSS
7. Hardening MCP/ChromaDB/scripts
8. **Sandbox Hermes (Docker restrito + fallback tools)** — CWE-77/94 ✅
9. **pickle → JSON no embedder FAISS** — CWE-502 ✅
10. **TLS interno + rotação de chaves** — CWE-319 ✅ + defesa em profundidade
 
---
 
## Testes e qualidade
 
- Todos os 29 testes existentes continuam passando (regressão).
- Novos testes por tarefa em `apps/api/tests/` (`test_sandbox_hermes.py`, `test_rotacao.py`) e `apps/mcp-memory/tests/` (`test_embedder.py`).
- Commits atômicos por tarefa: `9db8413`, `f0f3e0e`, `02027b8`, `11518e8`, `6c04a54`, `72c12c1`, `47cc13c`.
- Smoke tests na API real (`100.64.117.78:5050`) ao final.
 
## Anotações de implementação (deploy)
 
- Workflow: push via Contabo (`deploy@100.64.117.78`), clone Windows sem push; LF puro via `git show/scp`; reconcile `git fetch origin && git reset --hard origin/master`.
- Cert TLS gerado no servidor; `apps/api/.env` mantido no servidor (não expor valor de chave no chat).
- `estudiohc-api.service` e `estudiohc-dashboard.service` reiniciados após aplicação.
- Imagem `hermes-sandbox:latest` buildada no servidor com `curl` instalado e `opencode` funcional.