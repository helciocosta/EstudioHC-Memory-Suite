from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.notas import Nota
from ..models.resumos_diarios import ResumoDiario
from ..schemas import NotaEntry, ResumoPayload
from ..security import Identity, get_current_estacao

router = APIRouter(prefix="/api", tags=["Notas / Diários"])


@router.get("/diarios")
async def get_diarios(
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            func.substr(Nota.timestamp, 1, 10).label("data_dia"),
            func.sum(func.length(Nota.texto)).label("tamanho"),
        )
        .group_by(func.substr(Nota.timestamp, 1, 10))
        .order_by(func.substr(Nota.timestamp, 1, 10).desc())
    )
    if identity.scope == "estacao":
        query = query.where(Nota.estacao == identity.estacao)
    result = await db.execute(query)
    diarios = [{"data": r[0], "tamanho": r[1] or 0} for r in result.fetchall()]

    hoje = datetime.now().strftime("%Y-%m-%d")
    if not any(x["data"] == hoje for x in diarios):
        diarios.insert(0, {"data": hoje, "tamanho": 0})
    return diarios


@router.get("/diario/{data}")
async def get_diario(
    data: str,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Nota).where(func.substr(Nota.timestamp, 1, 10) == data)
    if identity.scope == "estacao":
        query = query.where(Nota.estacao == identity.estacao)
    query = query.order_by(Nota.timestamp.asc())
    result = await db.execute(query)
    rows = result.scalars().all()

    result_res = await db.execute(
        select(ResumoDiario).where(ResumoDiario.data == data)
    )
    resumo_row = result_res.scalar_one_or_none()

    conteudo = f"# Diário — {data}\n\n"
    if not rows:
        conteudo += "*(Nenhuma nota registrada para este dia)*\n"
    else:
        for r in rows:
            hora = r.timestamp[11:16] if len(r.timestamp) >= 16 else "00:00"
            conteudo += f"## {hora} ({r.estacao})\n{r.texto}\n\n"

    return {
        "data": data,
        "conteudo": conteudo,
        "resumo": resumo_row.resumo if resumo_row else None,
        "agente": resumo_row.agente if resumo_row else None,
    }


@router.post("/diario/{data}/resumo")
async def save_diario_resumo(data: str, payload: ResumoPayload, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(ResumoDiario).where(ResumoDiario.data == data))
    row = existing.scalar_one_or_none()
    if row:
        row.resumo = payload.resumo
        row.agente = payload.agente
        row.timestamp = datetime.now().isoformat()
    else:
        db.add(
            ResumoDiario(
                data=data,
                resumo=payload.resumo,
                agente=payload.agente,
                timestamp=datetime.now().isoformat(),
            )
        )
    await db.commit()
    return {"status": "success"}


@router.post("/nota")
async def save_nota(
    payload: NotaEntry,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    nota = Nota(
        estacao=identity.estacao,
        texto=payload.texto,
        timestamp=datetime.now().isoformat(),
    )
    db.add(nota)
    await db.commit()
    return {"ok": True}