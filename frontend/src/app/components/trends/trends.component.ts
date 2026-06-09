import { Component, OnInit, OnDestroy, AfterViewInit, ViewChild, ElementRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrackingService } from '../../services/tracking.service';
import { SpinnerComponent } from '../spinner/spinner.component';

declare var Chart: any;

@Component({
  selector: 'app-trends',
  standalone: true,
  imports: [CommonModule, SpinnerComponent],
  template: `
<div class="page">
  <div class="head">
    <div>
      <h1>Trends &amp; Capacity</h1>
      <p class="sub">Historical clients, system load, and per-AP capacity</p>
    </div>
    <div class="ranges">
      <button *ngFor="let r of ranges" class="rg" [class.on]="range===r.v" (click)="setRange(r.v)">{{ r.l }}</button>
    </div>
  </div>

  <app-spinner *ngIf="loading" label="Loading trends…"></app-spinner>

  <div *ngIf="!loading && empty" class="empty">
    <div class="ic">📈</div>
    <div class="t">No trend data yet</div>
    <p>Metrics accumulate while the collector runs. Check back in a few minutes.</p>
  </div>

  <div class="grid" [style.display]="(!loading && !empty) ? 'grid' : 'none'">
    <div class="card">
      <div class="card-title">WIRELESS CLIENTS OVER TIME</div>
      <canvas #clientsChart></canvas>
    </div>
    <div class="card">
      <div class="card-title">CONTROLLER CPU &amp; MEMORY</div>
      <canvas #sysChart></canvas>
    </div>
    <div class="card">
      <div class="card-title">BUSIEST ACCESS POINTS (avg clients)</div>
      <canvas #topChart></canvas>
    </div>
    <div class="card">
      <div class="card-title">CLIENTS BY HOUR OF DAY (UTC)</div>
      <canvas #hourChart></canvas>
    </div>
  </div>
</div>`,
  styles: [`
    .page { max-width: 1200px; }
    .head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:18px; }
    h1 { font-size:22px; font-weight:800; color:var(--text-1); }
    .sub { font-size:12px; color:var(--text-muted); margin-top:2px; }
    .ranges { display:flex; gap:4px; }
    .rg { background:var(--bg-card); border:1px solid var(--border); color:var(--text-3); font-size:11px; font-weight:600; padding:7px 12px; border-radius:8px; cursor:pointer; }
    .rg.on { background:var(--brand); border-color:var(--brand); color:#fff; }
    .grid { grid-template-columns:1fr 1fr; gap:16px; }
    .card { background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:16px 18px; }
    .card-title { font-size:10px; font-weight:700; letter-spacing:1.5px; color:var(--text-muted); margin-bottom:12px; }
    canvas { width:100% !important; height:240px !important; }
    .empty { text-align:center; padding:60px 20px; background:var(--bg-card); border:1px solid var(--border); border-radius:12px; color:var(--text-3); }
    .empty .ic { font-size:34px; margin-bottom:10px; }
    .empty .t { font-size:16px; font-weight:700; color:var(--text-2); margin-bottom:6px; }
    @media (max-width:820px){ .grid { grid-template-columns:1fr; } }
  `],
})
export class TrendsComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('clientsChart') clientsCv!: ElementRef;
  @ViewChild('sysChart') sysCv!: ElementRef;
  @ViewChild('topChart') topCv!: ElementRef;
  @ViewChild('hourChart') hourCv!: ElementRef;

  private ts = inject(TrackingService);
  range = 'last24h';
  loading = true;
  empty = false;
  ranges = [
    { l: '2h', v: 'last2h' }, { l: '6h', v: 'last6h' },
    { l: '24h', v: 'last24h' }, { l: '7d', v: 'last7d' },
  ];
  private charts: any[] = [];
  private viewReady = false;

  ngOnInit() { this.load(); }
  ngAfterViewInit() { this.viewReady = true; }
  ngOnDestroy() { this.killCharts(); }

  setRange(v: string) { this.range = v; this.load(); }

  private css(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888';
  }
  private killCharts() { this.charts.forEach(c => { try { c.destroy(); } catch {} }); this.charts = []; }

  load() {
    this.loading = true;
    this.ts.getTrends(this.range).subscribe({
      next: d => {
        this.empty = !(d.system && d.system.length);
        this.loading = false;
        // wait a tick for *ngIf grid to render the canvases
        setTimeout(() => this.render(d), 0);
      },
      error: () => { this.loading = false; this.empty = true; },
    });
  }

  private render(d: any) {
    if (typeof Chart === 'undefined' || this.empty) return;
    this.killCharts();
    const tick = this.css('--text-3'), grid = 'rgba(128,128,128,0.15)';
    const baseOpts = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: tick, boxWidth: 12, font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } }, grid: { color: grid } },
        y: { beginAtZero: true, ticks: { color: tick, font: { size: 10 } }, grid: { color: grid } },
      },
    };

    const sys = d.system || [];
    const labels = sys.map((p: any) => this.fmt(p.timestamp));

    // 1) Clients over time (band breakdown)
    this.charts.push(new Chart(this.clientsCv.nativeElement, {
      type: 'line',
      data: { labels, datasets: [
        this.ds('Total', sys.map((p: any) => p.total_clients), '#3E6BB0', true),
        this.ds('5 GHz', sys.map((p: any) => p.clients_5g), '#34C759'),
        this.ds('2.4 GHz', sys.map((p: any) => p.clients_2g), '#E8A838'),
        this.ds('6 GHz', sys.map((p: any) => p.clients_6g), '#9B72CF'),
      ] }, options: baseOpts,
    }));

    // 2) CPU & memory
    this.charts.push(new Chart(this.sysCv.nativeElement, {
      type: 'line',
      data: { labels, datasets: [
        this.ds('CPU %', sys.map((p: any) => p.cpu_5s), '#C8102E', true),
        this.ds('Memory %', sys.map((p: any) => p.mem_used_pct), '#5A9BD5', true),
      ] },
      options: { ...baseOpts, scales: { ...baseOpts.scales, y: { ...baseOpts.scales.y, max: 100 } } },
    }));

    // 3) Top APs (horizontal bar)
    const top = d.top_aps || [];
    this.charts.push(new Chart(this.topCv.nativeElement, {
      type: 'bar',
      data: { labels: top.map((t: any) => t.ap_name),
        datasets: [{ label: 'Avg clients', data: top.map((t: any) => t.avg_clients), backgroundColor: '#3E6BB0', borderRadius: 4 }] },
      options: { ...baseOpts, indexAxis: 'y', plugins: { legend: { display: false } } },
    }));

    // 4) Clients by hour
    const hours = Array.from({ length: 24 }, (_, h) => h);
    const hmap: any = {}; (d.hourly || []).forEach((x: any) => hmap[x.hour] = x.avg_clients);
    this.charts.push(new Chart(this.hourCv.nativeElement, {
      type: 'bar',
      data: { labels: hours.map(h => h + 'h'),
        datasets: [{ label: 'Avg clients', data: hours.map(h => hmap[h] || 0), backgroundColor: '#9B72CF', borderRadius: 3 }] },
      options: { ...baseOpts, plugins: { legend: { display: false } } },
    }));
  }

  private ds(label: string, data: any[], color: string, fill = false) {
    return { label, data, borderColor: color, backgroundColor: color + '22',
             fill, tension: 0.3, pointRadius: 0, borderWidth: 2 };
  }

  private fmt(iso: string): string {
    const t = Date.parse(iso);
    if (isNaN(t)) return '';
    const d = new Date(t);
    const hh = String(d.getHours()).padStart(2, '0'), mm = String(d.getMinutes()).padStart(2, '0');
    return this.range === 'last7d'
      ? `${d.getMonth() + 1}/${d.getDate()} ${hh}:${mm}`
      : `${hh}:${mm}`;
  }
}
