#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$SCRIPT_DIR"

APKS_DIR="$REPO_ROOT/apks"
ANDROID_DIR="$SCRIPT_DIR/android-sdk"
ADB="$ANDROID_DIR/platform-tools/adb"

# --- 1. Prerequisites ---
if [[ ! -f "$ADB" ]]; then
    echo "Error: ADB not found at $ANDROID_HOME. Run ./launch_emulator.sh first." >&2
    exit 1
fi

# --- 2. Download APKs if missing ---
if [[ ! -d "$APKS_DIR" ]]; then
    echo "APKs directory not found. Downloading from Zenodo..."
    ZENODO_URL="https://zenodo.org/records/21222213/files/apks.zip?download=1"
    curl -L -o "$REPO_ROOT/apks.zip" "$ZENODO_URL"
    unzip -q "$REPO_ROOT/apks.zip" -d "$REPO_ROOT"
    rm "$REPO_ROOT/apks.zip"
    echo "APKs downloaded and extracted."
fi

if [[ ! -d "$APKS_DIR" ]]; then
    echo "Error: APKs directory not found at $APKS_DIR." >&2
    exit 1
fi

# --- 3. Check emulator ---
if ! "$ADB" devices | grep -q "emulator-"; then
    echo "Error: No emulator detected. Start it with ./launch_emulator.sh first." >&2
    exit 1
fi

echo "Waiting for emulator to fully boot..."
"$ADB" wait-for-device

# Poll until boot completes (timeout 120s)
BOOTED=0
for i in $(seq 1 240); do
    if [[ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
        BOOTED=1
        break
    fi
    sleep 0.5
done

if [[ "$BOOTED" -ne 1 ]]; then
    echo "Error: Emulator did not finish booting within 120 seconds." >&2
    exit 1
fi

# --- 4. Install Trichrome Library (always first) ---
TRICHROME="$APKS_DIR/com.google.android.trichromelibrary.apk"
if [[ -f "$TRICHROME" ]]; then
    echo "Installing Trichrome library..."
    if "$ADB" install -r -d "$TRICHROME" 2>&1; then
        echo "  [OK] Trichrome library"
    else
        echo "  [FAILED] Trichrome library"
    fi
fi

# --- 5. Install APKs and split packages ---
echo "Installing APKs from $APKS_DIR..."

for entry in "$APKS_DIR"/*; do
    [[ -e "$entry" ]] || continue
    filename=$(basename "$entry")

    # Skip Trichrome (already installed above)
    if [[ "$filename" == "com.google.android.trichromelibrary.apk" ]]; then
        continue
    fi

    if [[ -f "$entry" && "$entry" == *.apk ]]; then
        # Standalone APK
        echo "Installing $filename..."
        if "$ADB" install -r -d "$entry" 2>&1; then
            echo "  [OK] $filename"
        else
            echo "  [FAILED] $filename"
        fi

    elif [[ -d "$entry" ]]; then
        # App directory with base.apk + splits
        apk_list=()
        for apk in "$entry"/*.apk; do
            [[ -f "$apk" ]] && apk_list+=("$apk")
        done

        if [[ ${#apk_list[@]} -eq 0 ]]; then
            continue
        fi

        echo "Installing split APKs from $filename..."
        if "$ADB" install-multiple -r -d "${apk_list[@]}" 2>&1; then
            echo "  [OK] $filename"
        else
            echo "  [FAILED] $filename"
        fi

    elif [[ -f "$entry" && "$entry" == *.apkm ]]; then
        # Fallback: extract and install .apkm bundles
        echo "Installing .apkm bundle $filename..."
        tmpdir=$(mktemp -d)
        unzip -q "$entry" -d "$tmpdir"

        apk_list=()
        for apk in "$tmpdir"/*.apk; do
            [[ -f "$apk" ]] && apk_list+=("$apk")
        done

        if [[ ${#apk_list[@]} -eq 0 ]]; then
            echo "  [FAILED] No APKs found inside $filename"
            rm -rf "$tmpdir"
            continue
        fi

        if "$ADB" install-multiple -r -d "${apk_list[@]}" 2>&1; then
            echo "  [OK] $filename"
        else
            echo "  [FAILED] $filename"
        fi
        rm -rf "$tmpdir"
    fi
done

echo "Done."
