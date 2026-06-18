"""
Cisco C9800 RESTCONF Client
Tailored for IOS-XE 17.15.x YANG model output.
Optimized: request caching, connection pooling, session duration calc.
"""
import os
import requests
import urllib3
import logging
import time
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger("C9800")


def _int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _str(val, default=""):
    if val is None:
        return default
    return str(val)


def _to_list(data):
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def _first(d, *keys, default=None):
    """Return the first present, non-null key from a dict (tolerates YANG
    field-name variations across IOS-XE trains)."""
    if isinstance(d, dict):
        for k in keys:
            if d.get(k) is not None:
                return d[k]
    return default


def _elapsed_seconds(iso_timestamp):
    if not iso_timestamp or "1970" in str(iso_timestamp):
        return 0
    try:
        ts = datetime.fromisoformat(str(iso_timestamp).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, int((now - ts).total_seconds()))
    except Exception:
        return 0


# Centralized RESTCONF paths
_PATHS = {
    "hostname":       "Cisco-IOS-XE-native:native/hostname",
    "version":        "Cisco-IOS-XE-native:native/version",
    "cpu":            "Cisco-IOS-XE-process-cpu-oper:cpu-usage",
    "memory":         "Cisco-IOS-XE-memory-oper:memory-statistics",
    "aps":            "Cisco-IOS-XE-wireless-access-point-oper:access-point-oper-data/capwap-data",
    "client_summary": "Cisco-IOS-XE-wireless-client-global-oper:client-global-oper-data/client-live-stats",
    "common":         "Cisco-IOS-XE-wireless-client-oper:client-oper-data/common-oper-data",
    "dot11":          "Cisco-IOS-XE-wireless-client-oper:client-oper-data/dot11-oper-data",
    "traffic":        "Cisco-IOS-XE-wireless-client-oper:client-oper-data/traffic-stats",
    "sisf":           "Cisco-IOS-XE-wireless-client-oper:client-oper-data/sisf-db-mac",
    "wlan":           "Cisco-IOS-XE-wireless-wlan-cfg:wlan-cfg-data",
    "rf":             "Cisco-IOS-XE-wireless-rrm-oper:rrm-oper-data",
    "interfaces":     "Cisco-IOS-XE-interfaces-oper:interfaces",
    # RF / RRM troubleshooting (validated against IOS-XE 17.x RRM oper)
    "rrm_load":       "Cisco-IOS-XE-wireless-rrm-oper:rrm-oper-data/rrm-measurement",
    "rrm_nbr":        "Cisco-IOS-XE-wireless-rrm-oper:rrm-oper-data/ap-auto-rf-dot11-data",
    "radio_oper":     "Cisco-IOS-XE-wireless-access-point-oper:access-point-oper-data/radio-oper-data",
    "ap_name_map":    "Cisco-IOS-XE-wireless-access-point-oper:access-point-oper-data/ap-name-mac-map",
}

# Protocol / band derivation tables
_PROTO_MAP = [
    ("dot11be",       "Wi-Fi 7"),
    ("dot11ax-6ghz",  "Wi-Fi 6E"),
    ("dot11ax-5ghz",  "Wi-Fi 6 (5G)"),
    ("dot11ax-24ghz", "Wi-Fi 6 (2.4G)"),
    ("dot11ax",       "Wi-Fi 6"),
    ("dot11ac",       "Wi-Fi 5"),
    ("dot11n",        "Wi-Fi 4"),
]


