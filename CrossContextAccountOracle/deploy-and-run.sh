#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APK_PATH="${SCRIPT_DIR}/Spill/app/build/outputs/apk/debug/app-debug.apk"
PACKAGE_NAME="com.example.spill"
ACTIVITY="${PACKAGE_NAME}/.MainActivity"

echo "=== Spill App Deployment Script ==="

# Check if adb is available
if ! command -v adb &> /dev/null; then
    echo "ERROR: adb command not found. Please install Android SDK Platform Tools."
    exit 1
fi
echo "✓ adb found"

# Check if device is connected
if ! adb devices | grep -q "device$"; then
    echo "ERROR: No Android device or emulator detected. Please connect a device or start an emulator."
    exit 1
fi
echo "✓ Device connected"

# Check if APK exists
if [ ! -f "${APK_PATH}" ]; then
    echo "ERROR: APK not found at ${APK_PATH}"
    echo "Please ensure the APK has been built and is located at the expected path."
    exit 1
fi
echo "✓ APK found at ${APK_PATH}"

# Uninstall existing version (ignore errors if not installed)
echo ""
echo "Uninstalling existing version..."
adb uninstall "${PACKAGE_NAME}" 2>/dev/null || echo "No existing installation found"

# Install APK
echo ""
echo "Installing APK..."
adb install -r "${APK_PATH}"

# Launch app (fire-and-forget)
echo ""
echo "Launching app..."
adb shell am start -n "${ACTIVITY}"

echo ""
echo "=== Deployment complete ==="
