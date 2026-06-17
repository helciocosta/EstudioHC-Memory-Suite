import os
import json
import subprocess

from fastapi import APIRouter

from ..config import settings
from ..schemas import ChatPayload

router = APIRouter(prefix="/api", tags=["Chat IA"])

OPENCODE_CLI = "/home/deploy/.opencode/bin/opencode"
HERMES_CLI = settings.HERMES_CLI


async def _call_opencode(prompt: str) -> dict | None:
    try:
        resultado = subprocess.run(
            [OPENCODE_CLI, "run", "--format", "json", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        saida = resultado.stdout.strip()
        if not saida:
            return None

        texts = []
        for line in saida.splitlines():
            try:
                event = json.loads(line)
                if event.get("type") == "text":
                    text = event.get("part", {}).get("text", "")
                    if text:
                        texts.append(text)
                elif event.get("type") == "message":
                    content = event.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        for c in content:
                            if c.get("type") == "text":
                                texts.append(c.get("text", ""))
                    elif content:
                        texts.append(content)
            except json.JSONDecodeError:
                continue

        if texts:
            return {"resposta": "\n".join(texts).strip(), "agente": "opencode"}
        return None
    except Exception:
        return None


async def _call_hermes(prompt: str) -> dict:
    try:
        resultado = subprocess.run(
            [HERMES_CLI, "-z", prompt, "chat"],
            capture_output=True,
            text=True,
            timeout=settings.HERMES_TIMEOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        saida = resultado.stdout.strip()
        erro = resultado.stderr.strip() if resultado.stderr else ""
        if resultado.returncode != 0:
            return {"resposta": f"Erro Hermes CLI ({resultado.returncode}): {erro}", "agente": "hermes-error"}
        return {"resposta": saida, "agente": "hermes"}
    except Exception as e:
        return {"resposta": f"Falha ao chamar Hermes: {e}", "agente": "hermes-failed"}


@router.post("/hermes")
async def chat_ia(payload: ChatPayload):
    prompt = payload.mensagem
    if payload.contexto:
        prompt = f"[Contexto EstudioHC: {payload.contexto}]\n\n{payload.mensagem}"

    result = await _call_opencode(prompt)
    if result:
        return result

    return await _call_hermes(prompt)