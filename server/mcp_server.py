import sqlite3
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import List

app = FastAPI(title="EstudioHC Memory Hub (MCP)")

# Caminho ajustado para seu Linux Mint
DB_PATH = "/home/helcio/Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db"

class MemoryEntry(BaseModel):
    agent_name: str
    project: str
    content: str
    category: str = "task"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS agent_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        agent_name TEXT,
                        project TEXT,
                        category TEXT,
                        content TEXT
                    )''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

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
    
    # Busca tarefas pendentes e concluídas separadamente
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
