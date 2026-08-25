#!/bin/bash
# Configura credenciais de email para alertas do EstudioHC no Contabo

CONFIG_FILE="/home/deploy/Apps/EstudioHC-Memory-Suite/config/alerts_contabo.json"

echo "=== EstudioHC Contabo Email Alerts Setup ==="
echo ""

if [ -f "$CONFIG_FILE" ]; then
    echo "Config atual:"
    cat "$CONFIG_FILE" | python3 -m json.tool | grep -A 10 '"smtp"'
    echo ""
fi

read -p "SMTP Host (default: smtp.gmail.com): " SMTP_HOST
SMTP_HOST=${SMTP_HOST:-smtp.gmail.com}

read -p "SMTP Port (default: 587): " SMTP_PORT
SMTP_PORT=${SMTP_PORT:-587}

read -p "Email (username): " SMTP_USER
read -p "Senha de app (não a senha normal): " -s SMTP_PASS
echo ""

read -p "From email (default: $SMTP_USER): " FROM_EMAIL
FROM_EMAIL=${FROM_EMAIL:-$SMTP_USER}

read -p "From name (default: EstudioHC Contabo Alerts): " FROM_NAME
FROM_NAME=${FROM_NAME:-EstudioHC Contabo Alerts}

read -p "Destinatário critical (default: helciocosta@gmail.com): " CRITICAL_EMAIL
CRITICAL_EMAIL=${CRITICAL_EMAIL:-helciocosta@gmail.com}

read -p "Destinatário warning (default: helciocosta@gmail.com): " WARNING_EMAIL
WARNING_EMAIL=${WARNING_EMAIL:-helciocosta@gmail.com}

# Atualizar config
python3 << PYEOF
import json

with open("$CONFIG_FILE", "r") as f:
    config = json.load(f)

config["smtp"]["enabled"] = True
config["smtp"]["host"] = "$SMTP_HOST"
config["smtp"]["port"] = int("$SMTP_PORT")
config["smtp"]["username"] = "$SMTP_USER"
config["smtp"]["password"] = "$SMTP_PASS"
config["smtp"]["use_tls"] = True
config["smtp"]["from_email"] = "$FROM_EMAIL"
config["smtp"]["from_name"] = "$FROM_NAME"

config["recipients"]["critical"] = ["$CRITICAL_EMAIL"]
config["recipients"]["warning"] = ["$WARNING_EMAIL"]

with open("$CONFIG_FILE", "w") as f:
    json.dump(config, f, indent=2)

print("Config atualizado!")
PYEOF

echo ""
echo "=== Teste de envio ==="
read -p "Enviar email de teste? (y/N): " TEST
if [[ "$TEST" =~ ^[Yy]$ ]]; then
    python3 /home/deploy/Apps/EstudioHC-Memory-Suite/scripts/alert_system_contabo.py --test-email "$CRITICAL_EMAIL"
fi
