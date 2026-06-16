"""MCP stdio server for local AI agent integration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp.server.models import InitializationOptions
from mcp.server import Server
from mcp.server.stdio import stdio_server
from sqlalchemy import create_engine, text

# DB path relative to user home
DB_PATH = Path.home() / "Apps/EstudioHC-Memory-Suite" / "data" / "estudiohc.db"

server = Server("estudiohc-memory")


@server.list_tools()
async def handle_list_tools():
    from mcp.types import Tool

    return [
        Tool(
            name="get_project_status",
            description="Recupera o status atual do projeto (tarefas pendentes e concluídas)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Nome do projeto (ex: EstudioHC)",
                    }
                },
                "required": ["project"],
            },
        ),
        Tool(
            name="recall_memory",
            description="Recupera as memórias/fatos mais recentes do projeto",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Nome do projeto"},
                    "limit": {
                        "type": "integer",
                        "description": "Número de registros",
                        "default": 10,
                    },
                },
                "required": ["project"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    from mcp.types import TextContent

    if arguments is None:
        arguments = {}

    engine = create_engine(f"sqlite:///{DB_PATH}")

    if name == "get_project_status":
        project = arguments.get("project", "EstudioHC")
        with engine.connect() as conn:
            pending = conn.execute(
                text(
                    "SELECT content FROM agent_memory "
                    "WHERE project = :proj AND category = 'task_pending' "
                    "ORDER BY timestamp DESC LIMIT 5"
                ),
                {"proj": project},
            ).fetchall()

            completed = conn.execute(
                text(
                    "SELECT content FROM agent_memory "
                    "WHERE project = :proj AND category = 'task_completed' "
                    "ORDER BY timestamp DESC LIMIT 3"
                ),
                {"proj": project},
            ).fetchall()

        pending_list = [row[0] for row in pending] if pending else ["Nenhuma"]
        completed_list = [row[0] for row in completed] if completed else ["Nenhuma"]

        res = (
            f"Status do Projeto {project}:\n"
            f"- Pendentes: {', '.join(pending_list)}\n"
            f"- Concluídas: {', '.join(completed_list)}"
        )
        return [TextContent(type="text", text=res)]

    elif name == "recall_memory":
        project = arguments.get("project", "EstudioHC")
        limit = arguments.get("limit", 10)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT * FROM agent_memory "
                    "WHERE project = :proj ORDER BY timestamp DESC LIMIT :lim"
                ),
                {"proj": project, "lim": limit},
            ).fetchall()

        if not rows:
            return [TextContent(type="text", text="Nenhuma memória encontrada.")]

        res = "\n".join(
            [
                f"[{row.timestamp}] {row.agent_name}: {row.content}"
                for row in rows
            ]
        )
        return [TextContent(type="text", text=res)]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="estudiohc-memory",
                server_version="3.0.0",
                capabilities=server.get_capabilities(),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())