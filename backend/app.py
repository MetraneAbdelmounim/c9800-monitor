"""
WLC Monitor — Flask backend (composition root).

Wires together: MongoDB, auth + settings stores, the swappable WLC client
(demo ↔ cisco ↔ ruckus), the background collector / event engine / cleanup
scheduler, and the route blueprints (routes/). Business logic lives in
services/, the vendor-neutral client contract in models/.
"""
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from pymongo import MongoClient
import logging, atexit, os

from config import *
from services.cisco_client import C9800RestconfClient
from services.collector import ClientCollector
from services.events import EventEngine
from services.cleanup import CleanupScheduler
from services.settings_watcher import SettingsWatcher
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
from services.limiter import limiter

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

# ── License gate ───────────────────────────────────────
# Verify the signed license. Enforced in production (LICENSE_ENFORCE); in dev
# it's a warning so local work isn't blocked.
from services.licensing import verify_license, LicenseError
try:
    _lic = verify_license()
    log.info(f"License OK — '{_lic['customer']}' ({_lic['edition']}), "
             f"expires {_lic['expires']} ({_lic['days_left']} days left)")
    if _lic["days_left"] <= 30:
        log.warning(f"License expires in {_lic['days_left']} days — renew soon")
except LicenseError as _e:
    if LICENSE_ENFORCE:
        raise RuntimeError(
            f"License check failed: {_e}\n"
            "Provide a valid license via LICENSE_KEY or license.key. "
            "(Set LICENSE_ENFORCE=false to bypass for internal use.)")
    log.warning(f"License not enforced — {_e}")

# In Docker, FRONTEND_DIR points at the built Angular bundle so Flask serves the
# SPA itself (static assets + index.html). Left unset in dev (ng serve).
FRONTEND_DIR = os.getenv("FRONTEND_DIR")
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
# Behind nginx: trust one proxy hop so request.remote_addr / scheme reflect the
# real client (needed for correct per-IP rate limiting and X-Forwarded-Proto).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
# Auth is via Bearer token (not cookies); origins are restrictable via CORS_ORIGINS.
CORS(app, origins=cors_origins())
# Per-IP rate limiting (brute-force protection on /api/auth/login).
limiter.init_app(app)

# ── Persistence + auth/settings stores ─────────────────
# Pass credentials as kwargs (not in the URI) so special chars like '@' in the
# password don't need URL-encoding.
_mongo_kwargs = {"serverSelectionTimeoutMS": 5000}
if MONGO_USER:
    _mongo_kwargs.update(username=MONGO_USER, password=MONGO_PASS, authSource=MONGO_AUTH_SOURCE)
mongo_client = MongoClient(MONGO_URI, **_mongo_kwargs)
mongo_db = mongo_client[MONGO_DB]
init_auth(mongo_db)
bootstrap_admin(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS)
init_settings(mongo_db)

# ── Live WLC client (vendor-selectable, demo override wins) ─
client = None
collector = None
event_engine = None
settings_watcher = None


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
    if settings_watcher is not None:
        settings_watcher.mark_synced()   # this process is already up to date


register_swap_callback(swap_wlc_client)

# ── Background workers & settings sync ─────────────────
# Two independent gates:
#  • _is_primary — true in production; under the dev reloader, true only in the
#    serving child (WERKZEUG_RUN_MAIN), so threads don't run twice in one host.
#  • RUN_WORKERS — true for the all-in-one container and the dedicated worker;
#    set false on web replicas so they DON'T poll (avoids N× load on the WLC and
#    duplicate event/cleanup runs). See docker-compose.scale.yml.
_is_primary = (not FLASK_DEBUG) or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
_run_workers = RUN_WORKERS and _is_primary

collector = ClientCollector(client, mongo_db, interval=COLLECT_INTERVAL)
cleanup_scheduler = CleanupScheduler(mongo_db)
register_cleanup(cleanup_scheduler)
event_engine = EventEngine(client, mongo_db, interval=60)
register_engine(event_engine)
# Every instance (worker or web replica) watches for settings edits made
# elsewhere so its own live client — used for on-demand WLC reads — stays current.
settings_watcher = SettingsWatcher(mongo_db, swap_wlc_client)

if _run_workers:
    collector.start();        atexit.register(collector.stop)
    cleanup_scheduler.start(); atexit.register(cleanup_scheduler.stop)
    event_engine.start();      atexit.register(event_engine.stop)
    log.info("Background workers STARTED (collector + events + cleanup)")
elif _is_primary:
    log.info("Web/API role — background workers disabled (RUN_WORKERS=false)")
else:
    log.info("Reloader parent process — background workers not started")

if _is_primary:
    settings_watcher.start(); atexit.register(settings_watcher.stop)

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
