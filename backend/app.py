"""
C9800 WLC Monitor - Flask Backend
With MongoDB tracking, background collector, pagination for scale, JWT auth,
and runtime-mutable WLC settings (admin can hot-swap host/port).
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import logging, atexit, os

from config import *
from restconf_client import C9800RestconfClient
from client_collector import ClientCollector
from tracking_routes import tracking_bp, init_tracking
from map_routes import map_bp, init_map
from auth import init_auth, bootstrap_admin, require_auth
from auth_routes import auth_bp
from settings import init_settings, get_wlc_settings, get_demo_mode_override, get_setup_complete
from settings_routes import settings_bp, register_swap_callback, register_cleanup
from cleanup import CleanupScheduler

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
log = logging.getLogger("WLC-API")

# In Docker, FRONTEND_DIR points at the built Angular bundle so Flask serves
# the SPA itself (static assets + index.html). Left unset in dev (ng serve).
FRONTEND_DIR = os.getenv("FRONTEND_DIR")
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
# Allow all origins (auth is via Bearer token, not cookies, so wildcard is safe).
CORS(app, origins="*")

# MongoDB
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
mongo_db = mongo_client[MONGO_DB]

# Auth (init users collection + bootstrap default admin)
init_auth(mongo_db)
bootstrap_admin(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS)

# Settings (Mongo persistence for runtime-mutable WLC config)
init_settings(mongo_db)

# RESTCONF Client (built from settings — Mongo overrides config defaults)
# Demo mode: Mongo override (set via admin UI) wins over env DEMO_MODE.
client = None
collector = None


def effective_demo_mode() -> bool:
    override = get_demo_mode_override()
    if override is not None:
        return override
    return DEMO_MODE


def _build_real_client():
    s = get_wlc_settings()
    log.info(f"Connecting to WLC {s['host']}:{s['port']} (source={s.get('source','config')})")
    return C9800RestconfClient(s["host"], s["port"], s["username"], s["password"], s["verify_ssl"])


def _build_client():
    if effective_demo_mode():
        from demo_data import DemoClient
        log.info("Live client: DemoClient (simulated data)")
        return DemoClient()
    return _build_real_client()


client = _build_client()


def swap_wlc_client():
    """Re-instantiate the live client (demo or real) and rewire the collector."""
    global client
    new_c = _build_client()
    client = new_c
    if collector is not None:
        collector.rc = new_c


register_swap_callback(swap_wlc_client)

# Background Collector
collector = ClientCollector(client, mongo_db, interval=COLLECT_INTERVAL)
collector.start()
atexit.register(collector.stop)

# Scheduled tracking-data cleanup (admin-configurable cadence + retention)
cleanup_scheduler = CleanupScheduler(mongo_db)
cleanup_scheduler.start()
atexit.register(cleanup_scheduler.stop)
register_cleanup(cleanup_scheduler)

# AP floor-map blueprint (routes carry their own @require_auth / @require_role)
init_map(mongo_db)
app.register_blueprint(map_bp)

# Tracking blueprint: protect every route inside with require_auth
init_tracking(mongo_db)

@tracking_bp.before_request
def _tracking_auth():
    # Let CORS preflights through untouched: browsers send OPTIONS with no
    # Authorization header, so enforcing auth here would 401 the preflight and
    # the real request would never fire. flask_cors answers the OPTIONS itself.
    if request.method == "OPTIONS":
        return None
    return require_auth(lambda: None)()

app.register_blueprint(tracking_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(settings_bp)

# ── API Routes ─────────────────────────────────────────
# /api/health is intentionally public (used by the sidebar status dot).
@app.route("/api/health")
def health():
    return jsonify(client.health_check())

@app.route("/api/dashboard")
@require_auth
def dashboard():
    return jsonify(client.get_dashboard())

@app.route("/api/system")
@require_auth
def system_info():
    return jsonify(client.get_system_info())

@app.route("/api/cpu")
@require_auth
def cpu():
    return jsonify(client.get_cpu_usage())

@app.route("/api/memory")
@require_auth
def memory():
    return jsonify(client.get_memory_usage())

@app.route("/api/aps")
@require_auth
def aps():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)
    return jsonify(client.get_ap_summary(page=page, per_page=per_page))

@app.route("/api/aps/count")
@require_auth
def ap_count():
    return jsonify(client.get_ap_count())

@app.route("/api/aps/<path:mac>")
@require_auth
def ap_detail(mac):
    return jsonify(client.get_ap_detail(mac))

@app.route("/api/clients")
@require_auth
def clients_summary():
    return jsonify(client.get_client_summary())

@app.route("/api/clients/detail")
@require_auth
def clients_detail():
    page = request.args.get("page", None, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)
    return jsonify(client.get_client_details(page=page, per_page=per_page))

@app.route("/api/clients/search")
@require_auth
def clients_search():
    q = request.args.get("q", "")
    return jsonify(client.search_clients(q))

@app.route("/api/clients/stats")
@require_auth
def clients_stats():
    return jsonify(client.get_client_stats())

@app.route("/api/clients/<mac>")
@require_auth
def client_detail(mac):
    return jsonify(client.get_client_detail(mac))

@app.route("/api/wlans")
@require_auth
def wlans():
    return jsonify(client.get_wlan_list())

@app.route("/api/rf")
@require_auth
def rf():
    return jsonify(client.get_rf_data())

@app.route("/api/interfaces")
@require_auth
def interfaces():
    return jsonify(client.get_interfaces())


@app.route("/api/setup/status")
@require_auth
def setup_status():
    """First-run signal for the UI:
       - setup_complete: has an admin saved WLC settings yet?
       - demo_mode: is the live client currently the simulator?
       - user_count: how many user accounts exist."""
    return jsonify({
        "setup_complete": get_setup_complete(),
        "demo_mode": effective_demo_mode(),
        "user_count": mongo_db["users"].estimated_document_count(),
    })


# ── Serve built frontend (production / Docker) ─────────
# With hash routing the SPA only ever requests "/" + static assets, so a single
# index route plus Flask's static handler is enough — no catch-all needed.
if FRONTEND_DIR:
    @app.route("/")
    def _spa_index():
        return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
