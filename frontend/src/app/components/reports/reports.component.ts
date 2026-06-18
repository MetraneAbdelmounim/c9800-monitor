import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { WlcService } from '../../services/wlc.service';
import { EventService } from '../../services/event.service';
import { LifecycleService } from '../../services/lifecycle.service';
import { LicenseService } from '../../services/license.service';
import { SiteContextService } from '../../services/site-context.service';
import { ChartComponent } from '../chart/chart.component';
import { SpinnerComponent } from '../spinner/spinner.component';
import * as M from '../../models/models';

const QUALITY = [
  ['Excellent', '#34C759'], ['Good', '#5A9BD5'], ['Fair', '#E8A838'],
  ['Poor', '#E07830'], ['Critical', '#C8102E'],
];
const BAND_COLOR: Record<string, string> = {
  '2.4 GHz': '#E8A838', '5 GHz': '#5A9BD5', '6 GHz': '#9B72CF',
};
const SEVERITY = [
  ['critical', '#C8102E'], ['high', '#E07830'], ['medium', '#E8A838'], ['low', '#5A9BD5'],
];
const TEXT = '#3a4456';   // dark text so charts read on the white report

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, ChartComponent, SpinnerComponent],
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.css',
})
export class ReportsComponent implements OnInit {
  private wlc = inject(WlcService);
  private events = inject(EventService);
  private lifecycleSvc = inject(LifecycleService);
  private license = inject(LicenseService);
  private siteCtx = inject(SiteContextService);

  loading = signal(true);
  error = signal<string | null>(null);
  generatedAt = signal('');

  dash = signal<M.Dashboard | null>(null);
  aps = signal<M.AccessPoint[]>([]);
  stats = signal<M.ClientStats | null>(null);
  advisor = signal<M.AdvisorResult | null>(null);
  eventList = signal<M.EventList | null>(null);
  lifecycle = signal<any | null>(null);

  // Chart option overrides (dark text/legend for the white report surface)
  readonly donutOpts = { plugins: { legend: { labels: { color: TEXT } } } };
  readonly barOpts = {
    indexAxis: 'y', plugins: { legend: { display: false } },
    scales: { x: { ticks: { color: TEXT } }, y: { ticks: { color: TEXT } } },
  };

  ngOnInit() { this.generate(); }

  get customer(): string { return this.license.info()?.customer || ''; }
  get siteName(): string { return this.siteCtx.current()?.name || ''; }
  get siteLocation(): string { return this.siteCtx.current()?.location || ''; }

  generate() {
    this.loading.set(true); this.error.set(null);
    forkJoin({
      dash: this.wlc.getDashboard().pipe(catchError(() => of(null))),
      aps: this.wlc.getAllAps().pipe(catchError(() => of([] as M.AccessPoint[]))),
      stats: this.wlc.getClientStats().pipe(catchError(() => of(null))),
      advisor: this.wlc.getAdvisor().pipe(catchError(() => of(null))),
      events: this.events.list(false).pipe(catchError(() => of(null))),
      lifecycle: this.lifecycleSvc.get().pipe(catchError(() => of(null))),
    }).subscribe({
      next: r => {
        this.dash.set(r.dash);
        this.aps.set(r.aps || []);
        this.stats.set(r.stats);
        this.advisor.set(r.advisor);
        this.eventList.set(r.events);
        this.lifecycle.set(r.lifecycle);
        this.generatedAt.set(new Date().toLocaleString());
        this.loading.set(false);
      },
      error: () => { this.error.set('Failed to build the report'); this.loading.set(false); },
    });
  }

  download() { window.print(); }

  // ── KPIs ──
  private isUp(s: string) {
    const x = (s || '').toLowerCase();
    return x.includes('registered') || x.includes('run') || x.includes('online') || x.includes('connected');
  }
  apsOnline = computed(() => this.aps().filter(a => this.isUp(a.state)).length);
  apsTotal = computed(() => this.aps().length || this.dash()?.aps?.total_aps || 0);
  apsOffline = computed(() => this.apsTotal() - this.apsOnline());
  clients = computed(() => this.dash()?.clients?.total_clients ?? 0);
  wlans = computed(() => this.dash()?.wlans?.total_wlans ?? 0);
  cpu = computed(() => Math.round(this.dash()?.cpu?.one_minute ?? this.dash()?.cpu?.five_seconds ?? 0));
  mem = computed(() => {
    const p = this.dash()?.memory?.pools?.find(x => /system|memory/i.test(x.name));
    return Math.round(p?.used_percent ?? 0);
  });
  alerts = computed(() => this.eventList()?.unacked ?? 0);
  compliance = computed(() => {
    const s = this.lifecycle()?.summary;
    return s && s.total ? Math.round((s.compliant / s.total) * 100) : null;
  });
  avgRssi = computed(() => this.stats()?.avg_rssi_dbm ?? null);
  avgSnr = computed(() => this.stats()?.avg_snr_db ?? null);
  worstClients = computed(() => (this.stats()?.worst_clients || []).slice(0, 8));
  recommendations = computed(() => (this.advisor()?.recommendations || []).slice(0, 8));
  poorClients = computed(() => {
    const q = this.stats()?.quality_distribution || {};
    return (q['Poor'] || 0) + (q['Critical'] || 0);
  });

  // ── Charts ──
  qualityData = computed(() => {
    const q = this.stats()?.quality_distribution || {};
    return {
      labels: QUALITY.map(x => x[0]),
      datasets: [{ data: QUALITY.map(x => q[x[0]] || 0), backgroundColor: QUALITY.map(x => x[1]), borderWidth: 0 }],
    };
  });
  bandData = computed(() => {
    const b = this.stats()?.band_distribution || {};
    const labels = Object.keys(b);
    return {
      labels,
      datasets: [{ data: labels.map(l => b[l]), backgroundColor: labels.map(l => BAND_COLOR[l] || '#706868'), borderWidth: 0 }],
    };
  });
  apStatusData = computed(() => ({
    labels: ['Online', 'Offline'],
    datasets: [{ data: [this.apsOnline(), this.apsOffline()], backgroundColor: ['#34C759', '#C8102E'], borderWidth: 0 }],
  }));
  apModelData = computed(() => {
    const m = new Map<string, number>();
    for (const a of this.aps()) { const k = (a.model || 'Unknown').trim(); m.set(k, (m.get(k) || 0) + 1); }
    const top = [...m.entries()].sort((x, y) => y[1] - x[1]).slice(0, 8);
    return { labels: top.map(e => e[0]), datasets: [{ label: 'APs', data: top.map(e => e[1]), backgroundColor: '#5A9BD5', borderRadius: 4 }] };
  });
  eventsData = computed(() => {
    const evs = (this.eventList()?.events || []).filter(e => e.active && !e.acked);
    return {
      labels: SEVERITY.map(s => s[0][0].toUpperCase() + s[0].slice(1)),
      datasets: [{ data: SEVERITY.map(s => evs.filter(e => e.severity === s[0]).length),
        backgroundColor: SEVERITY.map(s => s[1]), borderWidth: 0 }],
    };
  });

  hasClients = computed(() => (this.stats()?.total_clients ?? 0) > 0);
  hasEvents = computed(() => (this.eventList()?.events?.length ?? 0) > 0);
}
