import frida
import sys
import json
import threading
import sqlite3
import logging
import time
import subprocess
import os
from flask import Flask, Blueprint, request, render_template, make_response, jsonify
from functools import partial
from werkzeug.serving import make_server 

# ==========================================
# 0. SETUP FLAGS
# ==========================================

DEBUG_MODE = "--debug" in sys.argv or "-d" in sys.argv
NO_FRIDA = "--no-frida" in sys.argv          # COMPLETELY DISABLES FRIDA
NO_PWM_HOOKS = "--no-pwm-hooks" in sys.argv  # Hooks Browser, but skips PWM hooks

if DEBUG_MODE:
    DB_FILE = 'results_debug.db'
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print(f"[DEBUG] Removed existing {DB_FILE}")
        except OSError as e:
            print(f"[DEBUG] Error removing {DB_FILE}: {e}")
    print(f"[DEBUG] ORCHESTRATOR STARTED IN DEBUG MODE (DB: {DB_FILE})")
else:
    DB_FILE = 'results.db'
    print(f"[*] ORCHESTRATOR STARTED (DB: {DB_FILE})")

if NO_FRIDA:
    print("[*] MODE: NO-FRIDA (All hooks disabled)")
elif NO_PWM_HOOKS:
    print("[*] MODE: PARTIAL HOOKS (Browser hooks ON, PWM hooks OFF)")

# ==========================================
# 1. LOGGING SETUP
# ==========================================

def setup_loggers():
    server_handler = logging.FileHandler('server.log', mode='w')
    server_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))

    srv_logger = logging.getLogger('server_custom')
    srv_logger.setLevel(logging.INFO)
    srv_logger.addHandler(server_handler)
    srv_logger.propagate = False 

    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.addHandler(server_handler)
    werkzeug_logger.propagate = False

    supervisor_handler = logging.FileHandler('supervisor.log', mode='w')
    supervisor_handler.setFormatter(logging.Formatter('%(message)s'))

    sup_logger = logging.getLogger('supervisor_custom')
    sup_logger.setLevel(logging.INFO)
    sup_logger.addHandler(supervisor_handler)
    sup_logger.propagate = False

    return srv_logger, sup_logger

srv_log, sup_log = setup_loggers()

# ==========================================
# 2. CONFIGURATION
# ==========================================

HTTPS_PORT = 443 
HTTP_PORT = 80 
CERT = 'cert/cert.pem'
KEY = 'cert/key.pem'
DB_LOCK = threading.Lock()
MAX_TESTS = 12  

TARGET_SERVICES_LIST = [
                   "com.google.android.gms", 
                   "com.callpod.android_apps.keeper", 
                   "com.lastpass.lpandroid",
                   "com.authenticator.app.starnest",
                   "com.x8bit.bitwarden",
                   "com.dashlane",
                   "com.symantec.mobile.idsafe",
                   "keepass2android.keepass2android",
                   "com.nordpass.android.app.password.manager",
                   "authenticator.app.otp.mfa.password.manager.private.browser",
                   "com.onepassword.android",
                   "house_intellect.keyring_free",
                   "io.enpass.app",
                   "com.avira.passwordmanager",
                   "com.siber.roboform"
                   ]

JS_FILE_SERVICE = "frida/my_hooks/_compiled_script_service.js"
JS_FILE_BROWSER = "frida/my_hooks/_compiled_script_browser.js"


# ==========================================
# 3. SHARED STATE
# ==========================================

