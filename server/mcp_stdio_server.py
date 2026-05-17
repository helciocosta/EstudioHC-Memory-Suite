import asyncio
import sqlite3
import os
from mcp.server.models import InitializationOptions
from mcp.server import Notification, Server
import mcp.types as types
from mcp.server.stdio import stdio_server

# Caminho do banco de dados
DB_PATH = "/home/helcio/Apps/EstudioHC-Memory-Suite/server/estudiohc_memory.db"

server = Server("estudiohc-memory")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="get_project_status",
            description="Recupera o status atual do projeto (tarefas pendentes e concluídas)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Nome do projeto (ex: EstudioHC)"}
                },
                "required": ["project"],
            },
        ),
        types.Tool(
            name="recall_memory",
            description="Recupera as memórias/fatos mais recentes do projeto",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Nome do projeto"},
                    "limit": {"type": "integer", "description": "Número de registros", "default": 10}
                },
                "required": ["project"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""
    if name == "get_project_status":
        project = arguments.get("project", "EstudioHC")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT content FROM agent_memory WHERE project = ? AND category = 'task_pending' ORDER BY timestamp DESC LIMIT 5", (project,))
        pending = [row['content'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT content FROM agent_memory WHERE project = ? AND category = 'task_completed' ORDER BY timestamp DESC LIMIT 3", (project,))
        completed = [row['content'] for row in cursor.fetchall()]
        conn.close()
        
        res = f"Status do Projeto {project}:\n- Pendentes: {', '.join(pending) if pending else 'Nenhuma'}\n- Concluídas: {', '.join(completed) if completed else 'Nenhuma'}"
        return [types.TextContent(type="text", text=res)]

    elif name == "recall_memory":
        project = arguments.get("project", "EstudioHC")
        limit = arguments.get("limit", 10)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_memory WHERE project = ? ORDER BY timestamp DESC LIMIT ?", (project, limit))
        rows = cursor.fetchall()
        conn.close()
        
        res = "\n".join([f"[{row['timestamp']}] {row['agent_name']}: {row['content']}" for row in rows])
        return [types.TextContent(type="text", text=res if res else "Nenhuma memória encontrada.")]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="estudiohc-memory",
                server_version="0.1.0",
                capabilities=server.get_capabilities(),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
