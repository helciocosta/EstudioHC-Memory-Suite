#!/usr/bin/env python3
"""
Inicializa e popula tabelas vazias do SQLite EstudioHC
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/home/helcio/Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. ESTACOES - registrar estações conhecidas
estacoes = [
    ("helcio-x99-b", "100.122.75.73", "active"),
    ("estudiohc", "100.107.208.50", "active"),
    ("vmi2968998", "100.64.117.78", "active"),
    ("luizanoot", "100.97.197.7", "active"),
    ("esutdiohc-i5-1", "100.97.90.121", "offline"),
    ("estudio-x79", "100.64.48.115", "offline"),
    ("estudiohc-x79g", "100.94.239.93", "offline"),
    ("pc062858521", "100.72.65.78", "offline"),
]

for hostname, ip, status in estacoes:
    cursor.execute("""
        INSERT OR REPLACE INTO estacoes (hostname, ip_tailscale, ultimo_ping, status)
        VALUES (?, ?, ?, ?)
    """, (hostname, ip, datetime.now().isoformat(), status))

print(f"✅ Estacoes: {len(estacoes)} inseridas")

# 2. TAREFAS - criar tarefas de exemplo para projetos principais
tarefas_exemplo = [
    (1, "Configurar busca semântica FAISS", "concluida", "alta", None),
    (1, "Integrar mem0 MCP server", "pendente", "alta", None),
    (1, "Ativar tabelas agenda/tarefas/notas", "em_andamento", "alta", datetime.now().date().isoformat()),
    (1, "Configurar ChromaDB para documentos", "pendente", "media", None),
    (7, "Atualizar scripts de backup", "pendente", "media", None),
    (7, "Documentar DNA do workspace", "pendente", "baixa", None),
    (8, "Criar CLI de sumarização LLM", "pendente", "alta", None),
    (8, "Integrar com EstudioHC Memory Suite", "pendente", "alta", None),
    (9, "Sincronizar skills antigravity", "pendente", "media", None),
    (6, "Finalizar parser de legacy systems", "pendente", "media", None),
]

for projeto_id, titulo, status, prioridade, data_limite in tarefas_exemplo:
    cursor.execute("""
        INSERT INTO tarefas (projeto_id, titulo, status, prioridade, data_limite)
        VALUES (?, ?, ?, ?, ?)
    """, (projeto_id, titulo, status, prioridade, data_limite))

print(f"✅ Tarefas: {len(tarefas_exemplo)} inseridas")

# 3. AGENDA - compromissos de exemplo
agenda_exemplo = [
    ("evt-001", datetime.now().date().isoformat(), "09:00", "Daily Sync - Memória Stack", "helcio-x99-b", "Revisar status da sincronização Local ↔ Contabo"),
    ("evt-002", (datetime.now() + timedelta(days=1)).date().isoformat(), "14:00", "Deploy mem0 MCP", "helcio-x99-b", "Deploy do servidor mem0 customizado"),
    ("evt-003", (datetime.now() + timedelta(days=2)).date().isoformat(), "10:00", "Review FAISS Index", "helcio-x99-b", "Validar qualidade da busca semântica"),
    ("evt-004", (datetime.now() + timedelta(days=3)).date().isoformat(), "15:00", "Backup Strategy", "helcio-x99-b", "Definir estratégia de backup cross-server"),
]

for id, data, hora, titulo, estacao, descricao in agenda_exemplo:
    cursor.execute("""
        INSERT OR REPLACE INTO agenda (id, data, hora, titulo, estacao, descricao, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (id, data, hora, titulo, estacao, descricao, datetime.now().isoformat()))

print(f"✅ Agenda: {len(agenda_exemplo)} inseridas")

# 4. NOTAS - notas de trabalho
notas_exemplo = [
    ("helcio-x99-b", "FAISS index rebuild concluído com 29 vetores. Busca semântica funcional.", datetime.now().isoformat()),
    ("helcio-x99-b", "Hybrid search RRF (k=60, kw=0.4, vec=0.6) ativo no memory_server.py", datetime.now().isoformat()),
    ("helcio-x99-b", "Sync bidirecional Local ↔ Contabo: projetos sincronizados (19), agent_memory push (122 regs).", datetime.now().isoformat()),
    ("helcio-x99-b", "KoboldCpp otimizado: threads=4, context=2048. Summarizer (11435) desabilitado.", datetime.now().isoformat()),
    ("helcio-x99-b", "Unsloth Desktop instalado mas travando. Focar em mem0 + SQLite tables + MCP custom.", datetime.now().isoformat()),
    ("helcio-x99-b", "ChromaDB MCP rodando no Contabo (porta 8765). Document layer ativo.", datetime.now().isoformat()),
]

for estacao, texto, timestamp in notas_exemplo:
    cursor.execute("""
        INSERT INTO notas (estacao, texto, timestamp)
        VALUES (?, ?, ?)
    """, (estacao, texto, timestamp))

print(f"✅ Notas: {len(notas_exemplo)} inseridas")

# 5. RESUMOS_DIARIOS - resumo de hoje
hoje = datetime.now().date().isoformat()
resumo_hoje = f"""# Resumo Diário - {hoje}

## Principais Realizações
- ✅ Busca semântica FAISS ativada (29 vetores, all-MiniLM-L6-v2)
- ✅ Hybrid search RRF funcional (keyword + vector)
- ✅ Sync bidirecional Local ↔ Contabo concluído
- ✅ 19 projetos sincronizados, 122 memórias no servidor central
- ✅ Memory server (MCP) rodando como systemd service
- ✅ ChromaDB MCP ativo no Contabo (porta 8765)

## Tabelas SQLite populadas
- estacoes: 8 estações registradas
- tarefas: 10 tarefas criadas
- agenda: 4 eventos agendados
- notas: 6 notas de trabalho
- resumos_diarios: 1 entrada

## Próximos Passos
1. Integrar mem0 MCP server (estudiohc-mcp-mem0)
2. Ativar Odoo MCP server (estudiohc-mcp-odoo)
3. Configurar agenda recorrente automática
4. Automatizar resumos diários via LLM
"""

cursor.execute("""
    INSERT OR REPLACE INTO resumos_diarios (data, resumo, agente, timestamp)
    VALUES (?, ?, ?, ?)
""", (hoje, resumo_hoje, "system_init", datetime.now().isoformat()))

print(f"✅ Resumo diário: {hoje} inserido")

conn.commit()
conn.close()
print("\n🎉 Todas as tabelas inicializadas e populadas com sucesso!")
