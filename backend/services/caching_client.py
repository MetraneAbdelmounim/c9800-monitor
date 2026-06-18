"""
CachingClient — short-lived TTL cache in front of a WlcClient for the API read
path. The C9800 RESTCONF API is slow for large oper data (clients/APs/RF), and a
single page load fires several calls (dashboard + aps + clients + advisor, which
itself calls many). Caching each (method, args) result for a few seconds means
the controller is hit at most once per TTL per distinct call, and repeated loads
/ auto-refresh polls return instantly.

Used ONLY for API requests (SiteManager.for_site). The collector/event engine
use the RAW client so their polling always reads fresh data.
"""
import time
import threading


class CachingClient:
    def __init__(self, inner, ttl=20):
        self._inner = inner
        self._ttl = ttl
        self._cache = {}
        self._lock = threading.Lock()

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def wrapped(*args, **kwargs):
            try:
                key = (name, args, tuple(sorted(kwargs.items())))
            except TypeError:
                return attr(*args, **kwargs)        # unhashable args → don't cache
            now = time.monotonic()
            with self._lock:
                hit = self._cache.get(key)
                if hit and (now - hit[0]) < self._ttl:
                    return hit[1]
            val = attr(*args, **kwargs)
            with self._lock:
                self._cache[key] = (now, val)
            return val
        return wrapped
