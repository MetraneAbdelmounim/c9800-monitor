import { Component, OnInit, computed, effect, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WlcService } from '../../services/wlc.service';
import { Wlan } from '../../models/models';
import { PaginatorComponent } from '../paginator/paginator.component';
import { SpinnerComponent } from '../spinner/spinner.component';

type SortKey = keyof Pick<Wlan,
  'wlan_id' | 'profile_name' | 'ssid' | 'status' | 'band_str' | 'security' | 'policy_tag'>;
type SortDir = 'asc' | 'desc';

@Component({
  selector: 'app-wlan-list',
  standalone: true,
  imports: [CommonModule, FormsModule, PaginatorComponent, SpinnerComponent],
  templateUrl: './wlan-list.component.html',
  styleUrl: './wlan-list.component.css',
})
export class WlanListComponent implements OnInit {
  private all = signal<Wlan[]>([]);
  total = signal(0);
  loading = signal(true);
  error = signal<string | null>(null);

  search = signal('');
  filterStatus = signal('');
  filterSecurity = signal('');
  filterBand = signal('');

  sortKey = signal<SortKey>('wlan_id');
  sortDir = signal<SortDir>('asc');

  page = signal(1);
  pageSize = signal(25);

  readonly statusOptions   = computed(() => this.distinct(w => w.status));
  readonly securityOptions = computed(() => this.distinct(w => w.security));
  readonly bandOptions     = computed(() => this.distinct(w => w.band_str));

  readonly filtered = computed<Wlan[]>(() => {
    const q = this.search().trim().toLowerCase();
    const fs = this.filterStatus();
    const fsec = this.filterSecurity();
    const fb = this.filterBand();

    const list = this.all().filter(w => {
      if (fs && w.status !== fs) return false;
      if (fsec && w.security !== fsec) return false;
      if (fb && w.band_str !== fb) return false;
      if (!q) return true;
      return (
        w.profile_name?.toLowerCase().includes(q) ||
        w.ssid?.toLowerCase().includes(q) ||
        w.policy_profile?.toLowerCase().includes(q) ||
        w.policy_tag?.toLowerCase().includes(q) ||
        String(w.wlan_id).includes(q)
      );
    });

    const key = this.sortKey();
    const dir = this.sortDir() === 'asc' ? 1 : -1;
    return list.sort((a, b) => {
      const va: any = a[key] ?? '';
      const vb: any = b[key] ?? '';
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  });

  readonly paged = computed<Wlan[]>(() => {
    const list = this.filtered();
    const p = this.page(), s = this.pageSize();
    return list.slice((p - 1) * s, p * s);
  });

  constructor(private wlc: WlcService) {
    effect(() => {
      this.search(); this.filterStatus(); this.filterSecurity(); this.filterBand();
      this.page.set(1);
    });
  }

  ngOnInit() { this.load(); }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.wlc.getWlans().subscribe({
      next: d => {
        this.all.set(d.wlans || []);
        this.total.set(d.total_wlans || 0);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(err?.error?.error || 'Failed to load WLANs');
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
    this.filterStatus.set('');
    this.filterSecurity.set('');
    this.filterBand.set('');
  }

  statusClass(s: string): string {
    return (s || '').toLowerCase() === 'enabled' ? 'up' : 'down';
  }

  trackById = (_: number, w: Wlan) => w.wlan_id;

  private distinct(pick: (w: Wlan) => string): string[] {
    const set = new Set<string>();
    for (const w of this.all()) {
      const v = (pick(w) || '').trim();
      if (v) set.add(v);
    }
    return [...set].sort();
  }
}
