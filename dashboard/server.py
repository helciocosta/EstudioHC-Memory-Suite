#!/usr/bin/env python3
"""
EstudioHC Hub — Servidor local
Porta: 8585
API: /api/diarios, /api/diario, /api/nota, /api/projetos, /api/agenda, /api/kobold
"""

import json
import os
import glob
import urllib.request
import urllib.error
from datetime import date
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Configurações ──────────────────────────────────────────────
PORT = 8585
DIARIO_DIR = "/home/helcio/Apps/estudiohc-diario"
PROJETOS_FILE = "/home/helcio/Apps/estudiohc-diario/PROJETOS_STATUS.md"
AGENDA_FILE = "/home/helcio/Apps/EstudioHC-Memory-Suite/dashboard/agenda.json"
KOBOLD_URL = "http://localhost:11434/v1/chat/completions"
HUB_DIR = "/home/helcio/Apps/EstudioHC-Memory-Suite/dashboard"
HERMES_CLI = "/home/helcio/.local/bin/hermes"  # agente principal


def get_diarios():
    """Lista todos os diários disponíveis."""
    arquivos = sorted(
        glob.glob(f"{DIARIO_DIR}/*_COMPLETO.txt"), reverse=True
    )
    return [
        {
            "data": os.path.basename(f).replace("_COMPLETO.txt", ""),
            "tamanho": os.path.getsize(f),
        }
        for f in arquivos
    ]


def get_diario(data):
    """Retorna conteúdo de um diário específico."""
    caminho = f"{DIARIO_DIR}/{data}_COMPLETO.txt"
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return {"data": data, "conteudo": f.read()}
    return None


def get_diario_hoje():
    """Retorna diário de hoje ou cria se não existir."""
    hoje = date.today().isoformat()
    caminho = f"{DIARIO_DIR}/{hoje}_COMPLETO.txt"
    if not os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(f"# Diário — {hoje}\n\n")
    return get_diario(hoje)


def adicionar_nota(texto):
    """Adiciona nota ao diário de hoje."""
    hoje = date.today().isoformat()
    caminho = f"{DIARIO_DIR}/{hoje}_COMPLETO.txt"
    from datetime import datetime
    hora = datetime.now().strftime("%H:%M")
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(f"\n## {hora}\n{texto}\n")
    return True


def get_projetos():
    """Lê e parseia o PROJETOS_STATUS.md."""
    if not os.path.exists(PROJETOS_FILE):
        return []
    with open(PROJETOS_FILE, "r", encoding="utf-8") as f:
        conteudo = f.read()
    projetos = []
    blocos = conteudo.split("## 🛠")
    for bloco in blocos[1:]:
        linhas = bloco.strip().split("\n")
        nome = linhas[0].strip()
        local = ""
        for l in linhas:
            if "**Local:**" in l:
                local = l.replace("- **Local:**", "").strip().strip("`")
        preview = " ".join(
            l for l in linhas[1:6] if l.strip() and "Local:" not in l
        )[:200]
        projetos.append({"nome": nome, "local": local, "preview": preview})
    return projetos


