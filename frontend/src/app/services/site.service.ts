import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Site, SiteList } from '../models/models';

export interface SiteTestResult {
  ok: boolean; status?: string; code?: number; error?: string;
  tested_host?: string; tested_port?: number;
}

export interface SitePayload {
  name?: string; location?: string; host?: string; port?: number;
  username?: string; password?: string; verify_ssl?: boolean; enabled?: boolean; id?: string;
}

@Injectable({ providedIn: 'root' })
export class SiteService {
  private http = inject(HttpClient);
  private api = '/api/sites';

  list(): Observable<SiteList> { return this.http.get<SiteList>(this.api); }
  create(p: SitePayload): Observable<Site> { return this.http.post<Site>(this.api, p); }
  update(id: string, p: SitePayload): Observable<Site> { return this.http.put<Site>(`${this.api}/${id}`, p); }
  remove(id: string): Observable<{ ok: boolean }> { return this.http.delete<{ ok: boolean }>(`${this.api}/${id}`); }
  test(p: SitePayload): Observable<SiteTestResult> { return this.http.post<SiteTestResult>(`${this.api}/test`, p); }
}
