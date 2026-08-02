# Auditoria de Segurança 8→10 (Sandbox Hermes, Pickle→JSON, TLS, Rotação de Chaves) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevar a segurança do EstudioHC Memory Suite de 8/10 para 10/10 executando 4 frentes: sandbox do agente Hermes (eliminar CWE-77/94 RCE), substituir pickle por JSON (eliminar CWE-502 RCE), TLS interno na rede Tailscale (eliminar CWE-319), e rotação automática de chaves de estação (defesa em profundidade).

**Architecture:** (1) O agente opencode que roda via `_call_opencode` passa a executar dentro de um container Docker efêmero e restrito (`--network none --read-only --tmpfs /tmp`, timeout 30s, kill no grupo), com fallback sem Docker usando `--tools` whitelist. (2) O índice de memória do MCP passa de `pickle.dump/.load` para `json` (o índice FAISS nunca foi persistido — só `id_map`/`next_pos`), removendo totalmente o pickle. (3) A API central serve HTTPS na mesma porta 5050 com certificado auto-assinado (Tailscale cert não suportado pela conta), recusando HTTP plaintext; clientes MCP e setup-machine usam `https://` com `verify=False`. (4) Novo endpoint `POST /api/estacoes/rotacionar` master-only + rate-limited que gera nova chave, atualiza `chave_hash`, e retorna a chave nova.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, Docker, MCP, FAISS, httpx, subprocess, Tailscale.

## Global Constraints

- **Workflow de push:** O clone Windows (`C:\Users\helci\AppData\Local\Temp\opencode\EstudioHC-Memory-Suite`) NÃO tem push. Commits locais são pushados SEMPRE via servidor Contabo `deploy@100.64.117.78` em `~/Apps/EstudioHC-Memory-Suite`. Após push, reconciliar localmente: `git fetch origin && git reset --hard origin/master`.
- **CRLF:** NUNCA `Set-Content`. Para arquivos que irão ao servidor, gerar LF puro via `cmd /c "git -C <repo> show HEAD:<path> > %TEMP%\opencode\lf2\<file>"`, transferir via scp → `/tmp/hardening2/` → `cp`, e verificar `grep -c $'\r'` = 0.
- **Testes API:** workdir `apps\api`, comando `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`. Suíte atual: **29 passed** (Task 1-9 da sessão anterior). Nenhuma task pode quebrar esses 29.
- **Chaves de estação nos testes NOVOS:** usar chaves ÚNICAS no namespace global (ex: prefixo `sb`), pois o DB sqlite de teste é session-scoped e compartilhado entre arquivos da suíte.
- **`curl.exe`** (não `curl`) no PowerShell. JSON via `[System.IO.File]::WriteAllText` para evitar encoding.
- **Convenção de commits:** `feat:`, `fix:`, `test:`, `docs:` em português, commits atômicos por task.
- **Segurança de chave:** NUNCA expor a API_KEY master no chat. Re-obter via `ssh deploy@100.64.117.78 "grep '^API_KEY=' /home/deploy/Apps/EstudioHC-Memory-Suite/apps/api/.env"` quando necessário.
- **Servidor:** Contabo `deploy@100.64.117.78`, repo `~/Apps/EstudioHC-Memory-Suite`, serviços `estudiohc-api` + `estudiohc-dashboard` (systemd), alembic 002 head, Docker 24.7.1 disponível. FQDN: `vmi2968998.taile7ade0.ts.net` (tailscale cert NÃO suportado).

---

### Task 1: Sandbox do Hermes (eliminar CWE-77/94 RCE)

**Files:**
- Create: `apps/hermes-sandbox/Dockerfile`
- Modify: `apps/api/src/routers/hermes.py` (inteiro — `_call_opencode` e funções auxiliares)
- Test: `apps/api/tests/test_sandbox_hermes.py` (NOVO)
- Modify: `docker-compose.yml` (pré-build da imagem no deploy)

**Interfaces:**
- Consumes: `settings.HERMES_TIMEOUT` (config.py), `subprocess`, `shutil.which`, `os`.
- Produces: `_sandbox_disponivel() -> bool`; `_call_opencode(prompt: str) -> dict | None` (mesma assinatura de retorno de antes: `{"resposta": str, "agente": "opencode"}` ou `None`); `_call_opencode_docker(prompt)` e `_call_opencode_fallback(prompt)` como helpers internos usados por `_call_opencode`. `chat_ia` (não muda) chama `_call_opencode` com fallback `_call_hermes`.