class C9800RestconfClient:
    def __init__(self, host, port, username, password, verify_ssl=False):
        self.base_url = f"https://{host}:{port}/restconf/data"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = verify_ssl
        self.session.headers.update({
            "Accept": "application/yang-data+json",
            "Content-Type": "application/yang-data+json",
        })
        # total=2 + backoff_factor=0.5 -> retries at ~0.5s, 1s. Still rides out the
        # transient 502s the controller emits while RESTCONF/pubd is busy, but caps
        # the worst-case added latency (~1.5s vs ~7s) so pages stay responsive.
        # Tune with WLC_HTTP_RETRIES / WLC_HTTP_BACKOFF if the controller is flaky.
        _retries = int(os.getenv("WLC_HTTP_RETRIES", "2"))
        _backoff = float(os.getenv("WLC_HTTP_BACKOFF", "0.5"))
        retry = Retry(total=_retries, backoff_factor=_backoff, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self._cache = {}
        self._cache_ttl = 10  # 10s for large deployments
        self._executor = ThreadPoolExecutor(max_workers=6)

    # ── Core GET with cache ────────────────────────────
    def _get(self, path, cache=True):
        now = time.time()
        if cache and path in self._cache:
            data, ts = self._cache[path]
            if now - ts < self._cache_ttl:
                return data
        url = f"{self.base_url}/{path}"
        try:
            r = self.session.get(url, timeout=30)
            r.raise_for_status()
            result = r.json()
        except requests.exceptions.RetryError:
            # Retries exhausted against 5xx (status_forcelist). The controller is
            # reachable but its RESTCONF backend is busy/unready — not a real outage.
            log.warning(f"RESTCONF busy (5xx after retries): {url}")
            return {"error": "RESTCONF temporarily unavailable (5xx)", "degraded": True}
        except requests.exceptions.ConnectionError:
            log.error(f"Connection failed: {url}")
            return {"error": "Connection failed"}
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            log.error(f"HTTP {code}: {url}")
            return {} if code == 404 else {"error": f"HTTP {code}"}
        except Exception as e:
            log.error(f"Error: {e}")
            return {"error": str(e)}
        if cache:
            self._cache[path] = (result, now)
        return result

    def clear_cache(self):
        self._cache.clear()

    def _get_parallel(self, paths):
        """Fetch multiple RESTCONF paths in parallel."""
        results = {}
        futures = {self._executor.submit(self._get, p, True): p for p in paths}
        for future in as_completed(futures):
            path = futures[future]
            try: results[path] = future.result()
            except Exception as e:
                log.error(f"Parallel fetch error {path}: {e}")
                results[path] = {"error": str(e)}
        return results

    # ── Health ─────────────────────────────────────────
    def health_check(self):
        host_part = self.base_url.split("/restconf")[0]
        try:
            r = self.session.get(f"{host_part}/restconf", timeout=10)
            return {"status": "connected" if r.status_code == 200 else "degraded",
                    "code": r.status_code, "timestamp": datetime.now().isoformat()}
        except requests.exceptions.RetryError as e:
            # Web server answered but kept returning 5xx through all retries:
            # controller is up, RESTCONF backend is busy — degraded, not down.
            return {"status": "degraded", "code": 502, "error": str(e),
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"status": "unreachable", "error": str(e),
                    "timestamp": datetime.now().isoformat()}

    # ── System ─────────────────────────────────────────
    def get_system_info(self):
        h = self._get(_PATHS["hostname"])
        v = self._get(_PATHS["version"])
        return {
            "hostname": _str(h.get("Cisco-IOS-XE-native:hostname"), "Unknown"),
            "version": _str(v.get("Cisco-IOS-XE-native:version"), "Unknown"),
            "timestamp": datetime.now().isoformat(),
        }

    # ── CPU ────────────────────────────────────────────
    def get_cpu_usage(self):
        d = self._get(_PATHS["cpu"])
        u = d.get("Cisco-IOS-XE-process-cpu-oper:cpu-usage", {}).get("cpu-utilization", {})
        return {
            "five_seconds": _int(u.get("five-seconds")),
            "one_minute": _int(u.get("one-minute")),
            "five_minutes": _int(u.get("five-minutes")),
        }

    # ── Memory ─────────────────────────────────────────
    def get_memory_usage(self):
        d = self._get(_PATHS["memory"])
        pools = []
        for m in d.get("Cisco-IOS-XE-memory-oper:memory-statistics", {}).get("memory-statistic", []):
            total = _int(m.get("total-memory"))
            used = _int(m.get("used-memory"))
            free = _int(m.get("free-memory"))
            pools.append({
                "name": _str(m.get("name"), "Unknown"),
                "total_mb": round(total / 1048576, 1),
                "used_mb": round(used / 1048576, 1),
                "free_mb": round(free / 1048576, 1),
                "used_percent": round(used / total * 100, 1) if total > 0 else 0,
            })
        return {"pools": pools}

    # ── Access Points ──────────────────────────────────
    def get_ap_count(self):
        """Fast AP count without loading full capwap-data."""
        d = self._get("Cisco-IOS-XE-wireless-access-point-oper:access-point-oper-data/ap-name-mac-map")
        aps = _to_list(d.get("Cisco-IOS-XE-wireless-access-point-oper:ap-name-mac-map", []))
        return {"total_aps": len(aps)}

    def get_ap_summary(self, page=1, per_page=50):
        d = self._get(_PATHS["aps"])
        raw = _to_list(d.get("Cisco-IOS-XE-wireless-access-point-oper:capwap-data", []))
        total = len(raw)
        start = (page - 1) * per_page
        page_data = raw[start:start + per_page]
        aps = []
        for ap in page_data:
            dev = ap.get("device-detail", {})
            si = dev.get("static-info", {})
            board = si.get("board-data", {})
            loc = ap.get("ap-location", {})
            state = ap.get("ap-state", {})
            mode = ap.get("ap-mode-data", {})
            ver = dev.get("wtp-version", {})
            tags = ap.get("tag-info", {}).get("resolved-tag-info", {})
            ti = ap.get("ap-time-info", {})
            aps.append({
                "name": _str(ap.get("name")),
                "wtp_mac": _str(ap.get("wtp-mac")),
                "mac": _str(board.get("wtp-enet-mac")),
                "ip": _str(ap.get("ip-addr") or ap.get("wtp-ip")),
                "model": _str(si.get("ap-models", {}).get("model")),
                "serial": _str(board.get("wtp-serial-num")),
                "location": _str(loc.get("location")),
                "sw_version": _str(ver.get("sw-version")),
                "state": _str(state.get("ap-operation-state")),
                "admin_state": _str(state.get("ap-admin-state")),
                "mode": _str(mode.get("wtp-mode")),
                "country": _str(ap.get("country-code", "")).strip(),
                "policy_tag": _str(tags.get("resolved-policy-tag")),
                "site_tag": _str(tags.get("resolved-site-tag")),
                "rf_tag": _str(tags.get("resolved-rf-tag")),
                "max_clients": _int(ap.get("max-clients-supported")),
                "uptime_sec": _elapsed_seconds(ti.get("boot-time")),
                "join_time": _str(ti.get("join-time")),
            })
        return {"total_aps": total, "page": page, "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page, "aps": aps}

    def get_ap_detail(self, mac):
        return self._get(f"{_PATHS['aps']}={mac}", cache=False)

    def get_ap_lifecycle(self):
        """Per-AP boot/join time, version, state — for reboot/flap detection and
        firmware-compliance reporting. Reuses the cached capwap-data fetch."""
        d = self._get(_PATHS["aps"])
        out = []
        for ap in _to_list(d.get("Cisco-IOS-XE-wireless-access-point-oper:capwap-data", [])):
            dev = ap.get("device-detail", {})
            si = dev.get("static-info", {})
            ti = ap.get("ap-time-info", {})
            out.append({
                "name": _str(ap.get("name")),
                "mac": _str(ap.get("wtp-mac")),
                "model": _str(si.get("ap-models", {}).get("model")),
                "sw_version": _str(dev.get("wtp-version", {}).get("sw-version")),
                "state": _str(ap.get("ap-state", {}).get("ap-operation-state")),
                "boot_time": _str(ti.get("boot-time")),
                "join_time": _str(ti.get("join-time")),
                "uptime_sec": _elapsed_seconds(ti.get("boot-time")),
            })
        return out

    def get_ap_addresses(self):
        """Minimal per-AP identity (name, MACs, IP) for duplicate-address checks.
        Reuses the cached capwap-data fetch."""
        d = self._get(_PATHS["aps"])
        out = []
        for ap in _to_list(d.get("Cisco-IOS-XE-wireless-access-point-oper:capwap-data", [])):
            board = ap.get("device-detail", {}).get("static-info", {}).get("board-data", {})
            out.append({
                "name": _str(ap.get("name")),
                "wtp_mac": _str(ap.get("wtp-mac")),
                "mac": _str(board.get("wtp-enet-mac")),
                "ip": _str(ap.get("ip-addr") or ap.get("wtp-ip")),
            })
        return out

    # ── Client Summary ─────────────────────────────────
    def get_client_summary(self):
        d = self._get(_PATHS["client_summary"])
        s = d.get("Cisco-IOS-XE-wireless-client-global-oper:client-live-stats", {})
        run = _int(s.get("run-state-clients"))
        auth = _int(s.get("auth-state-clients"))
        iplearn = _int(s.get("iplearn-state-clients"))
        webauth = _int(s.get("webauth-state-clients"))

        band_counts = {"2ghz": 0, "5ghz": 0, "6ghz": 0}
        try:
            rf = self._get(_PATHS["dot11"])
            for r in _to_list(rf.get("Cisco-IOS-XE-wireless-client-oper:dot11-oper-data", [])):
                phy = _str(r.get("ewlc-ms-phy-type")).lower()
                if "6ghz" in phy:       band_counts["6ghz"] += 1
                elif "5ghz" in phy:     band_counts["5ghz"] += 1
                elif "24ghz" in phy or "2ghz" in phy: band_counts["2ghz"] += 1
        except Exception:
            pass

        return {
            "total_clients": run + auth + iplearn + webauth,
            "run_state": run, "auth_state": auth,
            "iplearn_state": iplearn, "webauth_state": webauth,
            "random_mac_clients": _int(s.get("random-mac-clients")),
            "clients_2ghz": band_counts["2ghz"],
            "clients_5ghz": band_counts["5ghz"],
            "clients_6ghz": band_counts["6ghz"],
        }

    # ── Signal Quality ─────────────────────────────────
    @staticmethod
    def _signal_quality(rssi, snr):
        if rssi >= -55:     rs = 50
        elif rssi >= -67:   rs = 35 + (rssi + 67) * 1.25
        elif rssi >= -72:   rs = 20 + (rssi + 72) * 3
        elif rssi >= -80:   rs = 5 + (rssi + 80) * 1.875
        else:               rs = max(0, 5 + (rssi + 85))
        if snr >= 40:       ss = 50
        elif snr >= 25:     ss = 30 + (snr - 25) * 1.33
        elif snr >= 15:     ss = 15 + (snr - 15) * 1.5
        else:               ss = max(0, snr)
        return min(100, max(0, round(rs + ss)))

    @staticmethod
    def _quality_label(s):
        if s >= 80: return "Excellent"
        if s >= 60: return "Good"
        if s >= 40: return "Fair"
        if s >= 20: return "Poor"
        return "Critical"

    @staticmethod
    def _derive_protocol(phy):
        p = _str(phy).lower()
        for key, val in _PROTO_MAP:
            if key in p:
                return val
        return p or "Unknown"

    @staticmethod
    def _derive_band(phy):
        p = _str(phy).lower()
        if "6ghz" in p:                    return "6 GHz"
        if "5ghz" in p:                    return "5 GHz"
        if "24ghz" in p or "2ghz" in p:   return "2.4 GHz"
        return "Unknown"

    @staticmethod
    def _parse_mcs(current_rate):
        rate = _str(current_rate).lower().strip()
        if rate.startswith("m"):
            try:
                return int(rate.split()[0][1:])
            except (ValueError, IndexError):
                pass
        return 0

    # ── Client Details (merges 4 endpoints) ────────────
    def get_client_details(self, page=None, per_page=50):
        # Fetch all 4 sources IN PARALLEL for speed
        paths = [_PATHS["common"], _PATHS["dot11"], _PATHS["traffic"], _PATHS["sisf"]]
        results = self._get_parallel(paths)

        d1 = results.get(_PATHS["common"], {})
        if "error" in d1:
            return {"total": 0, "clients": [], "error": d1["error"]}
        common_list = _to_list(d1.get("Cisco-IOS-XE-wireless-client-oper:common-oper-data", []))

        d2 = results.get(_PATHS["dot11"], {})
        dot11_map = {_str(r.get("ms-mac-address")): r
                     for r in _to_list(d2.get("Cisco-IOS-XE-wireless-client-oper:dot11-oper-data", []))}

        d3 = results.get(_PATHS["traffic"], {})
        traf_map = {_str(t.get("ms-mac-address")): t
                    for t in _to_list(d3.get("Cisco-IOS-XE-wireless-client-oper:traffic-stats", []))}

        d4 = results.get(_PATHS["sisf"], {})
        ip_map = self._build_ip_map(_to_list(d4.get("Cisco-IOS-XE-wireless-client-oper:sisf-db-mac", [])))

        clients = []
        for c in common_list:
            try:
                clients.append(self._build_client(c, dot11_map, traf_map, ip_map))
            except Exception as e:
                log.warning(f"Failed to parse client {c.get('client-mac')}: {e}")
        total = len(clients)
        if page is not None:
            start = (page - 1) * per_page
            return {"total": total, "page": page, "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page,
                    "clients": clients[start:start + per_page]}
        return {"total": total, "clients": clients}

    @staticmethod
    def _build_ip_map(sisf_list):
        ip_map = {}
        for s in sisf_list:
            mac = _str(s.get("mac-addr", ""))
            ipv4 = s.get("ipv4-binding", {})
            ip = ""
            if isinstance(ipv4, dict):
                ip = _str(ipv4.get("ip-key", {}).get("ip-addr", ""))
            elif isinstance(ipv4, list) and ipv4:
                ip = _str(ipv4[0].get("ip-key", {}).get("ip-addr", ""))
            if mac:
                ip_map[mac] = ip
        return ip_map

    def _build_client(self, common, dot11_map, traf_map, ip_map):
        mac = _str(common.get("client-mac"))
        dot11 = dot11_map.get(mac, {})
        traf = traf_map.get(mac, {})

        phy = _str(dot11.get("ewlc-ms-phy-type", ""))
        rssi = _int(traf.get("most-recent-rssi"))
        snr = _int(traf.get("most-recent-snr"))

        if rssi != 0 and snr != 0:
            score = self._signal_quality(rssi, snr)
            label = self._quality_label(score)
        else:
            score, label = 0, "No Data"

        wifi = dot11.get("ms-wifi", {})

        return {
            "mac": mac,
            "ip": ip_map.get(mac, ""),
            "username": _str(common.get("username")),
            "hostname": "",
            "device_type": "Apple" if dot11.get("ms-apple-capable") else "Unknown",
            "os_type": "Unknown",
            "ap_name": _str(common.get("ap-name") or dot11.get("ap-mac-address", "")),
            "ssid": _str(dot11.get("vap-ssid")),
            "wlan_profile": _str(dot11.get("wlan-profile")),
            "band": self._derive_band(phy),
            "channel": _int(dot11.get("current-channel")),
            "channel_width": "",
            "protocol": self._derive_protocol(phy),
            "rssi_dbm": rssi,
            "snr_db": snr,
            "quality_score": score,
            "quality_label": label,
            "data_rate_mbps": _int(traf.get("speed")),
            "tx_power_dbm": 0,
            "spatial_streams": _int(traf.get("spatial-stream")),
            "mcs_index": self._parse_mcs(traf.get("current-rate")),
            "state": _str(common.get("co-state")),
            "vlan": _int(common.get("wlan-id") or dot11.get("ms-wlan-id")),
            "bytes_tx": _int(traf.get("bytes-tx")),
            "bytes_rx": _int(traf.get("bytes-rx")),
            "pkts_tx": _int(traf.get("pkts-tx")),
            "pkts_rx": _int(traf.get("pkts-rx")),
            "data_retries": _int(traf.get("data-retries")),
            "tx_drops": _int(traf.get("tx-total-drops")),
            "session_duration_sec": _elapsed_seconds(dot11.get("ms-assoc-time")),
            "roam_count": 0,
            "security": _str(wifi.get("wpa-version")),
            "auth_key_mgmt": _str(wifi.get("auth-key-mgmt")),
            "assoc_time": _str(dot11.get("ms-assoc-time")),
            "bssid": _str(dot11.get("ms-bssid")),
            "policy_profile": _str(dot11.get("policy-profile")),
            "is_active": traf.get("client-active", False),
        }

    # ── Search ─────────────────────────────────────────
    def search_clients(self, query):
        r = self.get_client_details()
        if "error" in r and not r.get("clients"):
            return r
        q = query.lower().strip()
        fields = ("mac", "ip", "username", "hostname", "ap_name", "ssid", "band", "protocol")
        matches = [c for c in r["clients"] if any(q in _str(c.get(f)).lower() for f in fields)]
        return {"query": query, "total": len(matches), "clients": matches[:100]}

    def get_client_detail(self, mac):
        r = self.get_client_details()
        if "error" in r and not r.get("clients"):
            return r
        ml = mac.lower()
        return next((c for c in r["clients"] if c["mac"].lower() == ml), {"error": "Client not found"})

    # ── Client Stats ───────────────────────────────────
    def get_client_stats(self):
        r = self.get_client_details()
        if "error" in r and not r.get("clients"):
            return r
        cl = r["clients"]
        t = len(cl)
        if t == 0:
            return {"total_clients": 0}

        dist = {"Excellent": 0, "Good": 0, "Fair": 0, "Poor": 0, "Critical": 0}
        bands, protos = {}, {}
        for c in cl:
            ql = c["quality_label"]
            if ql in dist: dist[ql] += 1
            b = c["band"] or "Unknown"
            bands[b] = bands.get(b, 0) + 1
            protos[c["protocol"]] = protos.get(c["protocol"], 0) + 1

        rssi_vals = [c["rssi_dbm"] for c in cl if c["rssi_dbm"] != 0]
        snr_vals = [c["snr_db"] for c in cl if c["snr_db"] != 0]
        score_vals = [c["quality_score"] for c in cl if c["quality_score"] > 0]

        return {
            "total_clients": t,
            "avg_rssi_dbm": round(sum(rssi_vals) / len(rssi_vals), 1) if rssi_vals else 0,
            "avg_snr_db": round(sum(snr_vals) / len(snr_vals), 1) if snr_vals else 0,
            "avg_quality_score": round(sum(score_vals) / len(score_vals), 1) if score_vals else 0,
            "quality_distribution": dist,
            "band_distribution": bands,
            "protocol_distribution": protos,
            "worst_clients": sorted(cl, key=lambda x: x["quality_score"])[:10],
        }

    # ── WLANs ──────────────────────────────────────────
    def get_wlan_list(self):
        d = self._get(_PATHS["wlan"])
        w = d.get("Cisco-IOS-XE-wireless-wlan-cfg:wlan-cfg-data", {})
        entries = _to_list(w.get("wlan-cfg-entries", {}).get("wlan-cfg-entry", []))

        wlan_to_policy = {}
        for tag in _to_list(w.get("policy-list-entries", {}).get("policy-list-entry", [])):
            tag_name = _str(tag.get("tag-name"))
            for wp in _to_list(tag.get("wlan-policies", {}).get("wlan-policy", [])):
                wlan_to_policy[_str(wp.get("wlan-profile-name"))] = {
                    "policy_tag": tag_name,
                    "policy_profile": _str(wp.get("policy-profile-name")),
                }

        wlans = []
        for e in entries:
            vap = e.get("apf-vap-id-data", {})
            name = _str(e.get("profile-name"))
            bands = []
            for rp in _to_list(e.get("wlan-radio-policies", {}).get("wlan-radio-policy", [])):
                b = _str(rp.get("band", ""))
                if "5-ghz" in b:     bands.append("5 GHz")
                elif "2-dot-4" in b: bands.append("2.4 GHz")
                elif "6-ghz" in b:   bands.append("6 GHz")
            sec = []
            if e.get("auth-key-mgmt-psk"):   sec.append("PSK")
            if e.get("auth-key-mgmt-dot1x"): sec.append("802.1X")
            pol = wlan_to_policy.get(name, {})
            wlans.append({
                "profile_name": name,
                "wlan_id": _int(e.get("wlan-id")),
                "ssid": _str(vap.get("ssid")),
                "status": "Enabled" if vap.get("wlan-status") else "Disabled",
                "bands": bands,
                "band_str": " / ".join(bands) or "All",
                "security": " + ".join(sec) or "Open",
                "policy_profile": _str(pol.get("policy_profile")),
                "policy_tag": _str(pol.get("policy_tag")),
            })
        return {"total_wlans": len(wlans), "wlans": wlans}

    def get_rf_data(self):
        return self._get(_PATHS["rf"])

    # ── RF / Channel-conflict analysis ─────────────────
    @staticmethod
    def _band_label(band, slot, ch):
        b = _str(band).lower()
        if "6-ghz" in b or "6ghz" in b:               return "6 GHz"
        if "2-dot-4" in b or "2.4" in b or "11bg" in b: return "2.4 GHz"
        if "5-ghz" in b or "5ghz" in b or "11a" in b:  return "5 GHz"
        if slot == 0:                        return "2.4 GHz"
        if slot == 1:                        return "5 GHz"
        if slot == 2:                        return "6 GHz"
        if 1 <= ch <= 14:                    return "2.4 GHz"
        if 36 <= ch <= 177:                  return "5 GHz"
        return "Unknown"

    # A co/adjacent-channel conflict only counts when the two radios actually
    # hear each other this strongly — otherwise same-channel is just RRM reuse.
    NEIGHBOR_RSSI_THRESHOLD = -80

    def get_rf_analysis(self):
        """Per-radio RF telemetry (channel, utilization, noise, TX) plus
        neighbor-aware co-channel / adjacent-channel conflict detection.
        Validated against IOS-XE 17.x: channel/width/band/TX from
        radio-oper-data, util/noise from rrm-measurement, RF neighbors from
        ap-auto-rf-dot11-data."""
        paths = [_PATHS["rrm_load"], _PATHS["rrm_nbr"], _PATHS["radio_oper"], _PATHS["ap_name_map"]]
        res = self._get_parallel(paths)

        name_by_mac = {}
        for m in _to_list(res.get(_PATHS["ap_name_map"], {}).get(
                "Cisco-IOS-XE-wireless-access-point-oper:ap-name-mac-map", [])):
            name_by_mac[_str(m.get("wtp-mac")).lower()] = _str(
                _first(m, "wtp-name", "ap-name"), _str(m.get("wtp-mac")))

        radios = {}

        def slot_radio(mac, slot):
            return radios.setdefault((_str(mac).lower(), _int(slot)),
                                     {"mac": _str(mac), "slot": _int(slot)})

        # Channel / width / band / TX power from radio-oper-data
        for it in _to_list(res.get(_PATHS["radio_oper"], {}).get(
                "Cisco-IOS-XE-wireless-access-point-oper:radio-oper-data", [])):
            if "remote-lan" in _str(it.get("radio-type")):   # non-Wi-Fi radio
                continue
            r = slot_radio(it.get("wtp-mac"), it.get("radio-slot-id"))
            cfg = (it.get("phy-ht-cfg") or {}).get("cfg-data", {}) or {}
            r["channel"] = _int(cfg.get("curr-freq"))
            w = _int(cfg.get("chan-width"))
            r["width_mhz"] = w
            r["width"] = f"{w} MHz" if w else ""
            r["band"] = self._band_label(_first(it, "current-active-band", "radio-type", default=""),
                                         r["slot"], r["channel"])
            r["oper_up"] = "up" in _str(it.get("oper-state")).lower()
            bands = _to_list(it.get("radio-band-info", []))
            b0 = bands[0] if bands else {}
            r["tx_level"] = _int(((b0.get("phy-tx-pwr-cfg") or {}).get("cfg-data", {}) or {})
                                 .get("current-tx-power-level"))
            r["tx_dbm"] = _int(((b0.get("phy-tx-pwr-lvl-cfg") or {}).get("cfg-data", {}) or {})
                               .get("curr-tx-power-in-dbm"))

        # Utilization + noise from rrm-measurement
        for it in _to_list(res.get(_PATHS["rrm_load"], {}).get(
                "Cisco-IOS-XE-wireless-rrm-oper:rrm-measurement", [])):
            r = slot_radio(it.get("wtp-mac"), it.get("radio-slot-id"))
            load = it.get("load") or {}
            r["util"] = _int(_first(load, "cca-util-percentage", "rx-noise-channel-utilization"))
            r["clients"] = _int(load.get("stations"))
            # noise is nested: noise -> noise -> noise-data[] {chan, noise}
            ndata = _to_list(((it.get("noise") or {}).get("noise") or {}).get("noise-data", []))
            r["_noise"] = {_int(n.get("chan")): _int(n.get("noise")) for n in ndata}

        # RF neighbors from ap-auto-rf-dot11-data → (mac, slot, rssi) heard by this radio
        for it in _to_list(res.get(_PATHS["rrm_nbr"], {}).get(
                "Cisco-IOS-XE-wireless-rrm-oper:ap-auto-rf-dot11-data", [])):
            r = slot_radio(it.get("wtp-mac"), it.get("radio-slot-id"))
            nbrs = []
            for n in _to_list((it.get("neighbor-radio-info") or {}).get("neighbor-radio-list", [])):
                ni = n.get("neighbor-radio-info") or {}
                nbrs.append((_str(ni.get("neighbor-radio-mac")).lower(),
                             _int(ni.get("neighbor-radio-slot-id")),
                             _int(ni.get("rssi"))))
            r["nbrs"] = nbrs

        pub = {}
        for key, r in radios.items():
            ch = r.get("channel", 0)
            noise_map = r.get("_noise", {})
            noise = noise_map.get(ch)
            if noise is None and noise_map:
                noise = max(noise_map.values())          # closest-to-0 = noisiest
            pub[key] = {
                "ap_name": name_by_mac.get(r["mac"].lower(), r["mac"]),
                "mac": r["mac"], "slot": r["slot"],
                "band": r.get("band") or self._band_label("", r["slot"], ch),
                "channel": ch, "width": r.get("width", ""), "width_mhz": r.get("width_mhz", 0),
                "utilization": r.get("util", 0),
                "noise_dbm": _int(noise) if noise is not None else 0,
                "interference": 0,
                "tx_level": r.get("tx_level", 0),
                "tx_dbm": r.get("tx_dbm", 0),
                "clients": r.get("clients", 0),
            }

        # Neighbor lists reference each radio by its OWN base MAC, which differs
        # per band (only the 2.4 GHz radio MAC equals wtp-mac). The radios of one
        # AP share the first 5 MAC octets, so resolve neighbors by (prefix, slot).
        pub_by_radio = {}
        for (mac, slot), p in pub.items():
            pub_by_radio[(mac.rsplit(":", 1)[0], slot)] = p

        conflicts = self._detect_conflicts(radios, pub, pub_by_radio)
        summary = {
            "critical": sum(1 for c in conflicts if c["severity"] == "critical"),
            "high":     sum(1 for c in conflicts if c["severity"] == "high"),
            "medium":   sum(1 for c in conflicts if c["severity"] == "medium"),
            "affected_aps": len({c["focal"]["mac"] for c in conflicts}),
        }
        return {"summary": summary, "conflicts": conflicts, "neighbor_aware": True,
                "radios": sorted(pub.values(), key=lambda r: (r["band"], r["channel"]))}

    def _detect_conflicts(self, radios, pub, pub_by_radio):
        """AP-centric: one conflict per radio that hears co-channel (or
        overlapping) neighbors ≥ NEIGHBOR_RSSI_THRESHOLD. The neighbor list is
        that radio's OWN direct neighbors (with the RSSI it hears them at) —
        mirroring the WLC 'Neighboring APs' table, no transitive grouping."""
        conflicts = []

        for key, r in radios.items():
            ch = r.get("channel", 0)
            if ch <= 0:
                continue
            band = pub[key]["band"]
            wa = r.get("width_mhz") or 20
            self_radio = (key[0].rsplit(":", 1)[0], key[1])
            co_n, ov_n = [], []
            for (nmac, nslot, rssi) in r.get("nbrs", []):
                if rssi < self.NEIGHBOR_RSSI_THRESHOLD:
                    continue
                nradio = (nmac.rsplit(":", 1)[0], nslot)
                if nradio == self_radio:
                    continue                       # never conflict with self
                np = pub_by_radio.get(nradio)      # resolve by (MAC-prefix, slot)
                if not np or np["band"] != band:
                    continue
                nch = np.get("channel", 0)
                if nch <= 0:
                    continue
                wb = np.get("width_mhz") or 20
                # Channel numbers are 5 MHz apart; two radios overlap spectrally
                # when the centre gap is below the average half-width — this is
                # what catches 5/6 GHz 40/80/160 MHz bleed onto nearby channels.
                if 5 * abs(ch - nch) >= (wa + wb) / 2:
                    continue
                nb = {"ap_name": np["ap_name"], "mac": np["mac"],
                      "slot": np["slot"], "channel": nch, "width": np["width"],
                      "rssi": rssi, "utilization": np["utilization"],
                      "noise_dbm": np["noise_dbm"]}
                if nch == ch:
                    co_n.append(nb)
                else:
                    ov_n.append(nb)

            focal = pub[key]
            util = focal["utilization"]

            if co_n:
                co_n.sort(key=lambda x: -x["rssi"])
                strongest, n = co_n[0]["rssi"], len(co_n)
                sev = ("critical" if (util >= 60 or (util >= 40 and n >= 2) or strongest >= -52)
                       else "high" if (n >= 3 or strongest >= -62 or util >= 25)
                       else "medium")
                conflicts.append({
                    "type": "co-channel", "band": band, "channel": ch, "severity": sev,
                    "ap_count": n + 1, "neighbor_count": n, "rssi": strongest,
                    "title": f"Co-Channel · {band}", "focal": focal,
                    "detail": f"{focal['ap_name']} (ch {ch}, {util}% util) has {n} co-channel "
                              f"neighbor{'s' if n != 1 else ''} on channel {ch}; "
                              f"strongest heard at {strongest} dBm.",
                    "neighbors": co_n,
                })

            if ov_n:
                ov_n.sort(key=lambda x: -x["rssi"])
                strongest, n = ov_n[0]["rssi"], len(ov_n)
                sev = ("critical" if (util >= 60 or strongest >= -50)
                       else "high" if (n >= 3 or strongest >= -58 or util >= 40)
                       else "medium")
                # 2.4 GHz overlap is "adjacent"; 5/6 GHz overlap is wide-channel bleed
                label = "Adjacent Channel" if band == "2.4 GHz" else "Overlapping Channel"
                conflicts.append({
                    "type": "overlapping", "band": band, "channel": ch, "severity": sev,
                    "ap_count": n + 1, "neighbor_count": n, "rssi": strongest,
                    "title": f"{label} · {band}", "focal": focal,
                    "detail": f"{focal['ap_name']} (ch {ch} @ {focal['width']}) overlaps {n} "
                              f"neighbor{'s' if n != 1 else ''} on nearby channels; "
                              f"strongest at {strongest} dBm.",
                    "neighbors": ov_n,
                })

        order = {"critical": 0, "high": 1, "medium": 2}
        conflicts.sort(key=lambda c: (order.get(c["severity"], 9),
                                      -c["neighbor_count"], -c["rssi"]))
        return conflicts

    # ── Security: rogue APs / clients + aWIPS ──────────
    def get_rogues(self):
        """Detected rogue APs and rogue clients from rogue-oper-data.
        Defensive parsing — field names vary by IOS-XE train; validate live."""
        d = self._get("Cisco-IOS-XE-wireless-rogue-oper:rogue-oper-data/rogue-data", cache=False)
        rogue_aps = []
        for it in _to_list(d.get("Cisco-IOS-XE-wireless-rogue-oper:rogue-data", [])):
            mac = _str(_first(it, "rogue-address", "rogue-mac", "mac-address"))
            if not mac:
                continue
            cls = _str(it.get("rogue-class-type", "")).lower()
            # Validated on IOS-XE 17.x: strongest-detection details are flat on
            # the rogue record, suffixed "-max-rssi".
            rogue_aps.append({
                "mac": mac,
                "classification": ("malicious" if "malicious" in cls
                                   else "friendly" if "friendly" in cls
                                   else "custom" if "custom" in cls
                                   else "unclassified"),
                "state": _str(it.get("rogue-mode", "")).replace("rogue-state-", ""),
                "ssid": _str(_first(it, "ssid-max-rssi", "last-heard-ssid", default="")),
                "channel": _int(_first(it, "channel-max-rssi", "last-channel", default=0)),
                "rssi": _int(it.get("max-detected-rssi", 0)),
                "num_clients": _int(_first(it, "n-clients", "rogue-client-count", default=0)),
                "on_wire": bool(it.get("rogue-is-on-my-network", False)),
                "detecting_ap": _str(_first(it, "ap-name-max-rssi", "lrad-mac-max-rssi", default="")),
                "last_heard": _str(_first(it, "rogue-last-timestamp", "last-heard", default="")),
                "severity_score": _int(it.get("severity-score", 0)),
            })

        dc = self._get("Cisco-IOS-XE-wireless-rogue-oper:rogue-oper-data/rogue-client-data", cache=False)
        rogue_clients = []
        for it in _to_list(dc.get("Cisco-IOS-XE-wireless-rogue-oper:rogue-client-data", [])):
            mac = _str(_first(it, "rogue-client-address", "rogue-address", "mac-address"))
            if not mac:
                continue
            rogue_clients.append({
                "mac": mac,
                "state": _str(_first(it, "rogue-client-state", "state", default="")).lower(),
                "rssi": _int(_first(it, "rssi", "max-rssi", default=0)),
                "rogue_ap": _str(_first(it, "rogue-address", "ap-mac", default="")),
                "ip": _str(_first(it, "rogue-client-ipaddr", "ip-address", default="")),
            })
        return {"rogue_aps": rogue_aps, "rogue_clients": rogue_clients}

    def get_awips(self):
        """aWIPS intrusion alarms (only present if aWIPS is enabled). Defensive."""
        d = self._get("Cisco-IOS-XE-wireless-awips-oper:awips-oper-data", cache=False)
        root = d.get("Cisco-IOS-XE-wireless-awips-oper:awips-oper-data", {}) if isinstance(d, dict) else {}
        alarms = []
        for it in _to_list(_first(root, "awips-per-signature-stats", "awips-dot11-frame-pkt-drop-stats",
                                  "awips-alarm", default=[])):
            alarms.append({
                "signature": _str(_first(it, "signature-string", "sign-name", "signature", default="alarm")),
                "ap_mac": _str(_first(it, "ap-mac", "wtp-mac", default="")),
                "count": _int(_first(it, "alarm-count", "count", "frame-count", default=0)),
                "last_seen": _str(_first(it, "last-alarm-time", "timestamp", default="")),
            })
        return {"alarms": alarms}

    def get_interfaces(self):
        d = self._get(_PATHS["interfaces"])
        raw = _to_list(d.get("Cisco-IOS-XE-interfaces-oper:interfaces", {}).get("interface", []))
        ifaces = []
        for i in raw[:50]:
            stats = i.get("statistics", {})
            speed = _int(i.get("speed"))
            oper = _str(i.get("oper-status"))
            status = "up" if "ready" in oper else "down" if "down" in oper or "not-ready" in oper else oper.replace("if-oper-state-", "")
            admin = _str(i.get("admin-status"))
            admin_st = "up" if "up" in admin else "down" if "down" in admin else admin.replace("if-state-", "")
            ifaces.append({
                "name": _str(i.get("name")),
                "type": _str(i.get("interface-type", "")).replace("iana-iftype-", ""),
                "admin_status": admin_st,
                "oper_status": status,
                "ipv4": _str(i.get("ipv4")),
                "subnet_mask": _str(i.get("ipv4-subnet-mask")),
                "mac": _str(i.get("phys-address")),
                "speed_mbps": round(speed / 1_000_000) if speed > 0 else 0,
                "mtu": _int(i.get("mtu")),
                "description": _str(i.get("description")),
                "last_change": _str(i.get("last-change")),
                "rx_kbps": _int(stats.get("rx-kbps")),
                "tx_kbps": _int(stats.get("tx-kbps")),
                "in_errors": _int(stats.get("in-errors")),
                "out_errors": _int(stats.get("out-errors")),
            })
        return {"interfaces": ifaces}

    def get_dashboard(self):
        """Lightweight dashboard - parallel fetch, counts only for APs."""
        self.clear_cache()
        # Parallel fetch system metrics
        sys_paths = [_PATHS["hostname"], _PATHS["version"], _PATHS["cpu"],
                     _PATHS["memory"], _PATHS["client_summary"]]
        results = self._get_parallel(sys_paths)

        h = results.get(_PATHS["hostname"], {})
        v = results.get(_PATHS["version"], {})
        cpu_d = results.get(_PATHS["cpu"], {})
        cpu_u = cpu_d.get("Cisco-IOS-XE-process-cpu-oper:cpu-usage", {}).get("cpu-utilization", {})

        mem_d = results.get(_PATHS["memory"], {})
        pools = []
        for m in mem_d.get("Cisco-IOS-XE-memory-oper:memory-statistics", {}).get("memory-statistic", []):
            total = _int(m.get("total-memory")); used = _int(m.get("used-memory"))
            pools.append({"name": _str(m.get("name"), "Unknown"),
                "total_mb": round(total / 1048576, 1), "used_mb": round(used / 1048576, 1),
                "used_percent": round(used / total * 100, 1) if total > 0 else 0})

        cl_d = results.get(_PATHS["client_summary"], {})
        cl_s = cl_d.get("Cisco-IOS-XE-wireless-client-global-oper:client-global-oper-data/client-live-stats", {})
        run = _int(cl_s.get("run-state-clients"))
        auth = _int(cl_s.get("auth-state-clients"))

        return {
            "system": {"hostname": _str(h.get("Cisco-IOS-XE-native:hostname"), "Unknown"),
                       "version": _str(v.get("Cisco-IOS-XE-native:version"), "Unknown"),
                       "timestamp": datetime.now().isoformat()},
                       
            "cpu": {"five_seconds": _int(cpu_u.get("five-seconds")),
                    "one_minute": _int(cpu_u.get("one-minute")),
                    "five_minutes": _int(cpu_u.get("five-minutes"))},
            "memory": {"pools": pools},
            "aps": self.get_ap_count(),
            "clients": self.get_client_summary(),
            "wlans": self.get_wlan_list(),
            "health": self.health_check(),
        }