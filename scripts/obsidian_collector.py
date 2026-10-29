#!/usr/bin/env python3
"""
Obsidian Collector v2.0 — Coletor Local Profissional para Estações Windows e Linux.
Monitora o cofre do Obsidian e replica notas para o EstudioHC-Memory-Suite:
  1. SQLite `notas` (POST /api/nota) com identificação real da estação
  2. Memória Semântica Versionada v4.6 Hy-Memory (POST /remember com supersedes_id)
  3. Indexação Vetorial Completa em ChromaDB + FAISS (POST :5051/api/index-doc)
  4. Heartbeat automático da estação (POST /api/estacoes/ping)
  5. Sincronização automática de Agenda (POST /api/agenda)
  6. Sincronização Bidirecional de Painel (00 - Painel/Status Ecossistema EstudioHC.md)
  7. Filtro rápido por mtime/size, Debounce de escrita (15s), Single-Instance Mutex,
     Log rotacionado e Failover automático Maestro Contabo <-> Servidor Local.
"""
import os
import re
import sys
import time
import json
import socket
import ssl
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import subprocess
import urllib.request
import urllib.parse
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
VAULT_DIR = os.getenv(
    "OBSIDIAN_VAULT",
    DEFAULT_VAULT_WIN if sys.platform == "win32" else DEFAULT_VAULT_LINUX
)

HUB_HOST = os.getenv("ESTUDIOHC_HUB", "hub.estudiohc")
PRIMARY_API_URL = os.getenv("ESTUDIOHC_API_URL", f"https://{HUB_HOST}:5050").rstrip("/")
PRIMARY_MCP_URL = os.getenv("ESTUDIOHC_MCP_URL", f"http://{HUB_HOST}:5051").rstrip("/")
FALLBACK_API_URL = os.getenv("ESTUDIOHC_FALLBACK_API_URL", "https://100.107.208.50:5050").rstrip("/")
FALLBACK_MCP_URL = os.getenv("ESTUDIOHC_FALLBACK_MCP_URL", "http://100.107.208.50:5051").rstrip("/")
API_KEY = os.getenv("ESTUDIOHC_API_KEY", "")
HOSTNAME = os.getenv("ESTUDIOHC_STATION_NAME", socket.gethostname())

HOME_DIR = os.path.expanduser("~")
ESTUDIOHC_DIR = os.path.join(HOME_DIR, ".estudiohc")
LOG_DIR = os.path.join(ESTUDIOHC_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

STATE_FILE = os.path.join(HOME_DIR, ".estudiohc_collector_state.json")
LOG_FILE = os.path.join(LOG_FILE_PATH := LOG_DIR, "obsidian_collector.log")
POLL_INTERVAL = int(os.getenv("COLLECTOR_INTERVAL", "5"))
DEBOUNCE_SEC = int(os.getenv("COLLECTOR_DEBOUNCE_SEC", "15"))
PING_INTERVAL_SEC = 300       # 5 min
STATUS_PULL_INTERVAL_SEC = 900 # 15 min
AGENDA_SYNC_INTERVAL_SEC = 600 # 10 min

GENERATED_STATUS_REL = os.path.join("00 - Painel", "Status Ecossistema EstudioHC.md")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# Configuração de Logging Estruturado com Rotação
logger = logging.getLogger("ObsidianCollector")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] [ObsidianCollector] %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def log(msg: str, level: str = "info"):
    getattr(logger, level, logger.info)(msg)


_MUTEX_HANDLE = None
_LOCK_FP = None


