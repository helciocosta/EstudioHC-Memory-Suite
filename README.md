# EstudioHC Context & Memory Hub

Este projeto é um ecossistema de memória persistente para agentes de IA (Gemini, Vibe, Antigravity, SillyTavern). Ele permite que você tenha um histórico unificado de tarefas e contextos que te segue entre diferentes terminais e computadores.

## Estrutura do Projeto

- **Memory Hub (FastAPI + SQLite):** Servidor central que armazena fatos e tarefas.
- **Agent Orchestrator:** Script que monitora atividades do PC e chats do SillyTavern.
- **Dashboard CLI:** Interface interativa para escolher tarefas ao abrir o terminal.
- **MCP Bridge:** Integração com agentes via Protocolo MCP (STDIO).

## Instalação

### 1. Servidor de Memória (MCP Host)
```bash
cd GeminiMCPHost
python3 -m venv mcp_env
source mcp_env/bin/activate
pip install -r requirements.txt
python3 -m uvicorn mcp_server:app --host 0.0.0.0 --port 5050
```

### 2. Orquestrador e Dashboard
```bash
cd LocalAI
pip install psutil requests
# Adicione ao seu .bashrc para o Dashboard iniciar com o terminal:
echo "python3 $(pwd)/dashboard.py" >> ~/.bashrc
```

## Sincronização entre PCs

Para que sua memória seja a mesma em todos os computadores, você tem duas opções:

### Opção A: Sincronização de Arquivos (Recomendado)
Use o **Syncthing** (ou Dropbox/Google Drive) para sincronizar as seguintes pastas/arquivos entre seus PCs:
1. `~/Apps/GeminiMCPHost/cgdoc_memory.db` (O banco de dados central)
2. `~/.gemini/GEMINI.md` (As instruções e contexto atual do agente)

Isso garantirá que, ao mudar de PC, o banco de dados e o contexto do Gemini estejam idênticos.

### Opção B: Servidor Centralizado
1. Instale o **Memory Hub** em um servidor Linux (ou em um dos PCs que fique sempre ligado).
2. Nos outros PCs, aponte a variável `MEMO_HUB_URL` no `agent_orchestrator.py` e `dashboard.py` para o IP desse servidor central (ex: `http://192.168.1.50:5050`).
3. Use o **Tailscale** para acessar o servidor de forma segura fora de casa.

## Integração com Agentes

### Gemini CLI
Adicione o servidor ao seu `~/.gemini/settings.json`:
```json
"estudiohc-memory": {
  "command": "/caminho/para/python3",
  "args": ["/caminho/para/mcp_stdio_server.py"]
}
```

### Vibe
Adicione ao seu `~/.vibe/config.toml`:
```toml
mcp_servers = ["python3 /caminho/para/mcp_stdio_server.py"]
```
