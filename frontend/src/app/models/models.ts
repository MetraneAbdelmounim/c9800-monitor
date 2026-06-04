// ── System / Resources ─────────────────────────────────
export interface SystemInfo {
  hostname: string;
  version: string;
  timestamp: string;
}

export interface CpuUsage {
  five_seconds: number;
  one_minute: number;
  five_minutes: number;
}

export interface MemoryPool {
  name: string;
  total_mb: number;
  used_mb: number;
  free_mb: number;
  used_percent: number;
}
export interface MemoryUsage { pools: MemoryPool[]; }

// ── Access Points (matches restconf_client.get_ap_summary) ─
export interface AccessPoint {
  name: string;
  wtp_mac: string;
  mac: string;
  ip: string;
  model: string;
  serial: string;
  location: string;
  sw_version: string;
  state: string;
  admin_state: string;
  mode: string;
  country: string;
  policy_tag: string;
  site_tag: string;
  rf_tag: string;
  max_clients: number;
  uptime_sec: number;
  join_time: string;
}
export interface ApSummary {
  total_aps: number;
  page: number;
  per_page: number;
  total_pages: number;
  aps: AccessPoint[];
}

// ── Clients ────────────────────────────────────────────
export interface ClientSummary {
  total_clients: number;
  run_state: number;
  auth_state: number;
  iplearn_state: number;
  webauth_state: number;
  random_mac_clients: number;
  clients_2ghz: number;
  clients_5ghz: number;
  clients_6ghz: number;
}

export interface WirelessClient {
  mac: string;
  ip: string;
  username: string;
  hostname: string;
  device_type: string;
  os_type: string;
  ap_name: string;
  ssid: string;
  wlan_profile: string;
  band: string;
  channel: number;
  channel_width: string;
  protocol: string;
  rssi_dbm: number;
  snr_db: number;
  quality_score: number;
  quality_label: string;
  data_rate_mbps: number;
  tx_power_dbm: number;
  spatial_streams: number;
  mcs_index: number;
  state: string;
  vlan: number;
  bytes_tx: number;
  bytes_rx: number;
  pkts_tx: number;
  pkts_rx: number;
  data_retries: number;
  tx_drops: number;
  session_duration_sec: number;
  roam_count: number;
  security: string;
  auth_key_mgmt: string;
  assoc_time: string;
  bssid: string;
  policy_profile: string;
  is_active: boolean;
}
export interface ClientDetails {
  total: number;
  page?: number;
  per_page?: number;
  total_pages?: number;
  clients: WirelessClient[];
  error?: string;
}

export interface ClientStats {
  total_clients: number;
  avg_rssi_dbm: number;
  avg_snr_db: number;
  avg_quality_score: number;
  quality_distribution: { [key: string]: number };
  band_distribution: { [key: string]: number };
  protocol_distribution: { [key: string]: number };
  worst_clients: WirelessClient[];
}

// ── WLANs ──────────────────────────────────────────────
export interface Wlan {
  profile_name: string;
  wlan_id: number;
  ssid: string;
  status: string;
  bands: string[];
  band_str: string;
  security: string;
  policy_profile: string;
  policy_tag: string;
}
export interface WlanList { total_wlans: number; wlans: Wlan[]; }

// ── Interfaces ─────────────────────────────────────────
export interface NetInterface {
  name: string;
  type: string;
  admin_status: string;
  oper_status: string;
  ipv4: string;
  subnet_mask: string;
  mac: string;
  speed_mbps: number;
  mtu: number;
  description: string;
  last_change: string;
  rx_kbps: number;
  tx_kbps: number;
  in_errors: number;
  out_errors: number;
}
export interface InterfaceList { interfaces: NetInterface[]; }

// ── Health / Dashboard ─────────────────────────────────
export interface HealthCheck {
  status: string;
  code?: number;
  timestamp: string;
  error?: string;
}

export interface Dashboard {
  system: SystemInfo;
  cpu: CpuUsage;
  memory: MemoryUsage;
  aps: { total_aps: number };
  clients: ClientSummary;
  wlans: WlanList;
  health: HealthCheck;
}

// ── AP Floor Map ───────────────────────────────────────
export interface FloorSummary {
  id: string;
  name: string;
  building: string;
  order: number;
  updated_at?: string;
}
export interface Floor extends FloorSummary {
  image: string;   // base64 data URL of the floor plan
}
export interface ApPlacement {
  ap_mac: string;  // matches AccessPoint.wtp_mac
  ap_name: string;
  x: number;       // 0-100 % of image width
  y: number;       // 0-100 % of image height
}

// ── RF / Channel conflicts ─────────────────────────────
export interface RfRadio {
  ap_name: string;
  mac: string;
  slot: number;
  band: string;
  channel: number;
  width: string;
  utilization: number;   // %
  noise_dbm: number;
  interference: number;  // %
  tx_level: number;      // 1-8 (1 = highest)
  tx_dbm?: number;
  clients: number;
}
export interface RfNeighbor {
  ap_name: string;
  mac: string;
  slot: number;
  channel: number;
  rssi: number;          // how the focal AP hears this neighbor
  utilization: number;
  noise_dbm: number;
}
export interface RfConflict {
  type: 'co-channel' | 'adjacent';
  band: string;
  channel: number;
  severity: 'critical' | 'high' | 'medium';
  ap_count: number;
  neighbor_count: number;
  rssi?: number;            // strongest neighbor RSSI
  title: string;
  detail: string;
  focal: RfRadio;
  neighbors: RfNeighbor[];
}
export interface RfAnalysis {
  summary: { critical: number; high: number; medium: number; affected_aps: number };
  conflicts: RfConflict[];
  radios: RfRadio[];
}