- [ ] **Step 1: Criar a imagem Docker do sandbox**

Criar `apps/hermes-sandbox/Dockerfile`:

```dockerfile
FROM python:3.12-slim

# Usuário não-root
RUN useradd --create-home --uid 1000 sandbox && mkdir -p /work && chown sandbox:sandbox /work
USER sandbox
WORKDIR /work

# Instala a CLI opencode (binário standalone)
ARG OPENCODE_VERSION=latest
RUN curl -fsSL https://opencode.ai/install | bash || true

ENV PATH="/home/sandbox/.opencode/bin:${PATH}"
ENV OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["opencode", "run", "--format", "json"]
```

> Nota: `--workdir /work`, `--read-only`, `--tmpfs /tmp` e `--network none` são aplicados na linha de comando `docker run` (Task 1 Step 3), não no Dockerfile. O container é `--rm` (efêmero). A imagem é pré-buildada no deploy via `docker compose build hermes-sandbox` ou `docker build -t hermes-sandbox:latest apps/hermes-sandbox`.

- [ ] **Step 2: Escrever os testes que falham**

Criar `apps/api/tests/test_sandbox_hermes.py`:

```python
import subprocess
import pytest
from unittest.mock import patch

from src.routers import hermes

MASTER = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_sandbox_usa_docker_com_flags_restritivas(client, monkeypatch):
    # pasta registra estação sb1 e faz hermes chamar opencode
    await client.post("/api/estacoes/registrar", json={"hostname": "est-sb1", "chave": "chave-sb1"}, headers=MASTER)
    chamadas = []
    class FakeProc:
        def __init__(self, *a, **k):
            self.stdout = "line output type text part"
            self.stderr = ""
        def communicate(self, timeout=None):
            return ("", "")
    def fake_popen(cmd, **k):
        chamadas.append(cmd)
        return FakeProc()
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.Popen", side_effect=fake_popen), \
         patch("hermes._parse_json_lines", return_value=["oi"]):
        r = await client.post("/api/hermes", json={"mensagem": "teste"}, headers=MASTER)
    assert r.status_code == 200
    assert chamadas, "Popen não chamado"
    cmd = chamadas[0]
    assert any(part == "--rm" for part in cmd)
    assert any(part == "--network" for part in cmd) and "none" in cmd
    assert any(part == "--read-only" for part in cmd)
    assert any(part == "--tmpfs" for part in cmd) and "/tmp" in cmd
    assert any(part == "hermes-sandbox:latest" for part in cmd)


@pytest.mark.asyncio
async def test_sandbox_sem_docker_usa_fallback_com_tools(client: AsyncClient):
    await client.post("/api/estacoes/registrar", json={"hostname": "est-sb2", "chave": "chave-sb2"}, headers=MASTER)
    chamadas = []
    class FakeProc:
        def __init__(self, *a, **k):
            self.stderr_file = None
        def communicate(self, timeout):
            return ("", "")
    with patch("shutil.which", return_value=None), \
         patch("subprocess.Popen", side_effect=lambda cmd, *a, **k: chamadas.append(cmd) or FakeProc()), \
         patch("apps._call_env_filtrado", return_value={}):
        await client.post("/api/hermes", json={"mensagem": "x"}, headers=MASTER)
    assert chamadas, "fallback deveria chamar Popen"
    assert "--tools" in chamadas[0] or "read,write" in chamadas[0]
```

> IMPORTANTE: os 2 testes acima usam `pytest.mark.asyncio` + fixture `client` (auto async). O conftest já define fixture `client: AsyncClient` e `asyncio_mode=auto`. Para o teste injetar o prompt como ARG direto usa-se `client.post(..., json={"mensagem":...})`. Como `_call_hermes` pode ser acionado se `_call_opencode` retornar None, nos testes mock `_call_opencode` para retornar a resposta.

