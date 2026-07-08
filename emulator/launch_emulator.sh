#!/bin/bash
set -euo pipefail

# --- 1. OS Check ---
if [[ "$(uname -sm)" != "Darwin arm64" ]]; then
    echo "Error: This script requires macOS running on Apple Silicon (arm64)." >&2
    exit 1
fi

# --- 2. Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

JAVA_DIR="$SCRIPT_DIR/jdk"
ANDROID_DIR="$SCRIPT_DIR/android-sdk"

mkdir -p "$ANDROID_DIR"

# --- 3. Java Setup ---
# Java 17+ is installed by ./setup.sh (into emulator/jdk/) or available
# system-wide. This script only reuses it; it does not install Java itself.
JAVA_CMD=""
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}')
    MAJOR_VERSION=$(echo "$JAVA_VERSION" | cut -d. -f1)
    if [[ "$MAJOR_VERSION" -ge 17 ]]; then
        echo "Using system Java $JAVA_VERSION"
        JAVA_CMD="java"
    fi
fi

if [[ -z "$JAVA_CMD" ]]; then
    if [[ -x "$JAVA_DIR/Contents/Home/bin/java" ]]; then
        echo "Using local Java 17 (installed by ./setup.sh)"
        export JAVA_HOME="$JAVA_DIR/Contents/Home"
        JAVA_CMD="$JAVA_HOME/bin/java"
        export PATH="$JAVA_HOME/bin:$PATH"
    else
        echo "Error: Java 17+ not found. Run ./setup.sh first." >&2
        exit 1
    fi
fi

# Verify Java
"$JAVA_CMD" -version

# --- 4. Android SDK Setup ---
export ANDROID_HOME="$ANDROID_DIR"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"

if [[ ! -f "$SDKMANAGER" ]]; then
    echo "Downloading Android SDK Command Line Tools..."
    SDK_ZIP="$SCRIPT_DIR/cmdline-tools.zip"
    CMDLINE_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip"

    curl -L -o "$SDK_ZIP" "$CMDLINE_TOOLS_URL"

    mkdir -p "$ANDROID_HOME/cmdline-tools"
    unzip -q "$SDK_ZIP" -d "$ANDROID_HOME/cmdline-tools/tmp"
    mv "$ANDROID_HOME/cmdline-tools/tmp/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
    rm -rf "$ANDROID_HOME/cmdline-tools/tmp" "$SDK_ZIP"
fi

# --- 5. Install Components & Strict Image Check ---
# Uses the google_apis image (Google APIs, no Play Store, rootable userdebug).
# A Play Store / production (user) build would fail: adb root, frida-server,
# system-CA injection, and iptables all require root.

VERSION="android-36"
API="google_apis"
ARCH="arm64-v8a"
SYSTEM_IMAGE="system-images;$VERSION;$API;$ARCH"
echo "Installing Android SDK components..."
PACKAGES=(
    "platform-tools"
    "emulator"
    "platforms;android-36"
    "$SYSTEM_IMAGE"
)

INSTALL_LOG="$SCRIPT_DIR/sdk_install.log"
if ! $SDKMANAGER --sdk_root="$ANDROID_HOME" "${PACKAGES[@]}" 2>&1 | tee "$INSTALL_LOG"; then
    echo "Error: Failed to install Android SDK components." >&2
    rm -f "$INSTALL_LOG"
    exit 1
fi

# Strict failure if the exact google_apis package could not be found/installed
IMAGE_DIR="$ANDROID_HOME/system-images/$VERSION/$API/$ARCH"
if grep -q "Failed to find package " "$INSTALL_LOG" || [[ ! -d "$IMAGE_DIR" ]]; then
    echo "Error: The required Google APIs system image '$SYSTEM_IMAGE' is not available in the SDK repository." >&2
    echo "The script will not proceed without the google_apis (rootable, no Play Store) image." >&2
    rm -f "$INSTALL_LOG"
    exit 1
fi
rm -f "$INSTALL_LOG"

# --- 6. AVD Setup ---
AVD_NAME="ae_android16"

if ! avdmanager list avd -c 2>/dev/null | grep -q "^${AVD_NAME}$"; then
    echo "Creating AVD '${AVD_NAME}'..."
    echo "no" | avdmanager create avd -n "$AVD_NAME" -k "$SYSTEM_IMAGE" --device pixel_6a
else
    echo "Reusing existing AVD '${AVD_NAME}'"
fi

# --- 7. Launch Emulator ---
echo "Launching emulator..."
$ANDROID_HOME/emulator/emulator -avd "$AVD_NAME" -gpu host -no-boot-anim -no-snapshot -partition-size 16384

