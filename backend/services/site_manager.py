"""
SiteManager — holds one live WLC client per enabled site (Phase 2).

Vendor is global; each site provides its own host/credentials. The manager is
rebuilt whenever sites or demo-mode change (via the swap callback). Collector and
event engine iterate entries(); read APIs resolve a client with for_site().
"""
import logging

log = logging.getLogger("Sites")


class SiteManager:
    def __init__(self, list_enabled, build_client):
        # list_enabled() -> [ {id,name,location,host,port,username,password,verify_ssl}, ... ]
        # build_client(site_dict) -> WlcClient
        self._list = list_enabled
        self._build = build_client
        self._clients = {}     # site_id -> client
        self._meta = {}        # site_id -> {id,name,location}
        self.rebuild()

    def rebuild(self):
        clients, meta = {}, {}
        for s in self._list():
            sid = s["id"]
            try:
                clients[sid] = self._build(s)
                meta[sid] = {"id": sid, "name": s.get("name", sid), "location": s.get("location", "")}
            except Exception as e:
                log.error(f"failed to build client for site {s.get('name', sid)}: {e}")
        self._clients, self._meta = clients, meta
        log.info(f"SiteManager: {len(clients)} site client(s) ready")

    def entries(self):
        """[{id, name, location, client}] for all enabled sites."""
        return [{**self._meta[sid], "client": c} for sid, c in self._clients.items()]

    def for_site(self, site_id):
        if site_id and site_id in self._clients:
            return self._clients[site_id]
        return self._clients.get(self.default_id())

    def meta(self, site_id):
        return self._meta.get(site_id)

    def ids(self):
        return list(self._clients.keys())

    def default_id(self):
        return next(iter(self._clients), None)
