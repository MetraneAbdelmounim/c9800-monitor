"""Demo data for testing without a real C9800 WLC."""
import random
from datetime import datetime


def _rand(a, b):
    return random.randint(a, b)


DEMO_APS = [
    {"name": "AP-FL1-LOBBY", "mac": "00:3a:9a:e1:22:10", "model": "C9130AXI", "ip": "10.10.1.11", "location": "Floor 1 - Lobby"},
    {"name": "AP-FL1-CONF-A", "mac": "00:3a:9a:e1:22:11", "model": "C9136I", "ip": "10.10.1.12", "location": "Floor 1 - Conference A"},
    {"name": "AP-FL2-OPEN", "mac": "00:3a:9a:e1:22:12", "model": "C9130AXI", "ip": "10.10.1.21", "location": "Floor 2 - Open Area"},
    {"name": "AP-FL2-EXEC", "mac": "00:3a:9a:e1:22:13", "model": "C9136I", "ip": "10.10.1.22", "location": "Floor 2 - Executive"},
    {"name": "AP-FL3-LAB", "mac": "00:3a:9a:e1:22:14", "model": "CW9166I", "ip": "10.10.1.31", "location": "Floor 3 - Lab"},
    {"name": "AP-FL3-BREAK", "mac": "00:3a:9a:e1:22:15", "model": "C9130AXI", "ip": "10.10.1.32", "location": "Floor 3 - Break Room"},
    {"name": "AP-OUTDOOR-N", "mac": "00:3a:9a:e1:22:16", "model": "C9124AXD", "ip": "10.10.2.10", "location": "Outdoor - North"},
    {"name": "AP-OUTDOOR-S", "mac": "00:3a:9a:e1:22:17", "model": "C9124AXD", "ip": "10.10.2.11", "location": "Outdoor - South"},
]

DEMO_WLANS = [
    {"profile_name": "CORP-SECURE", "wlan_id": 1, "ssid": "CorpNet", "status": "Enabled"},
    {"profile_name": "GUEST-OPEN", "wlan_id": 2, "ssid": "GuestWiFi", "status": "Enabled"},
    {"profile_name": "IOT-DEVICES", "wlan_id": 3, "ssid": "IoT-Sensors", "status": "Enabled"},
    {"profile_name": "VOICE-WLAN", "wlan_id": 4, "ssid": "VoiceNet", "status": "Enabled"},
    {"profile_name": "MGMT-SECURE", "wlan_id": 5, "ssid": "NetAdmin", "status": "Disabled"},
]