def acquire_single_instance_lock() -> bool:
    """Garante instância única do coletor por máquina (Mutex no Windows / flock no Linux)."""
    global _MUTEX_HANDLE, _LOCK_FP
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, "Local\\EstudioHCObsidianCollector_v2")
            last_err = kernel32.GetLastError()
            if last_err == 183:  # ERROR_ALREADY_EXISTS
                return False
            return True
        except Exception as e:
            log(f"Aviso ao criar mutex Windows: {e}", "warning")
            return True
    else:
        try:
            import fcntl
            lock_path = os.path.join(ESTUDIOHC_DIR, "collector.lock")
            _LOCK_FP = open(lock_path, "w")
            fcntl.flock(_LOCK_FP.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _LOCK_FP.write(str(os.getpid()))
            _LOCK_FP.flush()
            return True
        except Exception:
            return False


class EndpointRouter:
    """Gerencia failover automático entre o Maestro Contabo e o Servidor Local."""
    def __init__(self):
        self.using_fallback = False
        self.failures = 0
        self.last_primary_check = 0.0

    @property
    def api_url(self) -> str:
        if self.using_fallback and (time.time() - self.last_primary_check > 120):
            if self._probe(PRIMARY_API_URL):
                log(f"Failback automático: Maestro primário ({PRIMARY_API_URL}) voltou a ficar online!")
                self.using_fallback = False
                self.failures = 0
        return FALLBACK_API_URL if self.using_fallback else PRIMARY_API_URL

    @property
    def mcp_url(self) -> str:
        return FALLBACK_MCP_URL if self.using_fallback else PRIMARY_MCP_URL

    def _probe(self, base_url: str) -> bool:
        self.last_primary_check = time.time()
        try:
            req = urllib.request.Request(f"{base_url}/api/status", method="GET")
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def record_success(self):
        self.failures = 0

    def record_failure(self):
        self.failures += 1
        if not self.using_fallback and self.failures >= 3 and FALLBACK_API_URL:
            if self._probe(FALLBACK_API_URL):
                self.using_fallback = True
                log(f"FAILOVER ATIVADO: Comutado automaticamente para Servidor Local ({FALLBACK_API_URL})", "warning")


router = EndpointRouter()


def get_tailscale_ip() -> str:
    try:
        flags = 0x08000000 if sys.platform == "win32" else 0
        out = subprocess.check_output(["tailscale", "ip", "-4"], timeout=3, creationflags=flags).decode("utf-8").strip()
        return out.splitlines()[0].strip() if out else "desconhecido"
    except Exception:
        return "desconhecido"


def api_request(method: str, path: str, payload: dict | None = None, base_override: str | None = None, timeout: int = 8) -> tuple[int, dict | list | None]:
    base = base_override or router.api_url
    url = f"{base}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        "User-Agent": f"ObsidianCollector-v2/{HOSTNAME}",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not base_override:
                router.record_success()
            return resp.status, (json.loads(raw) if raw else {})
    except Exception as e:
        if not base_override:
            router.record_failure()
        log(f"Falha HTTP {method} {url}: {e}", "warning")
        return 0, None


def send_station_ping() -> bool:
    ip = get_tailscale_ip()
    status, _ = api_request("POST", "/api/estacoes/ping", {"hostname": HOSTNAME, "ip": ip})
    if status in (200, 201):
        log(f"Heartbeat registrado com sucesso: estação={HOSTNAME} ip={ip} alvo={router.api_url}")
        return True
    return False


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return slug[:48].strip("_") or "nota"


def build_memory_summary(title: str, content: str, rel_path: str) -> str:
    clean = content.strip()
    if len(clean) > 1500:
        clean = clean[:1500] + "\n...[truncado]"
    summary_text = f"[{rel_path} | Estação: {HOSTNAME}] {title}\n{clean}"
    return json.dumps({
        "s": summary_text,
        "r": None,
        "c": True,
        "path": rel_path,
        "estacao": HOSTNAME,
    }, ensure_ascii=False)


def sync_note_full_pipeline(title: str, content: str, rel_path: str, prev_entry: dict) -> dict | None:
    """
    Executa a ingestão tripla:
      1. POST /api/nota (diário/histórico bruto com estação real)
      2. POST /remember (agent_memory v4.6 com supersedes_id)
      3. POST :5051/api/index-doc (ChromaDB docs_obsidian + índice vetorial FAISS)
    """
    header_info = f"[{rel_path} | Estação: {HOSTNAME}]\n# {title}\n\n"
    st_nota, _ = api_request("POST", "/api/nota", {
        "texto": header_info + content,
        "estacao": HOSTNAME,
    })
    if st_nota not in (200, 201):
        return None

    # Categorização inteligente por pasta
    folder = rel_path.split(os.sep)[0] if os.sep in rel_path else "notas"
    category = "daily_log" if "Diário" in folder else ("long_term_memory" if "Painel" in folder else "obsidian_note")
    prev_mem_id = prev_entry.get("memory_id") if isinstance(prev_entry, dict) else None

    mem_payload = {
        "agent_name": "obsidian-collector",
        "project": "EstudioHC",
        "category": category,
        "content": build_memory_summary(title, content, rel_path),
        "estacao": HOSTNAME,
    }
    if prev_mem_id:
        mem_payload["supersedes_id"] = int(prev_mem_id)

    st_mem, mem_res = api_request("POST", "/remember", mem_payload)
    new_mem_id = mem_res.get("id") if (st_mem in (200, 201) and isinstance(mem_res, dict)) else prev_mem_id
    new_ver = mem_res.get("version", 1) if (st_mem in (200, 201) and isinstance(mem_res, dict)) else 1

    # Indexação Documental ChromaDB + FAISS no MCP Server (:5051)
    doc_id = f"obsidian_{slugify(rel_path)}"
    api_request(
        "POST",
        "/api/index-doc",
        {
            "project": "obsidian",
            "title": f"{title} ({rel_path})",
            "content": header_info + content,
            "tags": [folder, HOSTNAME],
            "doc_id": doc_id,
            "memory_id": new_mem_id,
            "category": category,
        },
        base_override=router.mcp_url,
        timeout=12,
    )

    return {
        "memory_id": new_mem_id,
        "version": new_ver,
        "doc_id": doc_id,
    }


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Migração transparente do formato v1 (str hash) para v2 (dict rico)
            upgraded = {}
            for k, v in raw.items():
                if isinstance(v, str):
                    upgraded[k] = {"hash": v, "mtime": 0.0, "size": 0, "memory_id": None, "version": 1}
                elif isinstance(v, dict):
                    upgraded[k] = v
            return upgraded
        except Exception as e:
            log(f"Aviso ao carregar estado ({STATE_FILE}): {e}", "warning")
    return {}


def save_state(state: dict):
    try:
        tmp_file = STATE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, STATE_FILE)
    except Exception as e:
        log(f"Erro ao salvar estado: {e}", "error")


