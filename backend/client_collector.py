"""
Client Collector - Scaled for 3000+ clients.
Changes: throttled inserts, batch processing, downsampling for old data.
"""
import threading, time, logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("Collector")

class ClientCollector:
    def __init__(self, restconf_client, mongo_db, interval=60):
        self.rc = restconf_client
        self.db = mongo_db
        self.interval = interval  # 60s for large deployments (not 30s)
        self._running = False
        self._thread = None
        self._last_ap = {}

    def _setup_db(self):
        try:
            snap = self.db["client_snapshots"]
            snap.create_index([("mac", 1), ("timestamp", -1)])
            snap.create_index([("ap_name", 1), ("timestamp", -1)])
            snap.create_index("timestamp", expireAfterSeconds=3*86400)  # 3 days for large deployments

            roam = self.db["roaming_events"]
            roam.create_index([("mac", 1), ("timestamp", -1)])
            roam.create_index("timestamp", expireAfterSeconds=7*86400)

            ap_load = self.db["ap_load_history"]
            ap_load.create_index([("ap_name", 1), ("timestamp", -1)])
            ap_load.create_index("timestamp", expireAfterSeconds=3*86400)

            # Downsampled data (1 per 5min, kept 30 days)
            ds = self.db["client_snapshots_5m"]
            ds.create_index([("mac", 1), ("timestamp", -1)])
            ds.create_index("timestamp", expireAfterSeconds=30*86400)

            log.info("MongoDB indexes ready (scaled mode)")
        except Exception as e:
            log.error(f"Index setup failed: {e}")

    def start(self):
        if self._running: return
        self._running = True
        self._setup_db()
        self._load_last_aps()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"Collector started (every {self.interval}s, scaled mode)")

    def stop(self):
        self._running = False
        if self._thread: self._thread.join(timeout=5)

    def _load_last_aps(self):
        try:
            for doc in self.db["client_snapshots"].aggregate([
                {"$sort": {"timestamp": -1}},
                {"$group": {"_id": "$mac", "ap": {"$first": "$ap_name"}}}
            ]):
                self._last_ap[doc["_id"]] = doc["ap"]
        except: pass

    def _loop(self):
        cycle = 0
        while self._running:
            try:
                self._collect(cycle)
                cycle += 1
            except Exception as e:
                log.error(f"Collection error: {e}")
            time.sleep(self.interval)

    def _collect(self, cycle):
        now = datetime.now(timezone.utc)
        data = self.rc.get_client_details()
        if "error" in data and not data.get("clients"): return
        clients = data.get("clients", [])

        snapshots, roams, ap_counts = [], [], {}
        # Store RF-relevant fields + identity fields for search/display
        for c in clients:
            mac, ap = c.get("mac",""), c.get("ap_name","")
            if not mac: continue
            snapshots.append({
                "mac": mac, "timestamp": now,
                "hostname": c.get("hostname",""),
                "ip": c.get("ip",""),
                "username": c.get("username",""),
                "ap_name": ap, "ssid": c.get("ssid",""),
                "band": c.get("band",""), "channel": c.get("channel",0),
                "rssi_dbm": c.get("rssi_dbm",0), "snr_db": c.get("snr_db",0),
                "quality_score": c.get("quality_score",0),
                "quality_label": c.get("quality_label",""),
                "data_rate_mbps": c.get("data_rate_mbps",0),
                "data_retries": c.get("data_retries",0),
                "bssid": c.get("bssid",""),
            })
            prev = self._last_ap.get(mac)
            if prev and prev != ap and ap:
                roams.append({
                    "mac": mac, "timestamp": now,
                    "from_ap": prev, "to_ap": ap,
                    "ssid": c.get("ssid",""), "band": c.get("band",""),
                    "channel": c.get("channel",0),
                    "rssi_after": c.get("rssi_dbm",0),
                    "snr_after": c.get("snr_db",0),
                    "quality_after": c.get("quality_score",0),
                })
                log.info(f"ROAM: {mac} {prev} -> {ap}")
            self._last_ap[mac] = ap
            if ap: ap_counts[ap] = ap_counts.get(ap,0)+1

        # Bulk inserts with write concern w=0 for speed
        if snapshots:
            try:
                self.db["client_snapshots"].with_options(
                    write_concern=__import__('pymongo').WriteConcern(w=0)
                ).insert_many(snapshots, ordered=False)
            except Exception as e: log.error(f"Snap insert: {e}")

        if roams:
            try: self.db["roaming_events"].insert_many(roams, ordered=False)
            except Exception as e: log.error(f"Roam insert: {e}")

        if ap_counts:
            docs = [{"ap_name":a,"client_count":n,"timestamp":now} for a,n in ap_counts.items()]
            try:
                self.db["ap_load_history"].with_options(
                    write_concern=__import__('pymongo').WriteConcern(w=0)
                ).insert_many(docs, ordered=False)
            except Exception as e: log.error(f"AP load insert: {e}")

        # Every 5th cycle (~5min), create downsampled snapshot
        if cycle % 5 == 0 and snapshots:
            self._downsample(now, clients)

        log.debug(f"Collected {len(snapshots)} clients, {len(roams)} roams")

    def _downsample(self, now, clients):
        """Store 5-minute averages for long-term history."""
        ds_docs = []
        for c in clients:
            mac = c.get("mac","")
            if not mac: continue
            ds_docs.append({
                "mac": mac, "timestamp": now,
                "ap_name": c.get("ap_name",""),
                "ssid": c.get("ssid",""),
                "band": c.get("band",""),
                "rssi_dbm": c.get("rssi_dbm",0),
                "snr_db": c.get("snr_db",0),
                "quality_score": c.get("quality_score",0),
                "data_rate_mbps": c.get("data_rate_mbps",0),
            })
        if ds_docs:
            try: self.db["client_snapshots_5m"].insert_many(ds_docs, ordered=False)
            except: pass

    def collect_now(self):
        self._collect(0)