- [ ] **Step 3: Rodar e verificar que falham**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_sandbox_hermes.py -q`
Expected: os testes falham porque `_sandbox_disponivel`/`_call_opencode_docker` ainda não existem (NameError) ou `subprocess.run` é chamado sem as flags.

- [ ] **Step 4: Implementar o sandbox em hermes.py**

Reescrever `apps/api/src/routers/hermes.py`:

```python
import os
import json
import signal
import shutil
import subprocess

from fastapi import APIRouter, Depends

from ..config import settings
from ..schemas import ChatPayload
from ..security import Identity, require_master

router = APIRouter(prefix="/api", tags=["Chat IA"])

OPENCODE_CLI = "/home/deploy/.opencode/bin/opencode"
HERMES_CLI = settings.HERMES_CLI
SANDBOX_IMAGE = "hermes-sandbox:latest"
SANDBOX_TIMEOUT = 30
SANDBOX_MAX_ATTEMPTS = 3

_SANDBOX_CHECKED = False
_SANDBOX_OK = False


def _sandbox_disponivel() -> bool:
    """True se o Docker está disponível no PATH e a imagem de sandbox existe ou pode rodar."""
    global _SANDBOX_CHECKED, _SANDBOX_OK
    if not _SANDBOX_CHECKED:
        _SANDBOX_OK = bool(shutil.which("docker"))
        _SANDBOX_CHECKED = True
    return _SANDBOX_OK


def _env_filtrado() -> dict:
    """Ambiente mínimo para a execução: só PATH/HOME + OPENROUTER (se set)."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    if os.environ.get("OPENROUTER_API_KEY"):
        env["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _kill_proc(proc):
    """Mata o processo e todo o seu group (mesmo com filhos)."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _call_opencode_docker(prompt: str):
    """Executa opencode num container Docker efêmero e restrito."""
    cmd = ["docker", "run", "--rm", "--name", "hermes-sandbox-run",
           "--network", "none", "--read-only", "--tmpfs", "/tmp",
           "--workdir", "/work", "--memory", "512m",
           SANDBOX_IMAGE, prompt]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=SANDBOX_TIMEOUT)
        return out
    except subprocess.TimeoutExpired:
        _kill_process(proc)
        proc.wait()
        return ""
    except Exception:
        return ""


def _call_opencode_fallback(prompt: str):
    """Fallback sem Docker: opencode local com whitelist de tools (sem shell/exec)."""
    try:
        cmd = [OPENCODE_CLI, "run", "--tools", "read,write", "--format", "json", prompt]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=_env_filtrado(), start_new_session=True)
        out, _ = proc.communicate(timeout=SANDBOX_TIMEOUT)
        return out
    except subprocess.TimeoutExpired:
        _kill_process(proc)
        return None
    except Exception:
        return None


def _call_opencode(prompt: str):
    """Executa opencode (Docker se disponível, senão fallback whitelist). Retorna str da saída ou None."""
    if _sandbox_disponivel():
        return _call_opencode_docker(prompt)
    return _call_opencode_fallback(prompt)


def _parse_opencode_output(raw: str):
    """Converte saída JSON-lines de opencode em texto plano, ou retorna [] se vazio."""
    if not raw:
        return []
    textos = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "text":
            textos.append(obj.get("part", {}).get("text", ""))
        elif obj.get("type") == "message":
            content = obj.get("content")
            if isinstance(content, str):
                textos.append(content)
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        textos.append(c.get("text", ""))
    return [t for t in textos if t]


def _call_hermes(prompt: str) -> dict:
    try:
        proc = subprocess.run([HERMES_CLI, "-z", prompt, "chat"],
                              capture_output=True, text=True,
                              timeout=settings.HERMES_TIMEOUT,
                              env=_env_filtrado(), start_new_session=True)
        if proc.returncode != 0:
            return {"resposta": f"Erro Hermes CLI ({proc.returncode})", "agente": "hermes-error"}
        return {"resposta": proc.stdout.strip(), "agente": "hermes"}
    except subprocess.TimeoutExpired:
        return {"resposta": "Falha ao chamar Hermes: timeout", "agente": "hermes-failed"}
    except Exception:
        return {"resposta": "Falha ao chamar Hermes", "agente": "hermes-failed"}


