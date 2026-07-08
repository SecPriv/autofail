#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure adb is on PATH (installed by setup.sh)
export PATH="$SCRIPT_DIR/../emulator/android-sdk/platform-tools:$PATH"
command -v adb >/dev/null 2>&1 || { echo "adb not found. Run ./setup.sh first." >&2; exit 1; }

echo "Launching PoC App..."
adb shell am start -n com.example.pocapp/.MainActivity
