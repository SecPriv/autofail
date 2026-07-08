#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure adb is on PATH (installed by setup.sh)
export PATH="$SCRIPT_DIR/../emulator/android-sdk/platform-tools:$PATH"
command -v adb >/dev/null 2>&1 || { echo "adb not found. Run ./setup.sh first." >&2; exit 1; }

echo "Uninstalling existing apps..."
adb uninstall com.example.xclmitigation 2>/dev/null
adb uninstall com.example.pocapp 2>/dev/null

echo ""
echo "Installing XCLMitigation (autofill service)..."
XCL_APK="$SCRIPT_DIR/XCLMitigation/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$XCL_APK" ]; then
    echo "ERROR: XCLMitigation APK not found."
    echo "Build it first:  cd ${SCRIPT_DIR}/XCLMitigation && ./gradlew assembleDebug"
    exit 1
fi
adb install -r "$XCL_APK"

echo ""
echo "Installing PoCApp (demo app)..."
adb install -r "$SCRIPT_DIR/PoCApp/app/build/outputs/apk/debug/app-debug.apk"

echo ""
echo "Done!"