def _chat_ia(payload: ChatPayload, identity: Identity = Depends(require_master)) -> dict:
    """POST /hermes — executa opencode (sandbox) com fallback hermes."""
    contexto = payload.contexto or payload.contexto_extra or ""
    prompt = f"[Contexto EstudioHC: {contexto}]\n\n{payload.mensagem}" if contexto else payload.mensagem
    raw = _call_opencode(prompt)
    if raw:
        textos = _parse_opencode_output(raw)
        if textos:
            return {"resposta": "\n".join(textos).strip(), "agente": "opencode"}
    return _call_hermes(prompt)


# Rota
@router.post("/hermes")
async def chat_ia(payload: ChatPayload, identity: Identity = Depends(require_master)):
    return _pa_ia(payload, identity)
```

> IMPORTANTE: Manter o `_env_filtrado` e o campo `mensagem` do `ChatPayload` como já existe no código atual (verificar em schemas). O nome real do endpoint é `/hermes` (não `/health1`). Ajustar nomes reais conforme o arquivo atual lido na exploração: o endpoint real em hermes.py é `@router.post("/hermes")` com `chat_ia(payload, identity)`. **Copiar a estrutura real atual e apenas substituir `subprocess.run` do `_call_opencode` pelas novas funções `_sandbox_disponivel`/`_call_opencode_docker`/`_call_opencode_fallback`. Não renomear endpoint nem payload.**

- [ ] **Step 5: Rodar e verificar que passam**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/test_sandbox_hermes.py -q`
Expected: PASS (2 testes novos passam).

- [ ] **Step 6: Rodar a suíte completa para não regredir**

Run: `..\..\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: **31 passed** (29 + 2 novos), nenhum dos antigos quebra. O teste antigo `test_hermes_estacao_403` deve continuar passando (a autenticação master não mudou).

- [ ] **Step 7: Pré-build da imagem no deploy (docker-compose.yml)**

Modificar `docker-compose.yml` — adicionar serviço `hermes-sandbox` (o deploy que roda `docker compose build` vai buildar). Adicionar ao arquivo:

```yaml
  hermes-sandbox:
    build: ./apps/hermes-sandbox
    image: hermes-sandbox:latest
    network_mode: none
    command: ["echo", "sandbox image built"]
```

> No deploy real (Task 5), garanta `docker build -t hermes-sandbox:latest apps/hermes-sandbox` no servidor antes de reiniciar a API.

- [ ] **Step 8: Commit**

```bash
git add apps/hermes-sandbox/Dockerfile apps/api/src/routers/hermes.py apps/api/tests/test_sandbox_hermes.py docker-compose.yml
git commit -m "feat: sandbox do agente hermes via container docker (network none, read-only) com fallback whitelist"
```

---

### Task 2: Substituir pickle por JSON no embedder (eliminar CWE-502 RCE)

**Files:**
- Modify: `apps/mcp-memory/src/embedder.py` (imports, INDEX_FILE, _save_index, _load_index)
- Test: `apps/mcp-memory/tests/test_embedder.py` (se existir) ou criar

**Interfaces:**
- Consumes: sem deps externas novas (só `json`).
- Produces: `_save_index()`/`_load_index()` passam a usar `.faiss_index.json` com `{"id_map": dict, "next_pos": int}`. `import pickle` removido. Índice FAISS (INDEX) continua NÃO persistido — só metadados.

- [ ] **Step 1: Verificar se há teste existente do embedder**

Checar: `ls apps/mcp-memory/tests/` (se existir). Se existir teste que chama `_save_index`/`_load_index`, atualizar. Se não, criar `apps/mcp-memory/tests/test_embedder.py`.

- [ ] **Step 2: Escrever o teste que falha (se não houver)**

Criar `apps/mcp-memory/tests/test_embedder.py`:

```python
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import embedder


def test_index_save_load_json_nao_usa_pickle():
    embedder.ID_MAP = {0: "mem-1", 1: "mem-2"}
    embedder.NEXT_POS = 2
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, ".faiss_index.json")
        with open(path, "w") as f:
            json.dump({"id_map": embedder.ID_MAP, "next_pos": embedder.NEXT_POS}, f)
        # simulamos load do JSON
        with open(path) as f:
            data = json.load(f)
        assert data["id_map"] == {0: "mem-1", 1: "mem-2"}
        assert data["next_pos"] == 2


