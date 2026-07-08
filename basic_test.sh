#!/bin/bash
#
# basic_test.sh — sanity checks for the ADAPT orchestrator stack.
#
# Verifies that:
#   1. An Android device (emulator or physical) is connected and fully booted.
#   2. The frida server is running on the device (process: simple_program).
#   3. The orchestrator is reachable from the device via https://a.com
#      (DNS resolution + CA certificate + connectivity), verified in Chrome.
#
# Usage: ./basic_test.sh
#
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PASSED=0
FAILED=0
SKIPPED=0

pass() { echo "[PASS] $1"; PASSED=$((PASSED + 1)); }
fail() { echo "[FAIL] $1"; FAILED=$((FAILED + 1)); }
skip() { echo "[SKIP] $1"; SKIPPED=$((SKIPPED + 1)); }

summary_and_exit() {
    echo
    echo "============================================================"
    echo " Summary: $PASSED/3 checks passed"
    echo "============================================================"
    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
    exit 0
}

# Locate adb: PATH first, then repo-local, then user-local.
find_adb() {
    if command -v adb >/dev/null 2>&1; then
        ADB_BIN="$(command -v adb)"
        return 0
    fi
    local candidates=(
        "$SCRIPT_DIR/emulator/android-sdk/platform-tools/adb"
        "$HOME/.android/platform-tools/adb"
    )
    for c in "${candidates[@]}"; do
        if [ -x "$c" ]; then
            ADB_BIN="$c"
            return 0
        fi
    done
    return 1
}

# Wrapper that targets the selected device for every subsequent adb call.
DEVICE_SERIAL=""
adbcmd() {
    "$ADB_BIN" -s "$DEVICE_SERIAL" "$@"
}

echo "============================================================"
echo " ADAPT basic test"
echo "============================================================"
echo

if ! find_adb; then
    fail "adb not found. Install platform-tools or run ./emulator/launch_emulator.sh."
    summary_and_exit
fi
echo "Using adb: $ADB_BIN"
echo

# --------------------------------------------------------------------------
# Check 1: device connected and fully booted
# --------------------------------------------------------------------------
echo "------------------------------------------------------------"
echo " Check 1: Android device connected and booted"
echo "------------------------------------------------------------"

DEVICES_OUT="$("$ADB_BIN" devices 2>&1)"

if echo "$DEVICES_OUT" | grep -q "offline$"; then
    fail "Device is offline. Start the emulator or connect the physical device."
elif echo "$DEVICES_OUT" | grep -q "unauthorized$"; then
    fail "Device is unauthorized. Accept the USB debugging prompt on the device."
else
    DEVICE_SERIAL="$(echo "$DEVICES_OUT" | grep -E '^[A-Za-z0-9:_-]+[[:space:]]+device$' | head -1 | awk '{print $1}')"
    if [ -z "$DEVICE_SERIAL" ]; then
        fail "No Android device connected."
    fi
fi

if [ -n "$DEVICE_SERIAL" ]; then
    BOOTED="$(adbcmd shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')"
    if [ "$BOOTED" = "1" ]; then
        pass "Device $DEVICE_SERIAL connected and fully booted."
    else
        fail "Device $DEVICE_SERIAL connected but not fully booted (sys.boot_completed != 1)."
        DEVICE_SERIAL=""
    fi
fi

if [ -z "$DEVICE_SERIAL" ]; then
    skip "frida check (no booted device)"
    skip "server reachability check (no booted device)"
    summary_and_exit
fi

echo

# --------------------------------------------------------------------------
# Check 2: frida server running as "simple_program"
# --------------------------------------------------------------------------
echo "------------------------------------------------------------"
echo " Check 2: frida server running (simple_program)"
echo "------------------------------------------------------------"

FRIDA_LINE="$(adbcmd shell "ps -A | grep -w '[s]imple_program'" 2>/dev/null | tr -d '\r')"

if [ -n "$FRIDA_LINE" ]; then
    FRIDA_PID="$(echo "$FRIDA_LINE" | awk '{print $2}')"
    pass "frida server running (pid $FRIDA_PID)"
else
    fail "frida server 'simple_program' is not running. Run ./ADAPT/run_server.sh (or ./ADAPT/frida.sh)."
fi

echo

# --------------------------------------------------------------------------
# Check 3: orchestrator reachable from device via https://a.com (manual)
# --------------------------------------------------------------------------
echo "------------------------------------------------------------"
echo " Check 3: orchestrator reachable via https://a.com (Chrome)"
echo "------------------------------------------------------------"

CHROME_PATH="$(adbcmd shell pm path com.android.chrome 2>/dev/null | tr -d '\r')"

if [ -z "$CHROME_PATH" ]; then
    fail "Chrome (com.android.chrome) is not installed."
    skip "server reachability check (Chrome not installed)"
    echo
    echo "  Install Chrome with:  ./emulator/install_apks.sh"
    echo "  Then re-run:          ./basic_test.sh"
    summary_and_exit
fi

URL="https://a.com/a/simple_login"
echo "Opening in Chrome: $URL"
adbcmd shell am start -a android.intent.action.VIEW -d "$URL" -n com.android.chrome/com.google.android.apps.chrome.Main >/dev/null 2>&1
echo
echo "Chrome should now display a login page over HTTPS."
echo "A successful load confirms DNS resolution (a.com -> 127.0.0.1)"
echo "and the trusted CA cert."
echo
printf "Did the page load correctly (HTTPS, no certificate error)? [y/n] "
read -r ANSWER

case "$ANSWER" in
    [yY]|[yY][eE][sS])
        pass "orchestrator reachable from device via $URL"
        ;;
    *)
        fail "page did not load correctly. Check ./ADAPT/run_server.sh and network setup."
        ;;
esac

summary_and_exit
