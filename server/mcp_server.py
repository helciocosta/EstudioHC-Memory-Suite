import sqlite3
import os
import subprocess
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

app = FastAPI(title="EstudioHC Central Hub API & Memory Suite")

# Permitir CORS de qualquer origem para que todas as estações locais acessem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Caminhos adaptáveis para PC e Servidor
DB_PATH = os.path.expanduser("~/Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db")
DASHBOARD_PATH = os.path.expanduser("~/Apps/EstudioHC-Memory-Suite/dashboard")
HERMES_CLI = os.path.expanduser("~/.local/bin/hermes")

# Modelos REST Pydantic
class MemoryEntry(BaseModel):
    agent_name: str
    project: str
    content: str
    category: str = "task"

class AgendaEntry(BaseModel):
    id: str
    data: str
    hora: str
    titulo: str
    estacao: Optional[str] = "central"
    descricao: Optional[str] = ""

class AgendaSavePayload(BaseModel):
    eventos: List[AgendaEntry]

class NotaEntry(BaseModel):
    texto: str
    estacao: Optional[str] = "desconhecida"

class ProjetoEntry(BaseModel):
    nome: str
    local_caminho: str
    status: Optional[str] = "ativo"
    tags: Optional[str] = ""
    readme_preview: Optional[str] = ""

class ProjetosSyncPayload(BaseModel):
    projetos: List[ProjetoEntry]

class ChatPayload(BaseModel):
    mensagem: str
    contexto: Optional[str] = ""