DEMO_CLIENTS = [
    {"mac": "AA:BB:CC:11:22:01", "ip": "10.10.5.41", "username": "jdupont", "hostname": "LAPTOP-JD01",
     "device_type": "Laptop", "os_type": "Windows 11",
     "ap_name": "AP-FL2-CONF-A", "ssid": "CorpNet", "band": "5 GHz", "channel": 36,
     "channel_width": "80MHz", "protocol": "Wi-Fi 6 (5G)",
     "rssi_dbm": -42, "snr_db": 48, "data_rate_mbps": 1201, "quality_score": 97, "quality_label": "Excellent",
     "tx_power_dbm": 17, "spatial_streams": 2, "mcs_index": 11,
     "state": "Run", "vlan": 100, "bytes_tx": 524288000, "bytes_rx": 1073741824,
     "data_retries": 12, "session_duration_sec": 14400, "roam_count": 1},
    {"mac": "AA:BB:CC:11:22:02", "ip": "10.10.5.42", "username": "amartin", "hostname": "iPhone-Ahmed",
     "device_type": "Smartphone", "os_type": "iOS 17",
     "ap_name": "AP-FL1-LOBBY", "ssid": "CorpNet", "band": "5 GHz", "channel": 149,
     "channel_width": "80MHz", "protocol": "Wi-Fi 6 (5G)",
     "rssi_dbm": -58, "snr_db": 34, "data_rate_mbps": 866, "quality_score": 76, "quality_label": "Good",
     "tx_power_dbm": 15, "spatial_streams": 2, "mcs_index": 9,
     "state": "Run", "vlan": 100, "bytes_tx": 104857600, "bytes_rx": 209715200,
     "data_retries": 45, "session_duration_sec": 3600, "roam_count": 3},
    {"mac": "AA:BB:CC:11:22:03", "ip": "10.10.5.43", "username": "sbenali", "hostname": "MBP-Sara",
     "device_type": "Laptop", "os_type": "macOS 14",
     "ap_name": "AP-FL3-LAB", "ssid": "CorpNet", "band": "6 GHz", "channel": 5,
     "channel_width": "160MHz", "protocol": "Wi-Fi 6E",
     "rssi_dbm": -38, "snr_db": 52, "data_rate_mbps": 2402, "quality_score": 99, "quality_label": "Excellent",
     "tx_power_dbm": 20, "spatial_streams": 2, "mcs_index": 11,
     "state": "Run", "vlan": 100, "bytes_tx": 2147483648, "bytes_rx": 4294967296,
     "data_retries": 3, "session_duration_sec": 28800, "roam_count": 0},
    {"mac": "AA:BB:CC:11:22:04", "ip": "10.10.5.44", "username": "guest_user1", "hostname": "Galaxy-S24",
     "device_type": "Smartphone", "os_type": "Android 14",
     "ap_name": "AP-FL1-LOBBY", "ssid": "GuestWiFi", "band": "5 GHz", "channel": 36,
     "channel_width": "40MHz", "protocol": "Wi-Fi 5",
     "rssi_dbm": -71, "snr_db": 18, "data_rate_mbps": 433, "quality_score": 38, "quality_label": "Poor",
     "tx_power_dbm": 14, "spatial_streams": 1, "mcs_index": 7,
     "state": "Run", "vlan": 200, "bytes_tx": 52428800, "bytes_rx": 157286400,
     "data_retries": 210, "session_duration_sec": 1800, "roam_count": 5},
    {"mac": "AA:BB:CC:11:22:05", "ip": "10.10.5.45", "username": "yelhadri", "hostname": "DESKTOP-YE",
     "device_type": "Desktop", "os_type": "Windows 10",
     "ap_name": "AP-FL2-OPEN", "ssid": "CorpNet", "band": "2.4 GHz", "channel": 6,
     "channel_width": "20MHz", "protocol": "Wi-Fi 4",
     "rssi_dbm": -78, "snr_db": 11, "data_rate_mbps": 72, "quality_score": 18, "quality_label": "Critical",
     "tx_power_dbm": 12, "spatial_streams": 1, "mcs_index": 4,
     "state": "Run", "vlan": 100, "bytes_tx": 10485760, "bytes_rx": 31457280,
     "data_retries": 890, "session_duration_sec": 7200, "roam_count": 0},
    {"mac": "AA:BB:CC:11:22:06", "ip": "10.10.5.46", "username": "nfassi", "hostname": "iPad-Nadia",
     "device_type": "Tablet", "os_type": "iPadOS 17",
     "ap_name": "AP-FL3-BREAK", "ssid": "CorpNet", "band": "5 GHz", "channel": 44,
     "channel_width": "40MHz", "protocol": "Wi-Fi 6 (5G)",
     "rssi_dbm": -63, "snr_db": 28, "data_rate_mbps": 574, "quality_score": 62, "quality_label": "Good",
     "tx_power_dbm": 16, "spatial_streams": 2, "mcs_index": 8,
     "state": "Run", "vlan": 100, "bytes_tx": 73400320, "bytes_rx": 209715200,
     "data_retries": 67, "session_duration_sec": 5400, "roam_count": 2},
    {"mac": "AA:BB:CC:11:22:07", "ip": "10.10.6.12", "username": "", "hostname": "IoT-TempSensor-03",
     "device_type": "IoT Sensor", "os_type": "Embedded",
     "ap_name": "AP-FL3-LAB", "ssid": "IoT-Sensors", "band": "2.4 GHz", "channel": 1,
     "channel_width": "20MHz", "protocol": "Wi-Fi 4",
     "rssi_dbm": -65, "snr_db": 22, "data_rate_mbps": 54, "quality_score": 47, "quality_label": "Fair",
     "tx_power_dbm": 10, "spatial_streams": 1, "mcs_index": 5,
     "state": "Run", "vlan": 300, "bytes_tx": 1048576, "bytes_rx": 524288,
     "data_retries": 34, "session_duration_sec": 86400, "roam_count": 0},
    {"mac": "AA:BB:CC:11:22:08", "ip": "10.10.5.47", "username": "kzineb", "hostname": "ThinkPad-KZ",
     "device_type": "Laptop", "os_type": "Linux",
     "ap_name": "AP-OUTDOOR-N", "ssid": "CorpNet", "band": "5 GHz", "channel": 100,
     "channel_width": "40MHz", "protocol": "Wi-Fi 6 (5G)",
     "rssi_dbm": -74, "snr_db": 15, "data_rate_mbps": 287, "quality_score": 30, "quality_label": "Poor",
     "tx_power_dbm": 14, "spatial_streams": 2, "mcs_index": 6,
     "state": "Run", "vlan": 100, "bytes_tx": 41943040, "bytes_rx": 125829120,
     "data_retries": 340, "session_duration_sec": 900, "roam_count": 7},
]


