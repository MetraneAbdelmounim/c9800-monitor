"""
Runtime-mutable settings persistence (WLC host/port/credentials).
Layered config:
  1. Default values from config.py (env / .env / hardcoded)
  2. Overrides from MongoDB `settings.wlc` document, if present

On startup, app.py reads via get_wlc_settings() which merges both.
Admins can update via PUT /api/settings/wlc, which writes to Mongo and
swaps the live RESTCONF client.

Note: the WLC password is stored cleartext in MongoDB because the
RESTCONF client needs it on every request. Restrict Mongo access
accordingly. A future improvement would be at-rest encryption.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import config as _config

log = logging.getLogger("Settings")
_db = None
_SETTINGS_KEY = "wlc"
_SYSTEM_KEY = "system"
_CLEANUP_KEY = "cleanup"

# Collector/tracking collections eligible for scheduled cleanup.
TRACKING_COLLECTIONS = (
    "client_snapshots", "client_snapshots_5m", "roaming_events", "ap_load_history",
)
CLEANUP_SCHEDULES = ("5min", "hourly", "daily", "weekly", "monthly")


def init_settings(mongo_db):
    global _db
    _db = mongo_db


def get_wlc_settings() -> dict:
    """Return the effective WLC settings (Mongo overrides config defaults)."""
    base = {
        "vendor": _config.WLC_VENDOR,
        "host": _config.WLC_HOST,
        "port": _config.WLC_PORT,
        "username": _config.WLC_USERNAME,
        "password": _config.WLC_PASSWORD,
        "verify_ssl": _config.WLC_VERIFY_SSL,
        "source": "config",
    }
    if _db is None:
        return base
    doc = _db["settings"].find_one({"_id": _SETTINGS_KEY})
    if not doc:
        return base
    return {
        "vendor": (doc.get("vendor") or base["vendor"]).lower(),
        "host": doc.get("host", base["host"]),
        "port": int(doc.get("port", base["port"])),
        "username": doc.get("username", base["username"]),
        "password": doc.get("password", base["password"]),
        "verify_ssl": bool(doc.get("verify_ssl", base["verify_ssl"])),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
        "source": "mongo",
    }


def save_wlc_settings(host: str, port: int, username: str,
                      password: Optional[str], verify_ssl: bool,
                      updated_by: str, vendor: Optional[str] = None) -> dict:
    """Persist settings. If password is empty/None, keep the previous one."""
    if _db is None:
        return {"error": "settings DB not initialized"}

    current = get_wlc_settings()
    final_pw = password if password else current["password"]
    final_vendor = (vendor or current.get("vendor") or "cisco").strip().lower()

    doc = {
        "_id": _SETTINGS_KEY,
        "vendor": final_vendor,
        "host": (host or "").strip(),
        "port": int(port),
        "username": (username or "").strip(),
        "password": final_pw,
        "verify_ssl": bool(verify_ssl),
        "updated_at": datetime.now(timezone.utc),
        "updated_by": updated_by,
    }
    _db["settings"].replace_one({"_id": _SETTINGS_KEY}, doc, upsert=True)
    log.info(f"WLC settings updated by {updated_by} -> {final_vendor} {doc['host']}:{doc['port']}")
    return {
        "vendor": doc["vendor"], "host": doc["host"], "port": doc["port"],
        "username": doc["username"], "verify_ssl": doc["verify_ssl"],
        "updated_at": doc["updated_at"], "updated_by": updated_by,
    }


def public_view(s: dict) -> dict:
    """Drop the password field for API responses."""
    out = {k: v for k, v in s.items() if k != "password"}
    out["password_set"] = bool(s.get("password"))
    return out


# ── Demo mode override ─────────────────────────────────
def get_demo_mode_override() -> Optional[bool]:
    """Returns the persisted demo-mode override, or None if not set."""
    if _db is None:
        return None
    doc = _db["settings"].find_one({"_id": _SYSTEM_KEY})
    if not doc or "demo_mode" not in doc:
        return None
    return bool(doc["demo_mode"])


def set_demo_mode_override(enabled: bool, updated_by: str) -> dict:
    if _db is None:
        return {"error": "settings DB not initialized"}
    doc = {
        "demo_mode": bool(enabled),
        "updated_at": datetime.now(timezone.utc),
        "updated_by": updated_by,
    }
    _db["settings"].update_one(
        {"_id": _SYSTEM_KEY},
        {"$set": doc},
        upsert=True,
    )
    log.info(f"Demo mode {'enabled' if enabled else 'disabled'} by {updated_by}")
    return {"demo_mode": bool(enabled),
            "updated_at": doc["updated_at"], "updated_by": updated_by}


def clear_demo_mode_override() -> dict:
    """Remove the runtime override → fall back to env DEMO_MODE."""
    if _db is None:
        return {"error": "settings DB not initialized"}
    _db["settings"].update_one(
        {"_id": _SYSTEM_KEY},
        {"$unset": {"demo_mode": ""}},
    )
    return {"ok": True}


# ── Initial setup flag ─────────────────────────────────
def get_setup_complete() -> bool:
    """True once the admin has confirmed initial WLC settings."""
    if _db is None:
        return False
    doc = _db["settings"].find_one({"_id": _SYSTEM_KEY})
    return bool(doc and doc.get("setup_complete"))


def set_setup_complete(updated_by: str) -> dict:
    if _db is None:
        return {"error": "settings DB not initialized"}
    _db["settings"].update_one(
        {"_id": _SYSTEM_KEY},
        {"$set": {
            "setup_complete": True,
            "setup_completed_at": datetime.now(timezone.utc),
            "setup_completed_by": updated_by,
        }},
        upsert=True,
    )
    log.info(f"Initial setup marked complete by {updated_by}")
    return {"ok": True}


# ── Tracking-data cleanup schedule ─────────────────────
def get_cleanup_settings() -> dict:
    base = {
        "enabled": False, "schedule": "weekly", "retention_days": 7,
        "last_run": None, "last_run_deleted": None, "last_bucket": None,
        "updated_at": None, "updated_by": None,
    }
    if _db is None:
        return base
    doc = _db["settings"].find_one({"_id": _CLEANUP_KEY})
    if not doc:
        return base
    return {
        "enabled": bool(doc.get("enabled", False)),
        "schedule": doc.get("schedule", "weekly"),
        "retention_days": int(doc.get("retention_days", 7)),
        "last_run": doc.get("last_run"),
        "last_run_deleted": doc.get("last_run_deleted"),
        "last_bucket": doc.get("last_bucket"),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


def save_cleanup_settings(enabled: bool, schedule: str,
                          retention_days, updated_by: str) -> dict:
    if _db is None:
        return {"error": "settings DB not initialized"}
    if schedule not in CLEANUP_SCHEDULES:
        return {"error": f"schedule must be one of {list(CLEANUP_SCHEDULES)}"}
    try:
        rd = max(0, int(retention_days))
    except (TypeError, ValueError):
        return {"error": "retention_days must be a number"}
    _db["settings"].update_one(
        {"_id": _CLEANUP_KEY},
        {"$set": {
            "enabled": bool(enabled), "schedule": schedule, "retention_days": rd,
            "updated_at": datetime.now(timezone.utc), "updated_by": updated_by,
        }},
        upsert=True,
    )
    log.info(f"Cleanup settings saved by {updated_by}: "
             f"enabled={enabled} schedule={schedule} retention={rd}d")
    return get_cleanup_settings()


def record_cleanup_run(deleted: int, bucket: Optional[str] = None) -> None:
    """Record a completed cleanup. Pass `bucket` only for scheduled runs so a
    manual run doesn't suppress the next scheduled one."""
    if _db is None:
        return
    upd = {"last_run": datetime.now(timezone.utc), "last_run_deleted": int(deleted)}
    if bucket is not None:
        upd["last_bucket"] = bucket
    _db["settings"].update_one({"_id": _CLEANUP_KEY}, {"$set": upd}, upsert=True)


def set_cleanup_bucket(bucket: str) -> None:
    if _db is None:
        return
    _db["settings"].update_one({"_id": _CLEANUP_KEY}, {"$set": {"last_bucket": bucket}}, upsert=True)


# ── AP firmware-compliance target ──────────────────────
def get_target_version() -> str:
    if _db is None:
        return ""
    doc = _db["settings"].find_one({"_id": "lifecycle"})
    return doc.get("target_ap_version", "") if doc else ""


def set_target_version(version: str, updated_by: str) -> None:
    if _db is None:
        return
    _db["settings"].update_one(
        {"_id": "lifecycle"},
        {"$set": {"target_ap_version": version, "updated_by": updated_by,
                  "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