def get_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def pull_ecosystem_status_to_vault():
    """Sincronização bidirecional (Pull): busca status das estações e tarefas da suíte para o Obsidian local."""
    if not os.path.exists(VAULT_DIR):
        return
    st_est, estacoes = api_request("GET", "/api/estacoes")
    st_proj, status_proj = api_request("GET", "/status/EstudioHC")
    if st_est != 200 or not isinstance(estacoes, list):
        return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Status do Ecossistema EstudioHC-Memory-Suite (Sincronizado via Maestro)",
        "",
        f"* **Última Sincronização Automática**: `{now_str}`",
        f"* **Estação Coletora Local**: `{HOSTNAME}`",
        f"* **Endpoint Ativo**: `{router.api_url}` ({'Failover Local' if router.using_fallback else 'Maestro Contabo 24/7'})",
        "",
        "## 🖥️ Estações Registradas na Malha Tailscale",
        "",
        "| Estação | IP Tailscale | Status | Último Heartbeat |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for e in estacoes:
        h = e.get("hostname", "?")
        ip = e.get("ip_tailscale", "-")
        st = e.get("status", "offline")
        badge = "🟢 online" if st == "online" else "⚪ offline"
        ping = (e.get("ultimo_ping") or "-")[:19].replace("T", " ")
        lines.append(f"| `{h}` | `{ip}` | {badge} | `{ping}` |")

    if st_proj == 200 and isinstance(status_proj, dict):
        lines.extend(["", "## 📌 Últimas Memórias / Tarefas Consolidadas (`EstudioHC`)", ""])
        completed = status_proj.get("completed") or []
        pending = status_proj.get("pending") or []
        if pending:
            lines.append("### Pendentes")
            for p in pending[:5]:
                lines.append(f"- [ ] {p[:180]}")
        if completed:
            lines.append("### Recentes / Concluídas")
            for c in completed[:5]:
                lines.append(f"- [x] {c[:180]}")

    out_path = os.path.join(VAULT_DIR, GENERATED_STATUS_REL)
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        new_text = "\n".join(lines) + "\n"
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                old_text = f.read()
            # Evita regravar se só o timestamp mudou
            old_body = "\n".join(old_text.splitlines()[4:])
            new_body = "\n".join(new_text.splitlines()[4:])
            if old_body == new_body:
                return
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        log(f"Painel bidirecional atualizado: {GENERATED_STATUS_REL}")
    except Exception as e:
        log(f"Aviso ao atualizar painel bidirecional: {e}", "warning")


def trigger_agenda_sync():
    try:
        import agenda_sync
        agenda_sync.sync_agenda(vault_dir=VAULT_DIR, api_url=router.api_url, api_key=API_KEY, hostname=HOSTNAME)
    except Exception as e:
        log(f"Aviso ao sincronizar agenda: {e}", "warning")


