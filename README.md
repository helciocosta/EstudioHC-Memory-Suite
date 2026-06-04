# 🎙️ EstudioHC Memory Suite & Hub Central

Bem-vindo ao **EstudioHC Memory Suite**, a infraestrutura de contexto e persistência de memória centralizada projetada especificamente para o ecossistema de agentes de IA (**Hermes Agent, Claude Portable, OpenCloud, Modelos Locais**) de **Helcio O. Costa**.

Este ecossistema unifica a memória de trabalho, tarefas pendentes, notas de diário e agenda de compromissos físicas, sincronizando-as de forma inteligente entre múltiplas estações de trabalho locais e o servidor central de nuvem **Contabo** por meio de uma VPN segura **Tailscale**.

## 🎯 Visão Centralizada

O **Servidor Contabo (100.64.117.78)** atua como o cérebro central e projeto orquestrador do ecossistema EstudioHC, fornecendo:

- **Memória Persistente MCP** (porta 5050): Armazenamento permanente de fatos, contexto, estado dos agentes e histórico de desenvolvimento
- **Hub de Visualização** (porta 8585): Interface web premium para visualização de agenda em tempo real, status dos projetos, diários de trabalho e chat de IA integrado
- **Fonte Única de Verdade do Stack**: Todas as estações de trabalho são automaticamente alimentadas com:
  - Qual projeto ativo estamos trabalhando atualmente
  - Agenda unificada de compromissos e marcos importantes
  - Estado atual de todos os projetos do ecossistema
  - Notificações de atualizações e mudanças críticas
  - Documentação e especificações técnicas vigentes
- **Sincronização Automática via Tailscale**: Garante que independentemente da estação onde você trabalha (helcio-x99-b, amd-estudio-c2, estudio-x79, ou qualquer nova estação), você tenha conhecimento completo e atualizado do ecossistema

Cada desenvolvedor/equipe possui consciência completa e em tempo real da situação real do stack, agenda, projetos e atualizações, garantindo continuidade perfeita, colaboração eficaz e eliminação de informações desatualizadas.

---

## 🏗️ Arquitetura Unificada do Sistema

O repositório está organizado em subpastas focadas e com responsabilidades bem definidas:

```
EstudioHC-Memory-Suite/
├── dashboard/               # Interface Web Premium e Backend Local
│   ├── server.py            # Servidor HTTP local (porta 8585)
│   ├── index.html           # Dashboard HTML5/JS rico com glassmorphism
│   └── agenda.json          # Cache local de compromissos da estação
├── server/                  # Cérebro de Persistência MCP Central
│   ├── mcp_server.py        # API FastAPI HTTP (porta 5050 no Contabo)
│   ├── mcp_stdio_server.py  # Conector STDIO nativo para agentes locais
│   └── estudiohc_memory.db  # Banco de dados SQLite persistente
└── cli/                     # Utilitários de Terminal
    └── estudio              # Comando de boot e monitoramento global
```

---

## 🚦 Componentes do Stack

### 1. O Cérebro Central: MCP Memory Suite (`/server`)
Hospedado de forma permanente no servidor Contabo (`100.64.117.78`). 
- **Tecnologia:** FastAPI + SQLite (`estudiohc_memory.db`).
- **Porta:** `5050` (MCP central) e futuramente `8586` (Central API de sincronização avançada).
- **Serviço Systemd:** `estudiohc-memory.service` gerenciado remotamente.
- **Função:** Fornecer armazenamento permanente de fatos, memórias e tarefas para os agentes de IA via endpoints `/remember` e `/recall`.

### 2. O Painel Web Interativo (`/dashboard`)
Roda localmente em cada estação de trabalho para fornecer uma experiência visual premium.
- **Tecnologia:** Servidor HTTP Python nativo + HTML5 / CSS Vanilla moderno.
- **Porta:** `8585` (Acesso via `http://localhost:8585`).
- **Serviço Systemd:** `estudiohc-hub.service` local.
- **Destaques:** 
  * Integração nativa com o **Hermes Agent** via OpenRouter com fallback automático e silencioso para o **Claude Portable** ou **modelos locais** (via OpenCloud ou similar) quando necessário.
  * Diário diário de trabalho automatizado em markdown sincronizado com a home central.
  * Exibe em tempo real: projeto ativo no qual estamos trabalhando, agenda unificada de compromissos, status de todos os projetos do ecossistema e notificações de atualizações e mudanças importantes.

### 3. A Central de Comando CLI (`/cli`)
O utilitário `/usr/local/bin/estudio` é a interface de terminal que atua como ponto de partida diário.
- **Uso:** Basta digitar `estudio` no terminal.
- **Exibe:** Status de saúde dos daemons locais, latência da rede Tailscale para o Contabo, lista de tarefas pendentes no servidor e a próxima ação recomendada.

---

## 🚀 Instalação e Inicialização Rápida

### Passo 1 — Executar o Servidor de Memória (Remoto ou Local)
Para subir a API FastAPI de persistência de memória:
```bash
cd server
python3 -m venv mcp_env
source mcp_env/bin/activate
pip install -r requirements.txt
python3 -m uvicorn mcp_server:app --host 0.0.0.0 --port 5050
```

### Passo 2 — Subir o Painel Visual Local
Para expor a porta local `8585` e acessar os diários e o chat de IA:
```bash
cd dashboard
python3 server.py
```

### Passo 3 — Instalar o Comando CLI `estudio`
Para instalar globalmente a central de comando:
```bash
sudo cp cli/estudio /usr/local/bin/estudio
sudo chmod +x /usr/local/bin/estudio
```

---

## 🤖 Integração com Agentes de IA

O ecossistema EstudioHC prioriza uma abordagem **Python-first** e foca nos seguintes agentes de IA, integrados via MCP ou interfaces padronizadas:

- **Hermes Agent**: Agente principal de raciocínio e codificação (via OpenRouter)
- **Claude Portable**: Agente alternativo para tarefas que beneficiam do Claude (disponível localmente como aplicativo portátil)
- **OpenCloud**: Interface para orquestração de modelos locais quando necessária privacidade, autonomia ou funcionamento offline
- **Modelos Locais**: Utilizados via ferramentas como Ollama ou similares para tarefas específicas (ex: geração de código, análise de documentos, embeddings)

*Note: O antigravity-awesome-skills foi descontinuado; focamos em manter e melhorar os agentes acima mencionados, que são diretamente integrados ao fluxo de trabalho via MCP ou interfaces locais.*

---
*Documentação atualizada e auditada por Antigravity em 2026-05-17.*
