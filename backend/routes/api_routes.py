"""
Core read API: dashboard, system, APs, clients, WLANs, RF, lifecycle, setup.
The live WLC client is swappable (demo ↔ cisco ↔ ruckus), so routes resolve it
through an accessor registered by app.py rather than importing it directly.
"""
from flask import Blueprint, jsonify, request, g

from services.auth import require_auth, require_role
from services.settings import get_target_version, set_target_version, get_setup_complete
from services.advisor import build_recommendations
from services.licensing import get_license_info
from services import sites as sites_svc
from services.access import resolve_site, allowed_sites
from models.wlc_client import WlcClient

_EMPTY_CLIENT = WlcClient()   # safe-defaults fallback when no site is configured

api_bp = Blueprint("api", __name__, url_prefix="/api")

_client_for = None      # callable(site_id) -> live client
_default_site = None    # callable() -> default site id
_db = None
_demo_mode = None       # callable -> bool


def init_api(client_for, default_site, mongo_db, effective_demo_mode):
    global _client_for, _default_site, _db, _demo_mode
    _client_for = client_for
    _default_site = default_site
    _db = mongo_db
    _demo_mode = effective_demo_mode


def _site_id():
    """Resolve the target site from ?site= — enforcing per-site access — then
    fall back to the default site."""
    return resolve_site(request.args.get("site")) or _default_site()


def _c():
    return _client_for(_site_id()) or _EMPTY_CLIENT


# ── health / system ────────────────────────────────────
# /api/health is intentionally public (used by the sidebar status dot).
@api_bp.route("/health")
def health():
    return jsonify(_c().health_check())


# ── multisite NOC overview (cached, no live controller hit) ─
@api_bp.route("/overview")
@require_auth
def overview():
    statuses = {d["_id"]: d for d in _db["site_status"].find()}
    allowed = allowed_sites()       # None = admin (all)
    out = []
    agg = {"sites": 0, "sites_online": 0, "total_aps": 0, "online_aps": 0, "clients": 0, "alerts": 0}
    for s in sites_svc.list_sites():
        if not s.get("enabled"):
            continue
        sid = s["id"]
        if allowed is not None and sid not in allowed:
            continue
        st = statuses.get(sid, {})
        alerts = _db["events"].count_documents({"site_id": sid, "active": True, "acked": False})
        reachable = bool(st.get("reachable"))
        out.append({
            "id": sid, "name": s.get("name", sid), "location": s.get("location", ""),
            "reachable": reachable, "total_aps": st.get("total_aps", 0), "online_aps": st.get("online_aps", 0),
            "clients": st.get("clients", 0), "cpu": st.get("cpu", 0), "mem": st.get("mem", 0),
            "alerts": alerts,
            "updated_at": st["updated_at"].isoformat() if st.get("updated_at") else None,
        })
        agg["sites"] += 1
        agg["sites_online"] += 1 if reachable else 0
        agg["total_aps"] += st.get("total_aps", 0)
        agg["online_aps"] += st.get("online_aps", 0)
        agg["clients"] += st.get("clients", 0)
        agg["alerts"] += alerts
    out.sort(key=lambda x: (x["name"] or "").lower())
    return jsonify({"totals": agg, "sites": out})


@api_bp.route("/dashboard")
@require_auth
def dashboard():
    return jsonify(_c().get_dashboard())


@api_bp.route("/system")
@require_auth
def system_info():
    return jsonify(_c().get_system_info())


@api_bp.route("/cpu")
@require_auth
def cpu():
    return jsonify(_c().get_cpu_usage())


@api_bp.route("/memory")
@require_auth
def memory():
    return jsonify(_c().get_memory_usage())


# ── access points ──────────────────────────────────────
@api_bp.route("/aps")
@require_auth
def aps():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    return jsonify(_c().get_ap_summary(page=page, per_page=per_page))


@api_bp.route("/aps/count")
@require_auth
def ap_count():
    return jsonify(_c().get_ap_count())


@api_bp.route("/aps/<path:mac>")
@require_auth
def ap_detail(mac):
    return jsonify(_c().get_ap_detail(mac))


# ── clients ─────────────────────────────────────────────
@api_bp.route("/clients")
@require_auth
def clients_summary():
    return jsonify(_c().get_client_summary())


@api_bp.route("/clients/detail")
@require_auth
def clients_detail():
    page = request.args.get("page", None, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    return jsonify(_c().get_client_details(page=page, per_page=per_page))


@api_bp.route("/clients/search")
@require_auth
def clients_search():
    return jsonify(_c().search_clients(request.args.get("q", "")))


@api_bp.route("/clients/stats")
@require_auth
def clients_stats():
    return jsonify(_c().get_client_stats())


@api_bp.route("/clients/<mac>")
@require_auth
def client_detail(mac):
    return jsonify(_c().get_client_detail(mac))


# ── wlans / rf / interfaces ─────────────────────────────
@api_bp.route("/wlans")
@require_auth
def wlans():
    return jsonify(_c().get_wlan_list())


@api_bp.route("/rf")
@require_auth
def rf():
    return jsonify(_c().get_rf_data())


@api_bp.route("/rf/analysis")
@require_auth
def rf_analysis():
    return jsonify(_c().get_rf_analysis())


@api_bp.route("/interfaces")
@require_auth
def interfaces():
    return jsonify(_c().get_interfaces())


@api_bp.route("/advisor")
@require_auth
def advisor():
    return jsonify(build_recommendations(_c(), _db))


# ── AP lifecycle / firmware compliance ──────────────────
@api_bp.route("/lifecycle")
@require_auth
def lifecycle():
    aps = _c().get_ap_lifecycle()
    target = get_target_version()
    counts = {d.get("mac"): d for d in _db["ap_lifecycle"].find(
        {"site_id": _site_id()}, {"mac": 1, "reboot_count": 1, "flap_count": 1})}
    rows, versions = [], {}
    for a in aps:
        c = counts.get(a["mac"], {})
        compliant = (not target) or (a.get("sw_version") == target)
        rows.append({**a, "compliant": compliant,
                     "reboot_count": c.get("reboot_count", 0),
                     "flap_count": c.get("flap_count", 0)})
        v = a.get("sw_version") or "unknown"
        versions[v] = versions.get(v, 0) + 1
    compliant_n = sum(1 for r in rows if r["compliant"])
    return jsonify({
        "target": target,
        "summary": {"total": len(rows), "compliant": compliant_n, "noncompliant": len(rows) - compliant_n},
        "by_version": [{"version": v, "count": n} for v, n in sorted(versions.items(), key=lambda x: -x[1])],
        "aps": sorted(rows, key=lambda r: (r["compliant"], -r["reboot_count"], r["name"])),
    })


@api_bp.route("/lifecycle/target", methods=["PUT"])
@require_role("admin")
def lifecycle_target():
    data = request.get_json(silent=True) or {}
    set_target_version((data.get("target") or "").strip(), g.user["username"])
    return jsonify({"target": get_target_version()})


# ── first-run setup signal ──────────────────────────────
@api_bp.route("/setup/status")
@require_auth
def setup_status():
    return jsonify({
        "setup_complete": get_setup_complete(),
        "demo_mode": _demo_mode(),
        "user_count": _db["users"].estimated_document_count(),
        "license": get_license_info(),
    })
