import os
import shutil
from datetime import datetime

from fastapi import APIRouter

from ..config import settings

router = APIRouter(prefix="/api", tags=["Status"])


@router.get("/status")
async def get_status():
    hermes_ok = os.path.exists(settings.HERMES_CLI) or shutil.which("hermes") is not None
    opencode_ok = shutil.which("opencode") is not None or os.path.exists("/home/deploy/.opencode/bin/opencode")
    return {
        "status": "online",
        "servidor": "central",
        "hermes": hermes_ok,
        "opencode": opencode_ok,
        "database": "SQLite",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/status_md")
async def get_status_md():
    paths = [
        os.path.expanduser("~/STATUS_ESTUDIOHC.md"),
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return {"conteudo": f.read()}
            except Exception as e:
                return {"erro": str(e)}
    return {"erro": "STATUS_ESTUDIOHC.md não encontrado nos locais padrão"}