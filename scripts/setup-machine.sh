#!/bin/bash
# setup-machine.sh — Provisiona uma estação Tailscale no EstudioHC Memory Suite
# Uso:
#   curl -sL https://raw.githubusercontent.com/helciocosta/EstudioHC-Memory-Suite/master/scripts/setup-machine.sh | bash
#   ou: ./scripts/setup-machine.sh
#
# Requer: git, python3, node/npm, tailscale (conectado à rede)
# Opcional: sudo (para systemd services)

set -euo pipefail

SERVIDOR_CENTRAL="100.64.117.78"   # Tailscale IP do Contabo
REPO_URL="git@github.com:helciocosta/EstudioHC-Memory-Suite.git"
REPO_DIR="$HOME/Apps/EstudioHC-Memory-Suite"
MODELS_DIR="$REPO_DIR/models"
MSTY_DIR="$HOME/.config/MstyStudio/llama-cpp"

# Chave de estação: gerada na primeira execução, persistida entre execuções.
# Requer ESTUDIOHC_API_KEY (master) no ambiente para auto-provisionamento.
CHAVE_ESTACAO="${CHAVE_ESTACAO:-$(openssl rand -hex 32)}"
MASTER_KEY="${ESTUDIOHC_API_KEY:-}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $1"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $1"; }
err()   { echo -e "${RED}[setup]${NC} $1"; }

# ── Pré-requisitos ──────────────────────────────────────────────
info "Verificando pré-requisitos..."
command -v git      >/dev/null 2>&1 || { err "git não encontrado"; exit 1; }
command -v python3  >/dev/null 2>&1 || { err "python3 não encontrado"; exit 1; }
command -v node     >/dev/null 2>&1 || warn "node não encontrado (opcional para opencode)"
command -v tailscale>/dev/null 2>&1 || warn "tailscale não encontrado (necessário para conectar ao servidor)"

TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "DESCONHECIDO")
info "IP Tailscale desta estação: $TAILSCALE_IP"

# ── Ping no servidor central ────────────────────────────────────
info "Testando conexão com servidor central ($SERVIDOR_CENTRAL)..."
if curl -s --connect-timeout 5 "http://${SERVIDOR_CENTRAL}:5050/api/status" >/dev/null 2>&1; then
    info "✅ Servidor central online em ${SERVIDOR_CENTRAL}:5050"
else
    warn "⚠️  Servidor central não respondeu. Verifique Tailscale."
    warn "   Continuando mesmo assim (instalação local apenas)."
fi

# ── Clonar repositório ──────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
    info "Repositório já existe. Atualizando..."
    cd "$REPO_DIR" && git pull origin master
else
    info "Clonando repositório..."
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone "$REPO_URL" "$REPO_DIR"
fi

# ── Criar diretório de modelos ─────────────────────────────────
mkdir -p "$MODELS_DIR"

# ── msty-llama-server ───────────────────────────────────────────
if [ -f "$MSTY_DIR/msty-llama-server" ]; then
    info "msty-llama-server já instalado em $MSTY_DIR"
else
    info "msty-llama-server não encontrado."
    warn "Copie manualmente de uma estação já configurada:"
    warn "  rsync -avz user@estacao:~/.config/MstyStudio/llama-cpp/ $MSTY_DIR/"
    warn "Ou baixe de: https://github.com/ggml-org/llama.cpp/releases"
fi

# ── Modelos GGUF ────────────────────────────────────────────────
download_model() {
    local url="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        info "Modelo $(basename "$dest") já existe. Pulando."
    else
        info "Baixando $(basename "$dest")..."
        curl -sL -o "$dest" "$url" &
    fi
}

# Baixar em background (paralelo)
download_model \
    "https://huggingface.co/AYI-NEDJIMI/CyberSec-Assistant-3B-GGUF/resolve/main/cybersec-assistant-3b-Q4_K_M.gguf" \
    "$MODELS_DIR/cybersec-assistant-3b-Q4_K_M.gguf"

download_model \
    "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf" \
    "$MODELS_DIR/Qwen3-1.7B-Q4_K_M.gguf"

wait
info "Downloads concluídos."

# ── Python venv + dependências MCP ──────────────────────────────
info "Configurando ambiente Python MCP..."
cd "$REPO_DIR/apps/mcp-memory"
python3 -m venv .venv
source .venv/bin/activate
pip install -q mcp requests sentence-transformers faiss-cpu numpy httpx pydantic 2>&1 | tail -3

# Testar import
python3 -c "
import sys
sys.path.insert(0, 'src')
from memory_server import main
print('[setup] memory_server OK')
" 2>&1

