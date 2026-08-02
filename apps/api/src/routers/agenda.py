from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agenda import Agenda
from ..schemas import AgendaSavePayload

router = APIRouter(prefix="/api/agenda", tags=["Agenda"])


@router.get("")
async def get_agenda(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Agenda).order_by(Agenda.data.asc(), Agenda.hora.asc())
    )
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
async def save_agenda(payload: AgendaSavePayload, db: AsyncSession = Depends(get_db)):
    processados = 0
    for ev in payload.eventos:
        existing = await db.execute(
            select(Agenda).where(Agenda.id == ev.id)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.data = ev.data
            row.hora = ev.hora
            row.titulo = ev.titulo
            row.estacao = ev.estacao
            row.descricao = ev.descricao
            row.timestamp = datetime.now().isoformat()
        else:
            db.add(
                Agenda(
                    id=ev.id,
                    data=ev.data,
                    hora=ev.hora,
                    titulo=ev.titulo,
                    estacao=ev.estacao,
                    descricao=ev.descricao,
                    timestamp=datetime.now().isoformat(),
                )
            )
        processados += 1
    await db.commit()
    return {"ok": True, "merge": processados}


@router.delete("/{evento_id}")
async def delete_evento(evento_id: str, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(Agenda).where(Agenda.id == evento_id)
    )
    if existing.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    await db.execute(delete(Agenda).where(Agenda.id == evento_id))
    await db.commit()
    return {"ok": True}