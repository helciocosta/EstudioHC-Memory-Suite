#!/usr/bin/env python3
"""
Obsidian Collector — Coletor Local Ativo para Estações Windows e Linux.
Monitora o cofre do Obsidian e replica notas para o Apps/EstudioHC-Memory-Suite (API :5050 e ChromaDB).
Utiliza apenas a biblioteca padrão do Python para execução leve e sem dependências externas.
"""
import os
import sys
import time
import json
import socket
import ssl
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime

# Configurações com fallback automático por plataforma
DEFAULT_VAULT_WIN = r"C:\Users\helcio\Documents\Notas"
DEFAULT_VAULT_LINUX = os.path.expanduser("~/Documentos/Notas")
VAULT_DIR = os.getenv(
    "OBSIDIAN_VAULT",
    DEFAULT_VAULT_WIN if sys.platform == "win32" else DEFAULT_VAULT_LINUX
)

HUB_HOST = os.getenv("ESTUDIOHC_HUB", "hub.estudiohc")
API_URL = os.getenv("ESTUDIOHC_API_URL", f"https://{HUB_HOST}:5050")
API_KEY = os.getenv("ESTUDIOHC_API_KEY", "7a2f4aed8ce8b4d6d5657686cbae94fb07882d598ae65f55320ca0afe82009b2")
HOSTNAME = socket.gethostname()
STATE_FILE = os.path.join(os.path.expanduser("~"), ".estudiohc_collector_state.json")
POLL_INTERVAL = int(os.getenv("COLLECTOR_INTERVAL", "5"))

# Contexto SSL ignorando autoassinado para hub local/tailscale
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ObsidianCollector] {msg}", flush=True)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"Erro ao salvar estado: {e}")


def get_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def send_note_to_api(title: str, content: str, rel_path: str) -> bool:
    url = f"{API_URL}/api/nota"
    header_info = f"[{rel_path} | Estação: {HOSTNAME}]\n# {title}\n\n"
    payload = json.dumps({
        "texto": header_info + content,
        "estacao": HOSTNAME
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            "User-Agent": f"ObsidianCollector/{HOSTNAME}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=5) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        log(f"Falha ao enviar nota '{title}' para {url}: {e}")
        return False


def scan_and_sync(state: dict) -> bool:
    if not os.path.exists(VAULT_DIR):
        return False

    targets = ["01 - Notas", "02 - Diário"]
    changes_detected = False

    for target in targets:
        target_dir = os.path.join(VAULT_DIR, target)
        if not os.path.exists(target_dir):
            continue

        for root, _, files in os.walk(target_dir):
            for file in files:
                if not file.endswith(".md"):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, VAULT_DIR)

                try:
                    file_hash = get_file_hash(full_path)
                except Exception:
                    continue

                if state.get(rel_path) != file_hash:
                    log(f"Nova alteração detectada: {rel_path}")
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()

                        title = os.path.splitext(file)[0]
                        if send_note_to_api(title, content, rel_path):
                            log(f"Nota sincronizada com sucesso na API: {rel_path}")
                            state[rel_path] = file_hash
                            changes_detected = True
                        else:
                            log(f"Pendente de sincronização: {rel_path}")
                    except Exception as e:
                        log(f"Erro ao processar {full_path}: {e}")

    if changes_detected:
        save_state(state)
    return changes_detected


def main():
    log(f"Iniciando Obsidian Collector na estação: {HOSTNAME}")
    log(f"Monitorando cofre em: {VAULT_DIR}")
    log(f"Alvo Central: {API_URL} (hub: {HUB_HOST})")

    state = load_state()

    # Primeira varredura
    scan_and_sync(state)

    while True:
        try:
            time.sleep(POLL_INTERVAL)
            scan_and_sync(state)
        except KeyboardInterrupt:
            log("Coletor finalizado pelo usuário.")
            break
        except Exception as e:
            log(f"Erro inesperado no loop principal: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
