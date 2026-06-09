import { Component, OnInit, computed, effect, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WlcService } from '../../services/wlc.service';
import { AccessPoint } from '../../models/models';
import { PaginatorComponent } from '../paginator/paginator.component';
import { SpinnerComponent } from '../spinner/spinner.component';

type SortKey = keyof Pick<AccessPoint,
  'name' | 'model' | 'ip' | 'state' | 'mode' | 'location' | 'sw_version' | 'uptime_sec' | 'max_clients'>;
type SortDir = 'asc' | 'desc';

@Component({
  selector: 'app-ap-list',
  standalone: true,
  imports: [CommonModule, FormsModule, PaginatorComponent, SpinnerComponent],
  templateUrl: './ap-list.component.html',
  styleUrl: './ap-list.component.css',
})
export class ApListComponent implements OnInit {
  // Raw data
  private all = signal<AccessPoint[]>([]);
  totalRegistered = signal(0);
  loading = signal(true);
  error = signal<string | null>(null);

  // Filters
  search = signal('');
  filterState = signal<string>('');     // '' = all
  filterMode = signal<string>('');
  filterModel = signal<string>('');

  // Sort
  sortKey = signal<SortKey>('name');
  sortDir = signal<SortDir>('asc');

  // Pagination
  page = signal(1);
  pageSize = signal(25);

  // Derived option lists for filter dropdowns
  readonly stateOptions = computed(() => this.distinct(a => a.state));
  readonly modeOptions  = computed(() => this.distinct(a => a.mode));
  readonly modelOptions = computed(() => this.distinct(a => a.model));

  // Filtered + sorted view
  readonly filtered = computed<AccessPoint[]>(() => {
    const q = this.search().trim().toLowerCase();
    const fs = this.filterState();
    const fmd = this.filterMode();
    const fml = this.filterModel();

    const list = this.all().filter(ap => {
      if (fs && ap.state !== fs) return false;
      if (fmd && ap.mode !== fmd) return false;
      if (fml && ap.model !== fml) return false;
      if (!q) return true;
      return (
        ap.name?.toLowerCase().includes(q) ||
        ap.ip?.toLowerCase().includes(q) ||
        ap.mac?.toLowerCase().includes(q) ||
        ap.wtp_mac?.toLowerCase().includes(q) ||
        ap.location?.toLowerCase().includes(q) ||
        ap.model?.toLowerCase().includes(q) ||
        ap.serial?.toLowerCase().includes(q)
      );
    });

    const key = this.sortKey();
    const dir = this.sortDir() === 'asc' ? 1 : -1;
    return list.sort((a, b) => {
      const va = a[key] ?? '';
      const vb = b[key] ?? '';
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  });

  // Page slice
  readonly paged = computed<AccessPoint[]>(() => {
    const list = this.filtered();
    const p = this.page(), s = this.pageSize();
    return list.slice((p - 1) * s, p * s);
  });

  constructor(private wlc: WlcService) {
    // Reset to page 1 whenever filters change
    effect(() => {
      this.search(); this.filterState(); this.filterMode(); this.filterModel();
      this.page.set(1);
    });
  }

  ngOnInit() { this.load(); }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.wlc.getAllAps().subscribe({
      next: aps => {
        this.all.set(aps);
        this.totalRegistered.set(aps.length);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(err?.error?.error || 'Failed to load access points');
        this.loading.set(false);
      },
    });
  }

  setSort(key: SortKey) {
    if (this.sortKey() === key) {
      this.sortDir.update(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      this.sortKey.set(key);
      this.sortDir.set('asc');
    }
  }

  sortIndicator(key: SortKey): string {
    if (this.sortKey() !== key) return '';
    return this.sortDir() === 'asc' ? '▲' : '▼';
  }

  clearFilters() {
    this.search.set('');
    this.filterState.set('');
    this.filterMode.set('');
    this.filterModel.set('');
  }

  stateClass(state: string): string {
    const s = (state || '').toLowerCase();
    if (s.includes('registered') || s.includes('run') || s.includes('online') || s.includes('connected')) return 'up';
    if (s.includes('down') || s.includes('disabled') || s.includes('offline') || s.includes('disconnect')) return 'down';
    return 'warn';
  }

  formatUptime(sec: number): string {
    if (!sec || sec <= 0) return '—';
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  trackByMac = (_: number, ap: AccessPoint) => ap.wtp_mac || ap.mac || ap.name;

  private distinct(pick: (a: AccessPoint) => string): string[] {
    const set = new Set<string>();
    for (const ap of this.all()) {
      const v = (pick(ap) || '').trim();
      if (v) set.add(v);
    }
    return [...set].sort();
  }
}
