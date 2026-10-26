# Orquestrador Central EstudioHC e Failover de Contingência Implementation Plan

> **Para a Equipe de Desenvolvimento e Agentes:** SUB-SKILL OBRIGATÓRIA: Utilize `superpowers:subagent-driven-development` ou `superpowers:executing-plans` para implementar este plano tarefa por tarefa. As etapas utilizam sintaxe de checkbox (`- [ ]`) para rastreamento no ledger.

**Goal:** Consolidar o `Apps/EstudioHC-Memory-Suite` como orquestrador único e memória central 24/7 de toda a malha Tailscale, estabelecendo a VPS Contabo como Hub principal permanente, o Servidor Local 32GB como Laboratório de Desenvolvimento sob demanda e Reserva de Contingência Imediata (Cold Standby com Auto-Boot e Auto-Assume), e os cofres do Obsidian nas estações (Windows e Linux) como coletores locais de notas, telemetria e agendas locais sincronizadas.

**Architecture:** A VPS Contabo (`100.64.117.78`) opera 24/7 provendo API (`:5050` HTTPS), MCP SSE (`:5051`), ChromaDB (`:8765`), Sync-Connect (`:5052`), Dashboard (`:8585`) e SQLite mestre (`estudiohc.db`). O Servidor Local EstudioHC (`100.107.208.50`, 32GB RAM) funciona como Laboratório de Desenvolvimento ligado apenas poucas horas para economia de energia; ao ser ligado, se a VPS estiver offline, assume 100% da stack e da rede via DNS canônico (`hub.estudiohc`) com failback sem perda de dados. O Obsidian no Windows e Linux opera como coletor ativo de arquivos Markdown, diários, telemetria (ActivityWatch + Git) e sincronização bidirecional de agendas locais com a API central. Cada início, progresso e conclusão de tarefa atualiza automaticamente o repositório remoto via ledger de controle de versão.

**Tech Stack:** Python 3.11/3.12, FastAPI, SQLAlchemy, SQLite (WAL mode), ChromaDB SSE, FastMCP SSE, Systemd, Tailscale, Rsync, Obsidian, Watchdog.

---

## 📐 Diretrizes Globais e Premissas de Engenharia

1. **Hierarquia de Servidores e Economia de Energia**:
   - **VPS Contabo (`100.64.117.78`)**: Servidor Principal Absoluto 24/7. Hospeda a memória mestre, banco SQLite e endpoints de agentes ininterruptamente.
   - **Servidor Local EstudioHC (`100.107.208.50`, 32GB RAM)**: Ambiente de Desenvolvimento e Laboratório de Processamento Pesado (Ollama, fine-tuning, embeddings pesados). Para economia de energia residencial, é ligado apenas poucas horas durante o uso ativo. Quando ligado em contingência (VPS offline), assume imediatamente como servidor reserva.
2. **Obsidian como Coletor Local Ativo**:
   - O Obsidian Desktop nas estações de trabalho (`win-x99` e `linux-i5`) atua como o coletor local de notas, tarefas, resumos e diários.
   - Uma bridge local de ingestão monitora os arquivos `.md` e transmite as novidades para a API central (`POST /api/nota`) e para o ChromaDB (`doc_add`).
3. **Agendas Locais das Estações no Obsidian**:
   - Cada estação mantém sua agenda de tarefas e prioridades sincronizada via arquivo local `00 - Painel/Agenda.md` e diários `02 - Diário/`, integrada bidirecionalmente com os endpoints de agenda da suíte central (`POST /api/agenda` e `GET /api/agenda`).
4. **Automação do Ciclo de Vida de Tarefas no Repositório (Ledger Git)**:
   - Toda tarefa executada pela equipe ou por agentes de IA deve registrar seu ciclo de vida no repositório remoto:
     - **Início da Tarefa**: Commit e push automático no repositório marcando a tarefa como `[IN_PROGRESS]`.
     - **Andamento**: Commits intermediários documentando alterações atômicas.
     - **Conclusão**: Execução de testes de fumaça / verificação, commit com tag `[COMPLETED]` e push para a branch `master`.

---

## 🗺️ Mapa de Arquitetura e Roteamento de Rede

