from flask import Flask, Blueprint, request, render_template, make_response, jsonify
from package_map import PACKAGE_MAP
import threading
import sqlite3
import os

# --- Configuration ---
HTTPS_PORT = 443 
HTTP_PORT = 80

CERT = 'cert/cert.pem'
KEY = 'cert/key.pem'
DB_FILE = 'results.db'

db_lock = threading.Lock()


# --- Database Setup ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Modified: Primary Key now includes browser and pwm to allow same test # on different setups
        c.execute('''
            CREATE TABLE IF NOT EXISTS autofill_results (
                test_number TEXT,
                repetition TEXT,
                browser_package TEXT,
                pwm_package TEXT,
                a_username_final TEXT,
                a_password_final TEXT,
                b_username_final TEXT,
                b_password_final TEXT,
                a_username_suggested TEXT,
                a_password_suggested TEXT,
                b_username_suggested TEXT,
                b_password_suggested TEXT,
                autofill_structure TEXT,
                autofill_response TEXT,
                PRIMARY KEY (test_number, repetition, browser_package, pwm_package)
            )
        ''')
        conn.commit()

init_db()

# --- Shared Database Logic ---
def update_result(data):
    test_number = str(data.get('test_number'))
    repetition = str(data.get('repetition', '0'))
    origin = data.get('origin')
    
    # Resolve package names
    browser_raw = data.get('browser_package')
    pwm_raw = data.get('pwm_package')
    browser = PACKAGE_MAP.get(browser_raw, browser_raw)
    pwm = PACKAGE_MAP.get(pwm_raw, pwm_raw)

    user_col = f"{origin}_username_final"
    pass_col = f"{origin}_password_final"
    
    username = data.get('username')
    password = data.get('password')

    with db_lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            
            # Check for existing row using ALL identifying columns
            c.execute(
                """SELECT 1 FROM autofill_results 
                   WHERE test_number = ? AND repetition = ? AND browser_package = ? AND pwm_package = ?""", 
                (test_number, repetition, browser, pwm)
            )
            exists = c.fetchone()
            
            if exists:
                query = f"""
                    UPDATE autofill_results 
                    SET {user_col} = ?, {pass_col} = ? 
                    WHERE test_number = ? AND repetition = ? AND browser_package = ? AND pwm_package = ?
                """
                c.execute(query, (username, password, test_number, repetition, browser, pwm))
            else:
                query = f'''
                    INSERT INTO autofill_results 
                    (test_number, repetition, browser_package, pwm_package, {user_col}, {pass_col}) 
                    VALUES (?, ?, ?, ?, ?, ?)
                '''
                c.execute(query, (test_number, repetition, browser, pwm, username, password))
            
            conn.commit()
            print(f"[{origin.upper()}] Data saved for Test {test_number} (Rep {repetition}) [{browser} / {pwm}]")

def get_context():
    """
    Extracts query parameters to pass to the templates.
    """
    return {
        "browser_package": request.args.get('browser_package', ''),
        "pwm_package": request.args.get('pwm_package', ''),
        "test_number": request.args.get('test_number', ''),
        "repetition": request.args.get('repetition', '0')
    }

# --- Blueprint Helpers ---
def add_report_route(bp, origin_name):
    """Adds the reporting endpoint to a blueprint"""
    @bp.route('/report', methods=['POST'])
    def report():
        data = request.json
        data['origin'] = origin_name
        update_result(data)
        return jsonify({"status": "success"})

# --------------------------
# BLUEPRINT FACTORIES
# --------------------------

def create_a_blueprint():
    bp = Blueprint('a_server', __name__, 
                   url_prefix='/a', 
                   static_folder='a', 
                   template_folder='a/templates')
    
    add_report_route(bp, 'a')
    
    @bp.route('/test_0')
    def test_0():    
        return make_response(render_template("simple_login.html", **get_context()))
    
    @bp.route('/test_1')
    def test_1():    
        return make_response(render_template("login_and_iframe_outside.html", **get_context()))
    
    @bp.route('/c')
    def c():    
        return make_response(render_template("login_and_iframe_inside.html"))
    
    @bp.route('/d')
    def d():    
        return make_response(render_template("sandboxed_iframe.html"))
    
    @bp.route('/e')
    def e():    
        return make_response(render_template("iframe.html"))
    
    @bp.route('/f')
    def f():    
        return make_response(render_template("simple_login.html"))
    
    @bp.route('/g')
    def g():    
        return make_response(render_template("object.html"))
    
    @bp.route('/h')
    def h():    
        return make_response(render_template("credentialless.html"))
    
    @bp.route('/i')
    def i():    
        return make_response(render_template("email_login_and_iframe.html"))

    return bp

def create_b_blueprint():
    bp = Blueprint('b_server', __name__, 
                   url_prefix='/b', 
                   static_folder='b', 
                   template_folder='b/templates')
    
    add_report_route(bp, 'b')

    @bp.route('/simple_login')
    def simple_login():
        return make_response(render_template("b_simple_login.html"))
    
    @bp.route('/iframe')
    def iframe():
        return make_response(render_template("iframe.html"))
    
    @bp.route('/pass_login')
    def pass_login():
        return make_response(render_template("pass_login.html"))
    
    return bp

# --------------------------
# MAIN APPLICATION
# --------------------------

def create_app():
    app = Flask(__name__)
    app.register_blueprint(create_a_blueprint())
    app.register_blueprint(create_b_blueprint())
    return app

# --------------------------
# THREAD RUNNERS
# --------------------------

def run_https(app):
    print(f"[HTTPS] Running on port {HTTPS_PORT} (Endpoints: /a/* and /b/*)")
    app.run(host='0.0.0.0', port=HTTPS_PORT, ssl_context=(CERT, KEY), use_reloader=False)

def run_http(app):
    print(f"[HTTP ] Running on port {HTTP_PORT} (Endpoints: /a/* and /b/*)")
    app.run(host='0.0.0.0', port=HTTP_PORT, use_reloader=False)

if __name__ == "__main__":
    main_app = create_app()
    threads = [
        threading.Thread(target=run_https, args=(main_app,)),
        threading.Thread(target=run_http, args=(main_app,))
    ]
    for t in threads:
        t.start()