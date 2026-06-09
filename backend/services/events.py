"""
Event engine — synthesizes a security/RF event log from WLC telemetry.

The C9800 has no unified, persisted "event log with ack state" over RESTCONF,
so we poll several oper sources, apply thresholds/classification, and store
events in MongoDB (collection `events`) with dedup, auto-resolve, and ack state.

Sources:
  - rogue-oper-data        → rogue APs / rogue clients      (security)
  - awips-oper-data        → aWIPS intrusion alarms          (security)
  - RRM analysis (RF)      → critical channel conflicts      (rf)
  - RRM radios             → sustained high utilization      (rf)
  - client details         → APs with multiple low-SNR clients (client)

Each event has a stable `key` so repeated polls update one record rather than
duplicating. Events not seen in a poll are marked inactive (resolved) but kept
until acknowledged.
"""
import threading
import time
import logging
from datetime import datetime, timezone

log = logging.getLogger("Events")

UTIL_THRESHOLD = 70          # % channel utilization → high-utilization event
SNR_THRESHOLD = 15           # dB; clients below this count as poor
SNR_MIN_CLIENTS = 3          # min poor-SNR clients on one AP to raise an event

_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class EventEngine:
    def __init__(self, restconf_client, mongo_db, interval=60):
        self.rc = restconf_client
        self.db = mongo_db
        self.interval = interval
        self._running = False
        self._thread = None

    # ── lifecycle ──────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self.db["events"].create_index("key", unique=True)
            self.db["events"].create_index([("acked", 1), ("last_seen", -1)])
        except Exception as e:
            log.error(f"events index setup failed: {e}")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(f"Event engine started (every {self.interval}s)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while self._running:
            try:
                self.evaluate()
            except Exception as e:
                log.error(f"event evaluate error: {e}")
            time.sleep(self.interval)

    # ── evaluation ─────────────────────────────────────
    def evaluate(self):
        current = []
        for collector in (self._rogues, self._dup_addr, self._lifecycle,
                          self._awips, self._rf, self._client_snr):
            try:
                current.extend(collector())
            except Exception as e:
                log.error(f"event source {collector.__name__} failed: {e}")

        now = datetime.now(timezone.utc)
        seen = set()
        for e in current:
            seen.add(e["key"])
            self.db["events"].update_one(
                {"key": e["key"]},
                {"$set": {
                    "type": e["type"], "category": e["category"],
                    "severity": e["severity"], "score": e["score"],
                    "title": e["title"], "detail": e["detail"],
                    "ap_name": e.get("ap_name", ""), "ssid": e.get("ssid", ""),
                    "last_seen": now, "active": True,
                 },
                 "$setOnInsert": {"key": e["key"], "first_seen": now, "acked": False}},
                upsert=True,
            )
        # Anything not seen this cycle is no longer active (resolved), but kept.
        self.db["events"].update_many(
            {"active": True, "key": {"$nin": list(seen)}},
            {"$set": {"active": False, "resolved_at": now}},
        )
        log.debug(f"event evaluate: {len(seen)} active events")

    # ── sources ────────────────────────────────────────
    def _rogues(self):
        out = []
        data = self.rc.get_rogues()
        for r in data.get("rogue_aps", []):
            cls = r["classification"]
            if cls == "friendly":
                continue                      # known/allowed — not an alert
            on_wire = r.get("on_wire")
            rssi = r.get("rssi", 0) or 0
            if cls == "malicious" or on_wire:
                sev, score = "critical", 98 if on_wire else 95
            elif cls == "custom":
                sev, score = "high", 85
            else:
                # Unclassified rogues are usually neighbor networks — weight by
                # how close they are (and whether they have clients) so distant
                # neighbors don't flood the log with high-severity alerts.
                if rssi >= -60 or r.get("num_clients", 0) >= 1:
                    sev, score = "medium", 60
                elif rssi >= -75:
                    sev, score = "low", 45
                else:
                    sev, score = "low", 30
            title = ("Malicious Rogue AP Detected" if cls == "malicious"
                     else "Rogue AP on Wired Network" if on_wire
                     else f"{cls.capitalize()} Rogue AP Detected")
            ssid = r.get("ssid") or "(hidden)"
            det = f" Detected by {r['detecting_ap']}." if r.get("detecting_ap") else ""
            wire = " Found on the wired network." if on_wire else ""
            out.append({
                "key": f"rogue_ap:{r['mac']}", "type": "rogue_ap", "category": "security",
                "severity": sev, "score": score,
                "title": title, "ap_name": r.get("detecting_ap", ""), "ssid": r.get("ssid", ""),
                "detail": f'SSID "{ssid}" on ch {r.get("channel", "?")}, {r.get("rssi", 0)} dBm, '
                          f'{r.get("num_clients", 0)} client(s).{wire}{det}',
            })
        for c in data.get("rogue_clients", []):
            out.append({
                "key": f"rogue_client:{c['mac']}", "type": "rogue_client", "category": "security",
                "severity": "medium", "score": 60,
                "title": "Rogue Client Detected", "ap_name": "", "ssid": "",
                "detail": f"Client {c['mac']} ({c.get('rssi', 0)} dBm) associated to rogue "
                          f"{c.get('rogue_ap', '?')}.",
            })
        return out

    def _dup_addr(self):
        """Detect APs sharing the same IP or ethernet MAC (misconfig / cloning)."""
        out = []
        aps = self.rc.get_ap_addresses()
        by_ip, by_mac = {}, {}
        for ap in aps:
            ip = (ap.get("ip") or "").strip()
            if ip and ip != "0.0.0.0":
                by_ip.setdefault(ip, []).append(ap)
            mac = (ap.get("mac") or "").strip().lower()
            if mac and mac != "00:00:00:00:00:00":
                by_mac.setdefault(mac, []).append(ap)

        for ip, grp in by_ip.items():
            names = sorted({a["name"] for a in grp if a.get("name")})
            if len(names) > 1:
                out.append({
                    "key": f"dup_ip:{ip}", "type": "duplicate_ap_ip", "category": "security",
                    "severity": "high", "score": 84,
                    "title": "Duplicate AP IP Address", "ap_name": names[0], "ssid": "",
                    "detail": f"IP {ip} is shared by {len(names)} APs: {', '.join(names)}.",
                })
        for mac, grp in by_mac.items():
            names = sorted({a["name"] for a in grp if a.get("name")})
            if len(names) > 1:
                out.append({
                    "key": f"dup_mac:{mac}", "type": "duplicate_ap_mac", "category": "security",
                    "severity": "critical", "score": 93,
                    "title": "Duplicate AP MAC Address", "ap_name": names[0], "ssid": "",
                    "detail": f"MAC {mac} is reported by {len(names)} APs: {', '.join(names)} "
                              f"— possible cloned or spoofed AP.",
                })
        return out

    def _lifecycle(self):
        """Detect AP reboots (boot-time reset) and flaps (re-join without reboot)
        by comparing against the persisted per-AP state, plus a firmware-
        compliance summary against the admin-set target version."""
        from services.settings import get_target_version
        out = []
        aps = self.rc.get_ap_lifecycle()
        coll = self.db["ap_lifecycle"]
        now = datetime.now(timezone.utc)

        for ap in aps:
            mac = ap.get("mac")
            if not mac:
                continue
            boot, join = ap.get("boot_time", ""), ap.get("join_time", "")
            name = ap.get("name") or mac
            state = (ap.get("state") or "").lower()

            # AP offline — active condition (resolves when it comes back online).
            if any(x in state for x in ("down", "offline", "disconnect")):
                out.append({
                    "key": f"ap_down:{mac}", "type": "ap_down", "category": "health",
                    "severity": "high", "score": 80, "title": f"AP Offline — {name}",
                    "ap_name": name, "ssid": "",
                    "detail": f"{name} ({ap.get('model','')}) is {ap.get('state') or 'offline'} — "
                              f"coverage gap in its area; check PoE/uplink.",
                })

            prev = coll.find_one({"_id": mac})
            inc = {}
            if prev:
                pboot, pjoin = prev.get("boot_time", ""), prev.get("join_time", "")
                if boot and pboot and boot != pboot and "1970" not in boot:
                    inc["reboot_count"] = 1
                    out.append({
                        "key": f"reboot:{mac}:{boot}", "type": "ap_reboot", "category": "lifecycle",
                        "severity": "high", "score": 76, "title": f"AP Rebooted — {name}",
                        "ap_name": name, "ssid": "",
                        "detail": f"{name} ({ap.get('model','')}) rebooted — uptime reset.",
                    })
                elif join and pjoin and join != pjoin and "1970" not in join:
                    inc["flap_count"] = 1
                    flaps = prev.get("flap_count", 0) + 1
                    sev = "high" if flaps >= 3 else "medium"
                    out.append({
                        "key": f"flap:{mac}:{join}", "type": "ap_flap", "category": "lifecycle",
                        "severity": sev, "score": 70 if sev == "high" else 55,
                        "title": f"AP Re-joined — {name}", "ap_name": name, "ssid": "",
                        "detail": f"{name} disconnected and re-joined the controller "
                                  f"(flap #{flaps}).",
                    })
            update = {"$set": {"boot_time": boot, "join_time": join, "name": name,
                               "version": ap.get("sw_version", ""), "state": ap.get("state", ""),
                               "last_seen": now}}
            if inc:
                update["$inc"] = inc
            coll.update_one({"_id": mac}, update, upsert=True)

        # Firmware-compliance summary (one rolling event)
        target = get_target_version()
        if target and aps:
            bad = [a for a in aps if a.get("sw_version") and a["sw_version"] != target]
            if bad:
                out.append({
                    "key": "fw_compliance", "type": "firmware_noncompliant", "category": "lifecycle",
                    "severity": "medium", "score": 50, "title": "AP Firmware Non-Compliant",
                    "ap_name": "", "ssid": "",
                    "detail": f"{len(bad)} of {len(aps)} APs are not on target version {target}.",
                })
        return out

    def _awips(self):
        out = []
        for a in self.rc.get_awips().get("alarms", []):
            if not a.get("count"):
                continue
            out.append({
                "key": f"awips:{a['signature']}:{a.get('ap_mac', '')}",
                "type": "awips", "category": "security", "severity": "high", "score": 80,
                "title": f"aWIPS Signature: {a['signature']}", "ap_name": a.get("ap_mac", ""),
                "ssid": "", "detail": f"{a['count']} detection(s) of '{a['signature']}'.",
            })
        return out

    def _rf(self):
        out = []
        rf = self.rc.get_rf_analysis()
        for cf in rf.get("conflicts", []):
            if cf["severity"] != "critical":
                continue                      # keep the log focused on the worst
            f = cf["focal"]
            out.append({
                "key": f"conflict:{f['mac']}:{f['slot']}:{cf['type']}",
                "type": "channel_conflict", "category": "rf",
                "severity": "critical", "score": 90,
                "title": f"Critical {cf['title']}", "ap_name": f["ap_name"], "ssid": "",
                "detail": cf["detail"],
            })
        for radio in rf.get("radios", []):
            if radio.get("utilization", 0) >= UTIL_THRESHOLD:
                out.append({
                    "key": f"util:{radio['mac']}:{radio['slot']}",
                    "type": "high_utilization", "category": "rf",
                    "severity": "high", "score": 75,
                    "title": "High Channel Utilization", "ap_name": radio["ap_name"], "ssid": "",
                    "detail": f"{radio['ap_name']} {radio['band']} ch {radio['channel']} "
                              f"utilization {radio['utilization']}%.",
                })
        return out

    def _client_snr(self):
        out = []
        data = self.rc.get_client_details()
        per_ap = {}
        for c in data.get("clients", []):
            snr = c.get("snr_db", 0)
            ap = c.get("ap_name", "")
            if ap and snr and snr < SNR_THRESHOLD:
                per_ap[ap] = per_ap.get(ap, 0) + 1
        for ap, n in per_ap.items():
            if n >= SNR_MIN_CLIENTS:
                out.append({
                    "key": f"snr:{ap}", "type": "client_snr_drop", "category": "client",
                    "severity": "high" if n >= 6 else "medium", "score": 70 if n >= 6 else 55,
                    "title": f"Client SNR Drop — {ap}", "ap_name": ap, "ssid": "",
                    "detail": f"{n} client(s) on {ap} report SNR below {SNR_THRESHOLD} dB.",
                })
        return out

    # ── queries / actions (used by routes) ─────────────
    def list_events(self, show_acked=False):
        q = {} if show_acked else {"acked": False}
        docs = list(self.db["events"].find(q))
        docs.sort(key=lambda d: (_SEV_RANK.get(d.get("severity"), 9),
                                 -(d.get("last_seen").timestamp() if d.get("last_seen") else 0)))
        events = [self._public(d) for d in docs]
        return {
            "events": events,
            "unacked": self.db["events"].count_documents({"acked": False}),
            "acked": self.db["events"].count_documents({"acked": True}),
        }

    def ack(self, ids, user):
        from bson import ObjectId
        oids = []
        for i in ids:
            try:
                oids.append(ObjectId(i))
            except Exception:
                pass
        if not oids:
            return {"acked": 0}
        res = self.db["events"].update_many(
            {"_id": {"$in": oids}, "acked": False},
            {"$set": {"acked": True, "acked_by": user, "acked_at": datetime.now(timezone.utc)}})
        return {"acked": res.modified_count}

    def ack_all(self, user):
        res = self.db["events"].update_many(
            {"acked": False},
            {"$set": {"acked": True, "acked_by": user, "acked_at": datetime.now(timezone.utc)}})
        return {"acked": res.modified_count}

    @staticmethod
    def _public(d):
        return {
            "id": str(d["_id"]),
            "type": d.get("type"), "category": d.get("category"),
            "severity": d.get("severity"), "score": d.get("score"),
            "title": d.get("title"), "detail": d.get("detail"),
            "ap_name": d.get("ap_name", ""), "ssid": d.get("ssid", ""),
            "active": d.get("active", True), "acked": d.get("acked", False),
            "first_seen": d["first_seen"].isoformat() if d.get("first_seen") else None,
            "last_seen": d["last_seen"].isoformat() if d.get("last_seen") else None,
        }
