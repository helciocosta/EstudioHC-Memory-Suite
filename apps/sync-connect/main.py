"""
EstudioHC Sync Connect — Bridge entre os serviços externos do stack e a API central.
Mapeia as entradas dos serviços (Logseq, Joplin, Vikunja, Ghost, MS To Do, Agenda)
para os schemas reais da API central (apps/api).
Fase 1 de produção: corrige rota/schema de cada integrador para a API real.
"""
import os
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

API_BASE = os.getenv("API_BASE", "https://127.0.0.1:5050")
API_KEY = os.getenv("API_KEY", "")
SSL_VERIFY = os.getenv("SSL_VERIFY", "false").lower() == "true"

app = FastAPI(title="Sync Connect — Secretário EstudioHC", version="1.1.0")

# ─── Schemas de entrada (o que os serviços externos enviam) ───────────────

class DiarioEntry(BaseModel):
    data: str
    conteudo: str
    tags: list[str] = []

class NotaEntry(BaseModel):
    titulo: str = ""
    conteudo: str = ""
    origem: str = "sync-connect"

class TarefaEntry(BaseModel):
    titulo: str
    descricao: str = ""
    status: str = "pendente"
    projeto: str = "geral"
    projeto_id: Optional[int] = None

class AgendaEvento(BaseModel):
    titulo: str
    data_hora: str
    descricao: str = ""
    tipo: str = "lembrete"

class ProjetoSync(BaseModel):
    nome: str
    descricao: str = ""
    tarefas: list[TarefaEntry] = []


# ─── Client para a API central ──────────────────────────────────────────

async def api_call(method: str, path: str, data: dict) -> dict:
    if not API_KEY:
        raise HTTPException(500, "API_KEY não configurada para o sync-connect")
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=timeout) as client:
        r = await client.request(
            method, f"{API_BASE}{path}", json=data,
            headers={"X-API-Key": API_KEY},
        )
        if r.status_code not in (200, 201):
            raise HTTPException(r.status_code, f"API error: {r.text}")
        return r.json()


async def api_get(path: str) -> list:
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(verify=SSL_VERIFY, timeout=timeout) as client:
        r = await client.get(f"{API_BASE}{path}", headers={"X-API-Key": API_KEY})
        r.raise_for_status()
        return r.json()


# ── Rotas de integração ─────────────────────────────────────────────────

@app.post("/sync/logseq/diario")
async def sync_logseq_diario(entry: DiarioEntry):
    """Logseq → Nota na API central (POST /api/nota)."""
    payload = {"texto": entry.conteudo, "estacao": "logseq"}
    return await api_call("POST", "/api/nota", payload)


@app.post("/sync/joplin/nota")
async def sync_joplin_nota(entry: NotaEntry):
    """Joplin → Nota na API central (POST /api/nota requer {texto})."""
    texto = f"{entry.titulo}: {entry.conteudo}" if entry.titulo else entry.conteudo
    payload = {"texto": texto, "estacao": "joplin"}
    return await api_call("POST", "/api/nota", payload)


@app.post("/sync/joplin/tarefa")
async def sync_joplin_tarefa(entry: TarefaEntry):
    """Joplin → Tarefa. API exige projeto_id (int); resolvido em _criar_tarefa."""
    return await _criar_tarefa(entry)


@app.post("/sync/vikunja/projeto")
async def sync_vikunja_projeto(entry: ProjetoSync):
    """Vikunja → Projeto na API central (POST /api/projetos/sync)."""
    payload = {
        "projetos": [
            {"nome": entry.nome, "local_caminho": "", "status": "ativo",
             "tags": "vikunja", "readme_preview": entry.descricao}
        ]
    }
    return await api_call("POST", "/api/projetos/sync", payload)


@app.post("/sync/ghost/relatorio")
async def sync_ghost_relatorio(entry: NotaEntry):
    """Ghost → Relatório persistido como nota na API central (não-blockante;
    evita a rota /gerar-relatorio que dispara geração de IA e pode travar)."""
    texto = f"[ghost/{entry.titulo}] {entry.conteudo}"
    return await api_call("POST", "/api/nota", {"texto": texto, "estacao": "ghost"})


@app.post("/sync/todo/tarefa")
async def sync_microsoft_todo(entry: TarefaEntry):
    """MS To Do → Tarefa."""
    return await _criar_tarefa(entry)


@app.post("/sync/agenda")
async def sync_agenda(entry: AgendaEvento):
    """Qualquer serviço → Agenda. API espera {eventos:[...]}."""
    _d, hora = _split_data_hora(entry.data_hora)
    evento = {
        "id": f"sync_{entry.titulo}_{_d}",
        "data": _d, "hora": hora, "titulo": entry.titulo,
        "estacao": "sync-connect", "descricao": entry.descricao,
    }
    return await api_call("POST", "/api/agenda", {"eventos": [evento]})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sync-connect", "api": API_BASE}


# ── Helpers de tarefa (a API exige projeto_id) ──────────────────────────

async def _criar_tarefa(entry: TarefaEntry) -> dict:
    pid = entry.projeto_id or await _resolver_projeto(entry.projeto)
    payload = {
        "projeto_id": pid,
        "titulo": entry.titulo,
        "status": entry.status,
        "prioridade": "media",
        "data_limite": None,
    }
    return await api_call("POST", "/api/tarefas", payload)


async def _resolver_projeto(nome: str) -> int:
    """Resolve o id do projeto pelo nome; cria 'geral' se ausente."""
    nome = nome.strip().lower() or "geral"
    try:
        projetos = await api_get("/api/projetos")
        for p in projetos:
            if isinstance(p, dict) and str(p.get("nome", "")).lower() == nome:
                return int(p["id"])
    except Exception:
        pass
    # cria o projeto se não existir
    await api_call("POST", "/api/projetos/sync", {
        "projetos": [{"nome": nome, "local_caminho": "", "status": "ativo",
                      "tags": "sync", "readme_preview": ""}]
    })
    projetos = await api_get("/api/projetos")
    for p in projetos:
        if isinstance(p, dict) and str(p.get("nome", "")).lower() == nome:
            return int(p["id"])
    raise HTTPException(500, f"Não foi possível criar/resolver o projeto '{nome}'")


def _split_data_hora(data_hora: str) -> tuple[str, str]:
    try:
        if "T" in data_hora:
            d, h = data_hora.replace("Z", "").split("T")
        elif " " in data_hora:
            d, h = data_hora.split(" ")
        else:
            d, h = data_hora[:10], "00:00"
        return d, (h[:5] if h else "00:00")
    except Exception:
        return data_hora[:10], "00:00"