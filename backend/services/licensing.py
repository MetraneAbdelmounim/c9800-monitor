"""
License verification + activation (Ed25519-signed token).

Activation flow: the app always boots, but is LOCKED (see the license gate in
app.py) until an admin uploads a valid license on the Licensing page
(POST /api/license). The token is stored in MongoDB and re-loaded on every
startup. As a convenience for automated installs, a LICENSE_KEY environment
variable auto-activates on first boot.

The public key is embedded; the private signing key stays with the vendor
(tools/license_private_key.pem, never shipped). See docs/LICENSING.md.
"""
import base64
import json
import logging
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

log = logging.getLogger("License")

# Embedded Ed25519 public key (hex of 32 raw bytes). Re-key by replacing this
# with the value printed by tools/gen_license.py after deleting the keypair.
_PUBLIC_KEY_HEX = "b8345423c3f6d156c5b40d2717e1a2ebd5a504c7d59e3364311e66ddd310e670"
_PREFIX = "WMLIC1"
_DOC_ID = "license"

_db = None
_state = {"token": None, "info": None, "exp": None}   # cached verification result


class LicenseError(Exception):
    pass


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _machine_fingerprint() -> str:
    mid = os.getenv("LICENSE_MACHINE_ID")
    if mid:
        return mid.strip()
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p) as f:
                return f.read().strip()
        except OSError:
            pass
    return ""


def verify_token(token: str):
    """Verify a token string → (info_dict, expiry_datetime). Raise LicenseError."""
    if not token or not token.strip():
        raise LicenseError("no license provided")
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != _PREFIX:
        raise LicenseError("malformed license token")
    _, body, sig = parts

    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(_PUBLIC_KEY_HEX))
    try:
        pub.verify(_b64url_decode(sig), body.encode())
    except (InvalidSignature, ValueError):
        raise LicenseError("invalid license signature (tampered or wrong key)")

    try:
        payload = json.loads(_b64url_decode(body))
    except Exception:
        raise LicenseError("unreadable license payload")

    expires = payload.get("expires")
    try:
        exp = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise LicenseError("license has no valid expiry date")
    now = datetime.now(timezone.utc)
    if now > exp:
        raise LicenseError(f"license expired on {expires}")

    mid = payload.get("machine_id")
    if mid and _machine_fingerprint() != mid:
        raise LicenseError("license not valid for this machine")

    info = {
        "customer": payload.get("customer", ""),
        "edition": payload.get("edition", "standard"),
        "expires": expires,
        "days_left": (exp - now).days,
        "machine_bound": bool(mid),
        "max_sites": payload.get("max_sites"),   # None = unlimited
        "valid": True,
    }
    return info, exp


def _cache(token, info, exp):
    _state["token"], _state["info"], _state["exp"] = token, info, exp


def _persist(token, info, user):
    if _db is not None:
        _db["settings"].replace_one({"_id": _DOC_ID}, {
            "_id": _DOC_ID, "key": token,
            "customer": info["customer"], "expires": info["expires"],
            "edition": info["edition"], "activated_by": user,
            "activated_at": datetime.now(timezone.utc),
        }, upsert=True)


def init_license(db):
    """Load a stored license from DB; if none, try auto-activating from LICENSE_KEY."""
    global _db
    _db = db

    token = None
    try:
        doc = db["settings"].find_one({"_id": _DOC_ID})
        token = (doc or {}).get("key")
    except Exception as e:
        log.error(f"license load failed: {e}")

    if not token:
        env = os.getenv("LICENSE_KEY")
        if env and env.strip():
            try:
                info, exp = verify_token(env)
                _persist(env.strip(), info, "env")
                _cache(env.strip(), info, exp)
                log.info(f"License auto-activated from LICENSE_KEY — '{info['customer']}' "
                         f"expires {info['expires']}")
                return
            except LicenseError as e:
                log.warning(f"LICENSE_KEY env invalid: {e}")

    if token:
        try:
            info, exp = verify_token(token)
            _cache(token, info, exp)
            log.info(f"License OK — '{info['customer']}' expires {info['expires']} "
                     f"({info['days_left']} days left)")
            if info["days_left"] <= 30:
                log.warning(f"License expires in {info['days_left']} days — renew soon")
            return
        except LicenseError as e:
            _cache(token, {"valid": False, "error": str(e)}, None)
            log.warning(f"Stored license invalid — {e}")
            return

    _cache(None, {"valid": False, "error": "no license activated"}, None)
    log.warning("No license activated — the application is locked until one is uploaded")


def activate_license(token: str, user: str = "admin"):
    """Verify + persist a license. Raise LicenseError if invalid/expired."""
    info, exp = verify_token(token)          # raises on bad/expired/wrong-machine
    token = token.strip()
    _persist(token, info, user)
    _cache(token, info, exp)
    log.info(f"License activated by {user} — '{info['customer']}' expires {info['expires']}")
    return info


def is_licensed() -> bool:
    info = _state["info"]
    if not info or not info.get("valid"):
        return False
    exp = _state["exp"]
    if exp and datetime.now(timezone.utc) > exp:           # expired while running
        _cache(_state["token"], {"valid": False, "error": "expired"}, exp)
        return False
    return True


def max_sites():
    """Site cap from the license, or None for unlimited (claim absent)."""
    info = _state["info"] or {}
    return info.get("max_sites") if info.get("valid") else None


def get_license_info():
    """Current license status (always a dict). Safe for the status API / GUI."""
    info = dict(_state["info"] or {"valid": False})
    exp = _state["exp"]
    if exp and info.get("valid"):
        days = (exp - datetime.now(timezone.utc)).days
        if days < 0:
            return {"valid": False, "error": "expired"}
        info["days_left"] = days
    return info