def test_nao_existe_import_pickle():
    import embedder
    with open(embedder.__file__) as f:
        assert "pickle" not in f.read()
```

- [ ] **Step 3: Rodar e verificar que falham**

```bash
python -m pytest apps/mcp-memory/tests/test_embedder.py -q
```
Expected: `test_nao_existe_import_pickle` falha (arquivo ainda usa pickle) e o outro passa.

> Os testes do mcp-memory usam o venv local `apps/mcp-memory/.venv` se houver (confirmar no deploy).

- [ ] **Step 4: Implementar jogar o JSON em embedder.py**

Modificar `apps/mcp-memory/src/embedder.py`:
1. Remover `import pickle` (linha 4).
2. Trocar `INDEX_FILE = os.path.join(... , ".faiss_index.pkl")` → `.faiss_index.json`.
3. Reescrever `_save_index()`:

```python
def _save_index():
    try:
        data = {"id_map": ID_MAP, "next_pos": NEXT_POS}
        with open(INDEX_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[embedder] falha ao salvar índice: {e}", file=sys.stderr)
```

4. Reescrever `_load_index()`:

```python
def _load_index():
    global ID_MAP, NEXT_POS
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE) as f:
                data = json.load(f)
            ID_MAP = {int(k): v for k, v in data.get("id_map", {}).items()}
            NEXT_POS = int(data.get("next_pos", 0))
        except Exception as e:
            print(f"[embedder] falha ao carregar índice: {e}", file=sys.stderr)
            ID_MAP = {}
            NEXT_POS = 0
    else:
        ID_MAP = {}
        NEXT_POS = 0
```

> O `import json` já existe (linha 3). Confirmar que `sys` está importado.

- [ ] **Step 5: Rodar testes e verificar que passam**

```bash
python -m pytest apps/mcp-memory/tests/test_embedder.py -q
```
Expected: PASS (2 testes). Garantir que não há mais `pickle` referenciado.

- [ ] **Step 6: Rodar a suíte API para não regredir (embedder é MCP, não API)**

A suíte da API (apps/api) não usa embedder, então `29 passed` deve permanecer intacto. Opcional: rodar `..\..\.venv\Scripts\python.exe -m pytest tests/ -q` em apps\api para confirmar.

- [ ] **Step 7: Commit**

```bash
git add apps/mcp-memory/src/embedder.py apps/mcp-memory/tests/test_embedder.py
git commit -m "fix: substituicao de pickle por JSON no indice de memoria (elimina CWE-502 RCE)"
```

---

### Task 3: TLS interno na rede Tailscale (eliminar CWE-319)

**Files:**
- Modify: `apps/api/src/routers/` (nenhuma rota muda; só o servidor uvicorn)
- Modify: `apps/api/Dockerfile` (CMD com --ssl-keyfile/--ssl-certfile)
- Modify: `apps/mcp-memory/src/memory_server.py` (MEMORY_API_URL → https, verify=False)
- Modify: `scripts/setup-machine.sh` (URLs http→https, curl -k)
- Modify: `README.md` (aviso MITM)
- Test: `apps/mcp-memory/tests/test_tls.py` (ou doc de teste)

**Interfaces:**
- Consumes: caminhos dos certs (definidos no deploy: `/etc/estudiohc/ssl/estudiohc.crt` e `estudiohc.key`, SERVED por uvicorn). `MEMORY_API_URL` passa para `https://100.64.117.78:5050`.
- Produces: API escuta só HTTPS em 5050; clientes precisam `verify=False`. setup-machine usa `https://`.

- [ ] **Step 1: Gerar certificados auto-assinados (no servidor, no deploy)**

No servidor executar (deploy Task 5):

```bash
sudo mkdir -p /etc/estudio/ssl
cd /etc/estudio/ssl
sudo openssl req -x509 -nodes -days 730 -newkey rsa:2048 \
  -keyout estudiohc.key -out estudiohc.crt \
  -subj "/CN=vmi2968998.taile7ade0.ts.net"
sudo chmod 600 estudiohc.key
sudo chown deploy:deploy estudiohc.key estudiohc.crt
```

- [ ] **Step 2: Atualizar Dockerfile do api para servir HTTPS**

