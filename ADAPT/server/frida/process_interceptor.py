import frida
import sys
import argparse
import os

# Global variable to hold the JS code loaded from file
JS_CODE = ""

def on_spawned(spawn):
    print(f'[*] New process spawned: {spawn.identifier} (PID: {spawn.pid})')
    
    # --- FILTERING ---
    # Example: Only hook the bitwarden app
    # Remove this block if you want to hook EVERYTHING (Risky!)
    if "bitwarden" not in spawn.identifier:
        # print(f"    -> Skipping: {spawn.identifier}")
        device.resume(spawn.pid)
        return

    try:
        # 1. Attach to the process
        session = device.attach(spawn.pid)
        
        # 2. Inject the JS code loaded from the file
        script = session.create_script(JS_CODE)
        script.load()
        print(f"    [+] Script successfully injected into {spawn.identifier}")

        # 3. Resume execution
        device.resume(spawn.pid)
        
    except Exception as e:
        print(f"    [-] Failed to inject: {e}")
        # Always resume to prevent hanging the app
        device.resume(spawn.pid)

# --- ARGUMENT PARSING ---
parser = argparse.ArgumentParser(description="Frida Spawn Gating Loader")
parser.add_argument("-D", "--device", help="Device ID to connect to", required=False)
parser.add_argument("-l", "--load", help="Path to the JS script file", required=True)
args = parser.parse_args()

# --- LOAD JS FILE ---
if not os.path.isfile(args.load):
    print(f"[-] Error: Script file '{args.load}' not found.")
    sys.exit(1)

try:
    with open(args.load, 'r', encoding='utf-8') as f:
        JS_CODE = f.read()
        print(f"[*] Loaded {len(JS_CODE)} bytes from {args.load}")
except Exception as e:
    print(f"[-] Error reading file: {e}")
    sys.exit(1)

# --- CONNECT TO DEVICE ---
try:
    if args.device:
        print(f"[*] Connecting to specific device: {args.device}")
        device = frida.get_device(args.device)
    else:
        print("[*] Connecting to default USB device...")
        device = frida.get_usb_device()

    print(f"[*] Connected to: {device.name} ({device.id})")

except frida.InvalidArgumentError:
    print(f"[-] Error: Device '{args.device}' not found.")
    sys.exit(1)

# --- START LISTENER ---
device.on('spawn-added', on_spawned)
device.enable_spawn_gating()

print("[*] Waiting for new processes... (Press Ctrl+C to stop)")
try:
    sys.stdin.read()
except KeyboardInterrupt:
    pass