```mermaid
flowchart TD
    subgraph Estacoes["Estações de Trabalho (Coletores Locais Ativos)"]
        Win["Windows win-x99\n(Obsidian Coletor + OMP)"]
        Linux["Linux linux-i5\n(Obsidian Coletor + Agy)"]
        Bridge["Obsidian Ingestion Bridge\n(Watchdog -> API :5050 / doc_add)"]
        AgendaLocal["Agenda da Estação\n(00 - Painel/Agenda.md)"]
    end

    subgraph DNS["Resolução Canônica de Host"]
        HostPointer["hub.estudiohc\n(Hosts File / Tailscale IP)"]
    end

    subgraph Contabo["Nó Primário 24/7 (VPS Contabo : 100.64.117.78)"]
        C_API["API Central :5050 HTTPS"]
        C_MCP["MCP SSE :5051"]
        C_Chroma["ChromaDB :8765"]
        C_DB[("estudiohc.db (Mestre)")]
    end

    subgraph LocalServer["Reserva & Dev (Servidor Local 32GB : 100.107.208.50)"]
        L_API["API Central :5050 HTTPS"]
        L_MCP["MCP SSE :5051"]
        L_Chroma["ChromaDB :8765"]
        L_DB[("estudiohc.db (Espelho / Assume)")]
        AutoAssume["Daemon de Assunção e Reconciliação"]
    end

    Win --> Bridge
    Linux --> Bridge
    Win --> AgendaLocal
    Linux --> AgendaLocal
    AgendaLocal -->|"Sincronização /api/agenda"| HostPointer
    Bridge --> HostPointer
    Win -->|"OMP / Agentes"| HostPointer
    Linux -->|"Agy / Agentes"| HostPointer

    HostPointer -->|"Normal 24/7 (100.64.117.78)"| C_API
    HostPointer -->|"Normal 24/7 (100.64.117.78)"| C_MCP

    HostPointer -.->|"Contingência / Failover (100.107.208.50)"| L_API
    HostPointer -.->|"Contingência / Failover (100.107.208.50)"| L_MCP

    C_DB ===|"Replicação Periódica (Snapshot/Rsync)"|===> L_DB
    C_Chroma ===|"Replicação Vetorial"|===> L_Chroma
    L_DB -.->|"Reconciliação Reversa no Failback"|.- C_DB
```

---

## 📋 Tarefas Detalhadas de Implementação

### FASE 1: Paridade Completa de Serviços no Servidor Local (`100.107.208.50`)

- [ ] **Tarefa 1.1: Provisionamento de Unit Files Systemd no Servidor Local**
  - Instalar e configurar os seguintes serviços em `/etc/systemd/system/`:
    - `estudiohc-api.service` (porta 5050 HTTPS, `apps/api`)
    - `estudiohc-mcp-sse.service` (porta 5051 SSE, `apps/mcp-memory`)
    - `chromadb-mcp.service` (porta 8765 SSE, `apps/chromadb-mcp`)
    - `estudiohc-sync-connect.service` (porta 5052 HTTP, `apps/sync-connect`)
    - `estudiohc-dashboard.service` (porta 8585 HTTP, `apps/dashboard`)
  - Verificar: `systemctl daemon-reload && systemctl status estudiohc-api estudiohc-mcp-sse chromadb-mcp`.

- [ ] **Tarefa 1.2: Configuração de Certificados TLS/SSL para Porta 5050 no Servidor Local**
  - Gerar par de chaves e certificado TLS com SANs (`hub.estudiohc`, `100.107.208.50`, `192.168.2.4`) em `/etc/estudiohc/ssl/`.
  - Verificar: `curl -sk https://100.107.208.50:5050/api/status` retornando `HTTP 200` e JSON de status.

- [ ] **Tarefa 1.3: Validação de Ambientes Virtuais e Dependências**
  - Garantir ambientes virtuais `.venv` atualizados em todas as subpastas da suíte no servidor local.
  - Habilitar auto-start no boot: `systemctl enable estudiohc-api estudiohc-mcp-sse chromadb-mcp estudiohc-sync-connect estudiohc-dashboard`.

---

### FASE 2: Obsidian como Coletor Local Ativo e Gestão de Agendas

- [ ] **Tarefa 2.1: Desenvolvimento da Bridge de Ingestão do Obsidian (`obsidian-collector`)**
  - Implementar script `scripts/obsidian_collector.py` monitorando os diretórios `01 - Notas/` e `02 - Diário/` das estações de trabalho Windows e Linux via `watchdog`.
  - Funcionalidade:
    - Extração de frontmatter (YAML) e corpo do Markdown.
    - Envio via HTTP para `POST https://hub.estudiohc:5050/api/nota`.
    - Chamada ao MCP `doc_add` para indexação semântica no ChromaDB (`docs_estudiohc`).

- [ ] **Tarefa 2.2: Sincronização e Gestão de Agendas das Estações no Obsidian**
  - Criar módulo de integração de agenda em `scripts/agenda_sync.py`:
    - Lê os eventos e tarefas agendadas em `00 - Painel/Agenda.md` e `02 - Diário/`.
    - Envia via `POST https://hub.estudiohc:5050/api/agenda`.
    - Atualiza os painéis das estações com os compromissos consolidados de toda a rede.

