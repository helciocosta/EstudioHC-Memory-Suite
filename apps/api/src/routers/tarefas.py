from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.projetos import Projeto
from ..models.tarefas import Tarefa
from ..schemas import TarefaCreate, TarefaUpdate
from ..security import Identity, get_current_estacao

router = APIRouter(prefix="/api/tarefas", tags=["Tarefas"])


async def _projeto_da_estacao(db, projeto_id: int, identity: Identity):
    result = await db.execute(select(Projeto).where(Projeto.id == projeto_id))
    projeto = result.scalar_one_or_none()
    if projeto is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if identity.scope == "estacao" and projeto.estacao != identity.estacao:
        raise HTTPException(status_code=403, detail="Projeto pertence a outra estação")
    return projeto


@router.get("")
async def listar_tarefas(
    projeto_id: int | None = None,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(Tarefa).join(Projeto, Tarefa.projeto_id == Projeto.id)
    if identity.scope == "estacao":
        query = query.where(Projeto.estacao == identity.estacao)
    if projeto_id is not None:
        query = query.where(Tarefa.projeto_id == projeto_id)
    query = query.order_by(Tarefa.prioridade.asc(), Tarefa.id.desc())
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
async def criar_tarefa(
    payload: TarefaCreate,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    await _projeto_da_estacao(db, payload.projeto_id, identity)
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
async def atualizar_tarefa(
    tarefa_id: int,
    payload: TarefaUpdate,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tarefa).where(Tarefa.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    await _projeto_da_estacao(db, tarefa.projeto_id, identity)
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
async def deletar_tarefa(
    tarefa_id: int,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tarefa).where(Tarefa.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    await _projeto_da_estacao(db, tarefa.projeto_id, identity)
    await db.delete(tarefa)
    await db.commit()
    return {"ok": True}
