#!/usr/bin/env python3
"""
Agenda Sync v2.0 — Sincronizador de Agendas das Estações no Obsidian.
Sincroniza eventos locais de '00 - Painel/Agenda.md' e '02 - Diário/' com o endpoint central /api/agenda da suíte.
Suporta carregamento seguro de ~/.estudiohc/.env e failover automático entre Maestro Contabo e Servidor Local.
"""
import os
import sys
import re
import json
import socket
import ssl
import hashlib
import urllib.request
from datetime import datetime


def load_estudiohc_env():
    env_path = os.path.join(os.path.expanduser("~"), ".estudiohc", ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


load_estudiohc_env()

DEFAULT_VAULT_WIN = r"C:\Users\helcio\Documents\Notas"
DEFAULT_VAULT_LINUX = os.path.expanduser("~/Documentos/Notas")
VAULT_DIR = os.getenv("OBSIDIAN_VAULT", DEFAULT_VAULT_WIN if sys.platform == "win32" else DEFAULT_VAULT_LINUX)
HUB_HOST = os.getenv("ESTUDIOHC_HUB", "hub.estudiohc")
API_URL = os.getenv("ESTUDIOHC_API_URL", f"https://{HUB_HOST}:5050")
FALLBACK_API_URL = os.getenv("ESTUDIOHC_FALLBACK_API_URL", "https://100.107.208.50:5050")
API_KEY = os.getenv("ESTUDIOHC_API_KEY", "")
HOSTNAME = os.getenv("ESTUDIOHC_STATION_NAME", socket.gethostname())

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [AgendaSync] {msg}", flush=True)


def parse_agenda_tasks(vault_dir: str = VAULT_DIR, hostname: str = HOSTNAME) -> list:
    tasks = []
    today = datetime.now().strftime("%Y-%m-%d")
    daily_file = os.path.join(vault_dir, "02 - Diário", f"{today}.md")
    agenda_file = os.path.join(vault_dir, "00 - Painel", "Agenda.md")

    files_to_check = [daily_file, agenda_file]
    for path in files_to_check:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    m = re.match(r"^-\s*\[([ xX])\]\s*(.*)", line)
                    if m:
                        done = m.group(1).lower() == "x"
                        text = m.group(2).strip()
                        if text:
                            ev_id = f"{hostname}_{today}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:8]}"
                            tasks.append({
                                "id": ev_id,
                                "data": today,
                                "hora": datetime.now().strftime("%H:%M"),
                                "titulo": text[:120],
                                "estacao": hostname,
                                "descricao": f"Status: {'[x] Concluída' if done else '[ ] Pendente'} | Origem: {os.path.basename(path)}"
                            })
        except Exception as e:
            log(f"Erro ao ler {path}: {e}")
    return tasks


def push_agenda(tasks: list, api_url: str = API_URL, api_key: str = API_KEY) -> bool:
    if not tasks:
        return True
    payload = json.dumps({"eventos": tasks}).encode("utf-8")
    for base_url in (api_url, FALLBACK_API_URL):
        if not base_url:
            continue
        url = f"{base_url.rstrip('/')}/api/agenda"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                log(f"Sucesso ({base_url}): {data.get('merge', len(tasks))} eventos sincronizados.")
                return resp.status in (200, 201)
        except Exception as e:
            log(f"Aviso: falha ao enviar agenda para {url}: {e}")
    return False


def sync_agenda(vault_dir: str = VAULT_DIR, api_url: str = API_URL, api_key: str = API_KEY, hostname: str = HOSTNAME) -> bool:
    tasks = parse_agenda_tasks(vault_dir=vault_dir, hostname=hostname)
    return push_agenda(tasks, api_url=api_url, api_key=api_key)


def main():
    log(f"Executando sincronização de agenda para estação: {HOSTNAME}")
    tasks = parse_agenda_tasks()
    log(f"Tarefas locais encontradas: {len(tasks)}")
    if push_agenda(tasks):
        log("Agenda sincronizada com sucesso na API central EstudioHC.")
    else:
        log("Aviso: Falha temporária ao sincronizar agenda.")


if __name__ == "__main__":
    main()
