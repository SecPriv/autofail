#!/bin/bash
#
# setup.sh — one-time setup for the ADAPT orchestrator.
# Installs a self-contained Python 3.12 environment (no root required)
# with flask and frida, via uv.
#
# Usage: ./setup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/ADAPT/server"
VENV_DIR="$SERVER_DIR/.venv"

# frida client version MUST match the bundled frida-server
# (setup_files/simple_program == frida-server 17.5.1).
FRIDA_VERSION="17.5.1"
PYTHON_VERSION="3.12"

echo "============================================================"
echo " ADAPT orchestrator — environment setup"
echo "============================================================"
echo " Server dir : $SERVER_DIR"
echo " Virtualenv : $VENV_DIR"
echo " Python     : $PYTHON_VERSION"
echo " Frida      : $FRIDA_VERSION  (must match bundled frida-server)"
echo "============================================================"
echo

# 1. uv (user-space, no root)
export PATH="$HOME/.local/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
    echo "[1/5] uv already installed: $(command -v uv)"
else
    echo "[1/5] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo

# 2. Python (prebuilt standalone CPython, no compilation)
echo "[2/5] Installing Python $PYTHON_VERSION..."
uv python install "$PYTHON_VERSION"
echo

# 3. Virtual environment
if [ -x "$VENV_DIR/bin/python" ]; then
    echo "[3/5] Virtualenv already exists, reusing it."
else
    echo "[3/5] Creating virtualenv at $VENV_DIR..."
    uv venv --python "$PYTHON_VERSION" "$VENV_DIR"
fi
echo

# 4. Dependencies
echo "[4/5] Installing dependencies (flask, frida)..."
uv pip install --python "$VENV_DIR/bin/python" flask "frida==$FRIDA_VERSION"
echo

# 5. Verify
echo "[5/5] Verifying..."
"$VENV_DIR/bin/python" - <<EOF
import frida
import importlib.metadata as m
print(f"  flask {m.version('flask')}")
print(f"  frida {frida.__version__}")
EOF
"$VENV_DIR/bin/python" -m py_compile "$SERVER_DIR/orchestrator.py" && echo "  orchestrator.py: syntax OK"
echo
echo "============================================================"
echo " Setup complete."
echo "============================================================"
echo
echo " Next: ./ADAPT/run_server.sh  (auto-uses this venv)"
echo
