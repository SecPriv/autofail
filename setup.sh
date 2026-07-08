#!/bin/bash
#
# setup.sh — one-time setup for the artifact evaluation.
# Installs a self-contained environment (no root required):
#   - Python 3.12 virtualenv with flask and frida (ADAPT orchestrator)
#   - Android platform-tools (adb) — needed even for a physical device
#   - Node.js + npm (RealWorldAnalysis iframe crawler)
#   - Java 17+ JDK (build the Android PoC apps; only if system Java < 17)
#   - Puppeteer + Chromium (RealWorldAnalysis iframe crawler)
#
# Usage: ./setup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/ADAPT/server"
VENV_DIR="$SERVER_DIR/.venv"
SDK_DIR="$SCRIPT_DIR/emulator/android-sdk"
PLATFORM_TOOLS_DIR="$SDK_DIR/platform-tools"
JAVA_DIR="$SCRIPT_DIR/emulator/jdk"

# frida client version MUST match the bundled frida-server
# (setup_files/simple_program == frida-server 17.5.1).
FRIDA_VERSION="17.5.1"
PYTHON_VERSION="3.12"

echo "============================================================"
echo " AutoFail — environment setup"
echo "============================================================"
echo " Server dir      : $SERVER_DIR"
echo " Virtualenv      : $VENV_DIR"
echo " Python          : $PYTHON_VERSION"
echo " Frida           : $FRIDA_VERSION  (must match bundled frida-server)"
echo " Platform-tools  : $PLATFORM_TOOLS_DIR"
echo "============================================================"
echo

# 1. uv (user-space, no root)
export PATH="$HOME/.local/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
    echo "[1/9] uv already installed: $(command -v uv)"
else
    echo "[1/9] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo

# 2. Python (prebuilt standalone CPython, no compilation)
echo "[2/9] Installing Python $PYTHON_VERSION..."
uv python install "$PYTHON_VERSION"
echo

# 3. Virtual environment
if [ -x "$VENV_DIR/bin/python" ]; then
    echo "[3/9] Virtualenv already exists, reusing it."
else
    echo "[3/9] Creating virtualenv at $VENV_DIR..."
    uv venv --python "$PYTHON_VERSION" "$VENV_DIR"
fi
echo

# 4. Dependencies
echo "[4/9] Installing dependencies (flask, frida)..."
uv pip install --python "$VENV_DIR/bin/python" "flask==3.1.3" "frida==$FRIDA_VERSION"
echo

# 5. Android platform-tools (adb)
# Standalone download — no Java or sdkmanager needed. Required even when
# using a physical device (the evaluator may never run launch_emulator.sh).
# install_apks.sh / basic_test.sh and all repo scripts look for adb here.
if [ -x "$PLATFORM_TOOLS_DIR/adb" ]; then
    echo "[5/9] platform-tools already installed: $PLATFORM_TOOLS_DIR/adb"
else
    echo "[5/9] Installing Android platform-tools (adb)..."
    OS_ID="$(uname -s | tr '[:upper:]' '[:lower:]')"
    case "$OS_ID" in
        darwin) PT_ZIP_URL="https://dl.google.com/android/repository/platform-tools-latest-darwin.zip" ;;
        linux)  PT_ZIP_URL="https://dl.google.com/android/repository/platform-tools-latest-linux.zip" ;;
        *)
            echo "  Unsupported OS: $(uname -s). Install platform-tools manually." >&2
            exit 1
            ;;
    esac
    mkdir -p "$SDK_DIR"
    PT_ZIP="$SDK_DIR/platform-tools.zip"
    curl -L -o "$PT_ZIP" "$PT_ZIP_URL"
    unzip -q "$PT_ZIP" -d "$SDK_DIR"
    rm "$PT_ZIP"
    echo "  Installed: $PLATFORM_TOOLS_DIR/adb"
fi
echo

# 6. Node.js (user-space, no root) — for RealWorldAnalysis/IframeConfigurationAnalysis
NODE_BIN_DIR="$HOME/.local/node/bin"
if command -v node >/dev/null 2>&1 && [ "$(node -v 2>/dev/null | cut -d. -f1 | tr -d v)" -ge 18 ]; then
    echo "[6/9] Node.js already installed: $(command -v node) ($(node -v))"
