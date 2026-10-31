#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EstudioHC Failover Monitor para Windows.
Monitora o Contabo (hub.estudiohc) periodicamente e, se falhar,
alterna automaticamente o arquivo hosts para o Servidor Local (100.107.208.50).
Quando o Contabo voltar, reverte automaticamente.

Execução: python failover_monitor.py
Ou como tarefa agendada no Windows.
"""

import os
import sys
import time
import socket
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
HOSTNAME = "hub.estudiohc"
PRIMARY_IP = "100.64.117.78"      # Contabo Maestro 24/7
FALLBACK_IP = "100.107.208.50"    # EstudioHC Local (Réplica Quente)
API_URL = "https://hub.estudiohc:5050/api/status"
MCP_URL = "http://hub.estudiohc:5051/sse"
CHECK_INTERVAL_SEC = 60          # Verificar a cada 60 segundos
FAILURE_THRESHOLD = 3            # 3 falhas consecutivas antes de fazer failover
RECOVERY_THRESHOLD = 2           # 2 sucessos para voltar ao primário

LOG_DIR = os.path.join(os.path.expanduser("~"), ".estudiohc", "logs")
LOG_FILE = os.path.join(LOG_DIR, "failover_monitor.log")
os.makedirs(LOG_DIR, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [FailoverMonitor] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def probe(url: str, timeout: int = 5) -> bool:
    """Tenta acessar uma URL e retorna True se respondeu com sucesso."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.status == 200
    except Exception as e:
        log(f"  Probe falhou ({url}): {e}")
        return False


def read_hosts() -> str:
    with open(HOSTS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_hosts(content: str):
    with open(HOSTS_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def set_host_to_ip(ip: str) -> bool:
    """Altera a linha hub.estudiohc no hosts para o IP especificado."""
    try:
        content = read_hosts()
        lines = content.splitlines(keepends=True)
        new_lines = []
        found = False
        for line in lines:
            if "hub.estudiohc" in line and not line.strip().startswith("#"):
                new_lines.append(f"{ip} hub.estudiohc\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"\n{ip} hub.estudiohc\n")
        write_hosts("".join(new_lines))
        log(f"  Hosts atualizado: hub.estudiohc -> {ip}")
        return True
    except PermissionError:
        log("  ERRO: Sem permissão para escrever no arquivo hosts. Execute como Administrador.", "error")
        return False
    except Exception as e:
        log(f"  ERRO ao escrever hosts: {e}", "error")
        return False


def is_primary(ip: str) -> bool:
    """Verifica se o hosts atual já aponta para o IP primário."""
    content = read_hosts()
    for line in content.splitlines():
        if "hub.estudiohc" in line and not line.strip().startswith("#"):
            return ip in line
    return False


def main():
    log("=" * 60)
    log("Iniciando Failover Monitor para EstudioHC")
    log(f"  Primário:   {PRIMARY_IP} (Contabo)")
    log(f"  Fallback:   {FALLBACK_IP} (Servidor Local)")
    log(f"  Intervalo:  {CHECK_INTERVAL_SEC}s")
    log(f"  Threshold:  {FAILURE_THRESHOLD} falhas / {RECOVERY_THRESHOLD} sucessos")
    log("=" * 60)

    consecutive_failures = 0
    consecutive_successes = 0
    currently_on_fallback = False

    while True:
        # Verifica se o primário está online
        primary_ok = probe(API_URL)

        if primary_ok:
            consecutive_successes += 1
            consecutive_failures = 0

            # Se estamos em fallback e conseguimos recuperar o primário
            if currently_on_fallback and consecutive_successes >= RECOVERY_THRESHOLD:
                log(">>> Primário recuperado! Fazendo failback para Contabo...")
                if set_host_to_ip(PRIMARY_IP):
                    currently_on_fallback = False
                    log("  >>> Failback concluído com sucesso.")
                consecutive_successes = 0
            elif not currently_on_fallback:
                log(f"  Primário OK ({PRIMARY_IP}) - {consecutive_successes}/{RECOVERY_THRESHOLD} sucessos")
        else:
            consecutive_successes = 0
            consecutive_failures += 1
            log(f"  Primário FALHOU ({PRIMARY_IP}) - {consecutive_failures}/{FAILURE_THRESHOLD} falhas")

            # Se não estamos em fallback e atingiu o threshold, faz failover
            if not currently_on_fallback and consecutive_failures >= FAILURE_THRESHOLD:
                log(f">>> Primário inacessível após {FAILURE_THRESHOLD} falhas!")
                log("  Verificando se o Servidor Local está online...")
                if probe(FALLBACK_API_URL.replace("hub.estudiohc", FALLBACK_IP)):
                    log("  Servidor Local está online. Fazendo failover...")
                    if set_host_to_ip(FALLBACK_IP):
                        currently_on_fallback = True
                        log("  >>> Failover concluído com sucesso.")
                    else:
                        log("  >>> FALHA ao atualizar hosts! Verifique privilégios de Administrador.", "error")
                else:
                    log("  Servidor Local também inacessível. Mantendo configuração atual.")
            elif currently_on_fallback:
                log(f"  Já em fallback ({FALLBACK_IP}) - aguardando recuperação do primário...")

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Monitor interrompido pelo usuário.")
    except Exception as e:
        log(f"ERRO CRÍTICO: {e}", "error")
        raise