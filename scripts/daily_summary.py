#!/usr/bin/env python3
"""
EstudioHC Daily Summary Generator
Uses local LLM (KoboldCpp) to generate daily summary from memory
"""
import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path.home() / "Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db"
KOBOLD_URL = "http://localhost:11434/v1/chat/completions"
KOBOLD_MODEL = "cybersec-assistant-3b"

def get_daily_data(date_str: str = None) -> dict:
    """Collect all data for the given date."""
    if date_str is None:
        date_str = datetime.now().date().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    data = {"date": date_str}
    
    # Agent memory for today
    cursor.execute("""
        SELECT agent_name, project, category, content, timestamp
        FROM agent_memory
        WHERE date(timestamp) = ?
        ORDER BY timestamp
    """, (date_str,))
    data["agent_memory"] = [dict(r) for r in cursor.fetchall()]
    
    # Tasks completed today
    cursor.execute("""
        SELECT t.titulo, p.nome as projeto, t.status, t.prioridade
        FROM tarefas t
        JOIN projetos p ON t.projeto_id = p.id
        WHERE date(t.data_limite) = ? OR date(t.data_limite) IS NULL
        ORDER BY t.prioridade DESC
    """, (date_str,))
    data["tarefas"] = [dict(r) for r in cursor.fetchall()]
    
    # Agenda for today
    cursor.execute("""
        SELECT hora, titulo, descricao, estacao
        FROM agenda
        WHERE data = ?
        ORDER BY hora
    """, (date_str,))
    data["agenda"] = [dict(r) for r in cursor.fetchall()]
    
    # Notes for today
    cursor.execute("""
        SELECT estacao, texto, timestamp
        FROM notas
        WHERE date(timestamp) = ?
        ORDER BY timestamp
    """, (date_str,))
    data["notas"] = [dict(r) for r in cursor.fetchall()]
    
    # Projects status
    cursor.execute("""
        SELECT nome, status, tags, readme_preview, estacao
        FROM projetos
        WHERE estacao = 'helcio-x99-b'
    """)
    data["projetos"] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return data


def format_context(data: dict) -> str:
    """Format data as context for LLM."""
    parts = [f"# Relatório Diário - {data['date']}\n"]
    
    if data.get("agent_memory"):
        parts.append("## Memórias de Agentes")
        for m in data["agent_memory"]:
            ts = m["timestamp"][:19].replace("T", " ")
            parts.append(f"- [{ts}] {m['agent_name']} ({m['project']}/{m['category']}): {m['content'][:200]}")
    
    if data.get("tarefas"):
        parts.append("\n## Tarefas")
        for t in data["tarefas"]:
            parts.append(f"- [{t['status']}/{t['prioridade']}] {t['titulo']} ({t['projeto']})")
    
    if data.get("agenda"):
        parts.append("\n## Agenda")
        for a in data["agenda"]:
            parts.append(f"- {a['hora']} {a['titulo']} ({a['estacao']}): {a['descricao'] or ''}")
    
    if data.get("notas"):
        parts.append("\n## Notas")
        for n in data["notas"]:
            ts = n["timestamp"][:19].replace("T", " ")
            parts.append(f"- [{ts}] {n['estacao']}: {n['texto'][:200]}")
    
    if data.get("projetos"):
        parts.append("\n## Projetos Ativos")
        for p in data["projetos"]:
            parts.append(f"- {p['nome']} [{p['status']}] ({p['estacao']})")
    
    return "\n".join(parts)


def generate_summary(context: str) -> str:
    """Generate summary using KoboldCpp."""
    prompt = f"""Você é um assistente que cria resumos executivos diários para um desenvolvedor.
Crie um resumo conciso e estruturado do dia baseado nos dados abaixo.

Dados do dia:
{context}

Formato do resumo:
## Resumo Executivo - {datetime.now().date().isoformat()}

### 🎯 Principais Realizações
- Item 1
- Item 2

### 📋 Tarefas Concluídas
- Tarefa 1
- Tarefa 2

### ⏳ Pendentes / Próximos Passos
- Item 1
- Item 2

### 💡 Insights / Observações
- Insight 1

Seja conciso, técnico e acionável. Use português do Brasil.
"""
    
    payload = {
        "model": KOBOLD_MODEL,
        "messages": [
            {"role": "system", "content": "Você é um assistente técnico que cria resumos diários executivos."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": False
    }
    
    try:
        import urllib.request
        req = urllib.request.Request(
            KOBOLD_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro ao gerar resumo via LLM: {e}"


def save_summary(date_str: str, summary: str):
    """Save summary to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO resumos_diarios (data, resumo, agente, timestamp)
        VALUES (?, ?, ?, ?)
    """, (date_str, summary, "auto_daily_summary", datetime.now().isoformat()))
    conn.commit()
    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date in YYYY-MM-DD (default: today)")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM generation, just save raw context")
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().date().isoformat()
    
    print(f"Gerando resumo para {date_str}...")
    data = get_daily_data(date_str)
    context = format_context(data)
    
    if args.no_llm:
        summary = f"# Resumo Bruto - {date_str}\n\n{context}"
    else:
        print("Chamando LLM local...")
        summary = generate_summary(context)
    
    print("Salvando no banco...")
    save_summary(date_str, summary)
    
    print(f"\n=== Resumo ({date_str}) ===")
    print(summary)
    print(f"\n✅ Salvo em resumos_diarios")


if __name__ == "__main__":
    main()

