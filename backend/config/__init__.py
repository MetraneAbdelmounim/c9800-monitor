"""
WLC Monitor — Configuration.
Reads from environment variables (load_dotenv reads .env if present).
Dev-friendly defaults so the app boots without a .env, BUT production
(FLASK_DEBUG=false) refuses to start with insecure secrets — see
validate_production(), called from app.py at startup.

For production, set at least:
  WLC_HOST, WLC_USERNAME, WLC_PASSWORD, JWT_SECRET, BOOTSTRAP_ADMIN_PASS,
  CORS_ORIGINS, and a MongoDB URI with credentials.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Known weak defaults — rejected in production by validate_production().
_WEAK_JWT = "change-me-in-prod-please-use-a-long-random-string"
_WEAK_PASS = {"", "admin", "change-me", "change-me-on-first-login", "password"}


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# ── WLC Connection ─────────────────────────────────────
# WLC_VENDOR selects the controller adapter: "cisco" (Catalyst 9800 RESTCONF)
# or "ruckus" (SmartZone/vSZ public REST API).
WLC_VENDOR = os.getenv("WLC_VENDOR", "cisco").strip().lower()
WLC_HOST = os.getenv("WLC_HOST", "192.168.100.16")
WLC_PORT = _int("WLC_PORT", 443)
WLC_USERNAME = os.getenv("WLC_USERNAME", "admin")
WLC_PASSWORD = os.getenv("WLC_PASSWORD", "")          # no baked-in credential
WLC_VERIFY_SSL = _bool("WLC_VERIFY_SSL", False)

# ── Flask Server ───────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = _int("FLASK_PORT", 5000)
FLASK_DEBUG = _bool("FLASK_DEBUG", True)
# Comma-separated allowed CORS origins; "*" only acceptable in dev.
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# ── Demo Mode ──────────────────────────────────────────
DEMO_MODE = _bool("DEMO_MODE", False)

# ── MongoDB ────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "c9800_monitor")
COLLECT_INTERVAL = _int("COLLECT_INTERVAL", 30)

# ── JWT Auth ───────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", _WEAK_JWT)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_HOURS = _int("JWT_EXPIRES_HOURS", 8)

# Bootstrap admin (created on first startup if no users exist)
BOOTSTRAP_ADMIN_USER = os.getenv("BOOTSTRAP_ADMIN_USER", "admin")
BOOTSTRAP_ADMIN_PASS = os.getenv("BOOTSTRAP_ADMIN_PASS", "admin")


def cors_origins():
    """CORS origins as a list, or '*' for any (dev only)."""
    v = (CORS_ORIGINS or "*").strip()
    if v == "*":
        return "*"
    return [o.strip() for o in v.split(",") if o.strip()]


def production_blockers():
    """Insecure config the app MUST NOT run with in production. app.py refuses
    to boot on any of these when FLASK_DEBUG is false; in dev they're warnings."""
    problems = []
    if JWT_SECRET == _WEAK_JWT or len(JWT_SECRET) < 24:
        problems.append("JWT_SECRET must be a strong random value (>= 24 chars). "
                        "Generate one:  python -c \"import secrets;print(secrets.token_urlsafe(48))\"")
    if BOOTSTRAP_ADMIN_PASS.strip().lower() in _WEAK_PASS:
        problems.append("BOOTSTRAP_ADMIN_PASS must be set to a strong, non-default password.")
    return problems


def security_warnings():
    """Non-fatal hardening advisories, logged at every startup."""
    w = []
    if CORS_ORIGINS.strip() == "*":
        w.append("CORS_ORIGINS is '*' — set it to the app's real URL in production.")
    if not WLC_VERIFY_SSL:
        w.append("WLC_VERIFY_SSL is false — TLS to the controller is not verified "
                 "(acceptable only with a controller cert you trust).")
    return w