#!/usr/bin/env python3
"""
Agenda Sync — Sincronizador de Agendas das Estações no Obsidian.
Sincroniza eventos locais de '00 - Painel/Agenda.md' e '02 - Diário/' com o endpoint central /api/agenda da suíte.
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

DEFAULT_VAULT_WIN = r"C:\Users\helcio\Documents\Notas"
DEFAULT_VAULT_LINUX = os.path.expanduser("~/Documentos/Notas")
VAULT_DIR = os.getenv("OBSIDIAN_VAULT", DEFAULT_VAULT_WIN if sys.platform == "win32" else DEFAULT_VAULT_LINUX)
HUB_HOST = os.getenv("ESTUDIOHC_HUB", "hub.estudiohc")
API_URL = os.getenv("ESTUDIOHC_API_URL", f"https://{HUB_HOST}:5050")
API_KEY = os.getenv("ESTUDIOHC_API_KEY", "7a2f4aed8ce8b4d6d5657686cbae94fb07882d598ae65f55320ca0afe82009b2")
HOSTNAME = socket.gethostname()

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [AgendaSync] {msg}", flush=True)


def parse_agenda_tasks() -> list:
    tasks = []
    today = datetime.now().strftime("%Y-%m-%d")
    daily_file = os.path.join(VAULT_DIR, "02 - Diário", f"{today}.md")
    agenda_file = os.path.join(VAULT_DIR, "00 - Painel", "Agenda.md")

    files_to_check = [daily_file, agenda_file]
    idx = 0
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
                            idx += 1
                            ev_id = f"{HOSTNAME}_{today}_{hashlib.md5(text.encode()).hexdigest()[:8]}"
                            tasks.append({
                                "id": ev_id,
                                "data": today,
                                "hora": datetime.now().strftime("%H:%M"),
                                "titulo": text[:120],
                                "estacao": HOSTNAME,
                                "descricao": f"Status: {'[x] Concluída' if done else '[ ] Pendente'} | Origem: {os.path.basename(path)}"
                            })
        except Exception as e:
            log(f"Erro ao ler {path}: {e}")
    return tasks


def push_agenda(tasks: list) -> bool:
    if not tasks:
        return True
    url = f"{API_URL}/api/agenda"
    payload = json.dumps({"eventos": tasks}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            log(f"Sucesso: {data.get('merge', len(tasks))} eventos sincronizados.")
            return resp.status in (200, 201)
    except Exception as e:
        log(f"Falha ao enviar eventos de agenda para {url}: {e}")
        return False


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
