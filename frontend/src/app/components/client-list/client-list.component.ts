import { Component, OnInit, computed, effect, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WlcService } from '../../services/wlc.service';
import { WirelessClient } from '../../models/models';
import { PaginatorComponent } from '../paginator/paginator.component';
import { SpinnerComponent } from '../spinner/spinner.component';
import { ChartComponent } from '../chart/chart.component';

const QUALITY = [
  ['Excellent', '#34C759'], ['Good', '#5A9BD5'], ['Fair', '#E8A838'],
  ['Poor', '#E07830'], ['Critical', '#C8102E'],
];
const BAND_COLOR: Record<string, string> = {
  '2.4 GHz': '#E8A838', '5 GHz': '#5A9BD5', '6 GHz': '#9B72CF',
};

type SortKey = keyof Pick<WirelessClient,
  'hostname' | 'mac' | 'ip' | 'username' | 'ap_name' | 'ssid' | 'band'
  | 'protocol' | 'rssi_dbm' | 'snr_db' | 'quality_score' | 'data_rate_mbps' | 'state'>;
type SortDir = 'asc' | 'desc';

@Component({
  selector: 'app-client-list',
  standalone: true,
  imports: [CommonModule, FormsModule, PaginatorComponent, SpinnerComponent, ChartComponent],
  templateUrl: './client-list.component.html',
  styleUrl: './client-list.component.css',
})
export class ClientListComponent implements OnInit {
  private all = signal<WirelessClient[]>([]);
  total = signal(0);
  loading = signal(true);
  error = signal<string | null>(null);

  // List ⇄ Charts view toggle
  view = signal<'list' | 'charts'>('list');

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

  // ── Chart data (reacts to the same filters as the table) ──
  readonly barOptions = { indexAxis: 'y', plugins: { legend: { display: false } } };

  readonly qualityData = computed(() => {
    const counts = QUALITY.map(([label]) =>
      this.filtered().filter(c => c.quality_label === label).length);
    return {
      labels: QUALITY.map(q => q[0]),
      datasets: [{ data: counts, backgroundColor: QUALITY.map(q => q[1]), borderWidth: 0 }],
    };
  });

  readonly bandData = computed(() => {
    const map = this.countBy(c => c.band || 'Unknown');
    const labels = [...map.keys()];
    return {
      labels,
      datasets: [{
        data: labels.map(l => map.get(l)),
        backgroundColor: labels.map(l => BAND_COLOR[l] || '#706868'), borderWidth: 0,
      }],
    };
  });

  readonly snrData = computed(() => {
    const buckets = ['0–10', '10–15', '15–20', '20–25', '25–30', '30+'];
    const counts = [0, 0, 0, 0, 0, 0];
    for (const c of this.filtered()) {
      const s = c.snr_db || 0;
      const i = s >= 30 ? 5 : s >= 25 ? 4 : s >= 20 ? 3 : s >= 15 ? 2 : s >= 10 ? 1 : 0;
      counts[i]++;
    }
    return { labels: buckets, datasets: [{ label: 'Clients', data: counts, backgroundColor: '#5A9BD5', borderRadius: 4 }] };
  });

  readonly ssidData = computed(() => this.topBar(c => c.ssid, 8, '#3E6BB0'));
  readonly apData = computed(() => this.topBar(c => c.ap_name, 10, '#9B72CF'));

  constructor(private wlc: WlcService) {
    effect(() => {
      this.search(); this.filterBand(); this.filterProtocol();
      this.filterSsid(); this.filterQuality();
      this.page.set(1);
    });
  }

  private countBy(pick: (c: WirelessClient) => string): Map<string, number> {
    const m = new Map<string, number>();
    for (const c of this.filtered()) {
      const k = (pick(c) || '').trim();
      if (k) m.set(k, (m.get(k) || 0) + 1);
    }
    return m;
  }

  private topBar(pick: (c: WirelessClient) => string, n: number, color: string) {
    const sorted = [...this.countBy(pick).entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
    return {
      labels: sorted.map(e => e[0]),
      datasets: [{ label: 'Clients', data: sorted.map(e => e[1]), backgroundColor: color, borderRadius: 4 }],
    };
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
