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

_sandbox_ok: bool | None = None


def _sandbox_disponivel() -> bool:
    """True se o Docker está disponível no PATH. Checado uma vez por processo."""
    global _sandbox_ok
    if _sandbox_ok is None:
        _sandbox_ok = bool(shutil.which("docker"))
    return _sandbox_ok


def _env_filtrado() -> dict:
    """Somente as variáveis mínimas necessárias — não vaza todo o os.environ."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    if os.environ.get("OPENROUTER_API_KEY"):
        env["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _kill_proc(proc) -> None:
    """Mata o processo e todos os filhos (kill no group)."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, AttributeError):
        pass


def _call_opencode_docker(prompt: str) -> str:
    """Executa opencode num container Docker efêmero e restrito."""
    cmd = [
        "docker", "run", "--rm", "--name", "hermes-sandbox-run",
        "--network", "none", "--read-only", "--tmpfs", "/tmp",
        "--tmpfs", "/home/sandbox", "--workdir", "/work", "--memory", "512m",
        SANDBOX_IMAGE, prompt,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=SANDBOX_TIMEOUT)
        return out
    except subprocess.TimeoutExpired:
        _kill_proc(proc)
        proc.wait()
        return ""
    except Exception:
        return ""


def _call_opencode_fallback(prompt: str) -> str | None:
    """Fallback sem Docker: opencode local com whitelist de tools (sem shell/exec)."""
    proc = None
    try:
        cmd = [OPENCODE_CLI, "run", "--tools", "read,write", "--format", "json", prompt]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=_env_filtrado(), start_new_session=True)
        out, _ = proc.communicate(timeout=SANDBOX_TIMEOUT)
        return out
    except subprocess.TimeoutExpired:
        if proc is not None:
            _kill_proc(proc)
        return None
    except Exception:
        return None


def _parse_opencode_output(raw: str) -> list:
    """Converte a saída JSON-lines de opencode num lista de textos."""
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


async def _call_opencode(prompt: str) -> dict | None:
    """Executa opencode (Docker isolado se disponível, senão fallback whitelist).
    Retorna {"resposta", "agente"} ou None."""
    if _sandbox_disponivel():
        raw = _call_opencode_docker(prompt)
    else:
        raw = _call_opencode_fallback(prompt)
    if not raw:
        return None
    textos = _parse_opencode_output(raw)
    if textos:
        return {"resposta": "\n".join(textos).strip(), "agente": "opencode"}
    return None


async def _call_hermes(prompt: str) -> dict:
    try:
        proc = subprocess.run([HERMES_CLI, "-z", prompt, "chat"],
                              capture_output=True, text=True,
                              timeout=settings.HERMES_TIMEOUT,
                              env=_env_filtrado())
        if proc.returncode != 0:
            return {"resposta": f"Erro Hermes CLI ({proc.returncode})", "agente": "hermes-error"}
        return {"resposta": proc.stdout.strip(), "agente": "hermes"}
    except subprocess.TimeoutExpired:
        return {"resposta": "Falha ao chamar Hermes: timeout", "agente": "hermes-failed"}
    except Exception:
        return {"resposta": "Falha ao chamar Hermes", "agente": "hermes-failed"}


@router.post("/hermes")
async def chat_ia(
    payload: ChatPayload,
    identity: Identity = Depends(require_master),
):
    prompt = payload.mensagem
    if payload.contexto:
        prompt = f"[Contexto EstudioHC: {payload.contexto}]\n\n{payload.mensagem}"

    result = await _call_opencode(prompt)
    if result:
        return result

    return await _call_hermes(prompt)