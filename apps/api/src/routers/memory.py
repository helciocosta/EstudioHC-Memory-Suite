import json
from datetime import datetime

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
    mem = AgentMemory(
        timestamp=datetime.now().isoformat(),
        agent_name=entry.agent_name.strip(),
        estacao=identity.estacao,
        project=entry.project.strip(),
        category=entry.category.strip(),
        content=entry.content,
    )
    db.add(mem)
    await db.commit()
    return {"status": "success", "id": mem.id}


@router.get("/recall/{project}")
async def get_memory(
    project: str,
    limit: int = Query(10, ge=1, le=200),
    identity: Identity = Depends(get_current_estacao),
    db: AsyncSession = Depends(get_db),
):
    query = select(AgentMemory).where(AgentMemory.project == project)
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
