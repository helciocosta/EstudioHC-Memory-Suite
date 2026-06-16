from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agent_memory import AgentMemory
from ..schemas import MemoryEntry

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/remember")
async def save_memory(entry: MemoryEntry, db: AsyncSession = Depends(get_db)):
    mem = AgentMemory(
        timestamp=datetime.now().isoformat(),
        agent_name=entry.agent_name,
        project=entry.project,
        category=entry.category,
        content=entry.content,
    )
    db.add(mem)
    await db.commit()
    return {"status": "success"}


@router.get("/recall/{project}")
async def get_memory(project: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.project == project)
        .order_by(AgentMemory.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "agent_name": r.agent_name,
            "project": r.project,
            "category": r.category,
            "content": r.content,
        }
        for r in rows
    ]


@router.get("/status/{project}")
async def get_status(project: str, db: AsyncSession = Depends(get_db)):
    result_pending = await db.execute(
        select(AgentMemory.content)
        .where(AgentMemory.project == project, AgentMemory.category == "task_pending")
        .order_by(AgentMemory.timestamp.desc())
        .limit(5)
    )
    result_completed = await db.execute(
        select(AgentMemory.content)
        .where(AgentMemory.project == project, AgentMemory.category == "task_completed")
        .order_by(AgentMemory.timestamp.desc())
        .limit(3)
    )
    return {
        "project": project,
        "pending": [r[0] for r in result_pending.fetchall()],
        "completed": [r[0] for r in result_completed.fetchall()],
    }