class TestState:
    def __init__(self):
        self.active_browser = "unknown_browser"
        self.active_pwm = "unknown_pwm"
        self.target_pwm_package = None
        self.current_test = 0
        self.current_repetition = 0
        self.test_mode_active = False 
        self.lock = threading.Lock()

    def set_pwm(self, package_name):
        with self.lock:
            self.active_pwm = package_name
            self.target_pwm_package = package_name
        sup_log.info(f"[SYNC] Active PWM set to: {self.active_pwm}")

    def get_target_pwm(self):
        with self.lock:
            return self.target_pwm_package

    def set_browser(self, package_name):
        self.active_browser = package_name
        sup_log.info(f"[SYNC] Active Browser set to: {self.active_browser}")

    def update_counters(self, test_num, rep_num):
        with self.lock:
            self.current_test = test_num
            self.current_repetition = rep_num

    def set_test_mode(self, active): 
        with self.lock:
            self.test_mode_active = active

    def is_test_mode(self): 
        with self.lock:
            return self.test_mode_active

    def get_identifiers(self):
        with self.lock:
            return (str(self.current_test), str(self.current_repetition), self.active_browser, self.active_pwm)

    def get_raw_identifiers(self):
        with self.lock:
            return (self.current_test, self.current_repetition, self.active_browser, self.active_pwm)

STATE = TestState()

