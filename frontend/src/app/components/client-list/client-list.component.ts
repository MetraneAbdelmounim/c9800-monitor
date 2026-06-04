import { Component, OnInit, computed, effect, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WlcService } from '../../services/wlc.service';
import { WirelessClient } from '../../models/models';
import { PaginatorComponent } from '../paginator/paginator.component';
import { SpinnerComponent } from '../spinner/spinner.component';

type SortKey = keyof Pick<WirelessClient,
  'hostname' | 'mac' | 'ip' | 'username' | 'ap_name' | 'ssid' | 'band'
  | 'protocol' | 'rssi_dbm' | 'snr_db' | 'quality_score' | 'data_rate_mbps' | 'state'>;
type SortDir = 'asc' | 'desc';

@Component({
  selector: 'app-client-list',
  standalone: true,
  imports: [CommonModule, FormsModule, PaginatorComponent, SpinnerComponent],
  templateUrl: './client-list.component.html',
  styleUrl: './client-list.component.css',
})
export class ClientListComponent implements OnInit {
  private all = signal<WirelessClient[]>([]);
  total = signal(0);
  loading = signal(true);
  error = signal<string | null>(null);

  // Filters
  search = signal('');
  filterBand = signal('');
  filterProtocol = signal('');
  filterSsid = signal('');
  filterQuality = signal('');  // 'Excellent' | 'Good' | 'Fair' | 'Poor' | 'Critical' | ''

  // Sort
  sortKey = signal<SortKey>('quality_score');
  sortDir = signal<SortDir>('desc');

  // Pagination
  page = signal(1);
  pageSize = signal(25);

  // Dropdown options
  readonly bandOptions     = computed(() => this.distinct(c => c.band));
  readonly protocolOptions = computed(() => this.distinct(c => c.protocol));
  readonly ssidOptions     = computed(() => this.distinct(c => c.ssid));
  readonly qualityOptions = ['Excellent', 'Good', 'Fair', 'Poor', 'Critical'];

  readonly filtered = computed<WirelessClient[]>(() => {
    const q = this.search().trim().toLowerCase();
    const fb = this.filterBand();
    const fp = this.filterProtocol();
    const fs = this.filterSsid();
    const fq = this.filterQuality();

    const list = this.all().filter(c => {
      if (fb && c.band !== fb) return false;
      if (fp && c.protocol !== fp) return false;
      if (fs && c.ssid !== fs) return false;
      if (fq && c.quality_label !== fq) return false;
      if (!q) return true;
      return (
        c.mac?.toLowerCase().includes(q) ||
        c.ip?.toLowerCase().includes(q) ||
        c.hostname?.toLowerCase().includes(q) ||
        c.username?.toLowerCase().includes(q) ||
        c.ap_name?.toLowerCase().includes(q) ||
        c.ssid?.toLowerCase().includes(q) ||
        c.bssid?.toLowerCase().includes(q)
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

  readonly paged = computed<WirelessClient[]>(() => {
    const list = this.filtered();
    const p = this.page(), s = this.pageSize();
    return list.slice((p - 1) * s, p * s);
  });

  constructor(private wlc: WlcService) {
    effect(() => {
      this.search(); this.filterBand(); this.filterProtocol();
      this.filterSsid(); this.filterQuality();
      this.page.set(1);
    });
  }

  ngOnInit() { this.load(); }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.wlc.getClientDetails().subscribe({
      next: d => {
        this.all.set(d.clients || []);
        this.total.set(d.total || 0);
        this.loading.set(false);
      },
      error: err => {
        this.error.set(err?.error?.error || 'Failed to load clients');
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
    this.filterBand.set('');
    this.filterProtocol.set('');
    this.filterSsid.set('');
    this.filterQuality.set('');
  }

  rssiColor(r: number): string {
    if (!r) return '#706868';
    if (r >= -55) return '#34C759';
    if (r >= -67) return '#5A9BD5';
    if (r >= -72) return '#E8A838';
    return '#C8102E';
  }

  snrColor(s: number): string {
    if (!s) return '#706868';
    if (s > 25) return '#34C759';
    if (s > 15) return '#E8A838';
    return '#C8102E';
  }

  qualColor(s: number): string {
    if (s >= 80) return '#34C759';
    if (s >= 60) return '#5A9BD5';
    if (s >= 40) return '#E8A838';
    if (s >= 20) return '#E07830';
    return '#C8102E';
  }

  bandClass(b: string): string {
    if (b?.includes('6')) return 'band-6';
    if (b?.includes('5')) return 'band-5';
    if (b?.includes('2')) return 'band-24';
    return '';
  }

  trackByMac = (_: number, c: WirelessClient) => c.mac;

  private distinct(pick: (c: WirelessClient) => string): string[] {
    const set = new Set<string>();
    for (const c of this.all()) {
      const v = (pick(c) || '').trim();
      if (v) set.add(v);
    }
    return [...set].sort();
  }
}