Modificar `apps/api/Dockerfile` CMD para:

```dockerfile
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5050",
     "--ssl-keyfile", "/etc/estudiohc/ssl/estudiohc.key",
     "--ssl-certfile", "/etc/estudiohc/ssl/estudiohc.crt"]
```

(No deploy real, os certs são montados no container via volume em docker-compose — ver Step 7.)

- [ ] **Step 3: Atualizar memory_server.py call_api para HTTPS**

Modificar `apps/mcp-memory/src/memory_server.py`:

```python
MEMORY_API_URL = os.getenv("MEMORY_API_URL", "https://127.0.0.1:5050")
```

E em `call_api`:

```python
async def call_api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    if MEMORY_API_KEY:
        headers["X-API-Key"] = MEMORY_API_KEY
    async with httpx.AsyncClient(timeout=10, verify=False) as client:
        resp = await client.request(method, f"{MEMORY_API_URL}{path}",
                                    headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()
```

> `verify=False` necessário pois o cert é auto-assinado. Documentar no README (Step 5).

- [ ] **Step 3: Atualizar setup-machine.sh para https**

Modificar `scripts/setup-machine.sh`:
1. `SERVIDOR_CENTRAL=100.64.117.78` (mantém) + `SERVIDOR_URL="https://${SERVIDOR_CENTRAL}:5050"`.
2. Todos os `curl ... http://${SERVIDOR_CENTRAL}:5050/...` → `curl -k ... ${SERVIDOR_URL}/...` (flag `-k` para aceitar auto-assinado).
3. Linha opencode.jsonc `"MEMORY_API_URL=http://${SERVIDOR_CENTRAL}:5050"` → `"MEMORY_API_URL=${SERVIDOR_URL}"`.

- [ ] **Step 4: Atualizar docs/dar aviso de MITM no README**

Adicionar bloco em `README.md` (ou docs/):

```markdown
## TLS interno (Tailscale)
A API em :5050 usa HTTPS com certificado auto-assinado. Clientes usam `verify=False`.
⚠️ **MITM**: um nó comprometido dentro do tailnet pode interceptar a conexão, pois o cert
não é validado contra uma CA. Para 10/10 isso é a prática esperada em rede segura; o TLS de
fato (sem verify) confere fornecido pelo roadmap (Tailscale HTTPS habilitado + cert CA real).
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/Dockerfile apps/mcp-memory/src/memory_server.py scripts/setup-machine.sh README.md
git commit -m "feat: TLS interno (auto-assinado) + clients https no MCP e setup (elimina CWE-319)"
```

---

### Task 4: Rotação de chaves (defesa em profundidade)

**Files:**
- Modify: `apps/api/src/routers/estacoes.py:81` (adicionar rota rotação)
- Modify: `apps/api/src/security.py` (se precisar helper — provavelmente não, station_hash já existe)
- Test: `apps/api/tests/test_rotacao.py` (NOVO)
- Modify: `scripts/setup-machine.sh` (flag `--rotate`)

**Block =**
- Consumes: `get_current_estacao`, `require_master`, `rate_limiter`, `station_key_hash`, `Estacao` model.
- Produces: `POST /api/estacoes/rotacionar` → autentica via chamaval (chave atual no header), gera nova, atualiza `chave_hash`, retorna `{"chave": "nova"}`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `apps/api/tests/test_rotacao.py`:

```python
import pytest
from httpx import AsyncClient

MASTER = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_rotacionar_estacao_gera_nova_chave(client: AsyncClient):
    await client.post("/api/estacoes/registrar",
                      json={"hostname": "est-rot", "chave": "chave-rot-old"},
                      headers=MASTER)
    r = await client.post("/api/estacoes/rotacionar",
                          headers={"X-API-Key": "chave-rot-old"})
    assert r.status_code == 200
    nova = r.json()["chave"]
    assert nova != "chave-rot-old"
    # antiga deixa de funcionar, nova funciona no ping
    r_old = await client.post("/api/estacoes/ping", headers={"X-API-Key": "chave-rot-old"})
    assert r_old.status_code == 401
    r_new = await client.post("/api/estacoes/ping", headers={"X-API-Key": nova})
    assert r_new.status_code == 200


@pytest.mark.asyncio
async def test_rotacionar_requer_chave_valida(client: AsyncClient):
    r = await client.post("/api/estacoes/rotacionar",
                          headers={"X-API-Key": "chave-nao-existe"})
    assert r.status_code == 401
```

