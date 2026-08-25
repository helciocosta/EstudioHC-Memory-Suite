# Gerenciamento de Projetos — EstudioHC

## Overview
Todo o gerenciamento de projetos do ecossistema EstudioHC é centralizado na API (5050):
- /api/projetos — CRUD de projetos
- /api/projetos/sync — sincronização externa (Vikunja, Ghost)
- /api/projetos/relatorio — geração de relatórios
- /api/projetos/gerar-relatorio — IA gera relatório via Ollama

## Stack Completo (Secretário Digital)
1. **Logseq** → Diários e notas pessoais → /api/diarios
2. **Joplin** → Notas técnicas e tarefas → /api/nota, /api/tarefas
3. **Vikunja** → Projetos e sprints → /api/projetos, /api/tarefas
4. **Ghost** → Publicação de relatórios e blog → /api/projetos/relatorio
5. **Microsoft To Do** → Tarefas do dia a dia → /api/tarefas

## Estações Tailscale Gerenciadas
| Estação | IP Tailscale | Sistema | Status |
|---------|-------------|---------|--------|
| esutdiohc-i5-1 | 100.97.90.121 | Windows | Ativa |
| estudiohc (Contabo) | 100.107.208.50 / 100.64.117.78 | Linux | Ativa |
| estudio-x79 | 100.64.48.115 | Windows | Offline |
| estudiohc-x79g | 100.94.239.93 | Linux | Offline |
| helcio-x99-b | 100.122.75.73 | Linux | Offline |
| luizanoot | 100.97.197.7 | Windows | Offline |
| pc062858521 | 100.72.65.78 | Linux | Offline |

## Workflow
1. Agente OMP local → MCP SSE (5051) → salva contexto na memória
2. Serviços do stack → Sync Connect (5052) → API Central → BD + ChromaDB
3. Contabo orquestra e responde mesmo quando PC local desliga
4. Tailscale mantém conectividade entre estações
