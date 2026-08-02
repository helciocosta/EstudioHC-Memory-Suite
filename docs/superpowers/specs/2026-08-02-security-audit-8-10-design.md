# Auditoria de Segurança 8→10 — Design

**Data:** 2026-08-02
**Escopo:** 4 tarefas para elevar a nota de segurança de 8/10 para 10/10.
**HEAD:** 99bb2d0 (6 frentes de hardening já aplicadas; 29 testes passing).

## Contexto

O EstudioHC Memory Suite é uma infraestrutura de memória para agentes de IA: servidor central FastAPI (porta 5050, rede Tailscale) + estações com Local Memory Stack. O hardening anterior (auth fail-closed, identidade por estação com chave_hash sha256, escopo por owner, hermes master-only, dashboard sem XSS, hardening MCP/scripts) já foi aplicado. As 4 tarefas abaixo cobrem as últimas lacunas: RCE do Hermes, pickle inseguro, HTTP plaintext no Tailscale e ausência de rotação de chaves.

## Objetivo

Eliminar CWE-77/94, CWE-502, CWE-319 e adicionar defesa em profundidade com rotação de chaves. Elevar a nota para 10/10.

---

## Tarefa 1 — Sandbox do Hermes (CWE-77/94 RCE)

**Arquivos:**
- `apps/api/src/routers/hermes.py` (reescrever `_call_opencode`)
- `apps/hermes-sandbox/Dockerfile` (novo)
- `apps/api/tests/test_hermes.py` (novos testes)

**Problema:** `subprocess.run([OPENCODE_CLI, "run", "--format", "json", prompt])` dá ao agente acesso à shell/filesystem do servidor, mesmo master-only e com env filtrado.

**Solução:**

1. **Imagem pré-build dedicada** `apps/hermes-sandbox/Dockerfile`:
   - Base `python:3.12-slim`, instala o CLI `opencode` (via COPY ou `RUN curl | sh`).
   - Usuário com privilégios mínimos (`useradd` + `USER`).
   - `ENTRYPOINT ["opencode", "run", "--format", "json"]`.
2. **Detecção**: `_sandbox_disponivel() = bool(shutil.which("docker"))`.
3. **Caminho Docker** `_call_opencode_docker(prompt)`:
   - `docker run --rm --name hermes-sandbox \
       --network none \
       --tmpfs /tmp \
       --read-only \
       --workdir /work \
       --memory 512m \
       --stop-timeout 1 \
       hermes-sandbox:latest <prompt>`
   - `subprocess.run(..., timeout=30, start_new_session=True)`; em `TimeoutExpired`, `os.killpg(os.getpgid(p.pid), SIGKILL)` (usar `Popen` + `communicate(timeout=30)`).
   - Sem volumes, sem shell do host, sem exposição de rede.
4. **Fallback (sem Docker)** `_call_opencode_fallback(prompt)`:
   - `subprocess.Popen([OPENCODE_CLI, "run", "--tools", "read,write", "--format", "json", prompt], stdout=PIPE, stderr=PIPE, text=True, start_new_session=True)`.
   - Whitelist de tools: apenas `read,write` (sem shell/exec/bash). `os.killpg(os.getpgid(proc.pid), SIGKILL)` em `TimeoutExpired` (proc.communicate(timeout=30) com try/except).
5. `_call_opencode(prompt)`: usa Docker se disponível, senão fallback.

**Testes:** `test_hermes.py` novos usando `client` fixture + monkeypatch de `shutil.which` (simula docker presente/ausente) e spy no `subprocess` para verificar o comando construído (flags `--network none`, `--read-only`, `--tools read,write`).

---

## Tarefa 2 — Substituir pickle por formato seguro (CWE-502)

**Arquivo:** `apps/mcp-memory/src/embedder.py` (linhas 155-173)

**Problema:** `pickle.load` em `.faiss_index.pkl` → RCE se ativado com arquivo malicioso.

**Descoberta de exploração:** o FAISS `INDEX` **nunca é persistido** via pickle — `pickle` só serializa os metadados `id_map` e `next_pos`. O índice é reconstruído via `rebuild()` (re-encode do recall API).