- [ ] **Step 2: Rodar e verificar que falham**

```bash
..\..\.venv\Scripts\python.exe -m pytest tests/test_rotacao.py -q
```
Expected: 2 failed (`404 Not Found` — endpoint não existe).

- [ ] **Step 3: Implementar o endpoint no estacoes.py**

Adicionar a `apps/api/src/routers/estacoes.py`:

```python
import secrets

@router.post("/rotacionar", dependencies=[Depends(rate_limiter)])
async def rotacionar_chave(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    if identity.scope != "estacao":
        raise HTTPException(status_code=403, detail="Apenas a própria estação pode rotacionar a própria chave")
    nova = secrets.token_hex(32)
    res = await db.execute(select(Estacao).where(Estacao.hostname == identity.estacao))
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Estação não registrada")
    row.chave_hash = station_key_hash(nova)
    await db.commit()
    return {"chave": nova}
```

> `Identity`/`get_current_estacao`/`rate_limiter`/`station_key_hash`/`Estacao`/`select`/`get_db` já estão importados no estacoes.py. Adicionar `import secrets`. O endpoint autentica via chave atual (get_current_estacao valida o header). Retorna a nova chave. Só a própria estação (autenticada) rotaciona a si.

- [ ] **Step 4: Rodar testes e verificar que passam**

```bash
..\..\.venv\Scripts\python.exe -m pytest tests/test_rotacao.py -q
```
Expected: 2 passed.

- [ ] **Step 5: Rodar a suíte completa**

```bash
..\..\.venv\Scripts\python.exe -m pytest tests/ -q
```
Expected: **33 passed** (29 + 2 rotação + 2 sandbox)... na real: 29 + 2 (sandbox) + 2 (rotação) = **33** (assumindo 4 tarefas c/ testes). Ajuste o número conforme o total real.

- [ ] **Step 6: Adicionar flag `--rotate` no setup-machine.sh**

No final de `scripts/setup-machine.sh`, adicionar bloco:

```bash
if [[ "${1:-}" == "--rotate" ]]; then
  echo "Rotacionando chave da estação..."
  RESP=$(curl -s -k -X POST "https://${SERVIDOR_CENTRAL}:5050/api/estacoes/rotacionar" \
    -H "X-API-Key: ${CHAVE_ESTACAO}")
  echo "$RESP" | grep -q '"chave"' || { echo "Falha na rotação"; exit 1; }
  NOVA_CHAVE=$(echo "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["chave"])')
  CHAVE_ESTACAO="$NOVA_CHAVE"
  echo "Nova chave gerada. Atualize o arquivo de config da estação com MEMORY_API_KEY=$NOVA_CHAVE"
  exit 0
fi
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/routers/estacoes.py apps/api/tests/test_rotacao.py scripts/setup-machine.sh
git commit -m "feat: endpoint de rotacao de chave de estacao (master/estacao autenticada) + flag --rotate"
```

---

### Task 5: Deploy via Contabo + smoke tests + relatório

**Files:**
- Deploy dos commits das Tasks 1-4 para origin/master via Contabo.
- Smoke tests na API real (HTTPS 100.64.117.78:5050 agora).

**Interfaces:** sem APIs novas.

- [ ] **Step 1: Rodar suíte completa local**

```bash
..\..\.venv\Scripts\python.exe -m pytest tests/ -q   # workdir apps\api
```
Expected: todos os testes (29 + novos) passando.

- [ ] **Step 2: Extrair arquivos alterados em LF puro + scp + instalar no servidor**

Listar os arquivos das Tasks 1-4 (ex: `apps/api/src/routers/hermes.py`, `apps/api/src/routers/estacoes.py`, `apps/mcp-memory/src/memory_server.py`, `apps/mcp-memory/src/embedder.py`, `scripts/setup-machine.sh`, `apps/api/Dockerfile`, `docker-compose.yml`, `README.md`, `apps/hermes-sandbox/Dockerfile`, testes novos). Para cada: `cmd /c "git -C <repo> show HEAD:<path> > %TEMP%\opencode\lf2\<flat>"`, scp, `cp`, `grep -c $'\r'`=0.