# ── opencode ─────────────────────────────────────────────────────
if command -v opencode &>/dev/null; then
    info "Configurando opencode..."
    mkdir -p "$HOME/.config/opencode"

    # Instalar matrixx plugin
    npm install -g opencode-matrixx 2>/dev/null || true
    cd "$HOME/.config/opencode" && npm install opencode-matrixx 2>/dev/null || true

    # Escrever config com MCP apontando para servidor central
    cat > "$HOME/.config/opencode/opencode.jsonc" << JSONEOF
{
  "\$schema": "https://opencode.ai/config.json",
  "mcp": {
    "memory": {
      "type": "local",
      "command": ["env", "MEMORY_API_URL=http://${SERVIDOR_CENTRAL}:5050", "MEMORY_API_KEY=${CHAVE_ESTACAO}", "python3", "${REPO_DIR}/apps/mcp-memory/src/memory_server.py"],
      "enabled": true
    }
  },
  "plugin": ["opencode-matrixx"],
  "model": "opencode/deepseek-v4-flash-free",
  "agent": {
    "morpheus": {"model": "opencode/deepseek-v4-flash-free"},
    "merovingian": {"model": "opencode/deepseek-v4-flash-free"},
    "operator": {"model": "opencode/deepseek-v4-flash-free"},
    "trinity": {"model": "opencode/deepseek-v4-flash-free"}
  }
}
JSONEOF
    info "opencode.jsonc configurado — MCP aponta para servidor central"
else
    warn "opencode não encontrado. Instale com: npm install -g opencode-ai"
fi

# ── Systemd services (se sudo disponível) ───────────────────────
if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
    info "Criando serviços systemd..."

    # llama-server.service
    sudo tee /etc/systemd/system/llama-server.service > /dev/null << SERVICEEOF
[Unit]
Description=llama.cpp server - LLM Principal (CPU, Flash Attn, KV Cache Shift)
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(id -gn)
ExecStart=${MSTY_DIR}/msty-llama-server \
    --model "${MODELS_DIR}/cybersec-assistant-3b-Q4_K_M.gguf" \
    --port 11434 --host 127.0.0.1 \
    --threads 4 --ctx-size 4096 \
    --flash-attn auto --cache-reuse 256 --keep -1 \
    --parallel 1 --cont-batching \
    --device none --no-kv-offload
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=llama-server

[Install]
WantedBy=multi-user.target
SERVICEEOF

    # llama-server-summarizer.service
    sudo tee /etc/systemd/system/llama-server-summarizer.service > /dev/null << SERVICEEOF
[Unit]
Description=llama.cpp server - Sumarizador (CPU, Flash Attn, KV Cache Shift)
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(id -gn)
ExecStart=${MSTY_DIR}/msty-llama-server \
    --model "${MODELS_DIR}/Qwen3-1.7B-Q4_K_M.gguf" \
    --port 11435 --host 127.0.0.1 \
    --threads 2 --ctx-size 2048 \
    --flash-attn auto --cache-reuse 256 --keep -1 \
    --parallel 1 --cont-batching \
    --device none --no-kv-offload
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=llama-server-summarizer

[Install]
WantedBy=multi-user.target
SERVICEEOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now llama-server.service 2>&1
    sudo systemctl enable --now llama-server-summarizer.service 2>&1

    info "Serviços systemd ativados."
else
    warn "Sem sudo. Serviços systemd não foram criados."
fi

# ── Registrar estação no servidor central (se online) ──────────
if [ -n "$MASTER_KEY" ]; then
    PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"hostname": sys.argv[1], "chave": sys.argv[2]}))' "$(hostname)" "$CHAVE_ESTACAO")
    curl -s -X POST "http://${SERVIDOR_CENTRAL}:5050/api/estacoes/registrar" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${MASTER_KEY}" \
        -d "$PAYLOAD" \
        >/dev/null 2>&1 && info "✅ Estação registrada (chave de estação gerada)" \
        || warn "Não foi possível registrar a estação. API offline ou MASTER_KEY inválida?"
fi

curl -s -X POST "http://${SERVIDOR_CENTRAL}:5050/api/estacoes/ping" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${CHAVE_ESTACAO}" \
    -d "{\"hostname\":\"$(hostname)\",\"ip\":\"${TAILSCALE_IP}\"}" \
    >/dev/null 2>&1 && info "✅ Ping de estação enviado" \
    || warn "Não foi possível enviar ping. API offline?"

# ── Final ───────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Estação configurada com sucesso!           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Hostname:    $(hostname)"
echo "  Tailscale:   $TAILSCALE_IP"
echo "  Servidor:    $SERVIDOR_CENTRAL:5050"
echo "  Repositório: $REPO_DIR"
echo "  Modelos:     $MODELS_DIR"
echo ""
echo "Próximos passos:"
echo "  1. Verificar se os modelos foram baixados: ls -lh $MODELS_DIR"
echo "  2. Testar LLM local: curl http://localhost:11434/v1/models"
echo "  3. Testar MCP: opencode mcp list"
echo "  4. Se for estação dev, continue trabalhando normalmente."
echo "     O MCP memory já aponta para o servidor central."
echo ""
