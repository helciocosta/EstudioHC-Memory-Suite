#!/bin/bash
# Wrapper to run MCP Memory Server as daemon
# Uses a named pipe for stdio communication

cd /home/helcio/Apps/EstudioHC-Memory-Suite/apps/mcp-memory/src

# Create FIFOs for stdin/stdout
FIFO_IN="/tmp/mcp_memory_stdin"
FIFO_OUT="/tmp/mcp_memory_stdout"

rm -f "$FIFO_IN" "$FIFO_OUT"
mkfifo "$FIFO_IN" "$FIFO_OUT"

# Keep FIFOs open
exec 3<>"$FIFO_IN"
exec 4<>"$FIFO_OUT"

# Run the server with stdin/stdout connected to FIFOs
exec python3 -m memory_server <"$FIFO_IN" >"$FIFO_OUT" 2>&1
