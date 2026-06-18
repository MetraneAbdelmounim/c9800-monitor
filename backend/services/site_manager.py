"""
SiteManager — holds one live WLC client per enabled site (Phase 2).

Vendor is global; each site provides its own host/credentials. The manager is
rebuilt whenever sites or demo-mode change (via the swap callback). Collector and
event engine iterate entries(); read APIs resolve a client with for_site().
"""
import logging

from services.caching_client import CachingClient

log = logging.getLogger("Sites")


class SiteManager:
    def __init__(self, list_enabled, build_client, api_cache_ttl=20):
        # list_enabled() -> [ {id,name,location,host,port,username,password,verify_ssl}, ... ]
        # build_client(site_dict) -> WlcClient
        self._list = list_enabled
        self._build = build_client
        self._ttl = api_cache_ttl
        self._clients = {}     # site_id -> RAW client (collector/events: always fresh)
        self._cached = {}      # site_id -> CachingClient (API reads: TTL-cached)
        self._meta = {}        # site_id -> {id,name,location}
        self.rebuild()

    def rebuild(self):
        clients, cached, meta = {}, {}, {}
        for s in self._list():
            sid = s["id"]
            try:
                raw = self._build(s)
                clients[sid] = raw
                cached[sid] = CachingClient(raw, ttl=self._ttl)
                meta[sid] = {"id": sid, "name": s.get("name", sid), "location": s.get("location", "")}
            except Exception as e:
                log.error(f"failed to build client for site {s.get('name', sid)}: {e}")
        self._clients, self._cached, self._meta = clients, cached, meta
        log.info(f"SiteManager: {len(clients)} site client(s) ready (API cache {self._ttl}s)")

    def entries(self):
        """[{id, name, location, client}] with RAW clients — for the collector
        and event engine (must read fresh, uncached)."""
        return [{**self._meta[sid], "client": c} for sid, c in self._clients.items()]

    def for_site(self, site_id):
        """Cached client for the API read path."""
        if site_id and site_id in self._cached:
            return self._cached[site_id]
        return self._cached.get(self.default_id())

    def meta(self, site_id):
        return self._meta.get(site_id)

    def ids(self):
        return list(self._clients.keys())

    def default_id(self):
        return next(iter(self._clients), None)