**Solução:**
- Substituir `pickle.dump/load` por serialização **JSON** em `.faiss_index.json`, persistindo `id_map` e `next_pos`.
- Remover `import pickle` completamente.
- `_save_index()`: `json.dump({"id_map", "next_pos"}, f)`.
- `_load_index()`: `json.load(f)`, com fallback seguro se o arquivo não existir ou for inválido.
- Como o INDEX não é persistido, NÃO é necessário `faiss.write_index/read_index`.

**Migração:** nenhuma (fanálise local). O arquivo `.pkl` legado se torna obsoleto; leitura falha graciosa já tratada por defaults.

---

## Tarefa 3 — TLS interno na rede Tailscale (CWE-319)

**Arquivos:** `apps/api/.env`, `apps/api/Dockerfile`, `scripts/setup-machine.sh`, `apps/mcp-memory/src/memory_server.py`

**Problema:** comunicação HTTP plaintext entre estações e central sobre Tailscale. Defesa em profundidade exige TLS.

**Decisões:**
- `tailscale cert` NÃO suportado pela conta → **TLS auto-assinado**.
- TLS na **mesma porta 5050**; conexões HTTP plaintext **recusadas** (não redirecionadas; simplesmente falham).

**Solução:**
1. Gerar cert auto-assinado (self-signed) via openssl, com validade ~1-2 anos (`apps/api/tls/` ou caminho em `.env`).
2. Uvicorn serve HTTPS: adicionar `--ssl-keyfile` e `--ssl-certfile` ao `CMD` do `Dockerfile` e ao `ExecStart` do `estudiohc-api.service` no servidor.
3. Client MCP (`memory_server.py` `call_api`): `MEMORY_API_URL` default passa a `https://100.64.117.78:5050`; `httpx.AsyncClient(..., verify=False)` para aceitar cert auto-assinado, com documentação/opção de instalar CA no trust store.
4. `setup-machine.sh`:
   - URLs de curl e `MEMORY_API_URL` passam a `https://`.
   - Registro/let; inclui suporte a `/estacoes/registrar`, `/ping`, e agora `/rotacionar`.
   - Opção de baixar e instalar o CA público no trust store; texto documenta `verify=False` como fallback.
5. Opcional: `curl -k` em vez de `-k`? O script de regeneração de cert e a documentação.

**Rejeição de HTTP:** uvicorn com ssl serve apenas HTTPS; a porta não aceita plaintext. Nenhuma rota/redirect adicional necessário.

---

## Tarefa 4 — Rotação de chaves (defesa em profundidade)

**Arquivos:** `apps/api/src/routers/estacoes.py`, `apps/api/src/security.py` (se `openssl rand` ou gerador), `scripts/setup-machine.sh`

**Problema:** sem rotação, chave vazada exige revogação manual no banco.

**Decisão:** rotação manual via endpoint, sem coluna de expiração (YAGNI).

**Solução:**
1. Nova rota `POST /api/estacoes/rotacionar`:
   - `dependencies=[Depends(rate_limiter)]`, autenticação via chave ATUAL (`get_current_estacao`).
   - Master também pode rotacionar de outra estação? Decisão: apenas a própria estação (autenticada com chave atual) rotaciona a si; servidor gera nova chave.
   - Gera nova chave aleatória (`openssl rand -hex 32` ou `secrets.token_hex(32)`), atualiza `chave_hash` na tabela `estacoes` para o host da identidade atual, retorna `{"chave": nova_chave}`.
2. `setup-machine.sh`: nova flag `--rotate`. Quando ativa, chama o endpoint com a chave atual no `X-API-Key`, salva a nova chave em `CHAVE_ESTACAO`/persistência local e re-emit o ping/uso com a nova chave.
3. Teste: rota master-only, rotação funciona (server guarda novo chave_hash, estação responde com nova chave), rate-limit aplicado.

---

## Testes e qualidade

- Todos os 29 testes existentes continuam passando (regressão).
- Novos testes por tarefa em `apps/api/tests/`.
- Commits atômicos por tarefa.
- Smoke tests na API real (100.64.117.78:5050) ao final.

## Anotações de implementação (deploy)

- Workflow: push via Contabo (`deploy@100.64.117.78`), clone Windows sem push; LF puro via `git show/scp`; reconcile `git fetch origin && git reset --hard origin/master`.
- Cert TLS gerado no servidor; `apps/api/.env` atualizado (não expor valor de chave no chat).
- `estudiohc-api.service` e `estudiohc-dashboard.service` reiniciados após aplicação.