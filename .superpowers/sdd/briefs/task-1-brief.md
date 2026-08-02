### Task 1: API `/remember` retorna `id` (raiz do bug FAISS)

**Files:**
- Modify: `apps/api/src/routers/memory.py:14-25`
- Test: `apps/api/tests/test_memory.py` (create)

**Interfaces:**
- Consumes: `AgentMemory` model, `MemoryEntry` schema, `get_db` (all exist).
- Produces: `save_memory()` returns `{"status": "success", "id": int}` - the persisted row id. `get_status()` returns readable text (summaries), not raw JSON.

**IMPORTANTE (encoding):** Use apenas ASCII sem acentos nos literais de teste (ex.: "Tarefa pendente legivel", sem cedilha/acentos). A string usada no POST deve ser EXATAMENTE igual a esperada no assert.

- [ ] **Step 1: Escrever o teste que falha**

```python
# apps/api/tests/test_memory.py
import json
from httpx import AsyncClient


async def test_remember_returns_id(client: AsyncClient):
    resp = await client.post("/remember", json={
        "agent_name": "opencode",
        "project": "opencode",
        "category": "context",
        "content": json.dumps({"s": "fato X", "r": None, "c": True}),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert isinstance(body["id"], int)
    assert body["id"] > 0


async def test_status_returns_readable_text(client: AsyncClient):
    await client.post("/remember", json={
        "agent_name": "opencode",
        "project": "opencode",
        "category": "task_pending",
        "content": json.dumps({"s": "Tarefa pendente legivel", "r": None, "c": True}),
    })
    resp = await client.get("/status/opencode")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending"] == ["Tarefa pendente legivel"]
```

- [ ] **Step 2: Rodar e confirmar falha**

Run (na pasta `apps/api`): `python -m pytest tests/test_memory.py -v`
Expected: FAIL - `body["id"]` ausente (KeyError) e `body["pending"]` contem o JSON bruto `{"s": "Tarefa pendente..."}`.

- [ ] **Step 3: Implementar o fix**

```python
# apps/api/src/routers/memory.py - save_memory
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
    return {"status": "success", "id": mem.id}
```

```python
# apps/api/src/routers/memory.py - get_status (extrair texto legivel)
import json

def _readable(content: str) -> str:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and parsed.get("s"):
            return parsed["s"]
    except (json.JSONDecodeError, TypeError):
        pass
    return content

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
        "pending": [_readable(r[0]) for r in result_pending.fetchall()],
        "completed": [_readable(r[0]) for r in result_completed.fetchall()],
    }
```

- [ ] **Step 4: Rodar e confirmar passagem**

Run: `python -m pytest tests/test_memory.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/routers/memory.py apps/api/tests/test_memory.py
git commit -m "fix(api): return memory id from /remember and readable status text"
```
