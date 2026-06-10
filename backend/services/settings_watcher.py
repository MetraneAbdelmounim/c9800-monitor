"""
SettingsWatcher — keeps a process's live WLC client in sync with settings that
were edited in another process.

In a split deployment (web tier + a single worker tier), an admin changes WLC
settings on a web replica, which persists them to MongoDB. The worker — and any
other web replica — must rebuild its own live client to match. This watcher
polls the settings document and invokes a callback (swap_wlc_client) when the
WLC config or demo-mode override changes. In single-container mode it's a no-op
in practice: the synchronous swap calls mark_synced() so it never re-triggers.
"""
import logging
import threading

log = logging.getLogger("SettingsWatcher")


class SettingsWatcher(threading.Thread):
    def __init__(self, db, on_change, interval=15):
        super().__init__(daemon=True)
        self._db = db
        self._on_change = on_change
        self._interval = interval
        self._stop = threading.Event()
        self._sig = None
        self._sig = self._signature()

    def _signature(self):
        """A cheap fingerprint of the settings that affect the live client."""
        try:
            wlc = self._db["settings"].find_one({"_id": "wlc"}, {"updated_at": 1}) or {}
            sysd = self._db["settings"].find_one({"_id": "system"}, {"updated_at": 1, "demo_mode": 1}) or {}
            return (str(wlc.get("updated_at")), str(sysd.get("updated_at")), sysd.get("demo_mode"))
        except Exception as e:
            log.warning(f"settings signature read failed: {e}")
            return self._sig

    def mark_synced(self):
        """Record the current settings as baseline. Call after an in-process swap
        so the watcher doesn't redundantly rebuild the client it just built."""
        self._sig = self._signature()

    def run(self):
        while not self._stop.wait(self._interval):
            sig = self._signature()
            if sig != self._sig:
                self._sig = sig
                log.info("Settings changed in DB — rebuilding live client")
                try:
                    self._on_change()
                except Exception as e:
                    log.error(f"live client rebuild failed: {e}")

    def stop(self):
        self._stop.set()