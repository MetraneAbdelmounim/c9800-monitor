import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, expand, reduce, EMPTY } from 'rxjs';
import * as M from '../models/models';

@Injectable({ providedIn: 'root' })
export class WlcService {
  private api = '/api';
  constructor(private http: HttpClient) {}
  getHealth(): Observable<M.HealthCheck> { return this.http.get<M.HealthCheck>(this.api + '/health'); }
  getDashboard(): Observable<M.Dashboard> { return this.http.get<M.Dashboard>(this.api + '/dashboard'); }
  getSystemInfo(): Observable<M.SystemInfo> { return this.http.get<M.SystemInfo>(this.api + '/system'); }
  getCpu(): Observable<M.CpuUsage> { return this.http.get<M.CpuUsage>(this.api + '/cpu'); }
  getMemory(): Observable<M.MemoryUsage> { return this.http.get<M.MemoryUsage>(this.api + '/memory'); }
  getAps(page = 1, perPage = 50): Observable<M.ApSummary> {
    return this.http.get<M.ApSummary>(`${this.api}/aps?page=${page}&per_page=${perPage}`);
  }

  /** Fetch every AP across all backend pages (uses per_page=200 max). */
  getAllAps(): Observable<M.AccessPoint[]> {
    const per = 200;
    return this.getAps(1, per).pipe(
      expand(res => (res.page < res.total_pages) ? this.getAps(res.page + 1, per) : EMPTY),
      reduce<M.ApSummary, M.AccessPoint[]>((acc, res) => acc.concat(res.aps || []), []),
    );
  }
  getClientSummary(): Observable<M.ClientSummary> { return this.http.get<M.ClientSummary>(this.api + '/clients'); }
  getClientDetails(): Observable<M.ClientDetails> { return this.http.get<M.ClientDetails>(this.api + '/clients/detail'); }
  searchClients(q: string): Observable<{query:string;total:number;clients:M.WirelessClient[]}> {
    return this.http.get<any>(this.api + '/clients/search?q=' + encodeURIComponent(q));
  }
  getClientDetail(mac: string): Observable<M.WirelessClient> {
    return this.http.get<M.WirelessClient>(this.api + '/clients/' + encodeURIComponent(mac));
  }
  getClientStats(): Observable<M.ClientStats> { return this.http.get<M.ClientStats>(this.api + '/clients/stats'); }
  getWlans(): Observable<M.WlanList> { return this.http.get<M.WlanList>(this.api + '/wlans'); }
  getRf(): Observable<any> { return this.http.get<any>(this.api + '/rf'); }
  getRfAnalysis(): Observable<M.RfAnalysis> { return this.http.get<M.RfAnalysis>(this.api + '/rf/analysis'); }
  getInterfaces(): Observable<M.InterfaceList> { return this.http.get<M.InterfaceList>(this.api + '/interfaces'); }
}



