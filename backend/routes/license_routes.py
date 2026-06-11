"""
License API:
  GET  /api/license   -> current status (any authenticated user)
  POST /api/license   -> activate/upload a license (admin only)  body: { "key": "WMLIC1...." }

These routes are exempt from the license lock gate (so an admin can activate
while the app is otherwise locked) — see the gate in app.py.
"""
from flask import Blueprint, request, jsonify, g

from services.auth import require_auth, require_role
from services.licensing import activate_license, get_license_info, LicenseError

license_bp = Blueprint("license", __name__, url_prefix="/api/license")


@license_bp.route("", methods=["GET"])
@require_auth
def status():
    return jsonify(get_license_info())


@license_bp.route("", methods=["POST"])
@require_role("admin")
def activate():
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"error": "license key required"}), 400
    try:
        info = activate_license(key, g.user["username"])
        return jsonify({"ok": True, **info})
    except LicenseError as e:
        return jsonify({"error": str(e)}), 400