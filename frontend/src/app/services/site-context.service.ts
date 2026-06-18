import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { Site, SiteList } from '../models/models';

const KEY = 'wlc.site';

/**
 * Holds the user's currently-selected site. The site interceptor appends
 * `?site=<id>` to data requests so every view is scoped to it.
 */
@Injectable({ providedIn: 'root' })
export class SiteContextService {
  private http = inject(HttpClient);

  readonly sites = signal<Site[]>([]);
  readonly currentId = signal<string | null>(localStorage.getItem(KEY));
  readonly current = computed(() => this.sites().find(s => s.id === this.currentId()) || null);

  private _loaded = false;
  get loaded() { return this._loaded; }

  /** Load the (enabled) sites and validate the current selection. */
  load(): Observable<SiteList> {
    return this.http.get<SiteList>('/api/sites').pipe(tap(r => {
      const enabled = (r.sites || []).filter(s => s.enabled);
      this.sites.set(enabled);
      this._loaded = true;
      const cur = this.currentId();
      if (!cur || !enabled.some(s => s.id === cur)) {
        this.setSite(enabled.length ? enabled[0].id : null);
      }
    }));
  }

  setSite(id: string | null) {
    this.currentId.set(id);
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  }
}
