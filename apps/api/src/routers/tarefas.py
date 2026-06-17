from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.tarefas import Tarefa
from ..schemas import TarefaCreate, TarefaUpdate

router = APIRouter(prefix="/api/tarefas", tags=["Tarefas"])


@router.get("")
async def listar_tarefas(projeto_id: int | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Tarefa).order_by(Tarefa.prioridade.asc(), Tarefa.id.desc())
    if projeto_id is not None:
        query = query.where(Tarefa.projeto_id == projeto_id)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "projeto_id": r.projeto_id,
            "titulo": r.titulo,
            "status": r.status,
            "prioridade": r.prioridade,
            "data_limite": r.data_limite,
        }
        for r in rows
    ]


@router.post("")
async def criar_tarefa(payload: TarefaCreate, db: AsyncSession = Depends(get_db)):
    tarefa = Tarefa(
        projeto_id=payload.projeto_id,
        titulo=payload.titulo,
        status=payload.status,
        prioridade=payload.prioridade,
        data_limite=payload.data_limite,
    )
    db.add(tarefa)
    await db.commit()
    await db.refresh(tarefa)
    return {
        "id": tarefa.id,
        "projeto_id": tarefa.projeto_id,
        "titulo": tarefa.titulo,
        "status": tarefa.status,
        "prioridade": tarefa.prioridade,
        "data_limite": tarefa.data_limite,
    }


@router.put("/{tarefa_id}")
async def atualizar_tarefa(tarefa_id: int, payload: TarefaUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tarefa).where(Tarefa.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    if payload.titulo is not None:
        tarefa.titulo = payload.titulo
    if payload.status is not None:
        tarefa.status = payload.status
    if payload.prioridade is not None:
        tarefa.prioridade = payload.prioridade
    if payload.data_limite is not None:
        tarefa.data_limite = payload.data_limite
    await db.commit()
    await db.refresh(tarefa)
    return {
        "id": tarefa.id,
        "projeto_id": tarefa.projeto_id,
        "titulo": tarefa.titulo,
        "status": tarefa.status,
        "prioridade": tarefa.prioridade,
        "data_limite": tarefa.data_limite,
    }


@router.delete("/{tarefa_id}")
async def deletar_tarefa(tarefa_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tarefa).where(Tarefa.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    await db.delete(tarefa)
    await db.commit()
    return {"ok": True}