elif [ -x "$NODE_BIN_DIR/node" ] && [ "$("$NODE_BIN_DIR/node" -v 2>/dev/null | cut -d. -f1 | tr -d v)" -ge 18 ]; then
    echo "[6/9] Node.js already installed: $NODE_BIN_DIR/node ($("$NODE_BIN_DIR/node" -v))"
else
    echo "[6/9] Installing Node.js (LTS)..."
    NODE_ARCH="$(uname -m)"
    case "$NODE_ARCH" in
        arm64|aarch64) NODE_ARCH="arm64" ;;
        x86_64)        NODE_ARCH="x64" ;;
        *)
            echo "  Unsupported architecture: $NODE_ARCH" >&2
            exit 1
            ;;
    esac
    case "$(uname -s)" in
        Darwin) NODE_OS="darwin" ;;
        Linux)  NODE_OS="linux" ;;
        *)
            echo "  Unsupported OS: $(uname -s)" >&2
            exit 1
            ;;
    esac
    # Resolve the latest LTS version from the official index.
    NODE_LATEST="$(curl -fsSL https://nodejs.org/dist/index.json \
        | "$VENV_DIR/bin/python" -c "import sys,json; print(next(v['version'] for v in json.load(sys.stdin) if v['lts']))" 2>/dev/null || true)"
    if [ -z "$NODE_LATEST" ]; then
        echo "  Could not determine the latest Node.js LTS version." >&2
        exit 1
    fi
    NODE_TARBALL="node-${NODE_LATEST}-${NODE_OS}-${NODE_ARCH}.tar.gz"
    NODE_URL="https://nodejs.org/dist/${NODE_LATEST}/${NODE_TARBALL}"
    NODE_TMP="$(mktemp -d)"
    echo "  Downloading $NODE_LATEST (${NODE_OS}-${NODE_ARCH})..."
    curl -fsSL -o "$NODE_TMP/$NODE_TARBALL" "$NODE_URL"
    rm -rf "$HOME/.local/node"
    mkdir -p "$HOME/.local/node"
    tar -xzf "$NODE_TMP/$NODE_TARBALL" -C "$HOME/.local/node" --strip-components=1
    rm -rf "$NODE_TMP"
    # Symlink into ~/.local/bin (already on PATH from step 1)
    for tool in node npm npx; do
        ln -sf "$NODE_BIN_DIR/$tool" "$HOME/.local/bin/$tool"
    done
    echo "  Installed: $NODE_BIN_DIR/node ($("$NODE_BIN_DIR/node" -v))"
fi
echo

# 7. Java 17+ (JDK) — required to run the Gradle wrapper that builds the
# Android PoC apps (Spill, XCLMitigation). Only installed if the system
# Java is missing or older than 17. Shares emulator/jdk/ with
# launch_emulator.sh so neither duplicates the other's work.
JAVA_USING_SYSTEM=0
if command -v java >/dev/null 2>&1; then
    JAVA_MAJOR=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d. -f1)
    if [ "${JAVA_MAJOR:-0}" -ge 17 ]; then
        echo "[7/9] Java $JAVA_MAJOR already on PATH."
        JAVA_USING_SYSTEM=1
    fi
fi
if [ "$JAVA_USING_SYSTEM" -eq 0 ]; then
    if [ -x "$JAVA_DIR/Contents/Home/bin/java" ]; then
        echo "[7/9] Java 17 already downloaded at $JAVA_DIR"
    else
        echo "[7/9] Installing Java 17 (Eclipse Temurin)..."
        case "$(uname -sm)" in
            "Darwin arm64")  JAVA_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_aarch64_mac_hotspot_17.0.11_9.tar.gz" ;;
            "Darwin x86_64") JAVA_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_mac_hotspot_17.0.11_9.tar.gz" ;;
            "Linux aarch64") JAVA_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_aarch64_linux_hotspot_17.0.11_9.tar.gz" ;;
            "Linux x86_64")  JAVA_URL="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz" ;;
            *)
                echo "  Unsupported platform: $(uname -sm). Install a JDK 17+ manually." >&2
                exit 1
                ;;
        esac
        mkdir -p "$JAVA_DIR"
        JAVA_ARCHIVE="$JAVA_DIR/jdk.tar.gz"
        curl -L -o "$JAVA_ARCHIVE" "$JAVA_URL"
        tar -xzf "$JAVA_ARCHIVE" -C "$JAVA_DIR" --strip-components=1
        rm "$JAVA_ARCHIVE"
        echo "  Installed: $JAVA_DIR/Contents/Home/bin/java"
    fi
    export JAVA_HOME="$JAVA_DIR/Contents/Home"
    export PATH="$JAVA_HOME/bin:$PATH"
