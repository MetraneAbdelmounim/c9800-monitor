"""
Client Collector — multi-site (Phase 2). Polls every enabled site each cycle and
tags all records with site_id. Also writes a per-site `site_status` summary doc
that powers the aggregate NOC overview (cheap to read, no live controller hit).
"""
import threading, time, logging
from datetime import datetime, timezone
from pymongo import WriteConcern

log = logging.getLogger("Collector")


def _is_up(state: str) -> bool:
    s = (state or "").lower()
    return any(x in s for x in ("registered", "run", "online", "connected"))


class ClientCollector:
    def __init__(self, site_provider, mongo_db, interval=60):
        # site_provider() -> [{id, name, location, client}, ...]
        self.sites = site_provider
        self.db = mongo_db
        self.interval = interval
        self._running = False
        self._thread = None
        self._last_ap = {}      # key "site_id|mac" -> ap_name
        self._ap_cache = {}     # site_id -> (total_aps, online_aps), refreshed every 5th cycle

    def _setup_db(self):
        try:
            snap = self.db["client_snapshots"]
            snap.create_index([("mac", 1), ("timestamp", -1)])
            snap.create_index([("site_id", 1), ("timestamp", -1)])
            snap.create_index("timestamp", expireAfterSeconds=3*86400)

            roam = self.db["roaming_events"]
            roam.create_index([("mac", 1), ("timestamp", -1)])
            roam.create_index([("site_id", 1), ("timestamp", -1)])
            roam.create_index("timestamp", expireAfterSeconds=7*86400)

            ap_load = self.db["ap_load_history"]
            ap_load.create_index([("ap_name", 1), ("timestamp", -1)])
            ap_load.create_index("timestamp", expireAfterSeconds=3*86400)

            ds = self.db["client_snapshots_5m"]
            ds.create_index([("mac", 1), ("timestamp", -1)])
            ds.create_index("timestamp", expireAfterSeconds=30*86400)

            sm = self.db["system_metrics"]
            sm.create_index([("site_id", 1), ("timestamp", -1)])
            sm.create_index("timestamp", expireAfterSeconds=30*86400)
            log.info("MongoDB indexes ready (multi-site mode)")
        except Exception as e:
            log.error(f"Index setup failed: {e}")

    def start(self):
        if self._running:
            return
        self._running = True
        self._setup_db()
        self._load_last_aps()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"Collector started (every {self.interval}s, multi-site)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _load_last_aps(self):
        try:
            for doc in self.db["client_snapshots"].aggregate([
                {"$sort": {"timestamp": -1}},
                {"$group": {"_id": {"s": "$site_id", "m": "$mac"}, "ap": {"$first": "$ap_name"}}},
            ]):
                k = f"{doc['_id'].get('s')}|{doc['_id'].get('m')}"
                self._last_ap[k] = doc["ap"]
        except Exception:
            pass

    def _loop(self):
        cycle = 0
        while self._running:
            try:
                for entry in self.sites():
                    try:
                        self._collect_site(entry, cycle)
                    except Exception as e:
                        log.error(f"collect site {entry.get('name')}: {e}")
                        self._mark_unreachable(entry)
                cycle += 1
            except Exception as e:
                log.error(f"Collection error: {e}")
            time.sleep(self.interval)

    def _collect_site(self, entry, cycle):
        sid, name, rc = entry["id"], entry.get("name", entry["id"]), entry["client"]
        now = datetime.now(timezone.utc)
        data = rc.get_client_details()
        reachable = not ("error" in data and not data.get("clients"))
        clients = data.get("clients", [])

        snapshots, roams, ap_counts = [], [], {}
        for c in clients:
            mac, ap = (c.get("mac") or "").lower(), c.get("ap_name", "")
            if not mac:
                continue
            snapshots.append({
                "site_id": sid, "mac": mac, "timestamp": now,
                "hostname": c.get("hostname", ""), "ip": c.get("ip", ""),
                "username": c.get("username", ""), "ap_name": ap, "ssid": c.get("ssid", ""),
                "band": c.get("band", ""), "channel": c.get("channel", 0),
                "rssi_dbm": c.get("rssi_dbm", 0), "snr_db": c.get("snr_db", 0),
                "quality_score": c.get("quality_score", 0), "quality_label": c.get("quality_label", ""),
                "data_rate_mbps": c.get("data_rate_mbps", 0), "data_retries": c.get("data_retries", 0),
                "bssid": c.get("bssid", ""),
            })
            k = f"{sid}|{mac}"
            prev = self._last_ap.get(k)
            if prev and prev != ap and ap:
                roams.append({
                    "site_id": sid, "mac": mac, "timestamp": now, "from_ap": prev, "to_ap": ap,
                    "ssid": c.get("ssid", ""), "band": c.get("band", ""), "channel": c.get("channel", 0),
                    "rssi_after": c.get("rssi_dbm", 0), "snr_after": c.get("snr_db", 0),
                    "quality_after": c.get("quality_score", 0),
                })
                log.info(f"ROAM[{name}]: {mac} {prev} -> {ap}")
            self._last_ap[k] = ap
            if ap:
                ap_counts[ap] = ap_counts.get(ap, 0) + 1

        if snapshots:
            try:
                self.db["client_snapshots"].with_options(write_concern=WriteConcern(w=0)).insert_many(snapshots, ordered=False)
            except Exception as e:
                log.error(f"Snap insert: {e}")
        if roams:
            try:
                self.db["roaming_events"].insert_many(roams, ordered=False)
            except Exception as e:
                log.error(f"Roam insert: {e}")
        if ap_counts:
            docs = [{"site_id": sid, "ap_name": a, "client_count": n, "timestamp": now} for a, n in ap_counts.items()]
            try:
                self.db["ap_load_history"].with_options(write_concern=WriteConcern(w=0)).insert_many(docs, ordered=False)
            except Exception as e:
                log.error(f"AP load insert: {e}")
        if cycle % 5 == 0 and snapshots:
            self._downsample(sid, now, clients)

        self._collect_status(entry, now, clients, reachable, cycle)

    def _collect_status(self, entry, now, clients, reachable, cycle):
        """Per-site summary for the overview + system_metrics time-series."""
        sid, rc = entry["id"], entry["client"]
        cpu_pct = mem_pct = 0
        # The full AP inventory is heavy on the C9800 (serialized RESTCONF) and
        # competes with user page requests — refresh it only every 5th cycle and
        # reuse the last counts in between, instead of every cycle.
        cached = self._ap_cache.get(sid)
        if cached is None or cycle % 5 == 0:
            try:
                aps = rc.get_ap_summary(page=1, per_page=100000).get("aps", [])
                cached = (len(aps), sum(1 for a in aps if _is_up(a.get("state", ""))))
                self._ap_cache[sid] = cached
            except Exception:
                reachable = False
                cached = cached or (0, 0)
        total_aps, online_aps = cached
        try:
            cpu_pct = rc.get_cpu_usage().get("one_minute", 0) or 0
            mem = rc.get_memory_usage()
            mem_pct = max((p.get("used_percent", 0) for p in mem.get("pools", [])), default=0)
        except Exception:
            pass

        b2 = b5 = b6 = 0
        for c in clients:
            band = c.get("band", "")
            if "6" in band: b6 += 1
            elif "5" in band: b5 += 1
            elif "2" in band: b2 += 1

        self.db["site_status"].update_one(
            {"_id": sid},
            {"$set": {
                "name": entry.get("name", sid), "location": entry.get("location", ""),
                "reachable": bool(reachable), "total_aps": total_aps, "online_aps": online_aps,
                "clients": len(clients), "cpu": round(cpu_pct), "mem": round(mem_pct),
                "updated_at": now,
            }},
            upsert=True,
        )
        try:
            self.db["system_metrics"].insert_one({
                "site_id": sid, "timestamp": now, "total_clients": len(clients),
                "clients_2g": b2, "clients_5g": b5, "clients_6g": b6,
                "cpu_1m": round(cpu_pct), "mem_used_pct": round(mem_pct, 1), "total_aps": total_aps,
            })
        except Exception as e:
            log.error(f"system metrics: {e}")

    def _mark_unreachable(self, entry):
        try:
            self.db["site_status"].update_one(
                {"_id": entry["id"]},
                {"$set": {"name": entry.get("name", entry["id"]), "reachable": False,
                          "updated_at": datetime.now(timezone.utc)}},
                upsert=True)
        except Exception:
            pass

    def _downsample(self, sid, now, clients):
        docs = []
        for c in clients:
            mac = (c.get("mac") or "").lower()
            if not mac:
                continue
            docs.append({
                "site_id": sid, "mac": mac, "timestamp": now, "ap_name": c.get("ap_name", ""),
                "ssid": c.get("ssid", ""), "band": c.get("band", ""), "rssi_dbm": c.get("rssi_dbm", 0),
                "snr_db": c.get("snr_db", 0), "quality_score": c.get("quality_score", 0),
                "data_rate_mbps": c.get("data_rate_mbps", 0),
            })
        if docs:
            try:
                self.db["client_snapshots_5m"].insert_many(docs, ordered=False)
            except Exception:
                pass
