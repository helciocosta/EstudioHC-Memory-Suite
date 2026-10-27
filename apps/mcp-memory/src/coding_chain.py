"""
Coding Chain Store — Version-Evolution Chain (Diff-Chain).
Portado e adaptado do Tencent Hy-Memory (hy_memory/coding/chain_store.py).

Rastreia trajetórias de código e diffs exatos de arquivos/funções/branches
em SQLite local com custo ZERO de LLM.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CODING_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data',
    'coding_memory_cv.db'
)

def _get_db():
    os.makedirs(os.path.dirname(CODING_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CODING_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS coding_thread (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                branch TEXT NOT NULL,
                file TEXT NOT NULL,
                symbol TEXT,
                lo INTEGER,
                hi INTEGER,
                n_rounds INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS coding_round (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                said TEXT NOT NULL,
                patch TEXT NOT NULL,
                adds INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES coding_thread(id)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_thread_lookup ON coding_thread (owner, branch, file, symbol)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_round_thread ON coding_round (thread_id, seq)')
    return conn

def record_change(
    workspace: str,
    branch: str,
    file: str,
    said: str,
    patch: str,
    symbol: Optional[str] = None,
    lo: Optional[int] = None,
    hi: Optional[int] = None
) -> Dict[str, Any]:
    """
    Registra uma modificação na cadeia de evolução de código (Diff-Chain).
    """
    conn = _get_db()
    owner = workspace.strip()
    branch = branch.strip() or 'main'
    file = file.strip()
    symbol = (symbol or '').strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    adds = patch.count('\n+')

    with conn:
        cur = conn.execute(
            '''SELECT id, n_rounds FROM coding_thread 
               WHERE owner = ? AND branch = ? AND file = ? AND symbol = ?''',
            (owner, branch, file, symbol)
        )
        row = cur.fetchone()
        if row:
            thread_id = row['id']
            seq = row['n_rounds'] + 1
            conn.execute(
                '''UPDATE coding_thread 
                   SET n_rounds = ?, lo = COALESCE(?, lo), hi = COALESCE(?, hi), updated_at = ?
                   WHERE id = ?''',
                (seq, lo, hi, now_iso, thread_id)
            )
        else:
            seq = 1
            cur = conn.execute(
                '''INSERT INTO coding_thread (owner, branch, file, symbol, lo, hi, n_rounds, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (owner, branch, file, symbol, lo, hi, seq, now_iso)
            )
            thread_id = cur.lastrowid

        conn.execute(
            '''INSERT INTO coding_round (thread_id, seq, said, patch, adds, created_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (thread_id, seq, said, patch, adds, now_iso)
        )

    return {
        'status': 'recorded',
        'thread_id': thread_id,
        'seq': seq,
        'workspace': owner,
        'branch': branch,
        'file': file,
        'symbol': symbol,
        'adds': adds,
        'timestamp': now_iso
    }

def get_evolution_chain(
    workspace: str,
    branch: Optional[str] = None,
    file: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Recupera a cadeia de evolução histórica de alterações para um arquivo/workspace.
    """
    conn = _get_db()
    query = '''SELECT t.id as thread_id, t.owner, t.branch, t.file, t.symbol, t.n_rounds,
                      r.seq, r.said, r.patch, r.adds, r.created_at
               FROM coding_thread t
               JOIN coding_round r ON t.id = r.thread_id
               WHERE t.owner = ?'''
    params = [workspace.strip()]

    if branch:
        query += ' AND t.branch = ?'
        params.append(branch.strip())
    if file:
        query += ' AND t.file = ?'
        params.append(file.strip())
    if symbol:
        query += ' AND t.symbol = ?'
        params.append(symbol.strip())

    query += ' ORDER BY r.created_at DESC LIMIT ?'
    params.append(limit)

    cur = conn.execute(query, params)
    rows = cur.fetchall()

    chain = []
    for r in rows:
        chain.append({
            'thread_id': r['thread_id'],
            'workspace': r['owner'],
            'branch': r['branch'],
            'file': r['file'],
            'symbol': r['symbol'],
            'seq': r['seq'],
            'said': r['said'],
            'patch': r['patch'],
            'adds': r['adds'],
            'timestamp': r['created_at']
        })
    return chain
