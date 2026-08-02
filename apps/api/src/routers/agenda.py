from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agenda import Agenda
from ..schemas import AgendaSavePayload
from ..security import Identity, get_current_estacao

router = APIRouter(prefix="/api/agenda", tags=["Agenda"])


@router.get("")
async def get_agenda(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Agenda).order_by(Agenda.data.asc(), Agenda.hora.asc())
    if identity.scope == "estacao":
        query = query.where(Agenda.estacao == identity.estacao)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "data": r.data,
            "hora": r.hora,
            "titulo": r.titulo,
            "estacao": r.estacao,
            "descricao": r.descricao,
        }
        for r in rows
    ]


@router.post("")
async def save_agenda(
    payload: AgendaSavePayload,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    processados = 0
    for ev in payload.eventos:
        estacao = identity.estacao if identity.scope == "estacao" else (ev.estacao or "central")
        existing = await db.execute(select(Agenda).where(Agenda.id == ev.id))
        row = existing.scalar_one_or_none()
        if identity.scope == "estacao" and row is not None and row.estacao != identity.estacao:
            raise HTTPException(status_code=403, detail="Evento pertence a outra estação")
        if row:
            row.data = ev.data
            row.hora = ev.hora
            row.titulo = ev.titulo
            row.estacao = estacao
            row.descricao = ev.descricao
            row.timestamp = datetime.now().isoformat()
        else:
            db.add(
                Agenda(
                    id=ev.id,
                    data=ev.data,
                    hora=ev.hora,
                    titulo=ev.titulo,
                    estacao=estacao,
                    descricao=ev.descricao,
                    timestamp=datetime.now().isoformat(),
                )
            )
        processados += 1
    await db.commit()
    return {"ok": True, "merge": processados}


@router.delete("/{evento_id}")
async def delete_evento(
    evento_id: str,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Agenda).where(Agenda.id == evento_id)
    if identity.scope == "estacao":
        query = query.where(Agenda.estacao == identity.estacao)
    existing = await db.execute(query)
    row = existing.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    await db.delete(row)
    await db.commit()
    return {"ok": True}
