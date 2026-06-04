"""
Scheduled cleanup of collector / tracking data.

Runs in a background thread; cadence and retention are admin-configurable
(persisted in Mongo via settings.py) and changeable at runtime with no restart.
This is independent of — and complementary to — the MongoDB TTL indexes set up
by the collector, which remain a backstop.

Cadence is decided with a "bucket" key: the current time is mapped to a bucket
for the chosen schedule, and cleanup runs once whenever that bucket changes.
Buckets change at midnight (UTC) boundaries, so daily/weekly/monthly fire at
"midnight" naturally; weekly is anchored to Sunday.
"""
import threading
import time
import logging
from datetime import datetime, timezone, timedelta

from settings import (
    get_cleanup_settings, record_cleanup_run, set_cleanup_bucket,
    TRACKING_COLLECTIONS,
)

log = logging.getLogger("Cleanup")
CHECK_INTERVAL = 60  # seconds between schedule checks


def bucket_for(schedule: str, now: datetime) -> str:
    if schedule == "5min":
        return "5m-" + str(int(now.timestamp()) // 300)
    if schedule == "hourly":
        return now.strftime("h-%Y%m%d%H")
    if schedule == "daily":
        return now.strftime("d-%Y%m%d")
    if schedule == "weekly":
        # Date of the most recent Sunday (UTC) → changes at Sunday 00:00.
        sunday = (now - timedelta(days=(now.weekday() + 1) % 7)).date()
        return "w-" + sunday.isoformat()
    if schedule == "monthly":
        return now.strftime("m-%Y%m")
    return "?"


class CleanupScheduler:
    def __init__(self, mongo_db):
        self.db = mongo_db
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Cleanup scheduler started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self):
        # Seed the bucket on boot so enabling cleanup doesn't purge immediately;
        # the first real run happens at the next schedule boundary.
        try:
            s = get_cleanup_settings()
            if s["enabled"] and not s.get("last_bucket"):
                set_cleanup_bucket(bucket_for(s["schedule"], datetime.now(timezone.utc)))
        except Exception as e:
            log.error(f"Cleanup seed failed: {e}")

        while self._running:
            try:
                self._tick()
            except Exception as e:
                log.error(f"Cleanup tick error: {e}")
            time.sleep(CHECK_INTERVAL)

    def _tick(self):
        s = get_cleanup_settings()
        if not s["enabled"]:
            return
        now = datetime.now(timezone.utc)
        bucket = bucket_for(s["schedule"], now)
        if bucket == s.get("last_bucket"):
            return
        deleted = self._purge(s["retention_days"], now)
        record_cleanup_run(deleted, bucket=bucket)
        log.info(f"Scheduled cleanup ({s['schedule']}) removed {deleted} docs "
                 f"(retention {s['retention_days']}d)")

    def _purge(self, retention_days: int, now: datetime) -> int:
        flt = {}
        if retention_days > 0:
            flt = {"timestamp": {"$lt": now - timedelta(days=retention_days)}}
        total = 0
        for coll in TRACKING_COLLECTIONS:
            try:
                total += self.db[coll].delete_many(flt).deleted_count
            except Exception as e:
                log.error(f"Purge {coll} failed: {e}")
        return total

    def run_now(self) -> dict:
        """Manual purge (does not change the schedule bucket)."""
        now = datetime.now(timezone.utc)
        s = get_cleanup_settings()
        deleted = self._purge(s["retention_days"], now)
        record_cleanup_run(deleted)
        log.info(f"Manual cleanup removed {deleted} docs (retention {s['retention_days']}d)")
        return {"deleted": deleted, "retention_days": s["retention_days"]}

    def stats(self) -> dict:
        out = {}
        for coll in TRACKING_COLLECTIONS:
            try:
                out[coll] = self.db[coll].estimated_document_count()
            except Exception:
                out[coll] = None
        return out
