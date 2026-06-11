import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, tap } from 'rxjs';

export interface LicenseInfo {
  valid: boolean;
  customer?: string;
  edition?: string;
  expires?: string;
  days_left?: number;
  machine_bound?: boolean;
  error?: string;
}

@Injectable({ providedIn: 'root' })
export class LicenseService {
  private http = inject(HttpClient);
  private api = '/api/license';

  /** Cached status (null until first fetched). */
  readonly info = signal<LicenseInfo | null>(null);

  /** Fetch status; cached unless `force`. */
  status(force = false): Observable<LicenseInfo> {
    const cached = this.info();
    if (cached && !force) return of(cached);
    return this.http.get<LicenseInfo>(this.api).pipe(tap(i => this.info.set(i)));
  }

  /** Activate / upload a license token (admin only). */
  activate(key: string): Observable<LicenseInfo> {
    return this.http.post<LicenseInfo>(this.api, { key }).pipe(tap(i => this.info.set(i)));
  }

  isValid(): boolean {
    return !!this.info()?.valid;
  }

  clear(): void {
    this.info.set(null);
  }
}