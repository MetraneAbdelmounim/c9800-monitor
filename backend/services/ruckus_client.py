"""
RuckusClient — adapter for Ruckus SmartZone / vSZ (public REST API).

Implements the WlcClient contract so the rest of the app works unchanged.
Validated against SmartZone 6.1.1 (API v11_0): auth via /serviceTicket, then
POST /query/{ap,client,wlan} (page is 1-based) returning {totalCount,list,hasMore}.
The query/ap response is rich (per-band channel, airtime utilization, noise,
EIRP, client counts), so AP/RF/spectrum views populate too.

Controller CPU/memory/disk/ports come from GET /controller + /controller/{id}/
statistics. Not wired (SmartZone exposes differently / not available): neighbor-
based channel-conflict detection, rogues (no /query/rogue in 6.1), aWIPS — these
fall back to WlcClient's safe defaults.
"""
import os
import re
import time
import logging
from datetime import datetime

import requests
import urllib3

from models.wlc_client import WlcClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger("Ruckus")

API_VERSION = os.getenv("RUCKUS_API_VERSION", "v11_0")
_WIDTH_RE = re.compile(r"\((\d+)\s*MHz\)", re.I)


def _i(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _s(v, d=""):
    return d if v is None else str(v)


def _first(d, *keys, default=None):
    if isinstance(d, dict):
        for k in keys:
            if d.get(k) is not None:
                return d[k]
    return default


def _to_mb(v):
    """Normalize a size to MB, auto-detecting the unit (bytes / KB / MB) by
    magnitude — SmartZone reports memory/disk inconsistently across versions."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    if v <= 0:
        return 0.0
    if v >= 1e9:                 # bytes (≥ ~1 GB worth)
        return v / (1024 * 1024)
    if v >= 1e6:                 # KB
        return v / 1024
    return v                     # already MB


def _band_from_channel(ch):
    if 1 <= ch <= 14:
        return "2.4 GHz"
    if 36 <= ch <= 177:
        return "5 GHz"
    return "Unknown"


class RuckusClient(WlcClient):
    def __init__(self, host, port, username, password, verify_ssl=False):
        self.base = f"https://{host}:{port}/wsg/api/public/{API_VERSION}"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({"Content-Type": "application/json"})
        self._ticket = None
        self._version = "Unknown"
        self._node_cache = None        # (controller_dict, latest_stats_dict, ts)

    # ── auth ───────────────────────────────────────────
    def _login(self):
        r = self.session.post(f"{self.base}/serviceTicket",
                              json={"username": self.username, "password": self.password}, timeout=15)
        r.raise_for_status()
        j = r.json()
        self._ticket = j.get("serviceTicket")
        self._version = j.get("controllerVersion", self._version)
        return self._ticket

    def _params(self):
        if not self._ticket:
            self._login()
        return {"serviceTicket": self._ticket}

    def _query(self, resource, limit=1000, max_pages=20):
        """SmartZone POST /query/<resource> (page is 1-based). Pages through
        until hasMore is false. Returns (list, totalCount)."""
        out, total, page = [], 0, 1
        while page <= max_pages:
            url = f"{self.base}/query/{resource}"
            try:
                r = self.session.post(url, params=self._params(),
                                      json={"page": page, "limit": limit, "filters": []}, timeout=40)
                if r.status_code in (401, 403):
                    self._ticket = None
                    r = self.session.post(url, params=self._params(),
                                          json={"page": page, "limit": limit, "filters": []}, timeout=40)
                r.raise_for_status()
                d = r.json()
            except Exception as e:
                log.error(f"query/{resource} page {page} failed: {e}")
                break
            lst = d.get("list") or []
            total = _i(d.get("totalCount"), total)
            out.extend(lst)
            if not d.get("hasMore") or not lst or len(out) >= total:
                break
            page += 1
        return out, total

    def _count(self, resource):
        try:
            r = self.session.post(f"{self.base}/query/{resource}", params=self._params(),
                                  json={"page": 1, "limit": 1, "filters": []}, timeout=20)
            r.raise_for_status()
            return _i(r.json().get("totalCount"), 0)
        except Exception as e:
            log.error(f"count {resource}: {e}")
            return 0

    def _get(self, path):
        url = f"{self.base}{path}"
        r = self.session.get(url, params=self._params(), timeout=25)
        if r.status_code in (401, 403):
            self._ticket = None
            r = self.session.get(url, params=self._params(), timeout=25)
        r.raise_for_status()
        return r.json() if r.content else {}

    def _node(self):
        """Cached (controller_dict, latest_stats_dict) for the cluster leader.
        Stats are 5-min time-series points; we use the most recent one."""
        if self._node_cache and (time.time() - self._node_cache[2]) < 15:
            return self._node_cache[0], self._node_cache[1]
        ctrl, stats = {}, {}
        try:
            lst = (self._get("/controller").get("list")) or []
            ctrl = next((c for c in lst if c.get("clusterRole") == "Leader"), lst[0] if lst else {})
            cid = ctrl.get("id")
            if cid:
                arr = self._get(f"/controller/{cid}/statistics")
                if isinstance(arr, list) and arr:
                    stats = arr[-1]
        except Exception as e:
            log.error(f"controller stats failed: {e}")
        self._node_cache = (ctrl, stats, time.time())
        return ctrl, stats

    # ── health / system ────────────────────────────────
    def health_check(self):
        try:
            self._login()
            return {"status": "connected" if self._ticket else "degraded",
                    "code": 200, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"status": "unreachable", "error": str(e), "timestamp": datetime.now().isoformat()}

    def get_system_info(self):
        ctrl, _ = self._node()
        return {"hostname": _s(_first(ctrl, "hostName", "name"), "SmartZone"),
                "version": _s(ctrl.get("version"), self._version),
                "model": _s(ctrl.get("model")),
                "timestamp": datetime.now().isoformat()}

    def get_cpu_usage(self):
        _, st = self._node()
        p = round(_first(st.get("cpu", {}), "percent", default=0) or 0)
        return {"five_seconds": p, "one_minute": p, "five_minutes": p}

    def get_memory_usage(self):
        ctrl, st = self._node()
        pools = []
        mem = st.get("memory") or {}
        if mem:
            pct = mem.get("percent")
            total = _first(mem, "total", "totalSize", "totalMemory", "totalBytes",
                           "totalInBytes", "max")
            # Total RAM may live on the controller node object instead of the sample.
            if not total:
                total = _first(ctrl, "totalMemory", "memorySize", "memTotal", "ramSize")
            used = _first(mem, "used", "usedSize", "usedBytes", "usedInBytes")
            free = _first(mem, "free", "freeSize", "available", "freeBytes", "freeInBytes")

            pool = {"name": "System Memory", "total_mb": 0, "used_mb": 0,
                    "used_percent": round(pct or 0, 1)}
            if total:
                t = _to_mb(total)
                if used is not None:
                    u = _to_mb(used)
                elif free is not None:
                    u = t - _to_mb(free)
                else:                       # only a percentage available → derive GB from it
                    u = (pct or 0) / 100.0 * t
                pool["total_mb"] = round(t)
                pool["used_mb"] = round(u)
                pool["free_mb"] = round(max(0.0, t - u))
                if pct is None and t:
                    pool["used_percent"] = round(u / t * 100, 1)
            pools.append(pool)
        disk = st.get("disk") or {}
        total, free = disk.get("total"), disk.get("free")
        if total:
            used = total - (free or 0)
            pools.append({"name": "Disk", "total_mb": round(total / 1024),
                          "used_mb": round(used / 1024), "free_mb": round((free or 0) / 1024),
                          "used_percent": round(used / total * 100, 1)})
        return {"pools": pools}

    def get_interfaces(self):
        _, st = self._node()
        ifaces = []
        for key in sorted(k for k in st if re.fullmatch(r"port\d+", k)):
            p = st[key] or {}
            active = bool(p.get("rxBytes") or p.get("txBytes"))
            ifaces.append({
                "name": key, "type": "ethernet", "admin_status": "up",
                "oper_status": "up" if active else "down", "ipv4": "", "subnet_mask": "",
                "mac": "", "speed_mbps": 0, "mtu": 0, "description": "", "last_change": "",
                "rx_kbps": round((p.get("rxBps", 0) or 0) / 1000),
                "tx_kbps": round((p.get("txBps", 0) or 0) / 1000),
                "in_errors": _i(p.get("rxDropped")), "out_errors": _i(p.get("txDropped")),
            })
        return {"interfaces": ifaces}

    # ── access points ──────────────────────────────────
    def get_ap_count(self):
        return {"total_aps": self._count("ap")}

    @staticmethod
    def _ap_row(ap):
        return {
            "name": _s(ap.get("deviceName")),
            "wtp_mac": _s(ap.get("apMac")), "mac": _s(ap.get("apMac")),
            "ip": _s(ap.get("ip")), "model": _s(ap.get("model")),
            "serial": _s(ap.get("serial")), "location": _s(_first(ap, "location", "apGroupName", "zoneName")),
            "sw_version": _s(ap.get("firmwareVersion")),
            "state": _s(ap.get("status")), "admin_state": _s(ap.get("administrativeState")),
            "mode": _s(ap.get("apGroupName")), "country": "",
            "policy_tag": _s(ap.get("apGroupName")), "site_tag": _s(ap.get("zoneName")), "rf_tag": "",
            "max_clients": 0, "uptime_sec": _i(ap.get("uptime")), "join_time": _s(ap.get("lastSeen")),
        }

    def get_ap_summary(self, page=1, per_page=50):
        rows, _ = self._query("ap")
        aps = [self._ap_row(a) for a in rows]
        start = (page - 1) * per_page
        return {"total_aps": len(aps), "page": page, "per_page": per_page,
                "total_pages": (len(aps) + per_page - 1) // per_page,
                "aps": aps[start:start + per_page]}

    def get_ap_addresses(self):
        rows, _ = self._query("ap")
        return [{"name": _s(a.get("deviceName")), "wtp_mac": _s(a.get("apMac")),
                 "mac": _s(a.get("apMac")), "ip": _s(a.get("ip"))} for a in rows]

    def get_ap_lifecycle(self):
        rows, _ = self._query("ap")
        return [{"name": _s(a.get("deviceName")), "mac": _s(a.get("apMac")),
                 "model": _s(a.get("model")), "sw_version": _s(a.get("firmwareVersion")),
                 "state": _s(a.get("status")), "boot_time": "",
                 "join_time": _s(a.get("lastSeen")), "uptime_sec": _i(a.get("uptime"))} for a in rows]

    # ── clients ────────────────────────────────────────
    @staticmethod
    def _client_band(c):
        ch = _i(c.get("channel"))
        if ch:
            return _band_from_channel(ch)
        return "Unknown"

    @staticmethod
    def _qual(rssi):
        if not rssi:        return 0, "No Data"
        if rssi >= -55:     return 90, "Excellent"
        if rssi >= -67:     return 70, "Good"
        if rssi >= -75:     return 50, "Fair"
        if rssi >= -82:     return 30, "Poor"
        return 10, "Critical"

    def _client_row(self, c):
        rssi = _i(c.get("rssi"))
        score, label = self._qual(rssi)
        return {
            "mac": _s(_first(c, "clientMac", "cpeMac")), "ip": _s(c.get("ipAddress")),
            "username": _s(c.get("userName")), "hostname": _s(c.get("hostname")),
            "device_type": _s(c.get("deviceType")), "os_type": _s(c.get("osType")),
            "ap_name": _s(_first(c, "apName", "apMac")), "ssid": _s(c.get("ssid")),
            "wlan_profile": _s(c.get("ssid")), "band": self._client_band(c),
            "channel": _i(c.get("channel")), "channel_width": "",
            "protocol": _s(c.get("radioType")),
            "rssi_dbm": rssi, "snr_db": _i(c.get("snr")),
            "quality_score": score, "quality_label": label,
            "data_rate_mbps": round(_i(c.get("txRatebps")) / 1_000_000) if c.get("txRatebps") else 0,
            "tx_power_dbm": 0, "spatial_streams": 0, "mcs_index": _i(c.get("medianTxMCSRate")),
            "state": _s(_first(c, "authStatus", "status")), "vlan": _i(c.get("vlan")),
            "bytes_tx": _i(c.get("txBytes")), "bytes_rx": _i(c.get("rxBytes")),
            "bssid": _s(c.get("bssid")), "assoc_time": _s(c.get("sessionStartTime")),
            "session_duration_sec": 0, "security": _s(c.get("encryptionMethod")),
        }

    def get_client_details(self, page=None, per_page=50):
        rows, _ = self._query("client")
        clients = [self._client_row(c) for c in rows]
        total = len(clients)
        if page is not None:
            start = (page - 1) * per_page
            return {"total": total, "page": page, "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page,
                    "clients": clients[start:start + per_page]}
        return {"total": total, "clients": clients}

    def get_client_summary(self):
        cl = self.get_client_details()["clients"]
        b = {"2.4 GHz": 0, "5 GHz": 0, "6 GHz": 0}
        for c in cl:
            if c["band"] in b:
                b[c["band"]] += 1
        return {"total_clients": len(cl), "run_state": len(cl),
                "auth_state": 0, "iplearn_state": 0, "webauth_state": 0, "random_mac_clients": 0,
                "clients_2ghz": b["2.4 GHz"], "clients_5ghz": b["5 GHz"], "clients_6ghz": b["6 GHz"]}

    def get_client_detail(self, mac):
        ml = mac.lower()
        for c in self.get_client_details()["clients"]:
            if c["mac"].lower() == ml:
                return c
        return {"error": "Client not found"}

    def search_clients(self, query):
        q = query.lower().strip()
        fields = ("mac", "ip", "username", "hostname", "ap_name", "ssid", "band")
        cl = [c for c in self.get_client_details()["clients"]
              if any(q in _s(c.get(f)).lower() for f in fields)]
        return {"query": query, "total": len(cl), "clients": cl[:100]}

    def get_client_stats(self):
        cl = self.get_client_details()["clients"]
        if not cl:
            return {"total_clients": 0}
        rssis = [c["rssi_dbm"] for c in cl if c["rssi_dbm"]]
        snrs = [c["snr_db"] for c in cl if c["snr_db"]]
        dist = {"Excellent": 0, "Good": 0, "Fair": 0, "Poor": 0, "Critical": 0}
        bands, protos = {}, {}
        for c in cl:
            dist[c["quality_label"]] = dist.get(c["quality_label"], 0) + 1
            bands[c["band"]] = bands.get(c["band"], 0) + 1
            protos[c["protocol"]] = protos.get(c["protocol"], 0) + 1
        return {"total_clients": len(cl),
                "avg_rssi_dbm": round(sum(rssis) / len(rssis), 1) if rssis else 0,
                "avg_snr_db": round(sum(snrs) / len(snrs), 1) if snrs else 0,
                "avg_quality_score": round(sum(c["quality_score"] for c in cl) / len(cl), 1),
                "quality_distribution": dist, "band_distribution": bands,
                "protocol_distribution": protos,
                "worst_clients": sorted(cl, key=lambda x: x["quality_score"])[:10]}

    # ── wlans ──────────────────────────────────────────
    def get_wlan_list(self):
        rows, _ = self._query("wlan")
        wlans = [{
            "profile_name": _s(w.get("name")), "wlan_id": _i(w.get("wlanId")),
            "ssid": _s(w.get("ssid")),
            "status": "Enabled" if _i(w.get("availability"), 1) else "Disabled",
            "bands": [], "band_str": "All",
            "security": _s(_first(w, "encryptionMethod", "authType"), "Open"),
            "policy_profile": _s(w.get("zoneName")), "policy_tag": _s(w.get("zoneName")),
        } for w in rows]
        return {"total_wlans": len(wlans), "wlans": wlans}

    # ── RF: per-band radios from query/ap (no neighbor data → no conflicts) ──
    def get_rf_analysis(self):
        rows, _ = self._query("ap")
        radios = []
        bands = [
            ("2.4 GHz", 0, "channel24G", "channel24gValue", "airtime24G", "noise24G", "numClients24G"),
            ("5 GHz",   1, "channel5G",  "channel50gValue", "airtime5G",  "noise5G",  "numClients5G"),
            ("6 GHz",   2, "channel6G",  "channel6gValue",  "airtime6G",  "noise6G",  "numClients6G"),
        ]
        for ap in rows:
            for band, slot, chstr, chval, util, noise, nclients in bands:
                ch = _i(ap.get(chval))
                if ch <= 0:
                    continue
                m = _WIDTH_RE.search(_s(ap.get(chstr)))
                w = _i(m.group(1)) if m else 20
                radios.append({
                    "ap_name": _s(ap.get("deviceName")), "mac": _s(ap.get("apMac")), "slot": slot,
                    "band": band, "channel": ch, "width": f"{w} MHz", "width_mhz": w,
                    "utilization": _i(ap.get(util)), "noise_dbm": _i(ap.get(noise)),
                    "interference": 0, "tx_level": 0, "clients": _i(ap.get(nclients)),
                })
        return {"summary": {"critical": 0, "high": 0, "medium": 0, "affected_aps": 0},
                "conflicts": [], "neighbor_aware": False,
                "radios": sorted(radios, key=lambda r: (r["band"], r["channel"]))}
