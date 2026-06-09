import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";

export interface TrackedClient {
  mac: string; hostname: string; username: string; ip: string;
  ap_name: string; ssid: string; band: string;
  rssi_dbm: number; quality_score: number;
  last_seen: string; first_seen: string; snapshot_count: number;
}

export interface TimelinePoint {
  timestamp: string; rssi_dbm: number; snr_db: number;
  quality_score: number; quality_label: string;
  data_rate_mbps: number; ap_name: string; ssid: string;
  band: string; channel: number; bytes_tx: number;
  bytes_rx: number; data_retries: number;
  mcs_index: number; spatial_streams: number; ip: string;
}

export interface RoamEvent {
  mac: string; timestamp: string;
  from_ap: string; to_ap: string;
  ssid: string; band: string; channel: number;
  rssi_after: number; snr_after: number; quality_after: number;
}

export interface ClientSummary {
  mac: string; range: string; count: number;
  avg_rssi: number; min_rssi: number; max_rssi: number;
  avg_snr: number; min_snr: number; max_snr: number;
  avg_quality: number; min_quality: number; max_quality: number;
  avg_rate: number; max_rate: number;
  total_retries: number; roam_count: number;
  aps_used: string[]; ssids_used: string[];
  bands_used: string[]; channels_used: number[];
  first_seen: string; last_seen: string;
}

export interface CollectorStatus {
  snapshots: number; roaming_events: number; last_collection: string | null;
}

export interface GraphNode {
  id: string; type: string; label: string;
  client_count: number; roam_count: number; quality_avg: number;
}

export interface GraphLink {
  source: string; target: string; count: number;
  mac: string | null; avg_quality: number; last_rssi: number;
}

export interface GraphData {
  nodes: GraphNode[]; links: GraphLink[];
}

@Injectable({ providedIn: "root" })
export class TrackingService {
  private api = "/api/tracking";

  constructor(private http: HttpClient) {}

  getStatus(): Observable<CollectorStatus> {
    return this.http.get<CollectorStatus>(`${this.api}/status`);
  }

  getTrackedClients(): Observable<TrackedClient[]> {
    return this.http.get<TrackedClient[]>(`${this.api}/clients`);
  }

  getTimeline(mac: string, range: string): Observable<{ mac: string; range: string; count: number; timeline: TimelinePoint[] }> {
    return this.http.get<any>(`${this.api}/client/${mac}/timeline?range=${range}`);
  }

  getRoaming(mac: string, range: string): Observable<{ mac: string; range: string; count: number; events: RoamEvent[] }> {
    return this.http.get<any>(`${this.api}/client/${mac}/roaming?range=${range}`);
  }

  getSummary(mac: string, range: string): Observable<ClientSummary> {
    return this.http.get<ClientSummary>(`${this.api}/client/${mac}/summary?range=${range}`);
  }

  getAllRoaming(range: string): Observable<{ range: string; count: number; events: RoamEvent[] }> {
    return this.http.get<any>(`${this.api}/roaming?range=${range}`);
  }

  getApLoad(apName: string, range: string): Observable<any> {
    return this.http.get<any>(`${this.api}/ap/${encodeURIComponent(apName)}/load?range=${range}`);
  }

  getRoamingGraph(range: string, mac?: string): Observable<GraphData> {
    let url = `${this.api}/roaming/graph?range=${range}`;
    if (mac) url += `&mac=${encodeURIComponent(mac)}`;
    return this.http.get<GraphData>(url);
  }

  getTrends(range: string): Observable<any> {
    return this.http.get<any>(`${this.api}/trends?range=${range}`);
  }
}