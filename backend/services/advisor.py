"""
Network Advisor — turns the telemetry the app already collects into prioritized,
plain-language recommendations. Read-only / advisory; vendor-agnostic (uses the
WlcClient contract, so it works for Cisco and Ruckus alike — checks that need
data a vendor doesn't expose simply don't fire).
"""
import logging
from datetime import datetime, timezone

from services.settings import get_target_version

log = logging.getLogger("Advisor")
_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _safe(fn, default):
    try:
        return fn()
    except Exception as e:
        log.error(f"advisor source failed: {e}")
        return default


def _rec(severity, category, title, detail, action, count=0, items=None):
    return {"severity": severity, "category": category, "title": title,
            "detail": detail, "action": action, "count": count, "items": items or []}


def build_recommendations(client, db):
    rf = _safe(client.get_rf_analysis, {})
    radios = rf.get("radios", []) or []
    conflicts = rf.get("conflicts", []) or []
    lifecycle = _safe(client.get_ap_lifecycle, []) or []
    cstats = _safe(client.get_client_stats, {}) or {}
    csum = _safe(client.get_client_summary, {}) or {}
    cpu = _safe(client.get_cpu_usage, {}) or {}
    mem = _safe(client.get_memory_usage, {}) or {}
    target = get_target_version()
    recs = []

    # ── RF: co-channel / overlap conflicts ──────────────
    crit = [c for c in conflicts if c.get("severity") == "critical"]
    high = [c for c in conflicts if c.get("severity") == "high"]
    if crit or high:
        focal = [c["focal"]["ap_name"] for c in (crit + high) if c.get("focal")][:5]
        recs.append(_rec(
            "high" if crit else "medium", "RF",
            f"{len(crit) + len(high)} APs in co-channel / overlap conflict",
            "These APs share or overlap channels with neighbors they hear strongly, "
            "causing airtime contention and retries.",
            "Let RRM/ChannelFly re-optimize, or re-plan channels manually "
            "(2.4 GHz: stick to 1/6/11; 5 GHz: spread across non-DFS, narrower width in dense areas).",
            len(crit) + len(high), focal))

    # ── Capacity: high airtime utilization ──────────────
    busy = sorted([r for r in radios if r.get("utilization", 0) >= 70],
                  key=lambda r: -r["utilization"])
    if busy:
        recs.append(_rec(
            "high", "Capacity", f"{len(busy)} radios above 70% airtime",
            "Heavily-utilized channels mean clients see latency and reduced throughput.",
            "Reduce channel width (80→40 MHz), enable band steering toward 5/6 GHz, "
            "or add capacity in these areas.",
            len(busy),
            [f"{r['ap_name']} · {r['band']} ch{r['channel']} ({r['utilization']}%)" for r in busy[:5]]))

    # ── Health: APs offline ─────────────────────────────
    down = [a for a in lifecycle
            if any(x in (a.get("state", "") or "").lower() for x in ("down", "offline", "disconnect"))]
    if down:
        recs.append(_rec(
            "high", "Health", f"{len(down)} access point(s) offline",
            "Offline APs create coverage holes and drop clients in those areas.",
            "Check PoE/power, switch ports, and uplink for these APs.",
            len(down), [a["name"] for a in down[:5]]))

    # ── Firmware compliance ─────────────────────────────
    if lifecycle:
        if target:
            bad = [a for a in lifecycle if a.get("sw_version") and a["sw_version"] != target]
            if bad:
                recs.append(_rec(
                    "medium", "Firmware", f"{len(bad)} AP(s) not on target {target}",
                    "Mixed firmware leads to inconsistent behavior and exposure to fixed bugs.",
                    f"Schedule an upgrade of these APs to {target}.",
                    len(bad), [a["name"] for a in bad[:5]]))
        else:
            versions = sorted({a.get("sw_version") for a in lifecycle if a.get("sw_version")})
            if len(versions) > 1:
                recs.append(_rec(
                    "low", "Firmware", "Multiple AP firmware versions in use",
                    f"{len(versions)} different versions detected and no compliance target is set.",
                    "Set a target version on the AP Lifecycle page to track and enforce compliance.",
                    len(versions), versions[:5]))

    # ── Coverage: weak-signal clients ───────────────────
    dist = cstats.get("quality_distribution", {}) or {}
    poor = (dist.get("Poor", 0) or 0) + (dist.get("Critical", 0) or 0)
    total = cstats.get("total_clients", 0) or 0
    if total and poor / total >= 0.15:
        recs.append(_rec(
            "medium", "Coverage",
            f"{poor} clients with poor signal ({round(poor / total * 100)}%)",
            "A large share of clients have low RSSI/SNR — likely coverage gaps or sticky clients.",
            "Review AP placement/density in affected areas; consider raising the minimum data rate "
            "to shed far/sticky clients.",
            poor))

    # ── RF: 2.4 GHz band imbalance ──────────────────────
    c2, c5, c6 = csum.get("clients_2ghz", 0), csum.get("clients_5ghz", 0), csum.get("clients_6ghz", 0)
    tt = c2 + c5 + c6
    if tt and c2 >= 10 and c2 / tt >= 0.40:
        recs.append(_rec(
            "low", "RF", f"{round(c2 / tt * 100)}% of clients on 2.4 GHz",
            "Heavy 2.4 GHz usage suggests capable clients aren't steering to faster 5/6 GHz.",
            "Enable band steering and disable legacy (802.11b) low data rates to push dual-band "
            "clients onto 5 GHz.",
            c2))

    # ── Health: controller CPU / memory ─────────────────
    cpu_now = cpu.get("five_seconds", 0) or cpu.get("one_minute", 0) or 0
    if cpu_now >= 85:
        recs.append(_rec("high", "Health", f"Controller CPU at {cpu_now}%",
                         "Sustained high controller CPU can delay RRM, joins, and API responses.",
                         "Investigate controller load and recent config/scale changes.", 1))
    himem = [p for p in (mem.get("pools", []) or []) if (p.get("used_percent", 0) or 0) >= 85]
    if himem:
        recs.append(_rec("medium", "Health", "Controller memory utilization high",
                         "High memory use risks instability on the controller.",
                         "Review memory/disk usage and plan capacity.", len(himem),
                         [f"{p['name']} ({p['used_percent']}%)" for p in himem]))

    recs.sort(key=lambda r: _ORDER.get(r["severity"], 9))
    summary = {sev: sum(1 for r in recs if r["severity"] == sev)
               for sev in ("critical", "high", "medium", "low")}
    return {"summary": summary, "recommendations": recs,
            "generated_at": datetime.now(timezone.utc).isoformat()}
