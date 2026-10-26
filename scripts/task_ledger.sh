#!/usr/bin/env bash
# ==============================================================================
# Task Lifecycle Ledger — Rastreamento Automatizado de Tarefas no Git
# Versiona automaticamente o início, progresso e conclusão no repositório remoto
# ==============================================================================
set -e

ACTION="$1"
TASK_ID="$2"
MESSAGE="$3"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LEDGER_FILE="$REPO_DIR/progress.md"

usage() {
    echo "Uso: $0 {start|progress|done} <task_id> <mensagem/evidencias>"
    exit 1
}

if [ -z "$ACTION" ] || [ -z "$TASK_ID" ] || [ -z "$MESSAGE" ]; then
    usage
fi

cd "$REPO_DIR"

# Garantir que o ledger existe
if [ ! -f "$LEDGER_FILE" ]; then
    echo "# Task Execution Ledger — EstudioHC Memory Suite" > "$LEDGER_FILE"
    echo "" >> "$LEDGER_FILE"
    echo "Rastreamento contínuo do ciclo de vida de tarefas para a equipe de desenvolvimento e agentes." >> "$LEDGER_FILE"
    echo "" >> "$LEDGER_FILE"
    echo "## Registro de Tarefas" >> "$LEDGER_FILE"
fi

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

case "$ACTION" in
    start)
        echo "- [ ] **Task $TASK_ID**: $MESSAGE | *Status: IN_PROGRESS* (Iniciado: $TIMESTAMP)" >> "$LEDGER_FILE"
        COMMIT_MSG="task($TASK_ID): [IN_PROGRESS] $MESSAGE"
        ;;
    progress)
        echo "  - *Progresso ($TIMESTAMP)*: $MESSAGE" >> "$LEDGER_FILE"
        COMMIT_MSG="task($TASK_ID): [PROGRESS] $MESSAGE"
        ;;
    done)
        sed -i "s/- \[ \] \*\*Task $TASK_ID\*\*:.*/- [x] **Task $TASK_ID**: $MESSAGE | *Status: COMPLETED* (Concluído: $TIMESTAMP)/" "$LEDGER_FILE" 2>/dev/null ||         echo "- [x] **Task $TASK_ID**: $MESSAGE | *Status: COMPLETED* (Concluído: $TIMESTAMP)" >> "$LEDGER_FILE"
        COMMIT_MSG="task($TASK_ID): [COMPLETED] $MESSAGE"
        ;;
    *)
        usage
        ;;
esac

# Atualizar repositório remoto automaticamente
git add "$LEDGER_FILE"
git commit -m "$COMMIT_MSG"
git push origin master

echo "[TaskLedger] Tarefa $TASK_ID ($ACTION) commitada e enviada para origin master com sucesso."
