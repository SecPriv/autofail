#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cleanup function for graceful shutdown
cleanup() {
    echo ""
    echo "[*] Received interrupt signal, shutting down..."
    echo "[*] Cleanup complete."
    exit 0
}

# Set trap for SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Step 1: Run network_setup.sh
echo "[*] Running network_setup.sh..."
"$SCRIPT_DIR/network_setup.sh"

# Step 2: Change to server directory and run orchestrator
echo "[*] Starting orchestrator..."
cd "$SCRIPT_DIR/server" || exit 1

# No sudo needed: orchestrator uses high ports (8443/8080).

# Run orchestrator in foreground (required for interactive input)
# Prefer the venv created by setup.sh; fall back to system python3.
if [ -x "$SCRIPT_DIR/server/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/server/.venv/bin/python"
else
    PYTHON="python3"
fi
$PYTHON orchestrator.py --no-frida --debug
