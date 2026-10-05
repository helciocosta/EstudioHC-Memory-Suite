#!/usr/bin/env python3
"""
EstudioHC Memory Sync - Bidirecional Local <-> Contabo
Sincroniza: projetos, agent_memory, tarefas, agenda, notas
"""
import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env  # noqa: F401,E402  — carrega o .env (MEMORY_API_KEY)

LOCAL_DB = Path.home() / "Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db"
CONTABO_HOST = "deploy@contabo"
CONTABO_API_DB = "~/Apps/EstudioHC-Memory-Suite/data/estudiohc.db"
CONTABO_DASHBOARD_URL = "http://localhost:8585/api/projetos/sync"

def run_ssh(cmd):
    return subprocess.run(["ssh", "-o", "ConnectTimeout=10", CONTABO_HOST, cmd], 
                         capture_output=True, text=True)

def run_scp(local, remote):
    return subprocess.run(["scp", local, f"{CONTABO_HOST}:{remote}"], 
                         capture_output=True, text=True)

def get_local_projects():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projetos WHERE estacao='helcio-x99-b'")
    return [dict(row) for row in cursor.fetchall()]

def get_contabo_projects():
    result = run_ssh(f"sqlite3 {CONTABO_API_DB} 'SELECT * FROM projetos WHERE estacao=\"helcio-x99-b\";'")
    rows = []
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split('|')
            if len(parts) >= 7:
                rows.append({
                    "id": parts[0], "nome": parts[1], "local_caminho": parts[2],
                    "status": parts[3], "tags": parts[4], "readme_preview": parts[5],
                    "estacao": parts[6], "ultima_atualizacao": parts[7] if len(parts) > 7 else ""
                })
    return rows

def sync_projects_push():
    """Push local projects to Contabo dashboard"""
    projects = get_local_projects()
    payload = {"projetos": projects}
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        local_path = f.name
    
    remote_path = "/tmp/sync_projects.json"
    run_scp(local_path, remote_path)
    result = run_ssh(f"curl -s -X POST {CONTABO_DASHBOARD_URL} -H 'Content-Type: application/json' -d @{remote_path}")
    print(f"Push projects: {result.stdout}")
    Path(local_path).unlink()

def sync_projects_pull():
    """Pull projects from Contabo API DB to local"""
    projects = get_contabo_projects()
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    for p in projects:
        cursor.execute("""
            INSERT OR REPLACE INTO projetos (id, nome, local_caminho, status, tags, readme_preview, estacao, ultima_atualizacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (p["id"], p["nome"], p["local_caminho"], p["status"], p["tags"], p["readme_preview"], p["estacao"], p["ultima_atualizacao"]))
    conn.commit()
    conn.close()
    print(f"Pulled {len(projects)} projects from Contabo")

def sync_agent_memory_push():
    """Push local agent_memory to Contabo API"""
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT agent_name, project, content, category 
        FROM agent_memory 
        WHERE project IN ('opencode', 'EstudioHC', 'EstudioHC-Memory-Suite', 'CGDOC')
        AND category IN ('task_completed', 'task_pending', 'decision', 'context', 'fact')
        ORDER BY id
    """)
    memories = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    API_KEY = os.environ.get("MEMORY_API_KEY", "")
    if not API_KEY:
        print("MEMORY_API_KEY não definida — abortando push")
        return
    for mem in memories:
        payload = {
            "agent_name": mem["agent_name"],
            "project": mem["project"],
            "content": mem["content"],
            "category": mem["category"]
        }
        result = subprocess.run([
            "curl", "-sk", "-X", "POST", "https://100.64.117.78:5050/memory/remember",
            "-H", "Content-Type: application/json",
            "-H", f"X-Api-Key: {API_KEY}",
            "-d", json.dumps(payload, ensure_ascii=False)
        ], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to push memory: {result.stderr}")

def full_sync(push=True, pull=True):
    print(f"=== EstudioHC Memory Sync {datetime.now().isoformat()} ===")
    if pull:
        print("Pulling projects from Contabo...")
        sync_projects_pull()
    if push:
        print("Pushing projects to Contabo...")
        sync_projects_push()
        print("Pushing agent_memory to Contabo...")
        sync_agent_memory_push()
    print("=== Sync Complete ===")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push-only", action="store_true")
    parser.add_argument("--pull-only", action="store_true")
    parser.add_argument("--projects-only", action="store_true")
    args = parser.parse_args()
    
    if args.push_only:
        full_sync(push=True, pull=False)
    elif args.pull_only:
        full_sync(push=False, pull=True)
    elif args.projects_only:
        if not args.push_only:
            sync_projects_pull()
        if not args.pull_only:
            sync_projects_push()
    else:
        full_sync()