def scan_and_sync(state: dict, initial_scan: bool = False) -> bool:
    if not os.path.exists(VAULT_DIR):
        return False

    targets = ["00 - Painel", "01 - Notas", "02 - Diário"]
    changes_detected = False
    agenda_touched = False
    now = time.time()

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

                # Ignora o próprio painel gerado automaticamente pelo pull para evitar loop
                if os.path.normpath(rel_path) == os.path.normpath(GENERATED_STATUS_REL):
                    continue

                try:
                    st = os.stat(full_path)
                    mtime = st.st_mtime
                    size = st.st_size
                except OSError:
                    continue

                prev = state.get(rel_path) or {}
                if isinstance(prev, str):
                    prev = {"hash": prev, "mtime": 0.0, "size": 0, "memory_id": None, "version": 1}

                # 1. Filtro rápido de metadados (zero leitura de disco se mtime e size não mudaram)
                if prev.get("mtime") == mtime and prev.get("size") == size and prev.get("hash"):
                    continue

                # 2. Debounce de escrita: aguarda estabilização após edição contínua no Obsidian
                if not initial_scan and prev.get("hash") and (now - mtime) < DEBOUNCE_SEC:
                    continue

                try:
                    file_hash = get_file_hash(full_path)
                except Exception:
                    continue

                # Se apenas mtime foi atualizado ou migração v1->v2 com mesmo hash, atualiza metadados sem reenviar
                if prev.get("hash") == file_hash:
                    prev["mtime"] = mtime
                    prev["size"] = size
                    state[rel_path] = prev
                    changes_detected = True
                    continue

                log(f"Sincronizando nota modificada: {rel_path}")
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()

                    title = os.path.splitext(file)[0]
                    sync_meta = sync_note_full_pipeline(title, content, rel_path, prev)
                    if sync_meta is not None:
                        state[rel_path] = {
                            "hash": file_hash,
                            "mtime": mtime,
                            "size": size,
                            "memory_id": sync_meta.get("memory_id"),
                            "version": sync_meta.get("version", 1),
                            "doc_id": sync_meta.get("doc_id"),
                            "last_sync": datetime.now().isoformat()[:19],
                        }
                        log(f"Sincronizada (v{sync_meta.get('version', 1)}, mem_id={sync_meta.get('memory_id')}): {rel_path}")
                        changes_detected = True
                        if "Diário" in rel_path or file.lower() == "agenda.md":
                            agenda_touched = True
                    else:
                        log(f"Pendente para próxima tentativa: {rel_path}", "warning")
                except Exception as e:
                    log(f"Erro ao processar {full_path}: {e}", "error")

    if changes_detected:
        save_state(state)
    if agenda_touched:
        trigger_agenda_sync()
    return changes_detected


def main():
    if not acquire_single_instance_lock():
        print("[ObsidianCollector] Outra instância já está em execução. Encerrando.", flush=True)
        sys.exit(0)

    log(f"=== Iniciando Obsidian Collector v2.0 na estação: {HOSTNAME} ===")
    log(f"Cofre monitorado: {VAULT_DIR}")
    log(f"Maestro Primário: {PRIMARY_API_URL} (MCP: {PRIMARY_MCP_URL})")
    log(f"Servidor Failover: {FALLBACK_API_URL} (MCP: {FALLBACK_MCP_URL})")

    state = load_state()

    # Heartbeat, varredura inicial, agenda e pull de painel
    send_station_ping()
    scan_and_sync(state, initial_scan=True)
    trigger_agenda_sync()
    pull_ecosystem_status_to_vault()

    last_ping = time.time()
    last_status_pull = time.time()
    last_agenda = time.time()

    while True:
        try:
            time.sleep(POLL_INTERVAL)
            now = time.time()

            scan_and_sync(state, initial_scan=False)

            if now - last_ping >= PING_INTERVAL_SEC:
                send_station_ping()
                last_ping = now

            if now - last_agenda >= AGENDA_SYNC_INTERVAL_SEC:
                trigger_agenda_sync()
                last_agenda = now

            if now - last_status_pull >= STATUS_PULL_INTERVAL_SEC:
                pull_ecosystem_status_to_vault()
                last_status_pull = now

        except KeyboardInterrupt:
            log("Coletor finalizado pelo usuário.")
            break
        except Exception as e:
            log(f"Erro inesperado no loop principal: {e}", "error")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
