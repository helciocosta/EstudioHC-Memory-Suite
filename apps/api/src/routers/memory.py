import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agent_memory import AgentMemory
from ..schemas import MemoryEntry
from ..security import Identity, get_current_estacao

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/remember")
async def save_memory(
    entry: MemoryEntry,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    target_version = 1
    old_mem = None
    if entry.supersedes_id:
        old_stmt = select(AgentMemory).where(AgentMemory.id == entry.supersedes_id)
        old_res = await db.execute(old_stmt)
        old_mem = old_res.scalar_one_or_none()
        if old_mem:
            old_mem.status = "superseded"
            target_version = (old_mem.version or 1) + 1

    estacao_efetiva = (
        entry.estacao.strip()
        if (identity.scope == "master" and getattr(entry, "estacao", None) and entry.estacao.strip() not in ("", "desconhecida"))
        else identity.estacao
    )
    mem = AgentMemory(
        timestamp=datetime.now().isoformat(),
        agent_name=entry.agent_name.strip(),
        estacao=estacao_efetiva,
        project=entry.project.strip(),
        category=entry.category.strip(),
        content=entry.content,
        status="active",
        version=target_version,
    )
    db.add(mem)
    await db.flush()

    if old_mem:
        old_mem.superseded_by = mem.id

    await db.commit()
    return {"status": "success", "id": mem.id, "version": mem.version}


@router.get("/recall/{project}")
async def get_memory(
    project: str,
    limit: int = Query(10, ge=1, le=200),
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
    include_superseded: bool = False,
):
    query = select(AgentMemory).where(AgentMemory.project == project)
    if not (include_superseded is True):
        query = query.where(AgentMemory.status == "active")
    if identity.scope == "estacao":
        query = query.where(AgentMemory.estacao == identity.estacao)
    query = query.order_by(AgentMemory.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "agent_name": r.agent_name,
            "project": r.project,
            "category": r.category,
            "content": r.content,
            "estacao": r.estacao,
            "status": r.status,
            "version": r.version,
            "superseded_by": r.superseded_by,
        }
        for r in rows
    ]


def _readable(content: str) -> str:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and parsed.get("s"):
            return parsed["s"]
    except (json.JSONDecodeError, TypeError):
        pass
    return content


@router.get("/status/{project}")
async def get_status(
    project: str,
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    base = select(AgentMemory.content).where(AgentMemory.project == project)
    if identity.scope == "estacao":
        base = base.where(AgentMemory.estacao == identity.estacao)
    result_pending = await db.execute(
        base.where(AgentMemory.category == "task_pending").order_by(AgentMemory.timestamp.desc()).limit(5)
    )
    result_completed = await db.execute(
        base.where(AgentMemory.category == "task_completed").order_by(AgentMemory.timestamp.desc()).limit(3)
    )
    return {
        "project": project,
        "pending": [_readable(r[0]) for r in result_pending.fetchall()],
        "completed": [_readable(r[0]) for r in result_completed.fetchall()],
    }
