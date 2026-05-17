# 🎙️ EstudioHC Hub — Guia de Instalação por Estação

> **Servidor central:** `deploy@100.64.117.78` (Tailscale)  
> **Versão:** 2026-05-17  
> **Estações conhecidas:** helcio-x99-b · amd-estudio-c2 · estudio-x79

Este guia descreve os passos exatos para instalar e sincronizar o **EstudioHC Hub** (interface visual porta `8585` e comando CLI `estudio`) em qualquer nova estação de trabalho de Helcio, apontando para o cérebro central no servidor Contabo.

---

## 📋 Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Instalação Rápida em Nova Estação](#instalação-rápida)
3. [O comando CLI `estudio`](#o-comando-estudio)
4. [Atualizar Memória e Tarefas](#atualizar-memória)
5. [Verificar Status dos Serviços](#verificar-status)
6. [Estrutura Arquitetural de Pastas](#estrutura)
7. [Solução de Problemas](#problemas)

---

## Pré-requisitos

Antes de configurar uma nova estação de desenvolvimento, certifique-se de que possui os seguintes requisitos conectados e operacionais:

```bash
# 1. Conexão Tailscale ativa para o Contabo
tailscale status | grep 100.64.117.78

# 2. Conectividade SSH direta para o deploy central
ssh deploy@100.64.117.78 "echo OK"

# 3. Python 3 disponível no sistema local
python3 --version
```

---

## Instalação Rápida

Execute estes 4 passos simples em qualquer estação para integrá-la instantaneamente ao ecossistema:

### Passo 1 — Instalar o Comando CLI `estudio`

```bash
# Baixar o script oficial do servidor central
scp deploy@100.64.117.78:/home/deploy/Apps/EstudioHC-Memory-Suite/cli/estudio /tmp/estudio

# Instalar no path global do sistema
sudo cp /tmp/estudio /usr/local/bin/estudio
sudo chmod +x /usr/local/bin/estudio

# Testar
estudio
```

### Passo 2 — Clonar/Configurar o Repositório de Memória
A suíte agora roda de forma unificada e limpa em uma única pasta padrão:

```bash
# Criar diretório de aplicativos se não existir
mkdir -p ~/Apps
cd ~/Apps

# Clonar o repositório EstudioHC-Memory-Suite do servidor ou do GitHub
git clone deploy@100.64.117.78:/home/deploy/Apps/EstudioHC-Memory-Suite.git EstudioHC-Memory-Suite

# Criar pasta física de diários locais
mkdir -p ~/Apps/estudiohc-diario
```

### Passo 3 — Criar o Serviço Local Systemd para o Painel Web (Porta 8585)

O painel visual e a API local serão executados de forma ininterrupta em segundo plano via systemd.

```bash
# Criar arquivo de configuração de serviço
sudo tee /etc/systemd/system/estudiohc-hub.service << 'EOF'
[Unit]
Description=EstudioHC Hub — Interface local porta 8585
After=network.target

[Service]
Type=simple
User=SEU_USUARIO
WorkingDirectory=/home/SEU_USUARIO/Apps/EstudioHC-Memory-Suite/dashboard
ExecStart=/usr/bin/python3 /home/SEU_USUARIO/Apps/EstudioHC-Memory-Suite/dashboard/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Adaptar automaticamente o nome do usuário ativo (ex: helcio)
sudo sed -i "s/SEU_USUARIO/$(whoami)/g" /etc/systemd/system/estudiohc-hub.service

# Carregar, ativar e inicializar o daemon
sudo systemctl daemon-reload
sudo systemctl enable --now estudiohc-hub

# Verificar status do serviço
systemctl status estudiohc-hub
```

### Passo 4 — Abrir no Navegador

```bash
# Basta acessar o endereço no seu navegador de preferência:
http://localhost:8585
```

---

## O Comando CLI `estudio`

O utilitário `estudio` no terminal é seu companheiro diário. Sempre que iniciar o computador ou abrir o terminal pela manhã, rode o comando:

```bash
estudio           # Mostra status geral da máquina local e do servidor
estudio --plano   # Mostra o plano geral completo de tarefas pendentes
```

---

## Atualizar Memória

### Como marcar uma tarefa como feita no servidor

```bash
# Conectar-se ao servidor central
ssh deploy@100.64.117.78

# Editar o arquivo de tarefas pendentes (marcar [ ] como [x])
nano /home/deploy/STATUS_ESTUDIOHC.md
```

### Como salvar nota rápida no Diário Central via SSH

Você pode usar o alias `nota` no terminal para mandar observações para o arquivo consolidado de diários do servidor a partir de qualquer estação:

```bash
# Adicionar no ~/.bashrc de sua estação:
alias nota='function _nota() { ssh deploy@100.64.117.78 "echo \"[\$(date +\"%Y-%m-%d %H:%M\") - \$(hostname)] \$*\" >> /home/deploy/DIARIO_CENTRAL.md" && echo "✅ Nota salva no Diário Central"; }; _nota'

# Uso:
nota Concluída a validação de rotas do dashboard no PC local
```

---

## Verificar Status

### Verificar se as portas e daemons estão ativos no Servidor Contabo

```bash
ssh deploy@100.64.117.78 "
  echo '=== Status do MCP Memory Suite ===' && systemctl is-active estudiohc-memory
  echo '=== Status da Porta 5050 ===' && ss -tlnp | grep ':5050'
"
```

---

## Estrutura

```
Servidor Contabo (100.64.117.78)
├── /home/deploy/
│   ├── STATUS_ESTUDIOHC.md          ← Plano de ação central do EstudioHC
│   ├── DIARIO_CENTRAL.md            ← Consolidado de notas enviadas por todas as estações
│   └── Apps/
│       └── EstudioHC-Memory-Suite/  ← Repositório Git Centralizado
│           └── server/
│               ├── mcp_server.py    ← API FastAPI da memória (porta 5050)
│               └── estudiohc_memory.db
│
Estação Local (helcio-x99-b)
├── ~/Apps/EstudioHC-Memory-Suite/
│   ├── dashboard/                   
│   │   ├── server.py                ← Executa localmente (porta 8585)
│   │   └── index.html               ← Visualizador visual do hub
│   └── cli/
│       └── estudio                  ← Comando linkado em /usr/local/bin/estudio
└── ~/Apps/estudiohc-diario/         ← Pasta física de diários da estação
```

---

## Solução de Problemas

### Erro fatal do Git no Chrome na home (`fatal: unable to stat '.config/google-chrome...'`)
- **Causa:** O repositório git acidental `/home/helcio/.git` tenta rastrear o cache dinâmico do Chrome.
- **Solução:** Foi atualizado o arquivo `/home/helcio/.gitignore` com exclusões profissionais de sistema. O status agora executa instantaneamente.

### O painel local (porta 8585) não abre
- Verifique os logs do serviço do sistema:
  `journalctl -u estudiohc-hub -n 20 --no-pager`
- Reinicie o serviço local se necessário:
  `sudo systemctl restart estudiohc-hub`

---
*Documento de estação mantido e unificado. Última atualização: 2026-05-17 — helcio-x99-b*
