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
    """Lê e parseia o PROJETOS_STATUS.md e sincroniza com o servidor central."""
    import socket
    estacao_local = socket.gethostname()
    
    # 1. Parse do arquivo local
    projetos_locais = []
    if os.path.exists(PROJETOS_FILE):
        try:
            with open(PROJETOS_FILE, "r", encoding="utf-8") as f:
                conteudo = f.read()
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
                projetos_locais.append({
                    "nome": nome,
                    "local_caminho": local,
                    "status": "ativo",
                    "tags": "",
                    "readme_preview": preview,
                    "estacao": estacao_local
                })
        except Exception as e:
            print("Erro ao ler PROJETOS_STATUS.md local:", e)

    # 2. Sincroniza com a API Central (Contabo)
    CENTRAL_URL = "http://100.64.117.78:8585"
    if projetos_locais:
        try:
            payload = {"projetos": projetos_locais}
            req = urllib.request.Request(
                f"{CENTRAL_URL}/api/projetos/sync",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            # Timeout curto para evitar lentidão
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                pass
        except Exception as e:
            print("Servidor central offline para sincronização:", e)

    # 3. Busca lista consolidada de todos os projetos (PC + Servidor + outras estações)
    try:
        req = urllib.request.Request(
            f"{CENTRAL_URL}/api/projetos",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            lista_central = json.loads(resp.read().decode("utf-8"))
            projetos_normalizados = []
            for p in lista_central:
                projetos_normalizados.append({
                    "nome": p.get("nome"),
                    "local": p.get("local") or p.get("local_caminho") or "",
                    "preview": p.get("preview") or p.get("readme_preview") or "",
                    "estacao": p.get("estacao", "desconhecida")
                })
            return projetos_normalizados
    except Exception as e:
        print("Erro ao buscar projetos do servidor central, usando locais:", e)
        # Fallback para locais apenas
        return [
            {
                "nome": p["nome"],
                "local": p["local_caminho"],
                "preview": p["readme_preview"],
                "estacao": p["estacao"]
            }
            for p in projetos_locais
        ]


def gerar_relatorio_local(nome):
    """Coleta metadados locais de um projeto e chama o backend remoto para gerar relatório por IA."""
    import socket
    estacao_local = socket.gethostname()
    projetos = get_projetos()
    proj = None
    
    for p in projetos:
        if p["nome"] == nome and p["estacao"] == estacao_local:
            proj = p
            break
            
    if not proj:
        for p in projetos:
            if p["nome"] == nome:
                proj = p
                break
                
    if not proj:
        proj = {"nome": nome, "local": "", "estacao": "desconhecida"}

    local_path = proj.get("local", "")
    readme_content = ""
    tasks_content = ""
    git_status = ""
    git_log = ""

    if local_path and os.path.exists(local_path):
        for readme_nome in ["README.md", "README_ESTUDIO.md", "STATUS_ESTUDIOHC.md", "readme.md"]:
            p_readme = os.path.join(local_path, readme_nome)
            if os.path.exists(p_readme):
                try:
                    with open(p_readme, "r", encoding="utf-8") as f:
                        readme_content = f.read(4000)
                    break
                except Exception:
                    pass
                    
        for task_nome in ["task.md", "todo.md", "tasks.md", "implementation_plan.md"]:
            p_task = os.path.join(local_path, task_nome)
            if os.path.exists(p_task):
                try:
                    with open(p_task, "r", encoding="utf-8") as f:
                        tasks_content = f.read(4000)
                    break
                except Exception:
                    pass

        import subprocess
        # Verifica se o diretório do projeto é a raiz de um repositório git legítimo
        e_repo_git = False
        try:
            res = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=local_path, capture_output=True, text=True, timeout=3)
            # Normaliza os caminhos para comparação segura
            if res.returncode == 0 and os.path.realpath(res.stdout.strip()) == os.path.realpath(local_path):
                e_repo_git = True
        except Exception:
            pass

        if e_repo_git:
            try:
                res = subprocess.run(["git", "status", "--porcelain"], cwd=local_path, capture_output=True, text=True, timeout=5)
                git_status = res.stdout.strip()
            except Exception:
                pass

            try:
                res = subprocess.run(["git", "log", "-n", "5", "--oneline"], cwd=local_path, capture_output=True, text=True, timeout=5)
                git_log = res.stdout.strip()
            except Exception:
                pass
        else:
            git_status = "Este diretório não é a raiz de um repositório Git isolado."
            git_log = "Sem histórico (não é repositório Git)."

    CENTRAL_URL = "http://100.64.117.78:8585"
    payload = {
        "nome": nome,
        "readme": readme_content,
        "git_status": git_status,
        "git_log": git_log,
        "estacao": proj.get("estacao", estacao_local),
        "tasks_content": tasks_content
    }
    
    try:
        req = urllib.request.Request(
            f"{CENTRAL_URL}/api/projetos/gerar-relatorio",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=240) as resp:
            data_res = json.loads(resp.read().decode("utf-8"))
            print("✅ Sucesso ao obter resposta do servidor central para o projeto:", nome)
            return data_res
    except Exception as e:
        print("❌ Erro ao gerar relatório com o servidor central, usando fallback local:", e)
        import datetime
        status_geral = "Ativo (Em Desenvolvimento)" if git_status else "Parado / Estável"
        fallback_rel = f"""# Relatório de Estado — {nome} (Offline Fallback)

> ⚠️ **Aviso:** O servidor central de IA está temporariamente offline. Este relatório básico foi gerado localmente sem enriquecimento de IA.

### 📊 Estado Geral
* **Status:** {status_geral}
* **Estação:** {proj.get('estacao', estacao_local)}
* **Diretório:** `{local_path or 'Não configurado'}`
* **Última Atualização:** {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

### 🔄 Ações Recentes (Git Log)
```text
{git_log or 'Nenhum commit recente encontrado.'}
```

### ⚠️ Arquivos Modificados (Git Status)
```text
{git_status or 'Nenhum arquivo modificado.'}
```

### 📋 Tarefas Pendentes
{'- Extraído de task.md/todo.md' if tasks_content else '- Nenhuma tarefa documentada.'}
"""
        return {
            "ok": False,
            "preview": "Servidor central offline.",
            "relatorio": fallback_rel
        }


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

        if path == "/api/projetos/relatorio":
            query = parse_qs(parsed.query)
            nome = query.get("nome", [""])[0]
            if not nome:
                return self.send_json({"erro": "Nome do projeto não fornecido"}, 400)
            res = gerar_relatorio_local(nome)
            return self.send_json(res)

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
