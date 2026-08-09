#!/bin/bash
# Monitoramento de recursos do EstudioHC Memory Suite
# Fase 6 — Coleta periódica de RAM/CPU/cache hits
#
# Saída: /var/log/estudiohc-metrics.csv (também copiado para backups/)
# Formato: timestamp,servico,rss_kb,cpu_pct,cache_hits,prompt_ms,temp_c

set -euo pipefail

LOG_DIR="${LOG_DIR:-$HOME/.local/share/estudiohc}"
LOG_FILE="$LOG_DIR/estudiohc-metrics.csv"
REPO_DIR="$HOME/Apps/EstudioHC-Memory-Suite"
BACKUP_LOG="$REPO_DIR/backups/estudiohc-metrics.csv"

mkdir -p "$LOG_DIR" "$REPO_DIR/backups"

# Cabeçalho se arquivo não existir
if [ ! -f "$LOG_FILE" ]; then
    echo "timestamp,servico,rss_kb,cpu_pct,cache_hits,prompt_ms,temp_c" > "$LOG_FILE"
fi

TS=$(date +%Y-%m-%dT%H:%M:%S%z)

collect_llama() {
    local service="$1"
    local port="$2"
    local pid
    pid=$(pgrep -f "msty-llama-server.*--port $port" 2>/dev/null | head -1 || true)

    if [ -z "$pid" ]; then
        echo "$TS,$service,0,0,0,0,0" >> "$LOG_FILE"
        return
    fi

    # RSS e CPU
    read rss cpu <<< "$(ps -o rss=,pcpu= -p "$pid" 2>/dev/null || echo "0 0")"
    rss=${rss:-0}
    cpu=${cpu:-0}

    # Cache hits da última requisição via healthcheck
    cache_hits=0
    prompt_ms=0
    if command -v curl &>/dev/null; then
        response=$(curl -s --max-time 3 http://127.0.0.1:"$port"/v1/chat/completions \
            -d '{"model":"llama","messages":[{"role":"user","content":"ping"}],"max_tokens":1}' 2>/dev/null) || true
        if [ -n "$response" ]; then
            cache_hits=$(echo "$response" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('usage',{}).get('prompt_tokens_details',{}).get('cached_tokens',0))
except: print(0)
" 2>/dev/null) || cache_hits=0
            prompt_ms=$(echo "$response" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(int(d.get('timings',{}).get('prompt_ms',0)))
except: print(0)
" 2>/dev/null) || prompt_ms=0
        fi
    fi

    # Temperatura (se sensors disponível)
    temp=$(sensors 2>/dev/null | grep -oP 'Package id 0:\s+\+\K[0-9.]+' | head -1 || echo "0")

    echo "$TS,$service,$rss,$cpu,$cache_hits,$prompt_ms,$temp" >> "$LOG_FILE"
}

collect_llama "llama-server" "11434"
collect_llama "llama-server-summarizer" "11435"

# Copiar para o repositório (acessível via git)
cp "$LOG_FILE" "$BACKUP_LOG" 2>/dev/null || true

# Últimas 5 linhas no journal
tail -5 "$LOG_FILE" | while read line; do
    echo "[monitor] $line"
done
