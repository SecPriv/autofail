import argparse
import subprocess
import sys
import time
import os
import json
import sqlite3
from server.package_map import PACKAGE_MAP

SCRIPT_SERVICE = "frida/script_service.js"
SCRIPT_BROWSER = "frida/script_browser.js"
DB_PATH = "server/results.db"

processes = []

def get_package_name(alias):
    return PACKAGE_MAP.get(alias, alias)

def run_shell_cmd(cmd):
    try:
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return result.decode('utf-8', errors='ignore').strip()
    except subprocess.CalledProcessError:
        return ""

# --- DATABASE COMMANDS ---
def update_db(test_num, repetition, browser_alias, service_alias, captured_fields, structure_json):
    """
    Updates the existing row in server/results.db with the pulled autofill data.
    """
    # Convert aliases to package names safely
    browser = get_package_name(browser_alias)
    service = get_package_name(service_alias)

    a_user = None
    a_pass = None
    b_user = None
    b_pass = None

    print(f"    [D] Analyze Captured Fields: {captured_fields}")

    for label, value in captured_fields.items():
        lbl = label.lower()
        
        # Determine if it belongs to group B (heuristic: contains 'b' or '2')
        is_b = 'b' in lbl or '_2' in lbl
        
        # Heuristic Matching
        if any(x in lbl for x in ['user', 'email', 'login', 'id']):
            if is_b: b_user = value
            else: a_user = value
        elif 'pass' in lbl:
            if is_b: b_pass = value
            else: a_pass = value
        else:
            print(f"    [!] Warning: Field '{label}' with value '{value}' did not match 'user' or 'pass' heuristic.")

    # Debug print to see what exactly is being sent to DB
    print(f"    [D] DB Payload -> A_User: {a_user}, A_Pass: {a_pass}, B_User: {b_user}, B_Pass: {b_pass}")

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        query = """
            UPDATE autofill_results
            SET a_username_suggested = ?,
                a_password_suggested = ?,
                b_username_suggested = ?,
                b_password_suggested = ?,
                autofill_structure = ?
            WHERE test_number = ? AND repetition = ? AND browser_package = ? AND pwm_package = ?
        """
        
        c.execute(query, (
            a_user, a_pass, b_user, b_pass, 
            structure_json, 
            test_num, repetition, browser, service
        ))
        
        if c.rowcount == 0:
            print(f"    [!] Warning: No existing row found in DB for Test {test_num} Rep {repetition} ({browser} / {service}). Data was not updated.")
        else:
            print(f"    [+] Database updated for Test {test_num} (Repetition {repetition})")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [!] Database Error: {e}")

# --- START COMMAND ---
def run_frida(device_id, package, script_path):
    if not os.path.exists(script_path):
        print(f"[!] Error: Script file not found at {script_path}")
        return None
    cmd = ["frida", "-D", device_id, "-f", package, "-l", script_path]
    print(f"[*] Launching: {' '.join(cmd)}")
    return subprocess.Popen(cmd)

def start_tests(args):
    service_pkg = get_package_name(args.service)
    browser_pkg = get_package_name(args.browser)
    
    print(f"\n[+] Starting Test Session")
    p1 = run_frida(args.device, service_pkg, SCRIPT_SERVICE)
    if p1: processes.append(p1)
    
    time.sleep(2) 
    p2 = run_frida(args.device, browser_pkg, SCRIPT_BROWSER)
    if p2: processes.append(p2)
    
    try:
        print("\n[+] Hooks running. Press Ctrl+C to stop.")
        while True: time.sleep(1)
    except KeyboardInterrupt:
        for p in processes: p.terminate()
        sys.exit(0)

# --- MERGE LOGIC ---
def inject_fill_data(node, fill_map, stats, captured_fields):
    if not node: return

    if 'autofillId' in node:
        af_id = node['autofillId']
        if af_id in fill_map:
            val_filled = fill_map[af_id]
            
            node['_FILLED_DATA_'] = {
                "value_filled": val_filled
            }
            
            # Smart Labeling
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
            
            # If still unknown, use autofillId as fallback so we capture something
            if label == "Unknown Field":
                label = f"Unknown_{af_id}"

            captured_fields[label] = val_filled
            stats['matched'] += 1
            del fill_map[af_id]

    if 'children' in node:
        for child in node['children']:
            inject_fill_data(child, fill_map, stats, captured_fields)

def process_test_folder(folder_path, test_num, repetition, browser_alias, service_alias):
    req_path = os.path.join(folder_path, "request.json")
    fill_path = os.path.join(folder_path, "fill.json")
    
    if not os.path.exists(req_path):
        print(f"    [-] Skipping process: No request.json found in {os.path.basename(folder_path)}")
        return

    try:
        with open(req_path, 'r') as f:
            report_json = json.load(f)

        stats = {"matched": 0}
        captured_fields = {}
        unmatched_fills = []

        if os.path.exists(fill_path):
            with open(fill_path, 'r') as f:
                fill_data = json.load(f)
            
            fill_map = {item['id']: item['value'] for item in fill_data.get('data', [])}
            
            if 'contexts' in report_json:
                for ctx in report_json['contexts']:
                    for win in ctx.get('structure', []):
                        inject_fill_data(win.get('root'), fill_map, stats, captured_fields)

            for af_id, val in fill_map.items():
                unmatched_fills.append(f"Unmatched ID {af_id}: {val}")
        
        report_json['_REPORT_SUMMARY_'] = {
            "total_filled_nodes": stats['matched'],
            "unmatched_count": len(unmatched_fills)
        }
        
        structure_str = json.dumps(report_json)
        
        # Check if we actually captured anything
        if not captured_fields and os.path.exists(fill_path):
            print(f"    [!] Warning: fill.json exists but no fields were matched in request.json. IDs might differ.")
            if unmatched_fills:
                print(f"    [!] Unmatched IDs in fill.json: {unmatched_fills}")

        update_db(test_num, repetition, browser_alias, service_alias, captured_fields, structure_str)

    except Exception as e:
        print(f"    [!] Error processing/merging: {e}")

