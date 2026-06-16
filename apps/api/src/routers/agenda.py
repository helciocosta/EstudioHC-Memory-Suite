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
    await db.execute(delete(Agenda))
    for ev in payload.eventos:
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
    await db.commit()
    return {"ok": True}