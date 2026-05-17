import time
import requests
import os
import json
import glob
import psutil
import socket
from datetime import date
# Configurações do ecossistema
MEMO_HUB_URL = "http://100.64.117.78:5050/remember"
RECALL_URL = "http://100.64.117.78:5050/recall/EstudioHC"
SILLY_TAVERN_LOGS = "/home/helcio/Apps/LocalAI/SillyTavern/data/default-user/chats"
KOBOLD_API_URL = "http://127.0.0.1:11434/v1/chat/completions"

# Caminhos do Diário e Dashboard
DIRETORIO_DIARIO = "/home/helcio/Apps/estudiohc-diario"
DASHBOARD_PATH = os.path.join(DIRETORIO_DIARIO, "PROJETOS_STATUS.md")

# Identidade da Máquina
HOSTNAME = socket.gethostname().upper()

AGENT_NAME = "Antigravity"
PROJECT_NAME = "EstudioHC"

def sync_to_memory(agent, project, content, category="chat"):
    data = {
        "agent_name": agent,
        "project": project,
        "content": content,
        "category": category
    }
    try:
        r = requests.post(MEMO_HUB_URL, json=data)
        if r.status_code == 200:
            print(f"[OK] Sincronizado: {content[:50]}...")
        else:
            print(f"[ERRO] Falha ao sincronizar: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"[ERRO] Servidor MCP offline: {e}")
        return False

# Armazenar a última modificação ou última linha lida para não repetir (simples)
last_processed_time = 0
last_processed_text = ""
known_chat_files = set()

# Controle de estado para Diário e Dashboard
last_dashboard_mtime = 0
last_diario_file = ""
last_diario_lines = 0

def check_diario_updates():
    """Monitora mudanças no Dashboard e no Log Diário"""
    global last_dashboard_mtime, last_diario_file, last_diario_lines
    
    # 1. Monitorar Dashboard de Projetos (PROJETOS_STATUS.md)
    if os.path.exists(DASHBOARD_PATH):
        mtime = os.path.getmtime(DASHBOARD_PATH)
        if mtime > last_dashboard_mtime:
            try:
                with open(DASHBOARD_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                    sync_to_memory(AGENT_NAME, PROJECT_NAME, content, category="dashboard")
                    print(f"[Dashboard] Sincronizado status dos projetos.")
                last_dashboard_mtime = mtime
            except Exception as e:
                print(f"Erro ao ler dashboard: {e}")

    # 2. Monitorar Log Diário Atual (YYYY-MM-DD_COMPLETO.txt)
    hoje = date.today().strftime("%Y-%m-%d")
    arquivo_hoje = os.path.join(DIRETORIO_DIARIO, f"{hoje}_COMPLETO.txt")
    
    if os.path.exists(arquivo_hoje):
        # Se mudou o arquivo (virou o dia)
        if arquivo_hoje != last_diario_file:
            last_diario_file = arquivo_hoje
            last_diario_lines = 0
            
        try:
            with open(arquivo_hoje, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > last_diario_lines:
                    new_content = "".join(lines[last_diario_lines:]).strip()
                    if new_content:
                        sync_to_memory(AGENT_NAME, PROJECT_NAME, new_content, category="daily_log")
                        print(f"[Diário] {len(lines) - last_diario_lines} novas linhas sincronizadas.")
                    last_diario_lines = len(lines)
        except Exception as e:
            print(f"Erro ao ler log diário: {e}")

def auto_inject_memory(filepath):
    """Busca memórias recentes e injeta como mensagem de sistema no novo chat"""
    try:
        r = requests.get(RECALL_URL, timeout=5)
        if r.status_code == 200:
            memories = r.json()
            if not memories:
                return
            
            summary = "\n".join([f"- {m['content']}" for m in memories[:5]])
            system_msg = {
                "name": "Sistema de Memória",
                "is_user": False,
                "is_system": True,
                "send_date": int(time.time() * 1000),
                "mes": f"--- CONTEXTO RECUPERADO (Continuar de Onde Parou) ---\nÚltimos acontecimentos:\n{summary}\n\nEscolha um ponto para continuar ou peça mais detalhes."
            }
            
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(system_msg) + "\n")
            print(f"[Memória] Contexto injetado com sucesso em: {os.path.basename(filepath)}")
    except Exception as e:
        print(f"Erro ao injetar memória: {e}")

def check_new_chats():
    """Monitora o diretório de chats do SillyTavern"""
    global last_processed_time
    global last_processed_text
    global known_chat_files
    
    if not os.path.exists(SILLY_TAVERN_LOGS):
        return

    list_of_files = glob.glob(os.path.join(SILLY_TAVERN_LOGS, '*.jsonl'))
    if not list_of_files:
        return
    
    # 1. Detectar novos arquivos de chat para injeção automática
    for filepath in list_of_files:
        if filepath not in known_chat_files:
            # Se o arquivo é novo, injeta a memória
            auto_inject_memory(filepath)
            known_chat_files.add(filepath)
        
    latest_file = max(list_of_files, key=os.path.getmtime)
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                last_msg = json.loads(lines[-1])
                msg_text = last_msg.get('mes', '')
                is_user = last_msg.get('is_user', False)
                send_date = last_msg.get('send_date', 0)
                
                # Previne envio duplicado
                if msg_text and msg_text != last_processed_text:
                    prefix = "Usuário: " if is_user else "AI: "
                    sync_to_memory(AGENT_NAME, PROJECT_NAME, prefix + msg_text)
                    last_processed_text = msg_text
    except Exception as e:
        print(f"Erro ao ler chat: {e}")

def gather_system_context():
    """Coleta o contexto atual do sistema usando psutil"""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    
    # Obtém os 5 processos que mais consomem CPU
    processes = []
    # psutil.process_iter requires specific attributes or we can use as_dict
    for proc in sorted(psutil.process_iter(['name', 'cpu_percent']), key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:5]:
        if proc.info['name'] not in ['System Idle Process', 'idle']:
            cpu_val = proc.info['cpu_percent'] or 0
            processes.append(f"{proc.info['name']} ({cpu_val}%)")
    
    context = f"CPU: {cpu}%, RAM: {ram}%\nTop Processos: {', '.join(processes)}"
    return context

def evaluate_with_llm(context):
    """Envia o contexto ao KoboldCpp para raciocínio"""
    system_prompt = (
        "Você é um observador invisível do sistema operando em background. "
        "Analise os dados de CPU, RAM e os principais processos ativos. "
        "Responda APENAS com uma frase curta em Português resumindo a provável atividade atual do usuário. "
        "Se não houver nada relevante, processos comuns do sistema (ex: chrome, systemd, plasmashell) com baixo uso, "
        "ou se o sistema estiver ocioso, responda EXATAMENTE a palavra 'OCIOSO'."
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Contexto do Sistema:\n{context}"}
        ],
        "temperature": 0.2,
        "max_tokens": 50
    }
    
    try:
        r = requests.post(KOBOLD_API_URL, json=payload, timeout=10)
        if r.status_code == 200:
            result = r.json()['choices'][0]['message']['content'].strip()
            return result
        return None
    except Exception as e:
        print(f"[ERRO] Falha ao conectar ao KoboldCpp (verifique se ele está rodando na porta 5001).")
        return None

if __name__ == "__main__":
    print(f"--- Orquestrador de Memória EstudioHC Ativo [{HOSTNAME}] ---")
    
    # Registrar início de sessão
    sync_to_memory(AGENT_NAME, "Ecosystem", f"SESSÃO INICIADA: {HOSTNAME}", category="session")
    
    print(f"Monitorando: {SILLY_TAVERN_LOGS}")
    print(f"Enviando para: {MEMO_HUB_URL}")
    print(f"Raciocínio via: {KOBOLD_API_URL}")
    
    last_llm_eval_time = 0
    EVAL_INTERVAL = 120 # Avaliar sistema a cada 2 minutos
    
    while True:
        current_time = time.time()
        
        # 1. Manter a leitura de logs do SillyTavern
        check_new_chats()

        # 2. Monitorar Diário e Dashboard
        check_diario_updates()
        
        # 3. Raciocínio Autônomo
        if current_time - last_llm_eval_time >= EVAL_INTERVAL:
            context = gather_system_context()
            # print(f"[Sistema] Contexto: {context}") # Descomente para debug detalhado
            
            insight = evaluate_with_llm(context)
            if insight and insight.upper() != "OCIOSO" and "OCIOSO" not in insight.upper():
                print(f"[Insight] {insight}")
                sync_to_memory(AGENT_NAME, PROJECT_NAME, f"Atividade: {insight}", category="fact")
                
            last_llm_eval_time = current_time

        time.sleep(5)