# --- TEST COMMAND (Interactive) ---
def perform_pull_step(device_id, browser_alias, service_alias, test_num, repetition):
    service_pkg = get_package_name(service_alias)
    browser_pkg = get_package_name(browser_alias)
    
    base_results_dir = os.path.join("test_results", browser_alias, service_alias)
    if not os.path.exists(base_results_dir):
        os.makedirs(base_results_dir)

    current_test_dir = os.path.join(base_results_dir, f"test_{test_num}")
    os.makedirs(current_test_dir, exist_ok=True)
    
    def pull_single_file(pkg_name, prefix, final_name):
        data_path = f"/data/user/0/{pkg_name}/files"
        ls_cmd = f"adb -s {device_id} shell \"su -c 'ls {data_path}/{prefix}*' 2>/dev/null\""
        files_list = run_shell_cmd(ls_cmd)
        
        paths = [f.strip() for f in files_list.splitlines() if f.strip().endswith('.json')]
        
        if not paths:
            return False

        remote_path = paths[-1] 
        local_path = os.path.join(current_test_dir, final_name)

        cat_cmd = f"adb -s {device_id} shell \"su -c 'cat {remote_path}'\""
        try:
            content = subprocess.check_output(cat_cmd, shell=True)
            with open(local_path, 'wb') as f:
                f.write(content)
            
            for p in paths:
                rm_cmd = f"adb -s {device_id} shell \"su -c 'rm {p}'\""
                run_shell_cmd(rm_cmd)
            return True
        except Exception as e:
            print(f"    [!] Error pulling {remote_path}: {e}")
            return False

    print(f"[*] Step 2: Pulling results for Test {test_num} (Repetition {repetition})...")
    has_req = pull_single_file(service_pkg, "req_", "request.json")
    has_fill = pull_single_file(browser_pkg, "fill_", "fill.json")
    
    if not has_req and not has_fill:
        print("    [-] No files found on device.")
    else:
        process_test_folder(current_test_dir, test_num, repetition, browser_alias, service_alias)

def interactive_test_session(args):
    device_id = args.device
    browser_alias = args.browser
    service_alias = args.service
    browser_pkg_name = get_package_name(browser_alias)
    
    test_counter = 0
    repetition_counter = 0
    repeat_total = 0 

    print("========================================")
    print(f" Interactive Test Session")
    print(f" Browser: {browser_alias} ({browser_pkg_name})")
    print(f" PWM:     {service_alias}")
    print("========================================")

    while True:
        try:
            is_repeating = repeat_total > 0
            
            if is_repeating:
                print(f"\n[TEST: {test_counter} | REPETITION: {repetition_counter} / {repeat_total-1}]")
                prompt_msg = "Press [Enter] to continue, or 'stop' to cancel repetition: "
            else:
                print(f"\n[NEXT TEST: {test_counter}]")
                prompt_msg = "Press [Enter], 'r <N>' to repeat, or number to jump: "

            user_in = input(prompt_msg).strip()
            
            if is_repeating and user_in.lower() == 'stop':
                print(f"-> Repetition cancelled.")
                repeat_total = 0
                repetition_counter = 0
                test_counter += 1
                continue

            if not is_repeating and user_in.isdigit():
                test_counter = int(user_in)
                repetition_counter = 0
                print(f"-> Jumped to Test {test_counter}")
            
            elif not is_repeating and (user_in.startswith('r ') or user_in == 'r'):
                parts = user_in.split()
                try:
                    count = int(parts[1]) if len(parts) > 1 else 1 
                    repeat_total = count
                    repetition_counter = 0
                    is_repeating = True
                    print(f"-> Repeat Mode Enabled: Will run Test {test_counter}, {count} times.")
                except ValueError:
                    print("-> Invalid repeat format. Use 'r <number>'.")
                    continue
            
            url = f"https://a.com/a/test_{test_counter}?test_number={test_counter}\\&repetition={repetition_counter}\\&browser_package={browser_alias}\\&pwm_package={service_alias}"
            
            cmd = f'adb -s {device_id} shell am start -a android.intent.action.VIEW -d "{url}" -p {browser_pkg_name}'
            print(f"[*] Step 1: Launching URL...")
            run_shell_cmd(cmd)

            input(f"[*] Test {test_counter} (Rep {repetition_counter}) launched. Perform actions.\n    Press [Enter] to Pull (Step 2)...")

            perform_pull_step(device_id, browser_alias, service_alias, test_counter, repetition_counter)

            if is_repeating:
                repetition_counter += 1
                if repetition_counter >= repeat_total:
                    print(f"-> All {repeat_total} repetitions completed for Test {test_counter}.")
                    repeat_total = 0
                    repetition_counter = 0
                    test_counter += 1
            else:
                test_counter += 1
                repetition_counter = 0

        except KeyboardInterrupt:
            print("\n[!] Session ended by user.")
            sys.exit(0)

# --- MAIN ---
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--device", required=True)
    parser.add_argument("-s", "--service", required=True)
    parser.add_argument("-b", "--browser", required=True)
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("start")
    subparsers.add_parser("test")

    args = parser.parse_args()

    if args.command == "start": 
        start_tests(args)
    elif args.command == "test": 
        interactive_test_session(args)

if __name__ == "__main__":
    main()