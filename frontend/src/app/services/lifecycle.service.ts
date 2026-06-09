import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface LcAp {
  name: string; mac: string; model: string; sw_version: string;
  state: string; boot_time: string; join_time: string; uptime_sec: number;
  compliant: boolean; reboot_count: number; flap_count: number;
}
export interface LifecycleData {
  target: string;
  summary: { total: number; compliant: number; noncompliant: number };
  by_version: { version: string; count: number }[];
  aps: LcAp[];
}

@Injectable({ providedIn: 'root' })
export class LifecycleService {
  private api = '/api/lifecycle';
  constructor(private http: HttpClient) {}

  get(): Observable<LifecycleData> { return this.http.get<LifecycleData>(this.api); }
  setTarget(target: string): Observable<{ target: string }> {
    return this.http.put<{ target: string }>(`${this.api}/target`, { target });
  }
}
