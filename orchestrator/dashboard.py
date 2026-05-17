import requests
import sys
import os

# Servidor de memória local (uvicorn rodando na porta 5050)
STATUS_URL = "http://localhost:5050/status/EstudioHC"
REMEMBER_URL = "http://localhost:5050/remember"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_dashboard():
    clear_screen()
    print("\033[95m" + "="*50 + "\033[0m")
    print("\033[1;97m" + "       HUB DE STATUS GLOBAL - PROJETO EstudioHC" + "\033[0m")
    print("\033[95m" + "="*50 + "\033[0m")

    try:
        r = requests.get(STATUS_URL, timeout=5)
        if r.status_code != 200:
            print("\033[91m[ERRO] Não foi possível carregar os dados.\033[0m")
            return
        
        data = r.json()
        
        print("\n\033[1;32m[✓] ÚLTIMAS TAREFAS CONCLUÍDAS:\033[0m")
        if not data['completed']:
            print("    Nenhuma tarefa concluída recentemente.")
        for task in data['completed']:
            print(f"    • {task}")

        print("\n\033[1;33m[!] TAREFAS PENDENTES:\033[0m")
        if not data['pending']:
            print("    Nenhuma tarefa pendente.")
        
        options = []
        for i, task in enumerate(data['pending'], 1):
            print(f"    {i}. {task}")
            options.append(task)
        
        print("\n" + "-"*50)
        print("\033[94mEscolha o número de uma tarefa para RETOMAR,\033[0m")
        print("\033[94mou pressione ENTER para apenas visualizar.\033[0m")
        
        choice = input("\n> ")
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                selected = options[idx]
                # Registrar a retomada na memória
                payload = {
                    "agent_name": "Dashboard_Terminal",
                    "project": "EstudioHC",
                    "content": f"USUÁRIO RETOMOU A TAREFA: {selected}",
                    "category": "fact"
                }
                requests.post(REMEMBER_URL, json=payload)
                
                # Sincronizar com a memória hierárquica do Gemini CLI
                gemini_md = os.path.expanduser("~/.gemini/GEMINI.md")
                try:
                    with open(gemini_md, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # Filtra linhas antigas de status para não acumular
                    new_lines = [l for l in lines if "STATUS ATUAL:" not in l and "## Contexto do Projeto" not in l]
                    new_lines.append("\n## Contexto do Projeto (EstudioHC)\n")
                    new_lines.append(f"- STATUS ATUAL: {selected}\n")
                    
                    with open(gemini_md, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                except Exception as e:
                    print(f"[AVISO] Não foi possível atualizar o GEMINI.md: {e}")

                print(f"\n\033[1;36m[OK] Foco definido para: {selected}\033[0m")
                print("Todos os seus agentes (Antigravity, Gemini, SillyTavern) já sabem disso.")
                sys.exit(0)

    except Exception as e:
        print(f"\033[91m[ERRO] Servidor de memória offline.\033[0m")

if __name__ == "__main__":
    show_dashboard()
