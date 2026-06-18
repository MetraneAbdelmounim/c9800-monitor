"""
Multi-site store — admin-managed controller "sites" (Phase 1).

A site is one WLC connection + metadata. The number of sites is dynamic and
capped by the license (max_sites). Vendor is GLOBAL (a deployment is all-Cisco
or all-Ruckus), so it's not stored per-site — read from the global WLC settings.

Passwords are encrypted at rest (services.crypto). public_view() never returns
the password. get_enabled_sites() returns decrypted passwords for the live
client builder (used from Phase 2 onward).
"""
import logging
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from services.crypto import encrypt_secret, decrypt_secret
from services import licensing

log = logging.getLogger("Sites")
_db = None


def init_sites(mongo_db):
    global _db
    _db = mongo_db
    try:
        _db["sites"].create_index("name")
    except Exception as e:
        log.error(f"sites index setup failed: {e}")


def _oid(v):
    try:
        return ObjectId(v)
    except (InvalidId, TypeError):
        return None


def public_view(doc) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "location": doc.get("location", ""),
        "host": doc.get("host", ""),
        "port": doc.get("port", 443),
        "username": doc.get("username", ""),
        "verify_ssl": bool(doc.get("verify_ssl", False)),
        "enabled": bool(doc.get("enabled", True)),
        "password_set": bool(doc.get("password")),
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
        "updated_by": doc.get("updated_by"),
    }


def count_sites() -> int:
    return _db["sites"].count_documents({}) if _db is not None else 0


def list_sites() -> list:
    if _db is None:
        return []
    docs = _db["sites"].find().sort([("name", 1)])
    return [public_view(d) for d in docs]


def get_site(site_id):
    oid = _oid(site_id)
    if not oid or _db is None:
        return None
    return _db["sites"].find_one({"_id": oid})


def get_enabled_sites() -> list:
    """Internal view WITH decrypted password — for the live client builder."""
    if _db is None:
        return []
    out = []
    for d in _db["sites"].find({"enabled": True}).sort([("name", 1)]):
        out.append({
            "id": str(d["_id"]), "name": d.get("name", ""), "location": d.get("location", ""),
            "host": d.get("host", ""), "port": int(d.get("port", 443)),
            "username": d.get("username", ""), "password": decrypt_secret(d.get("password", "")),
            "verify_ssl": bool(d.get("verify_ssl", False)),
        })
    return out


def _validate(data, require_host=True):
    name = (data.get("name") or "").strip()
    host = (data.get("host") or "").strip()
    if not name:
        return None, "name required"
    if require_host and not host:
        return None, "host required"
    try:
        port = int(data.get("port") or 443)
    except (TypeError, ValueError):
        return None, "port must be a number"
    if not (1 <= port <= 65535):
        return None, "port must be 1-65535"
    return {"name": name, "host": host, "port": port}, None


def create_site(data, updated_by) -> dict:
    if _db is None:
        return {"error": "sites DB not initialized"}

    cap = licensing.max_sites()
    if cap is not None and count_sites() >= cap:
        return {"error": f"license allows a maximum of {cap} site(s)"}

    base, err = _validate(data)
    if err:
        return {"error": err}

    doc = {
        "name": base["name"], "location": (data.get("location") or "").strip(),
        "host": base["host"], "port": base["port"],
        "username": (data.get("username") or "").strip(),
        "password": encrypt_secret(data.get("password") or ""),
        "verify_ssl": bool(data.get("verify_ssl", False)),
        "enabled": bool(data.get("enabled", True)),
        "updated_at": datetime.now(timezone.utc), "updated_by": updated_by,
    }
    res = _db["sites"].insert_one(doc)
    doc["_id"] = res.inserted_id
    log.info(f"Site created by {updated_by}: {doc['name']} ({doc['host']}:{doc['port']})")
    return public_view(doc)


def update_site(site_id, data, updated_by) -> dict:
    oid = _oid(site_id)
    if not oid or _db is None:
        return {"error": "invalid id"}
    cur = _db["sites"].find_one({"_id": oid})
    if not cur:
        return {"error": "not found"}

    upd = {"updated_at": datetime.now(timezone.utc), "updated_by": updated_by}
    if "name" in data:
        if not (data.get("name") or "").strip():
            return {"error": "name cannot be empty"}
        upd["name"] = data["name"].strip()
    if "location" in data:
        upd["location"] = (data.get("location") or "").strip()
    if "host" in data:
        if not (data.get("host") or "").strip():
            return {"error": "host cannot be empty"}
        upd["host"] = data["host"].strip()
    if "port" in data:
        try:
            port = int(data.get("port") or 443)
        except (TypeError, ValueError):
            return {"error": "port must be a number"}
        if not (1 <= port <= 65535):
            return {"error": "port must be 1-65535"}
        upd["port"] = port
    if "username" in data:
        upd["username"] = (data.get("username") or "").strip()
    if data.get("password"):                       # only replace when provided
        upd["password"] = encrypt_secret(data["password"])
    if "verify_ssl" in data:
        upd["verify_ssl"] = bool(data["verify_ssl"])
    if "enabled" in data:
        upd["enabled"] = bool(data["enabled"])

    _db["sites"].update_one({"_id": oid}, {"$set": upd})
    log.info(f"Site updated by {updated_by}: {upd.get('name', cur.get('name'))}")
    return public_view(_db["sites"].find_one({"_id": oid}))


def delete_site(site_id) -> dict:
    oid = _oid(site_id)
    if not oid or _db is None:
        return {"error": "invalid id"}
    res = _db["sites"].delete_one({"_id": oid})
    if res.deleted_count == 0:
        return {"error": "not found"}
    return {"ok": True, "deleted": site_id}


def migrate_legacy(get_wlc_settings) -> None:
    """One-time: seed the first site from the existing single-controller config
    so upgrades don't start with an empty Sites list."""
    if _db is None or count_sites() > 0:
        return
    s = get_wlc_settings()
    host = (s.get("host") or "").strip()
    if not host:
        return
    _db["sites"].insert_one({
        "name": s.get("host") or "Main Site",
        "location": "", "host": host, "port": int(s.get("port", 443)),
        "username": s.get("username", ""),
        "password": encrypt_secret(s.get("password") or ""),
        "verify_ssl": bool(s.get("verify_ssl", False)), "enabled": True,
        "updated_at": datetime.now(timezone.utc), "updated_by": "migration",
    })
    log.info(f"Migrated existing controller into first site: {host}")