# ==========================================
# 4. DATABASE & FLASK SERVER
# ==========================================

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS autofill_results (
                test_number TEXT, repetition TEXT, browser_package TEXT, pwm_package TEXT,
                a_username_final TEXT, a_password_final TEXT,
                b_username_final TEXT, b_password_final TEXT,
                a_username_suggested TEXT, a_password_suggested TEXT,
                b_username_suggested TEXT, b_password_suggested TEXT,
                autofill_structure TEXT, autofill_response TEXT,
                PRIMARY KEY (test_number, repetition, browser_package, pwm_package)
            )
        ''')
        conn.commit()

def upsert_db_field(field_name, value):
    if not STATE.is_test_mode():
        return
        
    test_num, rep, browser, pwm = STATE.get_identifiers()
    with DB_LOCK:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM autofill_results WHERE test_number=? AND repetition=? AND browser_package=? AND pwm_package=?", (test_num, rep, browser, pwm))
            if c.fetchone():
                c.execute(f"UPDATE autofill_results SET {field_name} = ? WHERE test_number=? AND repetition=? AND browser_package=? AND pwm_package=?", (value, test_num, rep, browser, pwm))
            else:
                c.execute(f"INSERT INTO autofill_results (test_number, repetition, browser_package, pwm_package, {field_name}) VALUES (?, ?, ?, ?, ?)", (test_num, rep, browser, pwm, value))
            conn.commit()

def update_web_result(data, origin):
    user_col = f"{origin}_username_final"
    pass_col = f"{origin}_password_final"
    upsert_db_field(user_col, data.get('username'))
    upsert_db_field(pass_col, data.get('password'))
    
    if STATE.is_test_mode():
        srv_log.info(f"[{origin.upper()}] Report saved for Test {STATE.current_test} [{STATE.active_browser}]")

def create_bp_a():
    bp = Blueprint(f'a_server', __name__, url_prefix=f'/a', static_folder='a', template_folder=f'a/templates')
    
    @bp.route('/report', methods=['POST'])
    def report():
        update_web_result(request.json, 'a')
        return jsonify({"status": "success"})
    
    @bp.route(f'/simple_login')
    def simple_login():
        return make_response(render_template("simple_login.html"))

    @bp.route(f'/test_<int:n>')
    def test_n(n):
        match n:
            case 0: return make_response(render_template("simple_login.html"))
            case 1: return make_response(render_template("login_and_iframe_inside.html"))
            case 2: return make_response(render_template("login_and_iframe_inside.html"))
            case 3: return make_response(render_template("login_and_iframe_outside.html"))
            case 4: return make_response(render_template("login_and_iframe_outside.html"))
            case 5: return make_response(render_template("sandboxed_iframe.html"))
            case 6: return make_response(render_template("iframe.html"))
            case 7: return make_response(render_template("simple_login.html"))
            case 8: return make_response(render_template("object.html"))
            case 9: return make_response(render_template("credentialless.html"))
            case 10: return make_response(render_template("simple_login.html"))
            case 11: return make_response(render_template("simple_iframe.html"))

    return bp

def create_bp_b():
    bp = Blueprint(f'b_server', __name__, url_prefix=f'/b', static_folder='b', template_folder=f'b/templates')
    
    @bp.route('/report', methods=['POST'])
    def report():
        update_web_result(request.json, 'b')
        return jsonify({"status": "success"})

    @bp.route('/simple_login')
    def simple_login():
        return make_response(render_template("b_simple_login.html"))
    @bp.route('/iframe')
    def iframe():
        return make_response(render_template("b_iframe.html"))
    
    return bp

app = Flask(__name__)
app.register_blueprint(create_bp_a())
app.register_blueprint(create_bp_b())

# ==========================================
# 5. SERVER MANAGEMENT
# ==========================================

class ServerContainer:
    def __init__(self):
        self.https_server = None
        self.https_thread = None

SERVERS = ServerContainer()

def _https_thread_target():
    SERVERS.https_server = make_server('0.0.0.0', HTTPS_PORT, app, ssl_context=(CERT, KEY), threaded=True)
    print(f"[*] HTTPS Server started on port {HTTPS_PORT}")
    SERVERS.https_server.serve_forever()

def start_https_server():
    if SERVERS.https_server is not None:
        return 

    SERVERS.https_thread = threading.Thread(target=_https_thread_target, daemon=True)
    SERVERS.https_thread.start()
    time.sleep(1)

def stop_https_server():
    if SERVERS.https_server is not None:
        print(f"[*] Stopping HTTPS Server on port {HTTPS_PORT}...")
        SERVERS.https_server.shutdown() 
        SERVERS.https_server = None
        SERVERS.https_thread = None
        print("[*] HTTPS Server stopped.")

# ==========================================
# 6. MERGE & ANALYSIS LOGIC
# ==========================================

def inject_fill_data(node, fill_map, captured_fields):
    if not node: return
    if 'autofillId' in node:
        af_id = node['autofillId']
        if af_id in fill_map:
            val_filled = fill_map[af_id]
            label = "Unknown Field"
            if 'htmlInfo' in node and 'attributes' in node['htmlInfo']:
                attrs = node['htmlInfo']['attributes']
                if 'name' in attrs and attrs['name']: label = attrs['name']
                elif 'label' in attrs and attrs['label']: label = attrs['label']
                elif 'id' in attrs and attrs['id']: label = attrs['id']
            if label == "Unknown Field" and node.get('hint'): label = node.get('hint')
            if label == "Unknown Field" and node.get('resourceId'):
                res_id = node.get('resourceId')
                label = res_id.split('/')[-1] if '/' in res_id else res_id
            if label == "Unknown Field": label = f"Unknown_{af_id}"
            captured_fields[label] = val_filled
    if 'children' in node:
        for child in node['children']:
            inject_fill_data(child, fill_map, captured_fields)

def analyze_captured_fields(captured_fields):
    result = { "a_user": None, "a_pass": None, "b_user": None, "b_pass": None }
    sup_log.info(f"    [Merge] Analyzing Fields: {list(captured_fields.keys())}")
    for label, value in captured_fields.items():
        lbl = label.lower()
        is_b = 'b' in lbl or '_2' in lbl
        if any(x in lbl for x in ['user', 'email', 'login', 'id']):
            if is_b: result['b_user'] = value
            else: result['a_user'] = value
        elif 'pass' in lbl:
            if is_b: result['b_pass'] = value
            else: result['a_pass'] = value
    return result

def trigger_analysis():
    if not STATE.is_test_mode():
        return

    test_num, rep, browser, pwm = STATE.get_identifiers()
    with DB_LOCK:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT autofill_structure, autofill_response FROM autofill_results WHERE test_number=? AND repetition=? AND browser_package=? AND pwm_package=?", (test_num, rep, browser, pwm))
                row = c.fetchone()
                
                # <--- MODIFICATION: Allow processing even if structure is missing, provided we have response
                if not row: return
                if not row[0] and not row[1]: return 

                struct_json = json.loads(row[0]) if row[0] else {}
                resp_json = json.loads(row[1]) if row[1] else {}
                
                fill_map = {}
                if 'data' in resp_json: fill_map = {item['id']: item['value'] for item in resp_json['data']}
                elif isinstance(resp_json, dict): fill_map = resp_json 

                captured_fields = {}
                
                # Check if we have structure
                if 'contexts' in struct_json:
                    for ctx in struct_json['contexts']:
                        for win in ctx.get('structure', []):
                            inject_fill_data(win.get('root'), fill_map, captured_fields)
                else:
                    # <--- FALLBACK: No structure (e.g. NO_PWM_HOOKS mode)
                    # We simply dump what we have from the browser so the DB gets filled
                    for fid, fval in fill_map.items():
                        # Use ID as label since we have no metadata
                        captured_fields[f"Raw_ID_{fid}"] = fval

                res = analyze_captured_fields(captured_fields)
                c.execute("""UPDATE autofill_results SET a_username_suggested = ?, a_password_suggested = ?, b_username_suggested = ?, b_password_suggested = ? WHERE test_number=? AND repetition=? AND browser_package=? AND pwm_package=?""", (res['a_user'], res['a_pass'], res['b_user'], res['b_pass'], test_num, rep, browser, pwm))
                conn.commit()
                sup_log.info(f"    [Merge] DB Updated with suggestions for {browser}/{pwm}")
        except Exception as e:
            sup_log.info(f"    [!] Merge Error: {e}")

# ==========================================
# 7. FRIDA & SUPERVISOR LOGIC
# ==========================================

def on_frida_message(message, data, origin_type):
    if message['type'] == 'send':
        payload = message['payload']
        try:
            parsed = json.loads(payload)
            json_db = json.dumps(parsed)
            json_log = json.dumps(parsed, indent=2)

            if origin_type == "SERVICE":
                sup_log.info(f"\n[+] 🔓 SERVICE DATA CAPTURED")
                upsert_db_field("autofill_structure", json_db)
            elif origin_type == "BROWSER":
                sup_log.info(f"\n[+] 🌐 BROWSER DATA CAPTURED")
                upsert_db_field("autofill_response", json_db)
            
            sup_log.info(json_log)
            trigger_analysis()
        except:
            sup_log.info(f"[{origin_type} MSG] {payload}")
    elif message['type'] == 'log':
        sup_log.info(f"[{origin_type} LOG] {message['payload']}")
        pass
    elif message['type'] == 'error':
        sup_log.info(f"[-] {origin_type} ERROR: {message['stack']}")

def on_spawned_service(spawn, device):
    name = spawn.identifier
    pid = spawn.pid
    
    target_pwm = STATE.get_target_pwm()
    should_hook = False
    
    if target_pwm:
        if target_pwm in name:
            should_hook = True
            STATE.set_pwm(name)
    else:
        for pkg in TARGET_SERVICES_LIST:
            if pkg in name:
                should_hook = True
                STATE.set_pwm(name)
                break

    if should_hook:
        if NO_PWM_HOOKS:
            sup_log.info(f"[+] DETECTED PWM TARGET: {name} (PID: {pid}) - NO_PWM_HOOKS active, skipping attachment.")
            try: device.resume(pid)
            except: pass
            return

        sup_log.info(f"[+] DETECTED PWM TARGET: {name} (PID: {pid})")
        try:
            session = device.attach(pid)
            with open(JS_FILE_SERVICE, 'r') as f: source = f.read()
            script = session.create_script(source)
            script.on('message', partial(on_frida_message, origin_type="SERVICE"))
            script.load()
            sup_log.info(f"[+] Service hooks injected.")
            device.resume(pid)
        except Exception as e:
            sup_log.info(f"[-] Service Injection Failed: {e}")
            try: device.resume(pid)
            except: pass
    else:
        try: device.resume(pid)
        except: pass

def spawn_browser(package_name, device):
    sup_log.info(f"[*] Command received: Spawning {package_name}...")
    
    if device is None and NO_FRIDA: 
        STATE.set_browser(package_name)
        print(f"[*] NO_FRIDA: State updated to {package_name}. (App not spawned)")
        return

    try:
        pid = device.spawn([package_name])
        sup_log.info(f"[+] Spawned {package_name} (PID: {pid})")
        STATE.set_browser(package_name)
        session = device.attach(pid)
        with open(JS_FILE_BROWSER, 'r') as f: source = f.read()
        script = session.create_script(source)
        script.on('message', partial(on_frida_message, origin_type="BROWSER"))
        script.load()
        sup_log.info(f"[+] Browser hooks injected.")
        device.resume(pid)
        print(f"SUCCESS: {package_name} spawned and hooked.") 
    except Exception as e:
        err = f"[-] Browser Spawn Failed: {e}"
        print(err)
        sup_log.info(err)

def set_pwm_target(package_name, device):
    STATE.set_pwm(package_name)
    print(f"[*] PWM Target set to: {package_name}")
    print(f"[*] Supervisor is now listening for packages containing: {package_name}")

# ==========================================
# 8. TEST AUTOMATION LOGIC
# ==========================================

def run_test_adb(test_num, browser_pkg):
    port_str = ""
    scheme = "https"

    if test_num == 7:
        print(f"[*] Test {test_num}: Shutting down HTTPS server to test plain HTTP...")
        stop_https_server()
        time.sleep(2)
        scheme = "http"
        port_str = "" 
    else:
        if SERVERS.https_server is None:
            print(f"[*] Test {test_num}: Restarting HTTPS server...")
            start_https_server()
        scheme = "https"

    if test_num == 10:
        port_str = ":8081"
    
    url = f"{scheme}://a.com{port_str}/a/test_{test_num}"
    
    cmd = [
        "adb", "shell", "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", url,
        "-p", browser_pkg
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[*] Launched Test {test_num}: {url}")
    except Exception as e:
        print(f"[-] ADB Failed: {e}")

def wait_for_completion(test_num, rep, browser, pwm):
    print(f"[*] Waiting for data (Test {test_num})... (Press ENTER to skip/proceed)")
    
    stop_check = threading.Event()

    def check_db_background():
        while not stop_check.is_set():
            with DB_LOCK:
                with sqlite3.connect(DB_FILE) as conn:
                    c = conn.cursor()
                    c.execute("""
                        SELECT 
                            autofill_structure, 
                            autofill_response, 
                            (a_username_final IS NOT NULL OR a_password_final IS NOT NULL OR b_username_final IS NOT NULL OR b_password_final IS NOT NULL) as has_final,
                            (a_username_suggested IS NOT NULL OR a_password_suggested IS NOT NULL OR b_username_suggested IS NOT NULL OR b_password_suggested IS NOT NULL) as has_suggested
                        FROM autofill_results 
                        WHERE test_number=? AND repetition=? AND browser_package=? AND pwm_package=?
                    """, (str(test_num), str(rep), browser, pwm))
                    row = c.fetchone()
            
            if row:
                has_structure = row[0] is not None
                has_response = row[1] is not None
                has_final = row[2]
                has_suggested = row[3]
                
                if has_structure and has_response and (has_final or has_suggested):
                    print(f"\n[+] Data complete for Test {test_num} (Rep {rep})! Ready to proceed.")
                    return
            
            time.sleep(1)

    t = threading.Thread(target=check_db_background, daemon=True)
    t.start()

    input()
    
    stop_check.set()
    t.join(timeout=1.0)

def run_test_mode(device):
    test_cnt = 0
    reps_remaining = 0
    
    _, _, browser_pkg, _ = STATE.get_raw_identifiers()
    if browser_pkg == "unknown_browser":
        print(f"[!] Warning: No browser set. Defaulting exiting test mode.")
        return

    print(f"\n[!!!] ENTERING TEST MODE (Max Tests: {MAX_TESTS})")
    print(f"      Target Browser: {browser_pkg}")
    print("      Commands: [ENTER] = Run, 'r n' = Set Repetitions, 'j n' = Jump, 'exit' = Quit")

    run_test_mode.actual_rep = 0

    try:
        while test_cnt < MAX_TESTS:
            cmd = input(f"(Test {test_cnt} | Reps left {reps_remaining}) >>> ").strip()

            if cmd == "exit":
                break
            
            elif cmd.startswith("r "):
                try:
                    reps_remaining = int(cmd.split(" ")[1])
                    print(f"[*] Repetitions set to {reps_remaining}")
                except: print("[-] Invalid format")
                continue

            elif cmd.startswith("j "):
                try:
                    test_cnt = int(cmd.split(" ")[1])
                    reps_remaining = 0
                    print(f"[*] Jumped to Test {test_cnt}")
                except: print("[-] Invalid format")
                continue
            
            elif cmd == "":
                if not hasattr(run_test_mode, "actual_rep"): run_test_mode.actual_rep = 0
                
                STATE.update_counters(test_cnt, run_test_mode.actual_rep)
                
                STATE.set_test_mode(True) 
                
                try:
                    run_test_adb(test_cnt, browser_pkg)
                    _, _, b_alias, p_alias = STATE.get_raw_identifiers()
                    wait_for_completion(test_cnt, run_test_mode.actual_rep, b_alias, p_alias)
                finally:
                    STATE.set_test_mode(False)
                
                if reps_remaining > 0:
                    reps_remaining -= 1
                    run_test_mode.actual_rep += 1
                    print(f"[*] Repetition finished. {reps_remaining} remaining for Test {test_cnt}.")
                else:
                    test_cnt += 1
                    run_test_mode.actual_rep = 0
                    print(f"[*] Test finished. Advancing to Test {test_cnt}.")
    finally:
        STATE.set_test_mode(False)
        print("[*] Test Mode Exited.")
        if SERVERS.https_server is None:
            start_https_server()

# ==========================================
# 9. MAIN LOOP
# ==========================================

if __name__ == "__main__":
    init_db()
    start_https_server()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=HTTP_PORT, use_reloader=False, threaded=True), daemon=True).start()
    srv_log.info(f"[*] Server listening on {HTTPS_PORT}/{HTTP_PORT}")
    
    device = None
    
    if not NO_FRIDA:
        try:
            device = frida.get_usb_device()
            device.enable_spawn_gating()
            device.on('spawn-added', lambda spawn: on_spawned_service(spawn, device))
            sup_log.info("[*] Supervisor listening for spawns...")
        except Exception as e:
            print(f"[-] Frida Error: {e}")
            sys.exit(1)
    
    print("\n" + "="*50)
    print(" ORCHESTRATOR RUNNING")
    if DEBUG_MODE:
        print(" [!!!] DEBUG MODE ACTIVE - results_debug.db")
    if NO_FRIDA:
        print(" [!!!] NO-FRIDA MODE ACTIVE - Hooks Disabled")
    if NO_PWM_HOOKS:
        print(" [!!!] NO-PWM-HOOKS MODE ACTIVE - Browser hooks enabled, PWM hooks disabled")
    print("="*50)
    print("COMMANDS:")
    print("  pwm <package_name>      -> Set target Password Manager")
    print("  browser <package_name>  -> Spawn and hook a browser")
    print("  test                    -> Enter Test Automation Mode")
    print("  exit                    -> Stop everything")
    print("="*50)

    while True:
        cmd = input(">>> ").strip()
        if cmd.startswith("browser "):
            try:
                pkg = cmd.split(" ")[1]
                spawn_browser(pkg, device)
            except IndexError: print("Usage: browser <package_name>")
        
        elif cmd.startswith("pwm "):
            try:
                pkg = cmd.split(" ")[1]
                set_pwm_target(pkg, device)
            except IndexError: print("Usage: pwm <package_name>")

        elif cmd == "test":
            run_test_mode(device)

        elif cmd == "exit":
            print("Stopping...")
            break
        elif cmd == "": pass
        else: print("Unknown command.")