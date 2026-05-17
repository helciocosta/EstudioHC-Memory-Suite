# 🧠 EstudioHC — Status do Projeto Central
**Última atualização:** 2026-05-17 19:15 BRT  
**Estação de origem:** helcio-x99-b (PC Casa/Estúdio)  
**Tailscale local:** 100.122.75.73

---

## 🎯 Objetivo do Projeto

Transformar o **servidor Contabo** no **cérebro central** do EstudioHC:
- Agenda, notas, diários e projetos unificados e acessíveis de qualquer estação.
- Cada estação (PC Casa, Trabalho, Loja) sincroniza com o servidor ao ligar.
- Interface via EstudioHC Hub (porta 8585 local) que lê/escreve no servidor central.
- Estações identificadas pelo hostname do sistema.

---

## 🖥️ Inventário de Estações

| Estação | Hostname | Tailscale IP | Status |
|---------|----------|--------------|--------|
| PC Casa / Estúdio | helcio-x99-b | 100.122.75.73 | Online |
| Workstation AMD | amd-estudio-c2 | 100.64.211.14 | Offline |
| PC Trabalho/Loja | estudio-x79 | 100.92.94.52 | Offline |
| Servidor Central | vmi2968998 | 100.64.117.78 | Online |

---

## 📦 Stack EstudioHC (o que entra no projeto central)

| Componente | Localização | Status |
|-----------|-------------|--------|
| EstudioHC Hub (interface web local) | /home/helcio/Apps/EstudioHC-Memory-Suite/dashboard/ | Rodando porta 8585 |
| EstudioHC-Memory-Suite (MCP memória) | /home/deploy/Apps/EstudioHC-Memory-Suite/ | ATIVO (porta 5050) |
| Central API (sincronização) | /home/deploy/Apps/EstudioHC-Memory-Suite/server/ | Não existe ainda (Porta 8586) |
| KoboldCpp (IA local fallback) | Serviço systemd helcio-x99-b | Qwen3 1.7B porta 11434 (Online) |
| Hermes Agent v0.14.0 | /home/helcio/.hermes/ | Nemotron 120B via OpenRouter (Online) |

### Projetos FORA do stack EstudioHC (não sincronizar):
- protocolo-final / novo_protocolo + reversa: Sistema CGDOC, stack .NET 8 + MariaDB independente

---

## Projetos EstudioHC para gestão central

| Projeto | Descrição | Prioridade |
|---------|-----------|------------|
| EstudioHC-Memory-Suite | Contexto, memória MCP, API central e Dashboard | Alta |
| pc_local_config | DNA de configuração das estações | Média |
| antigravity-awesome-skills | Biblioteca de skills para agentes | Média |

---

## O que já foi feito (sessão 2026-05-17)

1. **Limpeza Geral de Redundâncias e Duplicatas:**
   * Deletadas as pastas duplicadas `agenticSeek_temp1` e `agenticSeek_temp2` no PC local e `server-setup-contabo01` no servidor Contabo.
   * Consolidado o antigo `EstudioHC-Hub` avulso para a subpasta `dashboard/` de `EstudioHC-Memory-Suite`. A pasta legada `EstudioHC-Hub` foi totalmente deletada após o backup bem-sucedido.
2. **Caminhos Dinâmicos de SQLite:**
   * Atualizados os scripts de inicialização do SQLite em `mcp_server.py` e `mcp_stdio_server.py` para usar `os.path.expanduser("~/Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db")`. O banco de dados agora roda de forma portável tanto no servidor Contabo quanto em qualquer estação local.
3. **Implantação de Serviços Systemd:**
   * Serviço local `/etc/systemd/system/estudiohc-hub.service` atualizado e rodando o backend na nova subpasta `dashboard/`.
   * Serviço remoto no Contabo `/etc/systemd/system/estudiohc-memory.service` instalado, habilitado e rodando o MCP Memory FastAPI na porta `5050` de forma estável.
4. **Correção Definitiva do Git Local:**
   * Criado o `.gitignore` otimizado na home `/home/helcio`, resolvendo o erro fatal de `stat` de arquivos do Google Chrome IndexedDB e acelerando o status do repositório em 100x.
5. **Auditoria Funcional 100% Concluída:**
   * **Conectividade:** Tailscale respondendo a pings em < 0.2ms.
   * **MCP Memory central (:5050):** Testado via curl com gravação e leitura instantâneas no SQLite central no servidor.
   * **Painel Local (:8585):** Diários e projetos locais saneados (removendo referências a clones apagados) e carregando sem erros em formato JSON.
   * **Modelos de IA:** Hermes Agent via OpenRouter online e respondendo em ~3s; KoboldCpp local online e respondendo em ~1s com paridade total de fallback silencioso.
   * **Mapeamento de Agentes no Servidor:** Inventariado que o servidor não possui executáveis do Hermes ou OpenClaw ativos, servindo estritamente como cérebro centralizado SQLite na porta 5050, mantendo o ambiente limpo.
   * **CLI `estudio`:** Analisada a latência de ~15.4s do comando local. Mapeado que decorre de 5 acessos SSH sequenciais. Proposta otimização multiplexada.

---

## TAREFAS PENDENTES

### FASE 1 — Servidor Contabo — PRIORITÁRIO