def get_agenda():
    """Carrega agenda.json."""
    if not os.path.exists(AGENDA_FILE):
        return []
    with open(AGENDA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_agenda(eventos):
    """Salva agenda.json."""
    with open(AGENDA_FILE, "w", encoding="utf-8") as f:
        json.dump(eventos, f, ensure_ascii=False, indent=2)
    return True


def hermes_chat(mensagem, contexto=""):
    """Envia mensagem ao Hermes Agent (agente principal).
    - Online: usa modelo em nuvem via OpenRouter (Llama 3.3 70B)
    - Offline / rate-limit: cai automaticamente para KoboldCpp local
    """
    import subprocess
    prompt = mensagem
    if contexto:
        prompt = f"[Contexto EstudioHC: {contexto}]\n\n{mensagem}"
    try:
        resultado = subprocess.run(
            [HERMES_CLI, "-z", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            env={**__import__('os').environ, "PYTHONUNBUFFERED": "1"}
        )
        saida = resultado.stdout.strip()
        erro = resultado.stderr.strip() if resultado.stderr else ""
        # Detectar rate-limit ou indisponibilidade → fallback local
        sinais_offline = ["429", "rate", "quota", "HTTP 4", "HTTP 5",
                          "failed after", "No endpoints", "connection"]
        if not saida or any(s in saida or s in erro for s in sinais_offline):
            resposta_local = kobold_chat(mensagem, contexto)
            return f"[offline→local] {resposta_local}"
        return saida
    except subprocess.TimeoutExpired:
        return kobold_chat(mensagem, contexto)  # fallback silencioso
    except Exception:
        return kobold_chat(mensagem, contexto)  # fallback silencioso


def kobold_chat(mensagem, contexto=""):
    """Envia mensagem ao KoboldCpp local (fallback offline direto)."""
    payload = {
        "model": "koboldcpp",
        "messages": [
            {"role": "system", "content": f"/no_think\nVocê é um assistente pessoal do EstudioHC. Responda sempre em português brasileiro de forma concisa e útil.{' Contexto: ' + contexto if contexto else ''}"},
            {"role": "user", "content": mensagem}
        ],
        "max_tokens": 800,
        "temperature": 0.7,
        "stream": False
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        KOBOLD_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resultado = json.loads(resp.read())
            return resultado["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[KoboldCpp offline ou erro: {e}]"


class HubHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HUB_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # silencia logs no terminal

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/diarios":
            return self.send_json(get_diarios())

        if path.startswith("/api/diario/"):
            data = path.split("/api/diario/")[1]
            d = get_diario(data)
            if d:
                return self.send_json(d)
            return self.send_json({"erro": "não encontrado"}, 404)

        if path == "/api/diario/hoje":
            return self.send_json(get_diario_hoje())

        if path == "/api/projetos":
            return self.send_json(get_projetos())

        if path == "/api/agenda":
            return self.send_json(get_agenda())

        if path == "/api/status":
            import subprocess, shutil
            # KoboldCpp
            try:
                urllib.request.urlopen("http://localhost:11434/v1/models", timeout=3)
                kobold_ok = True
            except:
                kobold_ok = False
            # Hermes
            hermes_ok = shutil.which("hermes") is not None or os.path.exists(HERMES_CLI)
            return self.send_json({
                "hub": "online",
                "koboldcpp": kobold_ok,
                "hermes": hermes_ok,
                "porta": PORT
            })

        # Serve arquivos estáticos (index.html, etc.)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        try:
            dados = json.loads(body)
        except:
            dados = {}

        if path == "/api/nota":
            texto = dados.get("texto", "").strip()
            if texto:
                adicionar_nota(texto)
                return self.send_json({"ok": True})
            return self.send_json({"erro": "texto vazio"}, 400)

        if path == "/api/agenda":
            eventos = dados.get("eventos", [])
            salvar_agenda(eventos)
            return self.send_json({"ok": True})

        if path == "/api/hermes":
            # Agente principal — usa nuvem com fallback local automático
            mensagem = dados.get("mensagem", "")
            contexto = dados.get("contexto", "")
            if mensagem:
                resposta = hermes_chat(mensagem, contexto)
                return self.send_json({"resposta": resposta, "agente": "hermes"})
            return self.send_json({"erro": "mensagem vazia"}, 400)

        if path == "/api/kobold":
            # Fallback offline direto — KoboldCpp local
            mensagem = dados.get("mensagem", "")
            contexto = dados.get("contexto", "")
            if mensagem:
                resposta = kobold_chat(mensagem, contexto)
                return self.send_json({"resposta": resposta, "agente": "koboldcpp"})
            return self.send_json({"erro": "mensagem vazia"}, 400)

        return self.send_json({"erro": "rota não encontrada"}, 404)


if __name__ == "__main__":
    os.chdir(HUB_DIR)
    server = HTTPServer(("0.0.0.0", PORT), HubHandler)
    print(f"✅ EstudioHC Hub rodando em http://localhost:{PORT}")
    server.serve_forever()
