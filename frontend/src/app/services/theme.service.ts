import { Injectable, signal } from '@angular/core';

export type Theme = 'dark' | 'light';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly key = 'asb-theme';
  readonly theme = signal<Theme>(this.initial());

  constructor() { this.apply(this.theme()); }

  private initial(): Theme {
    try {
      return localStorage.getItem(this.key) === 'light' ? 'light' : 'dark';
    } catch {
      return 'dark';
    }
  }

  private apply(t: Theme) {
    document.documentElement.setAttribute('data-theme', t);
  }

  set(t: Theme) {
    this.theme.set(t);
    try { localStorage.setItem(this.key, t); } catch { /* ignore */ }
    this.apply(t);
  }

  toggle() {
    this.set(this.theme() === 'dark' ? 'light' : 'dark');
  }
}
