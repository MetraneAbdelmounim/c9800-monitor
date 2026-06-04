"""
Auth API Routes:
  POST /api/auth/login            -> { token, user }
  GET  /api/auth/me               -> current user
  POST /api/auth/change-password  -> change own password
  POST /api/auth/register         -> admin-only, create new user
  GET  /api/auth/users            -> admin-only, list users
"""
from flask import Blueprint, request, jsonify, g
from auth import (
    authenticate, create_token, create_user, change_password,
    require_auth, require_role, get_user,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    user = authenticate(username, password)
    if not user:
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["username"], user["role"])
    return jsonify({"token": token, "user": user})


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    # Refresh from DB so must_change_password reflects the latest state
    # (e.g., right after a password change without re-login).
    fresh = get_user(g.user["username"])
    if not fresh:
        return jsonify({"error": "user no longer exists"}), 404
    return jsonify(fresh)


@auth_bp.route("/change-password", methods=["POST"])
@require_auth
def change_pw():
    data = request.get_json(silent=True) or {}
    new_pw = data.get("new_password") or ""
    result = change_password(g.user["username"], new_pw)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@auth_bp.route("/register", methods=["POST"])
@require_role("admin")
def register():
    data = request.get_json(silent=True) or {}
    result = create_user(
        username=(data.get("username") or "").strip(),
        password=data.get("password") or "",
        role=data.get("role") or "viewer",
    )
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@auth_bp.route("/users", methods=["GET"])
@require_role("admin")
def list_users():
    from auth import _db
    users = list(_db["users"].find(
        {}, {"_id": 0, "password_hash": 0}
    ))
    # Normalize legacy docs that may lack the flag.
    for u in users:
        u["must_change_password"] = bool(u.get("must_change_password", False))
    return jsonify({"total": len(users), "users": users})


@auth_bp.route("/users/<username>", methods=["DELETE"])
@require_role("admin")
def delete_user(username):
    from auth import _db
    if username == g.user["username"]:
        return jsonify({"error": "you cannot delete your own account"}), 400
    target = _db["users"].find_one({"username": username})
    if not target:
        return jsonify({"error": "user not found"}), 404
    if target.get("role") == "admin":
        admin_count = _db["users"].count_documents({"role": "admin"})
        if admin_count <= 1:
            return jsonify({"error": "cannot delete the last admin"}), 400
    _db["users"].delete_one({"username": username})
    return jsonify({"ok": True, "deleted": username})
