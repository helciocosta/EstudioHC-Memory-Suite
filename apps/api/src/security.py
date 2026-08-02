import hashlib
import hmac
from time import monotonic
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models.estacoes import Estacao

_SALT = "estudiohc:"


def station_key_hash(chave: str) -> str:
    """Hash de chave de estação — sha256 com salt fixo. Suficiente pois a chave é
    um token aleatório de 256 bits (128 bits de entropia), não uma senha humana."""
    return hashlib.sha256((_SALT + chave).encode("utf-8")).hexdigest()


def require_api_key(x_api_key: str = Header(default="")):
    if not settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


_requests: dict[str, deque[float]] = defaultdict(deque)


async def rate_limiter(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = monotonic()
    dq = _requests[ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= settings.RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    dq.append(now)


@dataclass(frozen=True)
class Identity:
    estacao: str
    scope: str  # "master" | "estacao"


async def get_current_estacao(
    x_api_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> Identity:
    if settings.API_KEY and hmac.compare_digest(x_api_key, settings.API_KEY):
        return Identity(estacao="central", scope="master")
    if x_api_key:
        result = await db.execute(
            select(Estacao).where(Estacao.chave_hash == station_key_hash(x_api_key))
        )
        estacao = result.scalar_one_or_none()
        if estacao:
            return Identity(estacao=estacao.hostname, scope="estacao")
    raise HTTPException(status_code=401, detail="Invalid API key")


async def require_master(identity: Identity = Depends(get_current_estacao)) -> Identity:
    if identity.scope != "master":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return identity
