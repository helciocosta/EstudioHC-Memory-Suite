from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.estacoes import Estacao
from ..schemas import EstacaoRegistro
from ..security import Identity, get_current_estacao, require_master, rate_limiter, station_key_hash

router = APIRouter(prefix="/api/estacoes", tags=["Estações"])


@router.post("/registrar", dependencies=[Depends(rate_limiter)])
async def registrar_estacao(
    payload: EstacaoRegistro,
    identity: Identity = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    chave_hash = station_key_hash(payload.chave)
    existing = await db.execute(select(Estacao).where(Estacao.hostname == payload.hostname))
    row = existing.scalar_one_or_none()
    if row and row.chave_hash and row.chave_hash != chave_hash:
        raise HTTPException(status_code=409, detail="hostname já registrado com outra chave")
    ts = datetime.now().isoformat()
    if row:
        row.chave_hash = chave_hash
    else:
        db.add(Estacao(hostname=payload.hostname, chave_hash=chave_hash, ultimo_ping=ts, status="offline"))
    await db.commit()
    return {"ok": True}


@router.post("/ping")
async def estacao_ping(
    request: Request,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    hostname = identity.estacao
    ip = request.client.host if request.client else "desconhecido"
    existing = await db.execute(select(Estacao).where(Estacao.hostname == hostname))
    row = existing.scalar_one_or_none()
    ts = datetime.now().isoformat()
    if row:
        row.ip_tailscale = ip
        row.ultimo_ping = ts
        row.status = "online"
    else:
        db.add(Estacao(hostname=hostname, ip_tailscale=ip, ultimo_ping=ts, status="online"))
    await db.commit()
    return {"ok": True}


@router.get("")
async def get_estacoes(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Estacao).order_by(Estacao.hostname.asc()))
    rows = result.scalars().all()
    if identity.scope == "master":
        return [
            {
                "hostname": r.hostname,
                "ip_tailscale": r.ip_tailscale,
                "ultimo_ping": r.ultimo_ping,
                "status": r.status,
            }
            for r in rows
        ]
    return [
        {
            "hostname": r.hostname,
            "ultimo_ping": r.ultimo_ping,
            "status": r.status,
        }
        for r in rows
        if r.hostname == identity.estacao
    ]
