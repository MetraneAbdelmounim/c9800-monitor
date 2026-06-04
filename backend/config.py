"""
C9800 WLC Monitor — Configuration.
Reads from environment variables (load_dotenv reads .env if present).
Each setting falls back to a dev-friendly default so the app boots without a .env.

For production, set at least:
  WLC_HOST, WLC_USERNAME, WLC_PASSWORD, JWT_SECRET, BOOTSTRAP_ADMIN_PASS
"""
import os
from dotenv import load_dotenv

load_dotenv()


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
WLC_HOST = os.getenv("WLC_HOST", "192.168.100.16")
WLC_PORT = _int("WLC_PORT", 443)
WLC_USERNAME = os.getenv("WLC_USERNAME", "admin")
WLC_PASSWORD = os.getenv("WLC_PASSWORD", "P@ss2025")
WLC_VERIFY_SSL = _bool("WLC_VERIFY_SSL", False)

# ── Flask Server ───────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = _int("FLASK_PORT", 5000)
FLASK_DEBUG = _bool("FLASK_DEBUG", True)

# ── Demo Mode ──────────────────────────────────────────
DEMO_MODE = _bool("DEMO_MODE", False)

# ── MongoDB ────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "c9800_monitor")
COLLECT_INTERVAL = _int("COLLECT_INTERVAL", 30)

# ── JWT Auth ───────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-prod-please-use-a-long-random-string")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_HOURS = _int("JWT_EXPIRES_HOURS", 8)

# Bootstrap admin (created on first startup if no users exist)
BOOTSTRAP_ADMIN_USER = os.getenv("BOOTSTRAP_ADMIN_USER", "admin")
BOOTSTRAP_ADMIN_PASS = os.getenv("BOOTSTRAP_ADMIN_PASS", "admin")