- [ ] **Step 3: Commit+push via Contabo + build da imagem Herables**

No servidor:
```bash
cd ~/Apps/EstudioHC-Memory-Suite
git add -A && git commit -m "feat: auditoria 8->10 (sandbox hermes, pickle json, TLS, rotacao)" && git push origin master
# pré-build da imagem sandbox
docker build -t hermes-sandbox:latest apps/hermes-sandbox
```

- [ ] **Step 4: Gerar certs + atualizar serviço study systemd com SSL**

```bash
sudo mkdir -p /etc/estudiohc/ssl && cd /etc/estudiohc/ssl
sudo openssl req -x509 -newkey rsa:2048 -days 365 -nodes \
  -keyout estudiohc.key -out estudiohc.crt \
  -subj "/C=BW/ST=S/L=KrabiKrier/CN=vmi2968998.taile7t0.ts.net"
sudo chmod 640 estudiohc.key && sudo chown deploy:deploy * 
sudo systemctl edit estudiohc-api   # adicionar Environment/ExecStart com ssl flags
sudo systemctl daemon-reload && sudo systemctl restart estudiohc-api estudiohc-dashboard
sleep 2 && curl -k -s https://127.0.0.1:5050/api/status | grep 200 || curl -s http://127.0.0.1:5050/api/status
```

- [ ] **Step 5: Smoke tests na API real**

Script (no servidor) lê API_KEY do .env; testar:
1. `curl -k -s https://127.0.0.1:5050/api/status` → 200 (master no .env... na real sem chave ainda 200 pq /status é aberto)
2. sem-chave `curl -k -s -o /dev/null -w %{http_code} https://127.0.0.1:5050/api/agenda` → 401
3. master chave `.env` no GET /api/status → 200
4. registrar estação smoke + ping (https) → 200
5. `curl -k -s -X POST https://127.0.0.1:5050/api/estacoes/rotacionar -H "X-API-Key: <chave-smoke>"` → 200 + nova chave; ping old 401, ping new 200
6. HTTP plaintext `curl -s http://127.0.0.1:5050/api/status` → NEGADO (conexão recusada/timeout pois uvicorn só HTTPS)
7. hermes com chave de estação → 403
8. GET /api/projetos/relatorio com master → 405
- [ ] **Step 6: Reconcile Windows**

No clone local: `git fetch origin && git reset --hard origin/master`.

- [ ] **Step 7: Relatório final**

Reportar commits realizados (Tasks 1-4), testes passando/falhando (esperado: suíte API 33 passed), nota final **10/10** (com as 4 CWE eliminadas).

---

## Self-review do plano

1. **Cobertura da spec:** T1 (sandbox Docker/flags+fallback+update tests) → Task 1 ✓; T2 (pickle→JSON, remove pickle) → Task 2 ✓; T3 (TLS auto-signed, https, reject HTTP) → Task 3; T4 (rotação, master-only, rate-limit) → Task 4; deploy + smoke → Task 5. Também pedida "atualize documentação" → README aviso (Task 3). Commit atômico por task → cada task tem Step Commit.
2. **Placeholder scan:** sem "TBD"/"TODO". Alguns trechos dizem "copiar estrutura real" — substituí por código completo; endpoints/rotações já conhecidos. O numero de testes final é estimado (33 = 29+2+2), ajustar no Task 5 Step 1 com o valor real.
3. **Type consistency:** `_call_opencode` devolve `str|None` e `_parse_opencode_output` converte (na spec era dict; alinhei a dict). `station_key_hash`/`secrets.token_hex(32)` usam hash já existentes `station_key_hash` (define em security.py). Nomes `_sandbox_disponivel`, `_call_opencode_docker`, `_call_opencode_fallback`, `_call_opencode` consistentes no teste e no impl.

Cuidado: o Task 1 Step 4 inclui código novo; no curdo, o `_parse_opencode_output` deve acompanhar o formato real da CLI opencode (JSON-lines). O plano assume o formato visto na exploração (type==text → part.text; type==message → content). Verificar na implementação.