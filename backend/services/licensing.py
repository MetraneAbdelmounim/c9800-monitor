"""
License verification — Ed25519-signed token, paired with tools/gen_license.py.

The public key is embedded below; the private signing key stays with the vendor
(tools/license_private_key.pem, never shipped). A valid license is required to
run when LICENSE_ENFORCE is true (default: production). Provide it via:
  • LICENSE_KEY  — the token string, or
  • LICENSE_FILE — path to a file (default: ./license.key or /app/license.key)

A license carries: customer, issued, expires (YYYY-MM-DD), edition, and an
optional machine_id binding.
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

_INFO = None  # cached result of the last successful verification


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


def _load_token():
    tok = os.getenv("LICENSE_KEY")
    if tok and tok.strip():
        return tok.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.getenv("LICENSE_FILE"), "license.key", "/app/license.key",
                  os.path.join(here, "..", "license.key")]
    for c in candidates:
        if c and os.path.exists(c):
            with open(c) as f:
                return f.read().strip()
    return None


def verify_license():
    """Return a license-info dict if valid; raise LicenseError otherwise."""
    global _INFO
    token = _load_token()
    if not token:
        raise LicenseError("no license found (set LICENSE_KEY or provide license.key)")

    parts = token.split(".")
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

    mid_claim = payload.get("machine_id")
    if mid_claim and _machine_fingerprint() != mid_claim:
        raise LicenseError("license not valid for this machine")

    _INFO = {
        "customer": payload.get("customer", ""),
        "edition": payload.get("edition", "standard"),
        "expires": expires,
        "days_left": (exp - now).days,
        "machine_bound": bool(mid_claim),
        "valid": True,
    }
    return _INFO


def get_license_info():
    """The last verified license info (or None). Safe for the GUI/status API."""
    return _INFO