"""
JWT authentication + user management.
- bcrypt for password hashing
- HS256 JWT tokens with role claim
- @require_auth / @require_role decorators
"""
import jwt
import bcrypt
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional
from flask import request, jsonify, g

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRES_HOURS

log = logging.getLogger("Auth")

VALID_ROLES = ("admin", "viewer")
MIN_PASSWORD_LEN = 8
_db = None


def init_auth(mongo_db):
    """Wire the users collection + indexes. Called once at startup."""
    global _db
    _db = mongo_db
    try:
        _db["users"].create_index("username", unique=True)
        log.info("Users collection indexes ready")
    except Exception as e:
        log.error(f"User index setup failed: {e}")


# ── Password hashing ───────────────────────────────────
def hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def verify_password(plain: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed)
    except Exception:
        return False


# ── JWT ────────────────────────────────────────────────
def create_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXPIRES_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── User CRUD ──────────────────────────────────────────
def create_user(username: str, password: str, role: str = "viewer",
                must_change_password: bool = True) -> dict:
    if not username or not password:
        return {"error": "username and password required"}
    if role not in VALID_ROLES:
        return {"error": f"role must be one of {VALID_ROLES}"}
    if len(password) < MIN_PASSWORD_LEN:
        return {"error": f"password must be at least {MIN_PASSWORD_LEN} characters"}
    if _db["users"].find_one({"username": username}):
        return {"error": "user already exists"}
    _db["users"].insert_one({
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "must_change_password": bool(must_change_password),
        "created_at": datetime.now(timezone.utc),
    })
    return {"username": username, "role": role,
            "must_change_password": bool(must_change_password)}


def authenticate(username: str, password: str) -> Optional[dict]:
    user = _db["users"].find_one({"username": username})
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {
        "username": user["username"],
        "role": user.get("role", "viewer"),
        "must_change_password": bool(user.get("must_change_password", False)),
    }


def get_user(username: str) -> Optional[dict]:
    user = _db["users"].find_one({"username": username})
    if not user:
        return None
    return {
        "username": user["username"],
        "role": user.get("role", "viewer"),
        "must_change_password": bool(user.get("must_change_password", False)),
    }


def change_password(username: str, new_password: str) -> dict:
    if len(new_password) < MIN_PASSWORD_LEN:
        return {"error": f"password must be at least {MIN_PASSWORD_LEN} characters"}
    res = _db["users"].update_one(
        {"username": username},
        {"$set": {
            "password_hash": hash_password(new_password),
            "must_change_password": False,
        }},
    )
    if res.matched_count == 0:
        return {"error": "user not found"}
    return {"ok": True}


def bootstrap_admin(default_user: str, default_pass: str):
    """Create a default admin if the users collection is empty.
    Flagged as must_change_password so the UI forces a rotation on first login."""
    if _db["users"].estimated_document_count() == 0:
        _db["users"].insert_one({
            "username": default_user,
            "password_hash": hash_password(default_pass),
            "role": "admin",
            "must_change_password": True,
            "created_at": datetime.now(timezone.utc),
        })
        log.warning(
            f"Bootstrap admin created: user='{default_user}' pass='{default_pass}' "
            "— must be changed on first login"
        )


# ── Decorators ─────────────────────────────────────────
def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid Authorization header"}), 401
        token = auth[7:].strip()
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user = {"username": payload["sub"], "role": payload.get("role", "viewer")}
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    def deco(fn):
        @wraps(fn)
        @require_auth
        def wrapper(*args, **kwargs):
            if g.user["role"] not in roles:
                return jsonify({"error": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco
