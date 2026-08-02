#!/bin/bash
# Backup automático do EstudioHC Memory Suite
# Fase 5 — Diário, mantém 7 dias de histórico
#
# Uso:
#   ./scripts/backup.sh                    # backup normal
#   ./scripts/backup.sh --dry-run          # simula sem copiar
#   DRY_RUN=1 ./scripts/backup.sh          # via env

set -euo pipefail

REPO_DIR="$HOME/Apps/EstudioHC-Memory-Suite"
BACKUP_DIR="$REPO_DIR/backups"
DB="$REPO_DIR/data/estudiohc.db"
FAISS="$REPO_DIR/apps/mcp-memory/src/.faiss_index.pkl"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

DRY_RUN="${DRY_RUN:-false}"
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=true; fi

mkdir -p "$BACKUP_DIR"

backup_file() {
    local src="$1"
    local name="$2"
    if [ ! -f "$src" ]; then
        echo "[backup] SKIP $name — arquivo não encontrado: $src"
        return
    fi
    local dest="$BACKUP_DIR/${name}.${TIMESTAMP}"
    if [ "$DRY_RUN" = "true" ]; then
        echo "[backup] DRY-RUN: cp $src → $dest"
    else
        cp "$src" "$dest"
        echo "[backup] OK $name → $(basename $dest) ($(du -h "$dest" | cut -f1))"
    fi
}

echo "[backup] === EstudioHC Backup $(date) ==="
backup_file "$DB" "memory-db"
backup_file "$FAISS" "faiss-index"

# Limpeza de backups antigos
if [ "$DRY_RUN" = "false" ]; then
    find "$BACKUP_DIR" -name "memory-db.*" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "faiss-index.*" -mtime +$RETENTION_DAYS -delete
    echo "[backup] Limpeza: backups com mais de $RETENTION_DAYS dias removidos"
fi

echo "[backup] === Concluído ==="
