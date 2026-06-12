#!/usr/bin/env python3
"""
WireMetry license generator — VENDOR-ONLY tool. Do NOT ship this or the private
key to clients.

It signs a license token (Ed25519) that the app verifies at startup with the
embedded public key. A license carries a customer name, an expiry date, an
edition, and an optional machine binding.

First run creates the keypair:
  tools/license_private_key.pem   (SECRET — keep it; never commit/ship)
  tools/license_public_key.hex    (embed this in backend/services/licensing.py)

Issue a license:
  python tools/gen_license.py --customer "American School of Benguerir" --days 365 --out license.key
  python tools/gen_license.py --customer "ACME" --expires 2027-12-31 --machine-id <id> --out acme.key

Give the resulting license.key to that client (mount it / set LICENSE_KEY).
"""
import argparse
import base64
import json
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

HERE = os.path.dirname(os.path.abspath(__file__))
PRIV_PATH = os.path.join(HERE, "license_private_key.pem")
PUB_HEX_PATH = os.path.join(HERE, "license_public_key.hex")
TOKEN_PREFIX = "WMLIC1"


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _load_keypair(allow_init=False):
    """Load the vendor signing key. Refuses to silently create one — a missing
    key almost always means "this isn't the vendor machine", and auto-generating
    a fresh key would mint licenses the SHIPPED app won't accept (its embedded
    public key differs) and quietly fork your signing identity."""
    if not os.path.exists(PRIV_PATH):
        if not allow_init:
            raise SystemExit(
                "\nERROR: signing key not found at:\n  " + PRIV_PATH + "\n\n"
                "This is the VENDOR private key — only the license issuer should have it.\n"
                "  - If you ARE the issuer: restore the key file to that path (back it up!).\n"
                "  - Genuine FIRST-TIME vendor setup only: re-run with  --init-keys\n"
                "    then embed the printed public key in backend/services/licensing.py\n"
                "    (_PUBLIC_KEY_HEX) and rebuild the app image.\n")
        priv = Ed25519PrivateKey.generate()
        with open(PRIV_PATH, "wb") as f:
            f.write(priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()))
        try:
            os.chmod(PRIV_PATH, 0o600)
        except OSError:
            pass
        print(f"[gen] created a NEW signing key -> {PRIV_PATH}  (KEEP SECRET — back it up)")
        print("[gen] You must embed the public key below in licensing.py and rebuild.")
    else:
        with open(PRIV_PATH, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None)

    pub_hex = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    with open(PUB_HEX_PATH, "w") as f:
        f.write(pub_hex)
    return priv, pub_hex


def make_token(priv, customer, expires, edition, machine_id):
    payload = {
        "customer": customer,
        "issued": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "expires": expires,
        "edition": edition,
        "machine_id": machine_id,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64url(priv.sign(body.encode()))
    return f"{TOKEN_PREFIX}.{body}.{sig}", payload


def main():
    ap = argparse.ArgumentParser(description="Generate a signed WireMetry license.")
    ap.add_argument("--customer", help="Client name embedded in the license")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--days", type=int, help="Valid for N days from today")
    g.add_argument("--expires", help="Explicit expiry date YYYY-MM-DD")
    ap.add_argument("--edition", default="standard")
    ap.add_argument("--machine-id", default=None,
                    help="Optional: bind to a machine fingerprint (see LICENSE_MACHINE_ID)")
    ap.add_argument("--out", default="license.key")
    ap.add_argument("--init-keys", action="store_true",
                    help="VENDOR first-time setup ONLY: create a new signing keypair")
    args = ap.parse_args()

    priv, pub_hex = _load_keypair(allow_init=args.init_keys)

    if not args.customer:
        if args.init_keys:
            print(f"\nPublic key (embed in backend/services/licensing.py, _PUBLIC_KEY_HEX):\n{pub_hex}")
            return
        ap.error("--customer is required to issue a license")

    if args.expires:
        expires = args.expires
    else:
        days = args.days if args.days else 365
        expires = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")

    token, payload = make_token(priv, args.customer, expires, args.edition, args.machine_id)
    with open(args.out, "w") as f:
        f.write(token + "\n")

    print(f"[gen] license -> {args.out}")
    print(f"      customer : {payload['customer']}")
    print(f"      expires  : {payload['expires']}")
    print(f"      edition  : {payload['edition']}")
    if payload["machine_id"]:
        print(f"      machine  : {payload['machine_id']}")
    print(f"\nPublic key (embed in backend/services/licensing.py if not already):\n{pub_hex}")


if __name__ == "__main__":
    main()