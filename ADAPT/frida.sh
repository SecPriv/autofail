#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="$SCRIPT_DIR/../emulator/android-sdk/platform-tools:$PATH"
command -v adb >/dev/null 2>&1 || { echo "adb not found. Run ./setup.sh first." >&2; exit 1; }

adb root

sleep 2

adb shell "killall simple_program" 2>/dev/null || true
adb push setup_files/simple_program /data/local/tmp
adb shell "chmod 755 /data/local/tmp/simple_program"
adb shell "nohup /data/local/tmp/simple_program > /dev/null 2>&1 &"
