import frida
import sys
import time

# --- CONFIGURATION ---
TARGET_SERVICES = ["com.onepassword.android", "com.x8bit.bitwarden"]
TARGET_BROWSERS = ["com.chrome.dev", "com.android.chrome"]
JS_FILE_SERVICE = "frida/my_hooks/_compiled_script_service.js"
JS_FILE_BROWSER = "frida/my_hooks/_compiled_script_browser.js"
# ---------------------

def on_spawned(spawn):
    process_name = spawn.identifier
    pid = spawn.pid
    
    target_type = None
    js_file_path = None

    # 1. Check if it's a Service (Password Manager)
    for pkg in TARGET_SERVICES:
        if pkg in process_name:
            target_type = "SERVICE"
            js_file_path = JS_FILE_SERVICE
            break

    # 2. If not a service, check if it's a Browser
    if not target_type:
        for pkg in TARGET_BROWSERS:
            if pkg in process_name:
                target_type = "BROWSER"
                js_file_path = JS_FILE_BROWSER
                break

    # 3. Injection Logic
    if target_type:
        print(f"\n[+] DETECTED {target_type}: {process_name} (PID: {pid})")
        
        try:
            # A. Attach to the frozen process
            session = device.attach(pid)
            
            # B. Load the specific JS file for this target type
            with open(js_file_path, 'r') as f:
                source = f.read()
            
            script = session.create_script(source)
            script.on('message', on_message)
            script.load()
            print(f"[+] {target_type} script injected successfully.")
            
            # C. Resume the target app so it runs
            device.resume(pid)
            print(f"[+] Resumed target process.")
            
        except Exception as e:
            print(f"[-] Error hooking {target_type}: {e}")
            # Ensure we resume even if hooking fails
            try: device.resume(pid)
            except: pass

    else:
        # Non-target app: Resume immediately to prevent hanging
        # (Optional: Comment out print to reduce noise)
        # print(f"[.] Resuming non-target: {process_name}")
        device.resume(pid)

def on_message(message, data):
    if message['type'] == 'send':
        print(f"[*] {message['payload']}")
    elif message['type'] == 'log':
        # This catches console.log() from JavaScript
        print(f"[JS] {message['payload']}")
    elif message['type'] == 'error':
        print(f"[-] ERROR: {message['stack']}")

try:
    device = frida.get_usb_device()
except Exception as e:
    print(f"[-] Error: {e}")
    sys.exit(1)

print("[*] Supervisor running.")
print(f"[*] holding all spawns, injecting into:{TARGET_SERVICES} {TARGET_BROWSERS}")
print(f"[*] services: {TARGET_SERVICES}")
print(f"[*] browsers: {TARGET_BROWSERS}")

# Enable Child Gating
device.enable_spawn_gating()
device.on('spawn-added', on_spawned)

try:
    sys.stdin.read()
except KeyboardInterrupt:
    print("Stopping.")