fi
echo

# 8. Puppeteer + Chromium (for RealWorldAnalysis/IframeConfigurationAnalysis)
CRAWLER_DIR="$SCRIPT_DIR/RealWorldAnalysis/IframeConfigurationAnalysis/crawler"
if [ -d "$CRAWLER_DIR/node_modules" ]; then
    echo "[8/9] Puppeteer already installed: $CRAWLER_DIR/node_modules"
else
    echo "[8/9] Installing Puppeteer and Chromium..."
    cd "$CRAWLER_DIR"
    npm ci --prefer-offline || npm install
    echo "  Installing Chrome browser for Puppeteer..."
    export PATH="$HOME/.local/node/bin:$PATH"
    npx puppeteer browsers install chrome
    cd "$SCRIPT_DIR"
    echo "  Puppeteer + Chromium installed"
fi
echo

# 9. Verify
echo "[9/9] Verifying..."
export PATH="$PLATFORM_TOOLS_DIR:$HOME/.local/bin:$PATH"
"$VENV_DIR/bin/python" - <<EOF
import frida
import importlib.metadata as m
print(f"  flask {m.version('flask')}")
print(f"  frida {frida.__version__}")
EOF
"$VENV_DIR/bin/python" -m py_compile "$SERVER_DIR/orchestrator.py" && echo "  orchestrator.py: syntax OK"
"$VENV_DIR/bin/python" -m py_compile "$SERVER_DIR/package_map.py"  && echo "  package_map.py: syntax OK"
echo "  adb  : $(adb version 2>/dev/null | head -1 || echo 'NOT FOUND')"
echo "  node : $(node -v 2>/dev/null || echo 'NOT FOUND')"
echo "  npm  : $(npm -v 2>/dev/null || echo 'NOT FOUND')"
echo "  java : $(java -version 2>&1 | head -1 || echo 'NOT FOUND')"
echo "  puppeteer: $([ -d "$CRAWLER_DIR/node_modules/puppeteer" ] && echo 'installed' || echo 'NOT FOUND')"
echo "  chrome: $([ -d "$HOME/.cache/puppeteer/chrome" ] && echo 'installed' || echo 'NOT FOUND')"
echo

# Make installs persistently available in future shells. ~/.local/bin holds
# uv/node/npm; JAVA_HOME is only needed when we installed a local Java (system
# Java < 17). Idempotent: appends once.
ZSHRC="$HOME/.zshrc"
ensure_path_line() {
    local line="$1"
    grep -qF "$line" "$ZSHRC" 2>/dev/null || printf '\n%s\n' "$line" >> "$ZSHRC"
}
ensure_path_line 'export PATH="$HOME/.local/bin:$PATH"'
if [ "$JAVA_USING_SYSTEM" -eq 0 ] && [ -n "${JAVA_HOME:-}" ]; then
    ensure_path_line "export JAVA_HOME=\"$JAVA_HOME\""
    ensure_path_line 'export PATH="$JAVA_HOME/bin:$PATH"'
fi
echo "  (PATH entries added to ~/.zshrc for future shells)"

echo
echo "============================================================"
echo " Setup complete."
echo "============================================================"
echo
echo " Next steps:"
echo "   ./emulator/launch_emulator.sh   (emulator; skip if using a physical device)"
echo "   ./emulator/install_apks.sh       (install Chrome + password managers)"
echo "   ./ADAPT/run_server.sh            (start frida + orchestrator; uses this venv)"
echo
