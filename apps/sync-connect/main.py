"""
EstudioHC Sync Connect — Bridge entre os 5 serviços do stack e a API central.
Coordena Logseq, Joplin, Vikunja, Ghost e MS To Do com a memória persistente.
"""
import asyncio, json, os, sys, httpx
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel

API_BASE = os.getenv("API_BASE", "https://127.0.0.1:5050")
API_KEY = os.getenv("API_KEY", "")
SSL_VERIFY = os.getenv("SSL_VERIFY", "false").lower() == "true"

app = FastAPI(title="Sync Connect — Secretário EstudioHC", version="1.0.0")

class DiarioEntry(BaseModel):
    data: str
    conteudo: str
    tags: list[str] = []

class NotaEntry(BaseModel):
    titulo: str
    conteudo: str
    origem: str = "sync-connect"

class TarefaEntry(BaseModel):
    titulo: str
    descricao: str = ""
    status: str = "pendente"
    projeto: str = "geral"

class AgendaEvento(BaseModel):
    titulo: str
    data_hora: str
    descricao: str = ""
    tipo: str = "lembrete"

class ProjetoSync(BaseModel):
    nome: str
    descricao: str = ""
    tarefas: list[TarefaEntry] = []

async def api_post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(verify=SSL_VERIFY) as client:
        r = await client.post(f"{API_BASE}{path}", json=data, headers={"X-API-Key": API_KEY})
        if r.status_code not in (200, 201):
            raise HTTPException(r.status_code, f"API error: {r.text}")
        return r.json()

# ─── Rotas para cada serviço ─────────────────────────────────

@app.post("/sync/logseq/diario")
async def sync_logseq_diario(entry: DiarioEntry):
    """Logseq → Diário na API central + ChromaDB"""
    return await api_post("/api/diarios", entry.model_dump())

@app.post("/sync/joplin/nota")
async def sync_joplin_nota(entry: NotaEntry):
    """Joplin → Nota na API central"""
    return await api_post("/api/nota", entry.model_dump())

@app.post("/sync/joplin/tarefa")
async def sync_joplin_tarefa(entry: TarefaEntry):
    """Joplin → Tarefa na API central"""
    return await api_post("/api/tarefas", entry.model_dump())

@app.post("/sync/vikunja/projeto")
async def sync_vikunja_projeto(entry: ProjetoSync):
    """Vikunja → Projeto + tarefas na API central"""
    return await api_post("/api/projetos/sync", entry.model_dump())

@app.post("/sync/ghost/relatorio")
async def sync_ghost_relatorio(entry: NotaEntry):
    """Ghost → Relatório de projeto"""
    return await api_post("/api/projetos/relatorio", entry.model_dump())

@app.post("/sync/todo/tarefa")
async def sync_microsoft_todo(entry: TarefaEntry):
    """MS To Do → Tarefa na API central"""
    return await api_post("/api/tarefas", entry.model_dump())

@app.post("/sync/agenda")
async def sync_agenda(entry: AgendaEvento):
    """Qualquer serviço → Agenda"""
    return await api_post("/api/agenda", entry.model_dump())

@app.get("/health")
async def health():
    return {"status": "ok", "service": "sync-connect", "api": API_BASE}
