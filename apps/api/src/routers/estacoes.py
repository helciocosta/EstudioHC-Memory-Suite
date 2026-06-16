from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.estacoes import Estacao
from ..schemas import EstacaoPing

router = APIRouter(prefix="/api/estacoes", tags=["Estações"])


@router.post("/ping")
async def estacao_ping(
    hostname: str = None,
    ip: str = "desconhecido",
    payload: EstacaoPing = None,
    db: AsyncSession = Depends(get_db),
):
    if payload:
        hostname = payload.hostname
        ip = payload.ip
    if not hostname:
        raise HTTPException(status_code=400, detail="hostname is required")
    existing = await db.execute(select(Estacao).where(Estacao.hostname == hostname))
    row = existing.scalar_one_or_none()
    ts = datetime.now().isoformat()
    if row:
        row.ip_tailscale = payload.ip
        row.ultimo_ping = ts
        row.status = "online"
    else:
        db.add(Estacao(hostname=payload.hostname, ip_tailscale=payload.ip, ultimo_ping=ts, status="online"))
    await db.commit()
    return {"ok": True}


@router.get("")
async def get_estacoes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Estacao).order_by(Estacao.hostname.asc()))
    rows = result.scalars().all()
    return [
        {
            "hostname": r.hostname,
            "ip_tailscale": r.ip_tailscale,
            "ultimo_ping": r.ultimo_ping,
            "status": r.status,
        }
        for r in rows
    ]