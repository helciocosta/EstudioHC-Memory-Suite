#!/bin/bash
# bootstrap-memory-stack.sh — Instala o journal_recovery skill + configs locais
# para o stack de memória local (WAL textual de sobrevivência pós-queda).
#
# Uso:
#   ./scripts/bootstrap-memory-stack.sh              # instala no $HOME
#   ./scripts/bootstrap-memory-stack.sh --dry-run     # só mostra o que faria
#
# Requer: ~/.agents/skills/ (criado automaticamente pelo OMP/agente)
#
# Este script é complementar ao setup-machine.sh.
# setup-machine.sh provisiona a estação inteira (LLM, MCP, systemd).
# bootstrap-memory-stack.sh só instala a camada de journal recovery.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="$REPO_DIR/config"
AGENTS_SKILLS="$HOME/.agents/skills"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[bootstrap]${NC} $1"; }
warn()  { echo -e "${YELLOW}[bootstrap]${NC} $1"; }
err()   { echo -e "${RED}[bootstrap]${NC} $1"; }

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# ── 1. Skill journal_recovery ─────────────────────────────────────
if [ -f "$CONFIG_DIR/skills/journal_recovery/SKILL.md" ]; then
    info "Instalando skill journal_recovery..."

    if [ "$DRY_RUN" = true ]; then
        echo "  mkdir -p $AGENTS_SKILLS/journal_recovery"
        echo "  cp $CONFIG_DIR/skills/journal_recovery/SKILL.md $AGENTS_SKILLS/journal_recovery/"
    else
        mkdir -p "$AGENTS_SKILLS/journal_recovery"
        cp "$CONFIG_DIR/skills/journal_recovery/SKILL.md" "$AGENTS_SKILLS/journal_recovery/"
        info "  -> $AGENTS_SKILLS/journal_recovery/SKILL.md"
    fi
else
    warn "SKILL.md não encontrado em $CONFIG_DIR/skills/journal_recovery/"
fi

# ── 2. Tmux config ────────────────────────────────────────────────
if [ -f "$CONFIG_DIR/tmux/.tmux.conf" ]; then
    info "Instalando .tmux.conf..."

    if [ "$DRY_RUN" = true ]; then
        echo "  cp $CONFIG_DIR/tmux/.tmux.conf $HOME/.tmux.conf"
    else
        cp "$CONFIG_DIR/tmux/.tmux.conf" "$HOME/.tmux.conf"
        info "  -> $HOME/.tmux.conf"
    fi
else
    warn ".tmux.conf não encontrado em $CONFIG_DIR/tmux/"
fi

# ── 3. Criar .matrixx/ (journal dir) ──────────────────────────────
if [ ! -d "$REPO_DIR/.matrixx" ]; then
    info "Criando .matrixx/ no diretório do repositório..."
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$REPO_DIR/.matrixx"
        chmod 750 "$REPO_DIR/.matrixx"
        # Inicializa journal.md com cabeçalho
        cat > "$REPO_DIR/.matrixx/journal.md" << 'EOH'
# Studio HC — Session Journal (append-only)
# Iniciado pelo bootstrap-memory-stack.sh

EOH
        echo "{}" > "$REPO_DIR/.matrixx/journal.yaml"
        info "  -> $REPO_DIR/.matrixx/"
    else
        echo "  mkdir -p $REPO_DIR/.matrixx"
    fi
else
    info ".matrixx/ já existe em $REPO_DIR/.matrixx"
fi

# ── 4. Verificar journal dir global (/tmp) ────────────────────────
if [ ! -d "/tmp/.matrixx" ]; then
    info "Criando /tmp/.matrixx/ (fallback global)..."
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "/tmp/.matrixx"
        chmod 750 "/tmp/.matrixx"
        info "  -> /tmp/.matrixx/"
    else
        echo "  mkdir -p /tmp/.matrixx"
    fi
else
    info "/tmp/.matrixx/ já existe"
fi

# ── Resumo ─────────────────────────────────────────────────────────
echo ""
info "===== Memory Stack instalado ====="
[ -f "$AGENTS_SKILLS/journal_recovery/SKILL.md" ] && echo "  ✅ skill journal_recovery" || echo "  ❌ skill journal_recovery"
[ -f "$HOME/.tmux.conf" ] && echo "  ✅ .tmux.conf" || echo "  ❌ .tmux.conf"
[ -d "$REPO_DIR/.matrixx" ] && echo "  ✅ .matrixx/ (repo)" || echo "  ❌ .matrixx/ (repo)"
[ -d "/tmp/.matrixx" ] && echo "  ✅ /tmp/.matrixx/ (fallback)" || echo "  ❌ /tmp/.matrixx/ (fallback)"
echo ""
info "Para ativar o tmux logging agora: tmux source-file ~/.tmux.conf"
