"""
WlcClient — the vendor-neutral contract every controller adapter implements.

Routes, the collector, the event engine, and the trends/lifecycle code all call
these methods and consume the normalized dict shapes documented here. Cisco
(C9800RestconfClient) and the DemoClient already conform de-facto; new vendors
(RuckusClient, …) subclass this base and override what they can. Methods left
unimplemented fall back to the safe empty values below, so a partial adapter
never crashes the app — the UI just shows "no data" for that area.

Keep the RETURN SHAPES identical across adapters — that's the whole contract.
"""
from datetime import datetime


class WlcClient:
    # ── health / system ────────────────────────────────
    def health_check(self):
        return {"status": "unreachable", "timestamp": datetime.now().isoformat()}

    def get_system_info(self):
        return {"hostname": "Unknown", "version": "Unknown",
                "timestamp": datetime.now().isoformat()}

    def get_cpu_usage(self):
        return {"five_seconds": 0, "one_minute": 0, "five_minutes": 0}

    def get_memory_usage(self):
        return {"pools": []}

    def get_dashboard(self):
        return {
            "system": self.get_system_info(),
            "cpu": self.get_cpu_usage(),
            "memory": self.get_memory_usage(),
            "aps": self.get_ap_count(),
            "clients": self.get_client_summary(),
            "wlans": self.get_wlan_list(),
            "health": self.health_check(),
        }

    # ── access points ──────────────────────────────────
    def get_ap_count(self):
        return {"total_aps": 0}

    def get_ap_summary(self, page=1, per_page=50):
        return {"total_aps": 0, "page": page, "per_page": per_page, "total_pages": 0, "aps": []}

    def get_ap_detail(self, mac):
        return {}

    def get_ap_addresses(self):
        return []

    def get_ap_lifecycle(self):
        return []

    # ── clients ────────────────────────────────────────
    def get_client_summary(self):
        return {"total_clients": 0, "run_state": 0, "auth_state": 0,
                "iplearn_state": 0, "webauth_state": 0, "random_mac_clients": 0,
                "clients_2ghz": 0, "clients_5ghz": 0, "clients_6ghz": 0}

    def get_client_details(self, page=None, per_page=50):
        return {"total": 0, "clients": []}

    def get_client_detail(self, mac):
        return {"error": "Client not found"}

    def search_clients(self, query):
        return {"query": query, "total": 0, "clients": []}

    def get_client_stats(self):
        return {"total_clients": 0}

    # ── wlans / rf / interfaces ────────────────────────
    def get_wlan_list(self):
        return {"total_wlans": 0, "wlans": []}

    def get_rf_data(self):
        return {}

    def get_rf_analysis(self):
        return {"summary": {"critical": 0, "high": 0, "medium": 0, "affected_aps": 0},
                "conflicts": [], "radios": []}

    def get_interfaces(self):
        return {"interfaces": []}

    # ── security ───────────────────────────────────────
    def get_rogues(self):
        return {"rogue_aps": [], "rogue_clients": []}

    def get_awips(self):
        return {"alarms": []}
