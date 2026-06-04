import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface WlcSettings {
  host: string;
  port: number;
  username: string;
  verify_ssl: boolean;
  source?: 'config' | 'mongo';
  password_set?: boolean;
  updated_at?: string;
  updated_by?: string;
}

export interface WlcSettingsPayload {
  host: string;
  port: number;
  username: string;
  password?: string;       // optional — empty means "keep current"
  verify_ssl: boolean;
}

export interface ConnectionTestResult {
  ok: boolean;
  status?: string;
  code?: number;
  error?: string;
  tested_host: string;
  tested_port: number;
}

export interface DemoModeStatus {
  demo_mode: boolean;
  env_default: boolean;
  override: boolean | null;
  source: 'override' | 'env';
}

export interface SetupStatus {
  setup_complete: boolean;
  demo_mode: boolean;
  user_count: number;
}

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private api = '/api/settings';

  constructor(private http: HttpClient) {}

  getWlc(): Observable<WlcSettings> {
    return this.http.get<WlcSettings>(`${this.api}/wlc`);
  }

  updateWlc(payload: WlcSettingsPayload): Observable<WlcSettings> {
    return this.http.put<WlcSettings>(`${this.api}/wlc`, payload);
  }

  testWlc(payload: Partial<WlcSettingsPayload>): Observable<ConnectionTestResult> {
    return this.http.post<ConnectionTestResult>(`${this.api}/wlc/test`, payload);
  }

  getDemoMode(): Observable<DemoModeStatus> {
    return this.http.get<DemoModeStatus>(`${this.api}/demo-mode`);
  }

  setDemoMode(enabled: boolean): Observable<{ demo_mode: boolean; updated_at?: string; updated_by?: string }> {
    return this.http.put<any>(`${this.api}/demo-mode`, { enabled });
  }

  resetDemoMode(): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(`${this.api}/demo-mode`);
  }

  getSetupStatus(): Observable<SetupStatus> {
    return this.http.get<SetupStatus>('/api/setup/status');
  }
}
