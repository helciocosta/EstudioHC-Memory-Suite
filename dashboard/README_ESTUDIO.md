# 🎙️ EstudioHC Hub — Guia de Instalação por Estação

> **Servidor central:** `deploy@100.64.117.78` (Tailscale)  
> **Versão:** 2026-05-16  
> **Estações conhecidas:** helcio-x99-b · amd-estudio-c2 · estudio-x79

---

## 📋 Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Instalação rápida em nova estação](#instalação-rápida)
3. [O comando `estudio`](#o-comando-estudio)
4. [Atualizar memória de tarefas e projetos](#atualizar-memória)
5. [Verificar status do sistema](#verificar-status)
6. [Estrutura dos arquivos](#estrutura)
7. [Solução de problemas](#problemas)

---

## Pré-requisitos

Antes de instalar em uma nova estação, confirme:

```bash
# 1. Tailscale instalado e conectado
tailscale status | grep vmi2968998

# 2. SSH funcionando para o servidor
ssh deploy@100.64.117.78 "echo OK"

# 3. Python 3 disponível
python3 --version
```

---

## Instalação Rápida

Execute estes comandos em qualquer nova estação:

### Passo 1 — Instalar o comando `estudio`

```bash
# Baixar o script do servidor central
scp deploy@100.64.117.78:/home/deploy/.local/bin/estudio /tmp/estudio

# Instalar globalmente
sudo cp /tmp/estudio /usr/local/bin/estudio
sudo chmod +x /usr/local/bin/estudio

# Testar
estudio
```

### Passo 2 — Instalar o Hub local (porta 8585)

```bash
# Criar pasta do Hub
mkdir -p ~/Apps/EstudioHC-Hub
cd ~/Apps/EstudioHC-Hub

# Baixar server.py e index.html do servidor
scp deploy@100.64.117.78:/home/deploy/Apps/EstudioHC-Hub/server.py ./
scp deploy@100.64.117.78:/home/deploy/Apps/EstudioHC-Hub/index.html ./

# Criar pasta de diários
mkdir -p ~/Apps/estudiohc-diario
```

> **Nota:** Quando a Fase 1 do projeto central estiver concluída, o `server.py`
> já estará configurado para buscar agenda e projetos diretamente do servidor.
> Por enquanto, o Hub funciona localmente com fallback.

### Passo 3 — Criar serviço systemd para o Hub

```bash
# Criar arquivo de serviço
sudo tee /etc/systemd/system/estudiohc-hub.service << 'EOF'
[Unit]
Description=EstudioHC Hub — Interface local porta 8585
After=network.target

[Service]
Type=simple
User=SEU_USUARIO
WorkingDirectory=/home/SEU_USUARIO/Apps/EstudioHC-Hub
ExecStart=/usr/bin/python3 /home/SEU_USUARIO/Apps/EstudioHC-Hub/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Substituir SEU_USUARIO pelo usuário real (ex: helcio)
sudo sed -i "s/SEU_USUARIO/$(whoami)/g" /etc/systemd/system/estudiohc-hub.service

# Ativar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable --now estudiohc-hub

# Verificar
systemctl status estudiohc-hub
```

### Passo 4 — Abrir o Hub no navegador

```bash
xdg-open http://localhost:8585
# ou simplesmente abra: http://localhost:8585
```

---

## O Comando `estudio`

O comando `estudio` é a **central de informações** do sistema. Rode ao ligar qualquer estação.

```bash
estudio           # Mostra status, serviços e próximas tarefas
estudio --plano   # Mostra o plano completo com todas as tarefas
```

**O que ele exibe:**
- ● Serviços locais (Hub, KoboldCpp)
- ● Status do servidor central (Tailscale)
- ○ Tarefas pendentes buscadas do servidor
- ▶ Próximo passo recomendado

---

## Atualizar Memória

### Marcar uma tarefa como concluída no servidor

```bash
# Acessar o servidor
ssh deploy@100.64.117.78

# Editar o arquivo de status (marcar [ ] como [x])
nano /home/deploy/STATUS_ESTUDIOHC.md

# Ou usando sed para marcar a primeira tarefa pendente como feita:
sed -i '0,/- \[ \]/s/- \[ \]/- \[x\]/' /home/deploy/STATUS_ESTUDIOHC.md
```

### Adicionar nova tarefa pendente

```bash
ssh deploy@100.64.117.78 \
  "echo '- [ ] DESCRICAO DA TAREFA' >> /home/deploy/STATUS_ESTUDIOHC.md"
```

### Sincronizar memória do Hermes Agent com o servidor

```bash
# Salvar memória atual do Hermes no servidor
hermes memory export 2>/dev/null | \
  ssh deploy@100.64.117.78 "cat > /home/deploy/Apps/EstudioHC-Memory-Suite/server/hermes_memory_$(hostname)_$(date +%Y%m%d).md"

# Ou salvar o arquivo USER.md do Hermes
scp ~/.hermes/memories/USER.md \
  deploy@100.64.117.78:/home/deploy/Apps/EstudioHC-Memory-Suite/memories/USER_$(hostname).md
```

### Salvar nota rápida no servidor (qualquer estação)

```bash
# Adicionar nota ao diário central
ssh deploy@100.64.117.78 \
  "echo '[$(date \"+%Y-%m-%d %H:%M\") - $(hostname)] NOTA AQUI' >> /home/deploy/DIARIO_CENTRAL.md"

# Alias útil — adicionar ao ~/.bashrc:
alias nota='function _nota() { ssh deploy@100.64.117.78 "echo \"[\$(date +\"%Y-%m-%d %H:%M\") - $(hostname)] \$*\" >> /home/deploy/DIARIO_CENTRAL.md" && echo "✅ Nota salva"; }; _nota'
```

### Atualizar status de projeto

```bash
ssh deploy@100.64.117.78 \
  "cat >> /home/deploy/STATUS_ESTUDIOHC.md << EOF

### Atualização $(date '+%Y-%m-%d') — $(hostname)
- STATUS: DESCREVA O QUE FOI FEITO
EOF"
```

---

## Verificar Status

### Visão rápida (local)
```bash
estudio
```

### Ver todas as tarefas pendentes
```bash
ssh deploy@100.64.117.78 "grep '\- \[ \]' /home/deploy/STATUS_ESTUDIOHC.md"
```

### Ver tarefas concluídas
```bash
ssh deploy@100.64.117.78 "grep '\- \[x\]' /home/deploy/STATUS_ESTUDIOHC.md"
```

### Ver plano completo no servidor
```bash
ssh deploy@100.64.117.78 "cat /home/deploy/STATUS_ESTUDIOHC.md"
# ou:
estudio --plano
```

### Ver diário central
```bash
ssh deploy@100.64.117.78 "cat /home/deploy/DIARIO_CENTRAL.md 2>/dev/null || echo 'Sem entradas ainda'"
```

### Ver quais estações estão online (Tailscale)
```bash
tailscale status
```

### Verificar serviços no servidor
```bash
ssh deploy@100.64.117.78 "
  echo '=== Hub ===' && systemctl is-active estudiohc-hub 2>/dev/null || echo nao-instalado
  echo '=== Central API ===' && systemctl is-active estudiohc-central 2>/dev/null || echo nao-instalado
  echo '=== MCP Memory ===' && systemctl is-active estudiohc-memory 2>/dev/null || echo nao-instalado
  echo '=== KoboldCpp ===' && systemctl is-active koboldcpp 2>/dev/null || echo nao-instalado
  echo '=== Porta 5050 ===' && ss -tlnp | grep ':5050' || echo offline
  echo '=== Porta 8586 ===' && ss -tlnp | grep ':8586' || echo offline
"
```

---

## Estrutura

```
Servidor Contabo (100.64.117.78)
├── /home/deploy/
│   ├── STATUS_ESTUDIOHC.md          ← Plano mestre + tarefas pendentes
│   ├── DIARIO_CENTRAL.md            ← Notas de todas as estações
│   ├── README_ESTUDIO.md            ← Este arquivo
│   └── Apps/
│       ├── EstudioHC-Memory-Suite/  ← MCP memória (FastAPI + SQLite)
│       │   └── server/
│       │       ├── mcp_server.py    ← API (porta 5050)
│       │       └── estudiohc_memory.db
│       ├── pc_local_config/         ← Configurações de hardware por estação
│       └── antigravity-awesome-skills/

Cada Estação Local
├── ~/Apps/EstudioHC-Hub/
│   ├── server.py                    ← Backend Hub (porta 8585)
│   └── index.html                   ← Interface web
├── ~/Apps/estudiohc-diario/
│   ├── PROJETOS_STATUS.md           ← Projetos mapeados localmente
│   └── YYYY-MM-DD_COMPLETO.txt      ← Diários locais
├── ~/.hermes/                       ← Hermes Agent (IA principal)
│   ├── config.yaml                  ← Modelo: Nemotron 120B
│   └── memories/USER.md             ← Memória pessoal
└── /usr/local/bin/estudio           ← Comando de status global
```

---

## Tarefas Pendentes do Projeto Central

Consulte sempre a versão atualizada no servidor:

```bash
estudio --plano
```

**Resumo das fases:**

| Fase | Descrição | Status |
|------|-----------|--------|
| **Fase 1** | API Central no Contabo (agenda, notas, projetos, tarefas, estações) | ⏳ Pendente |
| **Fase 2** | Hub local sincronizando com servidor central | ⏳ Pendente |
| **Fase 3** | Frontend multi-estação (Hermes no chat, dots de status, banner) | ⏳ Pendente |

---

## Problemas

### Tailscale não conecta
```bash
sudo tailscale up
tailscale status
```

### Hub não inicia
```bash
systemctl status estudiohc-hub
journalctl -u estudiohc-hub -n 20
# Reiniciar:
sudo systemctl restart estudiohc-hub
```

### `estudio` não encontrado
```bash
scp deploy@100.64.117.78:/home/deploy/.local/bin/estudio /tmp/estudio
sudo cp /tmp/estudio /usr/local/bin/estudio && sudo chmod +x /usr/local/bin/estudio
```

### MCP Memory Suite parado no servidor
```bash
ssh deploy@100.64.117.78 "
  cd /home/deploy/Apps/EstudioHC-Memory-Suite/server
  source mcp_env/bin/activate
  nohup uvicorn mcp_server:app --host 0.0.0.0 --port 5050 > mcp_server.log 2>&1 &
  echo PID: \$!
"
```

---

*Documento mantido no servidor central. Última atualização: 2026-05-16 — helcio-x99-b*
