"""
WLC Monitor — Flask backend (composition root).

Wires together: MongoDB, auth + settings stores, the swappable WLC client
(demo ↔ cisco ↔ ruckus), the background collector / event engine / cleanup
scheduler, and the route blueprints (routes/). Business logic lives in
services/, the vendor-neutral client contract in models/.
"""
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import logging, atexit, os

from config import *
from services.cisco_client import C9800RestconfClient
from services.collector import ClientCollector
from services.events import EventEngine
from services.cleanup import CleanupScheduler
from services.auth import init_auth, bootstrap_admin, require_auth
from services.settings import (
    init_settings, get_wlc_settings, get_demo_mode_override, get_setup_complete,
)
from routes.api_routes import api_bp, init_api
from routes.auth_routes import auth_bp
from routes.settings_routes import settings_bp, register_swap_callback, register_cleanup
from routes.tracking_routes import tracking_bp, init_tracking
from routes.map_routes import map_bp, init_map
from routes.event_routes import events_bp, register_engine

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
log = logging.getLogger("WLC-API")

# ── Security gate ──────────────────────────────────────
# Refuse to start in production (FLASK_DEBUG=false) with insecure secrets;
# in dev, downgrade to warnings so local runs aren't blocked.
_blockers = production_blockers()
if _blockers:
    if FLASK_DEBUG:
        for p in _blockers:
            log.warning(f"[dev] INSECURE CONFIG: {p}")
    else:
        raise RuntimeError(
            "Refusing to start in production with insecure configuration:\n  - "
            + "\n  - ".join(_blockers)
            + "\nSet these in your environment/.env. (FLASK_DEBUG=true bypasses this for local dev.)")
for _w in security_warnings():
    log.warning(f"SECURITY: {_w}")

# In Docker, FRONTEND_DIR points at the built Angular bundle so Flask serves the
# SPA itself (static assets + index.html). Left unset in dev (ng serve).
FRONTEND_DIR = os.getenv("FRONTEND_DIR")
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
# Auth is via Bearer token (not cookies); origins are restrictable via CORS_ORIGINS.
CORS(app, origins=cors_origins())

# ── Persistence + auth/settings stores ─────────────────
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
mongo_db = mongo_client[MONGO_DB]
init_auth(mongo_db)
bootstrap_admin(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS)
init_settings(mongo_db)

# ── Live WLC client (vendor-selectable, demo override wins) ─
client = None
collector = None
event_engine = None


def effective_demo_mode() -> bool:
    override = get_demo_mode_override()
    return override if override is not None else DEMO_MODE


def _build_real_client():
    s = get_wlc_settings()
    vendor = (s.get("vendor") or "cisco").lower()
    log.info(f"Connecting to {vendor} WLC {s['host']}:{s['port']} (source={s.get('source','config')})")
    if vendor == "ruckus":
        from services.ruckus_client import RuckusClient
        return RuckusClient(s["host"], s["port"], s["username"], s["password"], s["verify_ssl"])
    return C9800RestconfClient(s["host"], s["port"], s["username"], s["password"], s["verify_ssl"])


def _build_client():
    if effective_demo_mode():
        from services.demo_client import DemoClient
        log.info("Live client: DemoClient (simulated data)")
        return DemoClient()
    return _build_real_client()


client = _build_client()


def swap_wlc_client():
    """Re-instantiate the live client (demo or real) and rewire dependents."""
    global client
    client = _build_client()
    if collector is not None:
        collector.rc = client
    if event_engine is not None:
        event_engine.rc = client


register_swap_callback(swap_wlc_client)

# ── Background workers ─────────────────────────────────
# Start the polling threads in exactly ONE process. Under the Flask debug
# reloader the script runs twice (watcher parent + serving child); only the
# child sets WERKZEUG_RUN_MAIN. Starting workers in both would leave a second
# collector polling the stale (pre-swap) client — e.g. still hitting the old
# Cisco controller after you switch the vendor to Ruckus. Gunicorn (prod) has
# no reloader, so workers start normally there.
_run_workers = (not FLASK_DEBUG) or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

collector = ClientCollector(client, mongo_db, interval=COLLECT_INTERVAL)
cleanup_scheduler = CleanupScheduler(mongo_db)
register_cleanup(cleanup_scheduler)
event_engine = EventEngine(client, mongo_db, interval=60)
register_engine(event_engine)

if _run_workers:
    collector.start();        atexit.register(collector.stop)
    cleanup_scheduler.start(); atexit.register(cleanup_scheduler.stop)
    event_engine.start();      atexit.register(event_engine.stop)
else:
    log.info("Reloader parent process — background workers not started (avoids duplicate polling)")

# ── Blueprints ─────────────────────────────────────────
init_api(lambda: client, mongo_db, effective_demo_mode)
init_map(mongo_db)
init_tracking(mongo_db)


@tracking_bp.before_request
def _tracking_auth():
    # Let CORS preflights through: browsers send OPTIONS without an Authorization
    # header, so enforcing auth here would 401 the preflight. flask_cors answers it.
    if request.method == "OPTIONS":
        return None
    return require_auth(lambda: None)()


app.register_blueprint(api_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(map_bp)
app.register_blueprint(events_bp)

# ── Serve built frontend (production / Docker) ─────────
# Hash routing means the SPA only requests "/" + static assets — index + Flask's
# static handler is enough, no catch-all.
if FRONTEND_DIR:
    @app.route("/")
    def _spa_index():
        return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
