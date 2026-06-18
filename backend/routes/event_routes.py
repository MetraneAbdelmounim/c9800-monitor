"""
Event-log API (security + RF + client anomalies). Reads require auth;
acknowledging requires auth (any signed-in user).
"""
from flask import Blueprint, request, jsonify, g
from services.auth import require_auth
from services.access import resolve_site

events_bp = Blueprint("events", __name__, url_prefix="/api/events")
_engine = None


def register_engine(engine):
    global _engine
    _engine = engine


@events_bp.route("", methods=["GET"])
@require_auth
def list_events():
    if not _engine:
        return jsonify({"events": [], "unacked": 0, "acked": 0})
    show_acked = request.args.get("show_acked", "false").lower() in ("1", "true", "yes")
    site = resolve_site(request.args.get("site") or None)   # enforces per-site access
    return jsonify(_engine.list_events(show_acked=show_acked, site_id=site))


@events_bp.route("/ack", methods=["POST"])
@require_auth
def ack():
    if not _engine:
        return jsonify({"error": "event engine unavailable"}), 503
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    return jsonify(_engine.ack(ids, g.user["username"]))


@events_bp.route("/ack-all", methods=["POST"])
@require_auth
def ack_all():
    if not _engine:
        return jsonify({"error": "event engine unavailable"}), 503
    return jsonify(_engine.ack_all(g.user["username"]))
