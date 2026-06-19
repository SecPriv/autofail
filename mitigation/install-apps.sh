#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Uninstalling existing apps..."
adb uninstall com.example.xclmitigation 2>/dev/null
adb uninstall com.example.pocapp 2>/dev/null

echo ""
echo "Installing XCLMitigation (autofill service)..."
adb install -r "$SCRIPT_DIR/XCLMitigation/app/build/outputs/apk/debug/app-debug.apk"

echo ""
echo "Installing PoCApp (demo app)..."
adb install -r "$SCRIPT_DIR/PoCApp/app/build/outputs/apk/debug/app-debug.apk"

echo ""
echo "Done!"