# Inicialização de Banco de Dados com novas tabelas
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Tabela original do MCP de Memória
    cursor.execute('''CREATE TABLE IF NOT EXISTS agent_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        agent_name TEXT,
                        project TEXT,
                        category TEXT,
                        content TEXT
                    )''')
                    
    # 2. Tabela de Agenda
    cursor.execute('''CREATE TABLE IF NOT EXISTS agenda (
                        id TEXT PRIMARY KEY,
                        data TEXT,
                        hora TEXT,
                        titulo TEXT,
                        estacao TEXT,
                        descricao TEXT,
                        timestamp TEXT
                    )''')
                    
    # 3. Tabela de Projetos
    cursor.execute('''CREATE TABLE IF NOT EXISTS projetos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT UNIQUE,
                        local_caminho TEXT,
                        status TEXT,
                        tags TEXT,
                        readme_preview TEXT,
                        ultima_atualizacao TEXT
                    )''')
                    
    # 4. Tabela de Tarefas
    cursor.execute('''CREATE TABLE IF NOT EXISTS tarefas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        projeto_id INTEGER,
                        titulo TEXT,
                        status TEXT DEFAULT 'pendente',
                        prioridade TEXT DEFAULT 'media',
                        data_limite TEXT
                    )''')
                    
    # 5. Tabela de Notas (Diário de Trabalho Centralizado)
    cursor.execute('''CREATE TABLE IF NOT EXISTS notas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        estacao TEXT,
                        texto TEXT,
                        timestamp TEXT
                    )''')
                    
    # 6. Tabela de Estações
    cursor.execute('''CREATE TABLE IF NOT EXISTS estacoes (
                        hostname TEXT PRIMARY KEY,
                        ip_tailscale TEXT,
                        ultimo_ping TEXT,
                        status TEXT
                    )''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

# ── 1. Endpoints Originais do MCP de Memória ────────────────────

@app.post("/remember")
async def save_memory(entry: MemoryEntry):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO agent_memory (timestamp, agent_name, project, category, content) VALUES (?, ?, ?, ?, ?)",
                       (datetime.now().isoformat(), entry.agent_name, entry.project, entry.category, entry.content))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recall/{project}")
async def get_memory(project: str, limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_memory WHERE project = ? ORDER BY timestamp DESC LIMIT ?", (project, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/status/{project}")
async def get_status(project: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT content FROM agent_memory WHERE project = ? AND category = 'task_pending' ORDER BY timestamp DESC LIMIT 5", (project,))
    pending = [row['content'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT content FROM agent_memory WHERE project = ? AND category = 'task_completed' ORDER BY timestamp DESC LIMIT 3", (project,))
    completed = [row['content'] for row in cursor.fetchall()]
    
    conn.close()
    return {
        "project": project,
        "pending": pending,
        "completed": completed
    }

# ── 2. Novos Endpoints do Hub Central (Agenda, Diários, Projetos, Estações) ──

# --- AGENDA ---
@app.get("/api/agenda")
async def get_agenda_api():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, data, hora, titulo, estacao, descricao FROM agenda ORDER BY data ASC, hora ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agenda")
async def save_agenda_api(payload: AgendaSavePayload):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agenda")
        for ev in payload.eventos:
            cursor.execute("INSERT OR REPLACE INTO agenda (id, data, hora, titulo, estacao, descricao, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (ev.id, ev.data, ev.hora, ev.titulo, ev.estacao, ev.descricao, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- DIÁRIOS & NOTAS ---
@app.get("/api/diarios")
async def get_diarios_api():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT SUBSTR(timestamp, 1, 10) as data_dia FROM notas ORDER BY data_dia DESC")
        datas = [row[0] for row in cursor.fetchall()]
        
        diarios = []
        for d in datas:
            cursor.execute("SELECT SUM(LENGTH(texto)) FROM notas WHERE SUBSTR(timestamp, 1, 10) = ?", (d,))
            tamanho = cursor.fetchone()[0] or 0
            diarios.append({
                "data": d,
                "tamanho": tamanho
            })
        conn.close()
        
        hoje = datetime.now().strftime("%Y-%m-%d")
        if not any(x["data"] == hoje for x in diarios):
            diarios.insert(0, {"data": hoje, "tamanho": 0})
            
        return diarios
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/diario/{data}")
async def get_diario_api(data: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, estacao, texto FROM notas WHERE SUBSTR(timestamp, 1, 10) = ? ORDER BY timestamp ASC", (data,))
        rows = cursor.fetchall()
        conn.close()
        
        conteudo = f"# Diário — {data}\n\n"
        if not rows:
            conteudo += "*(Nenhuma nota registrada para este dia)*\n"
        else:
            for timestamp, estacao, texto in rows:
                hora = timestamp[11:16] if len(timestamp) >= 16 else "00:00"
                conteudo += f"## {hora} ({estacao})\n{texto}\n\n"
                
        return {"data": data, "conteudo": conteudo}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/nota")
async def save_nota_api(payload: NotaEntry):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        ts = datetime.now().isoformat()
        cursor.execute("INSERT INTO notas (estacao, texto, timestamp) VALUES (?, ?, ?)",
                       (payload.estacao, payload.texto, ts))
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- PROJETOS ---
@app.get("/api/projetos")
async def get_projetos_api():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT nome, local_caminho as local, readme_preview as preview, status, tags FROM projetos ORDER BY nome ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projetos/sync")
async def sync_projetos_api(payload: ProjetosSyncPayload):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for p in payload.projetos:
            cursor.execute("""
                INSERT INTO projetos (nome, local_caminho, status, tags, readme_preview, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(nome) DO UPDATE SET
                    local_caminho = excluded.local_caminho,
                    readme_preview = excluded.readme_preview,
                    ultima_atualizacao = excluded.ultima_atualizacao
            """, (p.nome, p.local_caminho, p.status, p.tags, p.readme_preview, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return {"ok": True, "count": len(payload.projetos)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ESTAÇÕES ---
@app.post("/api/estacoes/ping")
async def estacao_ping(hostname: str, ip: str = "desconhecido"):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        ts = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO estacoes (hostname, ip_tailscale, ultimo_ping, status)
            VALUES (?, ?, ?, 'online')
            ON CONFLICT(hostname) DO UPDATE SET
                ip_tailscale = excluded.ip_tailscale,
                ultimo_ping = excluded.ultimo_ping,
                status = 'online'
        """, (hostname, ip, ts))
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/estacoes")
async def get_estacoes_api():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT hostname, ip_tailscale, ultimo_ping, status FROM estacoes ORDER BY hostname ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- IA CHAT (HERMES) ---
@app.post("/api/hermes")
async def chat_hermes(payload: ChatPayload):
    prompt = payload.mensagem
    if payload.contexto:
        prompt = f"[Contexto EstudioHC: {payload.contexto}]\n\n{payload.mensagem}"
    try:
        resultado = subprocess.run(
            [HERMES_CLI, "-z", prompt, "chat"],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        saida = resultado.stdout.strip()
        erro = resultado.stderr.strip() if resultado.stderr else ""
        if resultado.returncode != 0:
            return {"resposta": f"Erro Hermes CLI ({resultado.returncode}): {erro}", "agente": "hermes-error"}
        return {"resposta": saida, "agente": "hermes"}
    except Exception as e:
        return {"resposta": f"Falha ao chamar Hermes no servidor: {e}", "agente": "hermes-failed"}

# --- STATUS ---
@app.get("/api/status")
async def get_status_api():
    hermes_ok = os.path.exists(HERMES_CLI) or shutil.which("hermes") is not None
    return {
        "status": "online",
        "servidor": "central",
        "hermes": hermes_ok,
        "database": "SQLite",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status_md")
async def get_status_md():
    for p in ["/home/deploy/STATUS_ESTUDIOHC.md", os.path.expanduser("~/STATUS_ESTUDIOHC.md")]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return {"conteudo": f.read()}
            except Exception as e:
                return {"erro": str(e)}
    return {"erro": "STATUS_ESTUDIOHC.md não encontrado nos locais padrão"}

# ── 3. Servidor de Arquivos Estáticos do Dashboard (Fim do Arquivo) ──

if os.path.exists(DASHBOARD_PATH):
    @app.get("/")
    async def get_dashboard_index():
        index_file = os.path.join(DASHBOARD_PATH, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": f"index.html not found in dashboard path {DASHBOARD_PATH}"}
        
    app.mount("/", StaticFiles(directory=DASHBOARD_PATH), name="dashboard")
