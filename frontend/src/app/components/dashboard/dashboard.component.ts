import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { WlcService } from '../../services/wlc.service';
import * as M from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';
import { ChartComponent } from '../chart/chart.component';

const QUALITY = [
  ['Excellent', '#34C759'], ['Good', '#5A9BD5'], ['Fair', '#E8A838'],
  ['Poor', '#E07830'], ['Critical', '#C8102E'],
];
const BAND_COLOR: Record<string, string> = {
  '2.4 GHz': '#E8A838', '5 GHz': '#5A9BD5', '6 GHz': '#9B72CF',
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, SpinnerComponent, ChartComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  private wlc = inject(WlcService);
  private interval: any;

  data = signal<M.Dashboard | null>(null);
  aps = signal<M.AccessPoint[]>([]);
  stats = signal<M.ClientStats | null>(null);
  advisor = signal<M.AdvisorResult | null>(null);
  error = signal('');

  ngOnInit() {
    this.load();
    this.interval = setInterval(() => this.load(), 15000);
  }
  ngOnDestroy() { clearInterval(this.interval); }

  load() {
    forkJoin({
      dash: this.wlc.getDashboard().pipe(catchError(() => of(null))),
      aps: this.wlc.getAllAps().pipe(catchError(() => of([] as M.AccessPoint[]))),
      stats: this.wlc.getClientStats().pipe(catchError(() => of(null))),
      advisor: this.wlc.getAdvisor().pipe(catchError(() => of(null))),
    }).subscribe({
      next: r => {
        if (r.dash) this.data.set(r.dash);
        if (r.aps?.length) this.aps.set(r.aps);
        if (r.stats) this.stats.set(r.stats);
        if (r.advisor) this.advisor.set(r.advisor);
        this.error.set(r.dash ? '' : 'Failed to load dashboard');
      },
      error: () => this.error.set('Failed to load dashboard'),
    });
  }

  // ── KPIs ──
  private isUp(s: string) {
    const x = (s || '').toLowerCase();
    return x.includes('registered') || x.includes('run') || x.includes('online') || x.includes('connected');
  }
  apsOnline = computed(() => this.aps().filter(a => this.isUp(a.state)).length);
  apsTotal = computed(() => this.aps().length || this.data()?.aps?.total_aps || 0);
  clients = computed(() => this.data()?.clients?.total_clients ?? 0);
  wlans = computed(() => this.data()?.wlans?.total_wlans ?? 0);
  cpu = computed(() => Math.round(this.data()?.cpu?.one_minute ?? this.data()?.cpu?.five_seconds ?? 0));
  mem = computed(() => {
    const p = this.data()?.memory?.pools?.find(x => /system|memory/i.test(x.name));
    return Math.round(p?.used_percent ?? 0);
  });
  findings = computed(() => {
    const s = this.advisor()?.summary;
    return s ? s.critical + s.high + s.medium + s.low : 0;
  });
  criticalFindings = computed(() => {
    const s = this.advisor()?.summary;
    return s ? s.critical + s.high : 0;
  });
  topFindings = computed(() => (this.advisor()?.recommendations || []).slice(0, 5));

  hasClients = computed(() => (this.stats()?.total_clients ?? 0) > 0);

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
    datasets: [{ data: [this.apsOnline(), this.apsTotal() - this.apsOnline()],
      backgroundColor: ['#34C759', '#C8102E'], borderWidth: 0 }],
  }));

  gaugeColor(pct: number): string {
    if (pct < 50) return '#34C759';
    if (pct < 80) return '#E8A838';
    return '#C8102E';
  }
}
