"""
Sites API (Phase 1 — admin-managed controllers):
  GET    /api/sites          -> { sites, count, max_sites }   (any authenticated user)
  POST   /api/sites          -> create site            (admin)
  PUT    /api/sites/<id>     -> update site            (admin)
  DELETE /api/sites/<id>     -> delete site            (admin)
  POST   /api/sites/test     -> test connectivity      (admin)

Vendor is global (all sites share one vendor), read from the WLC settings.
"""
from flask import Blueprint, request, jsonify, g

from services.auth import require_auth, require_role
from services import sites as sites_svc
from services import licensing
from services.access import allowed_sites
from services.settings import get_wlc_settings
from services.cisco_client import C9800RestconfClient

sites_bp = Blueprint("sites", __name__, url_prefix="/api/sites")


def _build_client(host, port, username, password, verify_ssl):
    vendor = (get_wlc_settings().get("vendor") or "cisco").lower()
    if vendor == "ruckus":
        from services.ruckus_client import RuckusClient
        return RuckusClient(host, port, username, password, verify_ssl)
    return C9800RestconfClient(host, port, username, password, verify_ssl)


@sites_bp.route("", methods=["GET"])
@require_auth
def list_all():
    sites = sites_svc.list_sites()
    allowed = allowed_sites()                    # None = admin (all)
    if allowed is not None:
        sites = [s for s in sites if s["id"] in allowed]
    return jsonify({
        "sites": sites,
        "count": len(sites) if allowed is not None else sites_svc.count_sites(),
        "max_sites": licensing.max_sites(),     # None = unlimited
    })


@sites_bp.route("", methods=["POST"])
@require_role("admin")
def create():
    data = request.get_json(silent=True) or {}
    res = sites_svc.create_site(data, g.user["username"])
    return (jsonify(res), 400) if "error" in res else (jsonify(res), 201)


@sites_bp.route("/<sid>", methods=["PUT"])
@require_role("admin")
def update(sid):
    data = request.get_json(silent=True) or {}
    res = sites_svc.update_site(sid, data, g.user["username"])
    if "error" in res:
        code = 404 if res["error"] in ("not found", "invalid id") else 400
        return jsonify(res), code
    return jsonify(res)


@sites_bp.route("/<sid>", methods=["DELETE"])
@require_role("admin")
def delete(sid):
    res = sites_svc.delete_site(sid)
    return (jsonify(res), 404) if "error" in res else jsonify(res)


@sites_bp.route("/test", methods=["POST"])
@require_role("admin")
def test():
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    if not host:
        return jsonify({"ok": False, "error": "host required"}), 400
    try:
        port = int(data.get("port") or 443)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid port"}), 400

    # Reuse the stored password when editing an existing site without retyping it.
    password = data.get("password")
    if not password and data.get("id"):
        doc = sites_svc.get_site(data["id"])
        if doc:
            from services.crypto import decrypt_secret
            password = decrypt_secret(doc.get("password", ""))

    tester = _build_client(host, port, (data.get("username") or "").strip(),
                           password or "", bool(data.get("verify_ssl", False)))
    result = tester.health_check()
    status = result.get("status")
    return jsonify({
        "ok": status == "connected", "status": status,
        "code": result.get("code"), "error": result.get("error"),
        "tested_host": host, "tested_port": port,
    })
