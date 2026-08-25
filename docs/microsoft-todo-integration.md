# Microsoft To Do — Integração com Sync Connect

## Visão Geral
O Sync Connect (porta 5052) recebe as tarefas do Microsoft To Do via:
- Postman/script local que envia para /sync/todo/tarefa
- Planejamento: conector direto MS Graph API (futuro)

## Como Funciona
1. Usuário cria/atualiza tarefas no Microsoft To Do (App Windows/Web)
2. Script local (sync-cliente.py) puxa tarefas e envia para Contabo:5052/sync/todo/tarefa
3. Sync Connect encaminha para EstudioHC API (5050) → BD central + ChromaDB

## API
POST /sync/todo/tarefa
Body: { "titulo": "string", "descricao": "string", "status": "pendente|em_andamento|concluido", "projeto": "string" }

## Microsof Graph API (futuro)
Para integração nativa: usar Microsoft Graph API + webhook
- GET /me/todo/lists -> listas
- GET /me/todo/lists/{id}/tasks -> tarefas
- POST webhook -> notificações em tempo real
