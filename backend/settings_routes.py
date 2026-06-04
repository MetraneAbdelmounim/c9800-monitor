"""
WLC settings management (admin-only):
  GET  /api/settings/wlc        -> current settings (no password)
  PUT  /api/settings/wlc        -> persist + hot-swap live RESTCONF client
  POST /api/settings/wlc/test   -> test connectivity with proposed config
"""
from flask import Blueprint, request, jsonify, g
from auth import require_role, require_auth
from settings import (
    get_wlc_settings, save_wlc_settings, public_view,
    get_demo_mode_override, set_demo_mode_override, clear_demo_mode_override,
    get_setup_complete, set_setup_complete,
    get_cleanup_settings, save_cleanup_settings,
)
from restconf_client import C9800RestconfClient
import config as _config

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

# Callback registered by app.py — invoked after a successful save
# so the running app can swap its live client + collector reference.
_swap_callback = None
# CleanupScheduler instance registered by app.py.
_cleanup = None


def register_swap_callback(fn):
    global _swap_callback
    _swap_callback = fn


def register_cleanup(scheduler):
    global _cleanup
    _cleanup = scheduler


@settings_bp.route("/wlc", methods=["GET"])
@require_role("admin")
def get_wlc():
    return jsonify(public_view(get_wlc_settings()))


@settings_bp.route("/wlc", methods=["PUT"])
@require_role("admin")
def update_wlc():
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    if not host:
        return jsonify({"error": "host required"}), 400
    try:
        port = int(data.get("port") or 443)
    except (TypeError, ValueError):
        return jsonify({"error": "port must be a number"}), 400
    if not (1 <= port <= 65535):
        return jsonify({"error": "port must be 1-65535"}), 400

    saved = save_wlc_settings(
        host=host,
        port=port,
        username=(data.get("username") or "").strip(),
        password=data.get("password"),
        verify_ssl=bool(data.get("verify_ssl", False)),
        updated_by=g.user["username"],
    )
    if "error" in saved:
        return jsonify(saved), 500

    # First save → mark the initial setup as done so the UI stops nagging.
    if not get_setup_complete():
        set_setup_complete(g.user["username"])

    # Hot-swap the live client so subsequent API calls use the new endpoint.
    if _swap_callback:
        try:
            _swap_callback()
        except Exception as e:
            return jsonify({**saved, "warning": f"saved but live swap failed: {e}"})
    return jsonify(saved)


@settings_bp.route("/demo-mode", methods=["GET"])
@require_auth
def get_demo_mode():
    override = get_demo_mode_override()
    env_default = bool(_config.DEMO_MODE)
    effective = env_default if override is None else override
    return jsonify({
        "demo_mode": effective,
        "env_default": env_default,
        "override": override,        # None | true | false
        "source": "override" if override is not None else "env",
    })


@settings_bp.route("/demo-mode", methods=["PUT"])
@require_role("admin")
def update_demo_mode():
    data = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return jsonify({"error": "'enabled' (boolean) is required"}), 400
    enabled = bool(data["enabled"])
    result = set_demo_mode_override(enabled, updated_by=g.user["username"])
    if "error" in result:
        return jsonify(result), 500
    if _swap_callback:
        try:
            _swap_callback()
        except Exception as e:
            return jsonify({**result, "warning": f"saved but live swap failed: {e}"})
    return jsonify(result)


@settings_bp.route("/demo-mode", methods=["DELETE"])
@require_role("admin")
def reset_demo_mode():
    """Clear the override → fall back to env DEMO_MODE."""
    result = clear_demo_mode_override()
    if "error" in result:
        return jsonify(result), 500
    if _swap_callback:
        try:
            _swap_callback()
        except Exception as e:
            return jsonify({**result, "warning": f"cleared but live swap failed: {e}"})
    return jsonify(result)


@settings_bp.route("/wlc/test", methods=["POST"])
@require_role("admin")
def test_wlc():
    """Try to reach the WLC with the given config WITHOUT saving."""
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    if not host:
        return jsonify({"ok": False, "error": "host required"}), 400
    try:
        port = int(data.get("port") or 443)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid port"}), 400

    # If password is omitted, reuse the current stored one (so the user can
    # test changes to host/port without re-typing the password).
    password = data.get("password")
    if not password:
        password = get_wlc_settings()["password"]

    tester = C9800RestconfClient(
        host=host, port=port,
        username=(data.get("username") or "").strip(),
        password=password,
        verify_ssl=bool(data.get("verify_ssl", False)),
    )
    result = tester.health_check()
    status = result.get("status")
    ok = status == "connected"
    return jsonify({
        "ok": ok,
        "status": status,
        "code": result.get("code"),
        "error": result.get("error"),
        "tested_host": host,
        "tested_port": port,
    })


# ── Tracking-data cleanup ──────────────────────────────
def _cleanup_payload():
    s = get_cleanup_settings()
    s["stats"] = _cleanup.stats() if _cleanup else {}
    for k in ("last_run", "updated_at"):
        if s.get(k) is not None and hasattr(s[k], "isoformat"):
            s[k] = s[k].isoformat()
    return s


@settings_bp.route("/cleanup", methods=["GET"])
@require_auth
def get_cleanup():
    return jsonify(_cleanup_payload())


@settings_bp.route("/cleanup", methods=["PUT"])
@require_role("admin")
def update_cleanup():
    data = request.get_json(silent=True) or {}
    res = save_cleanup_settings(
        enabled=bool(data.get("enabled", False)),
        schedule=(data.get("schedule") or "weekly"),
        retention_days=data.get("retention_days", 7),
        updated_by=g.user["username"],
    )
    if "error" in res:
        return jsonify(res), 400
    return jsonify(_cleanup_payload())


@settings_bp.route("/cleanup/run", methods=["POST"])
@require_role("admin")
def run_cleanup_now():
    if not _cleanup:
        return jsonify({"error": "cleanup scheduler not available"}), 503
    return jsonify(_cleanup.run_now())