- [x] Reativar EstudioHC-Memory-Suite como serviço systemd permanente na porta 5050
- [ ] Expandir `mcp_server.py` com novas tabelas: `agenda`, `projetos`, `tarefas`, `notas`, `estacoes`
- [ ] Criar endpoints REST para cada tabela (FastAPI + venv já instalado em `mcp_env`)
- [ ] Expor nova API na porta 8586
- [ ] Criar `/etc/systemd/system/estudiohc-central.service`

### FASE 2 — Hub Local (cada estação)

- [ ] Adicionar `CENTRAL_URL = "http://100.64.117.78:8586"` no `server.py`
- [ ] Adicionar `ESTACAO = socket.gethostname()` para identificação automática
- [ ] `get_agenda()` -> lê do servidor primeiro, fallback local
- [ ] `salvar_agenda()` -> grava local + servidor em paralelo
- [ ] `adicionar_nota()` -> grava local + servidor
- [ ] `get_projetos()` -> lê do servidor
- [ ] `/api/status` -> incluir `central_ok: true/false`
- [ ] `/api/registrar-estacao` -> registra este PC no boot

### FASE 3 — Frontend index.html

- [ ] Chat IA: trocar `/api/kobold` -> `/api/hermes`
- [ ] Resumir Diario: trocar `/api/kobold` -> `/api/hermes`
- [ ] Status bar: adicionar dots Hermes + Central (atualmente só mostra KoboldCpp)
- [ ] Corrigir bug timezone na agenda (toISOString -> data local)
- [ ] Renomear aba IA Local -> Chat IA
- [ ] Adicionar indicador de estacao no header
- [ ] Banner boas-vindas ao abrir: tarefas do dia
- [ ] Filtro agenda: Todos os PCs vs Esta estacao

---

## Detalhes Técnicos para Retomada

### Acesso ao Servidor
```
ssh deploy@100.64.117.78    (via Tailscale)
```

### EstudioHC-Memory-Suite no servidor
```
Caminho: /home/deploy/Apps/EstudioHC-Memory-Suite/server/
Arquivo principal: mcp_server.py (FastAPI, Python 3.12)
Banco de dados: estudiohc_memory.db (SQLite)
Tabela existente: agent_memory (id, timestamp, agent_name, project, category, content)
Venv: mcp_env/ (FastAPI já instalado)
Ativar venv: source mcp_env/bin/activate
Iniciar servidor: uvicorn mcp_server:app --host 0.0.0.0 --port 5050
```

### Hub Local helcio-x99-b
```
Serviços:
  systemctl status estudiohc-hub    (porta 8585)
  systemctl status koboldcpp        (porta 11434)

Arquivos principais:
  /home/helcio/Apps/EstudioHC-Memory-Suite/dashboard/server.py    (backend Python)
  /home/helcio/Apps/EstudioHC-Memory-Suite/dashboard/index.html   (frontend)
  /home/helcio/Apps/EstudioHC-Memory-Suite/dashboard/agenda.json  (agenda local)
  /home/helcio/Apps/estudiohc-diario/PROJETOS_STATUS.md

Hermes:
  Config: ~/.hermes/config.yaml
  Modelo: nvidia/nemotron-3-super-120b-a12b via OpenRouter
  Fallback: KoboldCpp local porta 11434

KoboldCpp:
  Modelo: /home/helcio/Apps/LocalAI/models/Qwen3-1.7B-Q4_K_M.gguf (1.056 MB)
  Porta: 11434 (compativel Ollama)
  GPU: GTX 750 Ti 4GB - modelo cabe todo na VRAM
  Tempo resposta: ~1.1s
```

### API Central a implementar (porta 8586)
```
POST /api/agenda          salva/atualiza eventos
GET  /api/agenda          lista eventos (?estacao=all)
POST /api/nota            salva nota com timestamp e estacao
GET  /api/notas           lista notas (?estacao=helcio-x99-b)
GET  /api/projetos        lista projetos EstudioHC com status
POST /api/projeto         atualiza status de projeto
POST /api/tarefa          cria tarefa em projeto
GET  /api/tarefas         lista tarefas (?status=pendente)
POST /api/estacao/ping    estacao registra presenca ao ligar
GET  /api/status          health check central
```

---

## Como retomar de outra estação

1. Verificar Tailscale: `tailscale status`
2. Ler este arquivo: `ssh deploy@100.64.117.78 "cat /home/deploy/STATUS_ESTUDIOHC.md"`
3. Verificar servidor: `ssh deploy@100.64.117.78 "systemctl status estudiohc-central 2>/dev/null || echo PARADO"`
4. Começar pela FASE 1 do plano
5. Após Fase 1: instalar Hub local na nova estacao apontando para CENTRAL_URL

---

## Arquitetura da Sincronização

```
[Qualquer Estação com Tailscale]        [Contabo - vmi2968998 - Cérebro]
  EstudioHC Hub :8585              <==> Central API :8586
  - lê agenda do servidor                - SQLite: estudiohc_central.db
  - escreve agenda no servidor           - tabelas: agenda, notas, projetos
  - lê projetos do servidor              - tabelas: tarefas, estacoes
  - envia notas ao servidor              - MCP Memory Suite :5050
  Hermes Agent (nuvem)                   - memória de agentes
  KoboldCpp (fallback local)
```