class DemoClient:
    """Provides demo data mimicking the C9800RestconfClient interface."""

    def health_check(self):
        return {"status": "demo", "code": 200, "timestamp": datetime.now().isoformat()}

    def get_system_info(self):
        return {"hostname": "WLC-C9800-DC1", "version": "17.9.5",
                "timestamp": datetime.now().isoformat()}

    def get_cpu_usage(self):
        return {"five_seconds": _rand(8, 35), "one_minute": _rand(10, 30),
                "five_minutes": _rand(12, 28)}

    def get_memory_usage(self):
        u1 = _rand(6000, 9500)
        u2 = _rand(2000, 4000)
        return {"pools": [
            {"name": "Processor", "total_mb": 16384, "used_mb": u1,
             "free_mb": 16384 - u1, "used_percent": round(u1 / 163.84, 1)},
            {"name": "lsmpi_io", "total_mb": 8192, "used_mb": u2,
             "free_mb": 8192 - u2, "used_percent": round(u2 / 81.92, 1)},
        ]}

    def get_ap_summary(self):
        return {"total_aps": len(DEMO_APS), "aps": DEMO_APS}

    def get_ap_detail(self, mac):
        for a in DEMO_APS:
            if a["mac"] == mac: return a
        return {"error": "AP not found"}

    def get_client_summary(self):
        c2 = _rand(40, 70)
        c5 = _rand(160, 220)
        c6 = _rand(30, 60)
        return {"total_clients": c2 + c5 + c6, "clients_2ghz": c2,
                "clients_5ghz": c5, "clients_6ghz": c6}

    def get_client_details(self):
        return {"total": len(DEMO_CLIENTS), "clients": DEMO_CLIENTS}

    def search_clients(self, query):
        q = query.lower().strip()
        m = [c for c in DEMO_CLIENTS
             if q in c["mac"].lower() or q in c["ip"].lower()
             or q in c["username"].lower() or q in c["hostname"].lower()
             or q in c["ap_name"].lower() or q in c["ssid"].lower()]
        return {"query": query, "total": len(m), "clients": m}

    def get_client_detail(self, mac):
        for c in DEMO_CLIENTS:
            if c["mac"].lower() == mac.lower(): return c
        return {"error": "Client not found"}

    def get_client_stats(self):
        cl = DEMO_CLIENTS
        t = len(cl)
        dist = {"Excellent": 0, "Good": 0, "Fair": 0, "Poor": 0, "Critical": 0}
        bands, protos = {}, {}
        for c in cl:
            dist[c["quality_label"]] += 1
            bands[c["band"]] = bands.get(c["band"], 0) + 1
            protos[c["protocol"]] = protos.get(c["protocol"], 0) + 1
        rssi = [c["rssi_dbm"] for c in cl]
        snr = [c["snr_db"] for c in cl]
        scores = [c["quality_score"] for c in cl]
        return {"total_clients": t,
                "avg_rssi_dbm": round(sum(rssi) / t, 1),
                "avg_snr_db": round(sum(snr) / t, 1),
                "avg_quality_score": round(sum(scores) / t, 1),
                "quality_distribution": dist, "band_distribution": bands,
                "protocol_distribution": protos,
                "worst_clients": sorted(cl, key=lambda x: x["quality_score"])[:10]}

    def get_wlan_list(self):
        return {"total_wlans": len(DEMO_WLANS), "wlans": DEMO_WLANS}

    def get_rf_data(self):
        return {"status": "demo", "message": "RF data available in live mode"}

    def get_rf_analysis(self):
        # No simulated RF telemetry — real RRM data only (live mode).
        return {"summary": {"critical": 0, "high": 0, "medium": 0, "affected_aps": 0},
                "conflicts": [], "neighbor_aware": True, "radios": []}

    def get_ap_addresses(self):
        return []

    def get_ap_lifecycle(self):
        return []

    def get_rogues(self):
        return {"rogue_aps": [], "rogue_clients": []}

    def get_awips(self):
        return {"alarms": []}

    def get_interfaces(self):
        return {"interfaces": [
            {"name": "GigabitEthernet0/0/0", "type": "iana-if-type:ethernetCsmacd", "enabled": True, "oper_status": "up"},
            {"name": "GigabitEthernet0/0/1", "type": "iana-if-type:ethernetCsmacd", "enabled": True, "oper_status": "up"},
            {"name": "Loopback0", "type": "iana-if-type:softwareLoopback", "enabled": True, "oper_status": "up"},
            {"name": "Vlan100", "type": "iana-if-type:l3ipvlan", "enabled": True, "oper_status": "up"},
        ]}

    def get_dashboard(self):
        return {"system": self.get_system_info(), "cpu": self.get_cpu_usage(),
                "memory": self.get_memory_usage(), "aps": self.get_ap_summary(),
                "clients": self.get_client_summary(), "wlans": self.get_wlan_list(),
                "health": self.health_check()}
