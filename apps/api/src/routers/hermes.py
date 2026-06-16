import os
import subprocess

from fastapi import APIRouter
from sqlalchemy import select

from ..config import settings
from ..schemas import ChatPayload
from ..database import get_db

router = APIRouter(prefix="/api", tags=["Hermes AI"])


@router.post("/hermes")
async def chat_hermes(payload: ChatPayload):
    prompt = payload.mensagem
    if payload.contexto:
        prompt = f"[Contexto EstudioHC: {payload.contexto}]\n\n{payload.mensagem}"
    try:
        resultado = subprocess.run(
            [settings.HERMES_CLI, "-z", prompt, "chat"],
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
        return {"resposta": f"Falha ao chamar Hermes no servidor: {e}", "agente": "hermes-failed"}