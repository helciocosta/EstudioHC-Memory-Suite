#!/usr/bin/env bash
# ==============================================================================
# EstudioHC Database & ChromaDB Replication to Local Server (Cold Standby)
# Executa snapshot quente do SQLite e vetores ChromaDB para o Servidor Local
# ==============================================================================
set -e

LOCAL_HOST="estudiohc"
DB_SRC="/home/deploy/Apps/EstudioHC-Memory-Suite/data/estudiohc.db"
CHROMA_SRC="/home/deploy/chroma_data/"
LOCAL_DB_DEST="/home/estudiohc/Projetos/dev/EstudioHC-Memory-Suite/data/estudiohc.db"
LOCAL_CHROMA_DEST="/home/estudiohc/chroma_data/"
TMP_BACKUP="/tmp/estudiohc_replicate.db"
LOG_FILE="/home/deploy/Apps/EstudioHC-Memory-Suite/scripts/replicate.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Replication] $1" | tee -a "$LOG_FILE"
}

# 1. Testar se o servidor local está ligado (economia de energia: ele fica desligado maior parte do tempo)
if ! ssh -o BatchMode=yes -o ConnectTimeout=3 "$LOCAL_HOST" "true" >/dev/null 2>&1; then
    log "Servidor Local ($LOCAL_HOST) está desligado em repouso/economia de energia. Pulando replicação."
    exit 0
fi

log "Servidor Local online detectado! Iniciando replicação de dados..."

# 2. Backup atômico quente do SQLite (WAL mode safe)
sqlite3 "$DB_SRC" ".backup $TMP_BACKUP"

# 3. Sincronizar banco para o Servidor Local
rsync -az "$TMP_BACKUP" "$LOCAL_HOST:$LOCAL_DB_DEST"
rm -f "$TMP_BACKUP"
log "Banco SQLite estudo-hc.db replicado com sucesso para $LOCAL_HOST."

# 4. Sincronizar ChromaDB
if [ -d "$CHROMA_SRC" ]; then
    rsync -az "$CHROMA_SRC" "$LOCAL_HOST:$LOCAL_CHROMA_DEST"
    log "Dados vetoriais do ChromaDB replicados com sucesso para $LOCAL_HOST."
fi

log "Replicação concluída com sucesso."