- [ ] **Tarefa 2.3: Telemetria de Atividades e Fechamento Diário**
  - Integrar os scripts de coleta do ActivityWatch e varredura de commits (`git log`) diretamente na nota `02 - Diário/YYYY-MM-DD.md`, enviando resumo automático para `POST /api/diario/{data}/resumo`.

---

### FASE 3: Replicação de Dados Contínua e Integridade (Master ➡️ Backup)

- [ ] **Tarefa 3.1: Pipeline de Snapshot Quente do SQLite e ChromaDB**
  - Criar script `/home/deploy/Apps/EstudioHC-Memory-Suite/scripts/replicate_to_local.sh` na VPS Contabo:
    - Backup quente atômico: `sqlite3 /data/estudiohc.db ".backup /tmp/estudiohc_snap.db"`.
    - Envio via Rsync: `rsync -avz /tmp/estudiohc_snap.db estudiohc@100.107.208.50:/home/estudiohc/Projetos/dev/EstudioHC-Memory-Suite/data/estudiohc.db`.
    - Envio de vetores: `rsync -avz /home/deploy/chroma_data/ estudiohc@100.107.208.50:/home/estudiohc/chroma_data/`.
  - Configurar timer systemd `estudiohc-replicate.timer` com execução a cada 30 minutos ou ao detectar o Servidor Local online.

- [ ] **Tarefa 3.2: Ativação de WAL Mode no Banco Mestre e Reserva**
  - Executar `PRAGMA journal_mode=WAL;` e `PRAGMA synchronous=NORMAL;` no `estudiohc.db` em ambos os servidores.

---

### FASE 4: Sistema de Assunção de Contingência e Failback Reverso

- [ ] **Tarefa 4.1: Script de Assunção Automática no Boot (`assume-master.sh`)**
  - No Servidor Local (`100.107.208.50`), criar script executado no boot:
    - Testa resposta da VPS Contabo (`curl -sk --connect-timeout 2 https://100.64.117.78:5050/api/status`).
    - Se a VPS responder: mantém serviços locais como ambiente de desenvolvimento e processamento sob demanda.
    - Se a VPS falhar: assume imediatamente como `MASTER_ATIVO`, iniciando os 5 serviços sobre o último snapshot replicado.

- [ ] **Tarefa 4.2: Scripts de Comutação Rápida nos Clientes (`switch-to-local` / `switch-to-contabo`)**
  - Atualizar scripts nos clientes Windows e Linux (`C:\Users\helcio\scripts` e `~/scripts`):
    - Altera o apontamento de `hub.estudiohc` no arquivo `hosts`.
    - Testa conectividade imediata com as portas `:5050` e `:5051` confirmando comutação.

- [ ] **Tarefa 4.3: Script de Reconciliação Reversa (Failback)**
  - Criar `/home/estudiohc/scripts/failback-to-contabo.sh`:
    - Antes de desligar o servidor local ou retornar a VPS Contabo para a produção:
      1. Extrai memórias e notas inseridas durante a contingência (`WHERE timestamp > data_queda`).
      2. Reinjeta os deltas na VPS Contabo via API REST.
      3. Comuta o DNS `hub.estudiohc` de volta para a VPS (`100.64.117.78`).
      4. Coloca o Servidor Local novamente em repouso.

---

### FASE 5: Automação do Ciclo de Vida de Tarefas no Repositório (Git Lifecycle Ledger)

- [ ] **Tarefa 5.1: Implementação do Script de Ledger de Tarefas (`task_ledger.sh`)**
  - Criar utilitário no repositório:
    - `./scripts/task_ledger.sh start <task-id> <descricao>`: atualiza `progress.md`, marca tarefa como `[IN_PROGRESS]`, efetua commit e push automático para `origin master`.
    - `./scripts/task_ledger.sh progress <task-id> <nota>`: commit intermediário de progresso.
    - `./scripts/task_ledger.sh done <task-id> <evidencias>`: executa suíte de testes de validação, atualiza status para `[COMPLETED]`, efetua commit e push para `origin master`.

---

### FASE 6: Testes Práticos e Simulação de Pane (Chaos Test)

- [ ] **Tarefa 6.1: Teste de Assunção e Failover**
  - Simular parada da VPS (`systemctl stop estudiohc-api`), ligar/ativar o Servidor Local e comutar o cliente Windows para o servidor local.
  - Verificar: chamadas de API e MCP operando normalmente em `hub.estudiohc`.
- [ ] **Tarefa 6.2: Teste de Ingestão do Coletor Obsidian**
  - Criar nota de teste no Obsidian e validar persistência automática no SQLite central e no ChromaDB.
- [ ] **Tarefa 6.3: Teste de Failback Completo**
  - Reativar a VPS Contabo, executar o failback e certificar zero perda de registros e dados.
