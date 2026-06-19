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

# Step 2: Change to server directory and run orchestrator with sudo
echo "[*] Starting orchestrator..."
cd "$SCRIPT_DIR/server" || exit 1

# Why sudo is necessary:
# The orchestrator binds to privileged ports 443 (HTTPS) and 80 (HTTP).
# On Linux, binding to ports below 1024 requires root privileges.
echo "[*] Note: sudo is required to bind to privileged ports 80 and 443"

# Run orchestrator in foreground (required for interactive input)
sudo -E python3 orchestrator.py --no-frida --debug
