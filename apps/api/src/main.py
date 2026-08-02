from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import settings
from .database import get_db, init_db
from .schemas import MemoryEntry
from .security import require_api_key, rate_limiter
from .routers import memory, agenda, notas, projetos, estacoes, status, hermes, tarefas

description = """
EstudioHC Central API — Cérebro central do ecossistema EstudioHC.

Gerencia memória persistente de agentes, agenda, projetos, notas,
diários, tarefas e estações de trabalho via Tailscale.
"""

app = FastAPI(
    title=settings.APP_NAME,
    description=description,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "Helcio O. Costa",
        "url": "https://github.com/helciocosta",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _r in (memory, agenda, notas, projetos, estacoes, tarefas):
    app.include_router(_r.router, dependencies=[Depends(require_api_key)])
app.include_router(hermes.router, dependencies=[Depends(require_api_key), Depends(rate_limiter)])
app.include_router(status.router)  # status fica aberto (healthcheck)


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.post("/remember", dependencies=[Depends(require_api_key)])
async def remember_backward(entry: MemoryEntry, db=Depends(get_db)):
    return await memory.save_memory(entry, db)


@app.get("/recall/{project}", dependencies=[Depends(require_api_key)])
async def recall_backward(project: str, limit: int = 10, db=Depends(get_db)):
    return await memory.get_memory(project, limit, db)


@app.get("/status/{project}", dependencies=[Depends(require_api_key)])
async def status_backward(project: str, db=Depends(get_db)):
    return await memory.get_status(project, db)


dashboard_path = Path(settings.DASHBOARD_PATH)
if dashboard_path.exists():
    @app.get("/")
    async def get_dashboard_index():
        index_file = dashboard_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"error": "index.html not found"}

    app.mount("/", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")
