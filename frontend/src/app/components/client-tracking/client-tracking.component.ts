import { Component, OnInit, OnDestroy, ViewChild, ElementRef } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { TrackingService, TrackedClient, ClientSummary, TimelinePoint, RoamEvent, CollectorStatus } from "../../services/tracking.service";
import { SpinnerComponent } from "../spinner/spinner.component";

declare var Chart: any;

@Component({
  selector: "app-client-tracking", standalone: true,
  imports: [CommonModule, FormsModule, SpinnerComponent],
  template: `
<div style="max-width:1200px">
  <h1 style="font-size:22px;font-weight:800;color:#F0EDED">Client Tracking</h1>
  <p style="font-size:12px;color:#504848;margin:2px 0 20px">Historical signal quality, roaming events, and performance analysis</p>

  <div style="display:flex;gap:12px;margin-bottom:20px;align-items:center">
    <div style="flex:1;position:relative">
      <input type="text" [(ngModel)]="query" (ngModelChange)="onSearch()" (focus)="showDD=true"
        placeholder="Search client by MAC, IP, hostname..."
        style="width:100%;padding:12px 16px;font-size:13px;font-family:JetBrains Mono,monospace;background:#1C1C1C;border:2px solid #2A2A2A;border-radius:10px;color:#F0EDED;outline:none"/>
      <div *ngIf="showDD&&hits.length" style="position:absolute;top:100%;left:0;right:0;z-index:20;background:#1C1C1C;border:1px solid #2A2A2A;border-radius:0 0 10px 10px;max-height:300px;overflow-y:auto">
        <div *ngFor="let c of hits" (click)="pick(c)" style="padding:10px 16px;cursor:pointer;border-bottom:1px solid #2A2A2A;display:flex;justify-content:space-between;align-items:center" onmouseover="this.style.background='#242424'" onmouseout="this.style.background='transparent'">
          <div>
            <div style="font-size:12px;font-weight:600;color:#F0EDED">{{c.hostname||c.mac}}</div>
            <div style="font-size:10px;color:#706868;font-family:JetBrains Mono,monospace">{{c.mac}} &#8212; {{c.ip||'No IP'}} &#8212; {{c.ssid}} &#8212; {{c.ap_name}}</div>
          </div>
          <span style="padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700" [style.color]="qc(c.quality_score)" [style.background]="qc(c.quality_score)+'18'">{{c.quality_score}}</span>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:4px">
      <button *ngFor="let r of ranges" (click)="setRange(r.v)"
        style="padding:8px 14px;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid #2A2A2A;transition:all .2s"
        [style.background]="range===r.v?'rgba(62,107,176,0.10)':'#1C1C1C'" [style.color]="range===r.v?'#6E97D6':'#706868'"
        [style.borderColor]="range===r.v?'rgba(62,107,176,0.3)':'#2A2A2A'">{{r.l}}</button>
    </div>
  </div>

  <app-spinner *ngIf="loading && !mac" label="Loading tracking data…"></app-spinner>

  <div *ngIf="!mac && !loading" style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px;margin-bottom:16px">
    <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">COLLECTOR STATUS</div>
    <div style="display:flex;gap:24px;font-size:12px">
      <div><span style="color:#706868">Snapshots:</span> <span style="color:#C8102E;font-family:JetBrains Mono,monospace;font-weight:600">{{status?.snapshots||0}}</span></div>
      <div><span style="color:#706868">Roaming Events:</span> <span style="color:#E8A838;font-family:JetBrains Mono,monospace;font-weight:600">{{status?.roaming_events||0}}</span></div>
      <div><span style="color:#706868">Last Poll:</span> <span style="color:#A8A0A0;font-family:JetBrains Mono,monospace">{{status?.last_collection||'Never'}}</span></div>
    </div>
  </div>

  <div *ngIf="!mac&&!loading&&gRoams.length" style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px;margin-bottom:16px">
    <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">RECENT ROAMING EVENTS</div>
    <div *ngFor="let r of gRoams" style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #2A2A2A;font-size:12px">
      <span style="color:#706868;font-family:JetBrains Mono,monospace;font-size:10px;min-width:70px">{{fmtT(r.timestamp)}}</span>
      <span style="color:#C8102E;font-family:JetBrains Mono,monospace;cursor:pointer;min-width:130px" (click)="goMac(r.mac)">{{r.mac}}</span>
      <span style="color:#E07830;font-weight:600">{{r.from_ap}}</span>
      <span style="color:#504848">&#8594;</span>
      <span style="color:#34C759;font-weight:600">{{r.to_ap}}</span>
      <span style="color:#706868">{{r.ssid}} / {{r.band}}</span>
      <span style="font-family:JetBrains Mono,monospace;font-weight:700" [style.color]="qc(r.quality_after)">{{r.rssi_after}} dBm</span>
    </div>
  </div>

  <div *ngIf="mac">
    <button (click)="back()" style="background:none;border:1px solid #2A2A2A;border-radius:8px;color:#706868;padding:8px 16px;cursor:pointer;font-size:12px;font-weight:600;margin-bottom:16px">&#8592; Back to overview</button>

    <div *ngIf="sum" style="display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:16px">
      <div *ngFor="let k of cards" style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:9px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:8px">{{k.label}}</div>
        <div style="font-family:JetBrains Mono,monospace;font-size:20px;font-weight:700" [style.color]="k.color">{{k.value}}<small *ngIf="k.unit" style="font-size:10px;color:#706868;margin-left:2px">{{k.unit}}</small></div>
        <div *ngIf="k.sub" style="font-size:10px;color:#706868;margin-top:4px;font-family:JetBrains Mono,monospace">{{k.sub}}</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px">
      <div style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">SIGNAL QUALITY OVER TIME</div>
        <canvas #qualityChart style="width:100%;height:200px"></canvas>
      </div>
      <div style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">RSSI / SNR OVER TIME</div>
        <canvas #rssiChart style="width:100%;height:200px"></canvas>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px">
      <div style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">DATA RATE (Mbps)</div>
        <canvas #rateChart style="width:100%;height:200px"></canvas>
      </div>
      <div style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">AP ROAMING TIMELINE</div>
        <canvas #apChart style="width:100%;height:200px"></canvas>
      </div>
    </div>

    <div *ngIf="roams.length" style="background:#1C1C1C;border:1px solid #2A2A2A;border-radius:10px;padding:18px 20px">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:#504848;margin-bottom:12px">ROAMING EVENTS ({{roams.length}})</div>
      <div *ngFor="let r of roams" style="display:flex;align-items:center;gap:16px;padding:10px 0;border-bottom:1px solid #2A2A2A;font-size:12px">
        <span style="color:#A8A0A0;font-family:JetBrains Mono,monospace;min-width:140px">{{fmtDT(r.timestamp)}}</span>
        <span style="color:#E07830;font-weight:600;min-width:140px">{{r.from_ap}}</span>
        <span style="color:#504848">&#8594;</span>
        <span style="color:#34C759;font-weight:600;min-width:140px">{{r.to_ap}}</span>
        <span style="color:#706868">{{r.band}} / Ch {{r.channel}}</span>
        <span style="font-family:JetBrains Mono,monospace;font-weight:700" [style.color]="rc(r.rssi_after)">{{r.rssi_after}} dBm</span>
        <span style="font-family:JetBrains Mono,monospace" [style.color]="qc(r.quality_after)">Q:{{r.quality_after}}</span>
      </div>
    </div>
  </div>
</div>`,
  styles: [`canvas{max-height:220px}`]
})
export class ClientTrackingComponent implements OnInit, OnDestroy {
  @ViewChild("qualityChart") qCv!: ElementRef;
  @ViewChild("rssiChart") rCv!: ElementRef;
  @ViewChild("rateChart") dCv!: ElementRef;
  @ViewChild("apChart") aCv!: ElementRef;

  query = ""; hits: TrackedClient[] = []; showDD = false;
  mac: string | null = null; range = "last2h";
  status: CollectorStatus | null = null;
  sum: ClientSummary | null = null;
  tl: TimelinePoint[] = []; roams: RoamEvent[] = []; gRoams: RoamEvent[] = [];
  cards: any[] = [];
  loading = true;
  private charts: any[] = [];
  private iv: any;
  private cjs = false;

  ranges = [
    { l: "30m", v: "last30m" }, { l: "1h", v: "last1h" },
    { l: "2h", v: "last2h" }, { l: "6h", v: "last6h" },
    { l: "Today", v: "today" }, { l: "24h", v: "last24h" },
    { l: "7d", v: "last7d" },
  ];

  constructor(private ts: TrackingService) {}

  ngOnInit() {
    this.loadCjs().then(() => {
      this.refresh();
      this.iv = setInterval(() => this.refresh(), 30000);
    });
  }

  ngOnDestroy() { clearInterval(this.iv); this.killCharts(); }

  private refresh() {
    this.ts.getStatus().subscribe({ next: d => this.status = d, error: () => {} });
    if (this.mac) this.loadClient();
    else this.ts.getAllRoaming(this.range).subscribe({
      next: d => { this.gRoams = (d.events || []).slice(0, 20); this.loading = false; },
      error: () => this.loading = false,
    });
  }

  // ── Search ──────────────────────────────────────────
  onSearch() {
    if (this.query.length < 2) { this.hits = []; return; }
    this.ts.getTrackedClients().subscribe({
      next: cl => {
       
        
        const q = this.query.toLowerCase();
        this.hits = cl.filter(c =>
          [c.mac, c.ip, c.hostname, c.username, c.ap_name, c.ssid]
            .some(f => (f || "").toLowerCase().includes(q))
        ).slice(0, 10);
      }, error: () => {}
    });
  }

  pick(c: TrackedClient) { this.mac = c.mac; this.showDD = false; this.query = c.hostname || c.mac; this.loadClient(); }
  goMac(m: string) { this.mac = m; this.query = m; this.showDD = false; this.loadClient(); }
  setRange(r: string) { this.range = r; this.refresh(); }
  back() { this.mac = null; this.query = ""; this.killCharts(); this.refresh(); }

  // ── Load client data ────────────────────────────────
  private loadClient() {
    if (!this.mac) return;
    const m = this.mac, r = this.range;

    this.ts.getSummary(m, r).subscribe({
      next: d => {
        this.sum = d;
        this.cards = [
          { label: "AVG RSSI", value: d.avg_rssi || 0, unit: "dBm", color: this.rc(d.avg_rssi || 0), sub: `${d.min_rssi || 0} / ${d.max_rssi || 0}` },
          { label: "AVG SNR", value: d.avg_snr || 0, unit: "dB", color: this.snrc(d.avg_snr || 0), sub: `${d.min_snr || 0} / ${d.max_snr || 0}` },
          { label: "AVG QUALITY", value: d.avg_quality || 0, unit: "/100", color: this.qc(d.avg_quality || 0), sub: `${d.min_quality || 0} / ${d.max_quality || 0}` },
          { label: "DATA RATE", value: d.avg_rate || 0, unit: "Mbps", color: "#C8102E", sub: "max " + d.max_rate },
          { label: "ROAMING", value: d.roam_count || 0, unit: "", color: d.roam_count > 0 ? "#E8A838" : "#34C759", sub: (d.aps_used || []).length + " APs" },
          { label: "SAMPLES", value: d.count || 0, unit: "", color: "#A8A0A0", sub: r },
        ];
      }, error: () => {}
    });

    this.ts.getTimeline(m, r).subscribe({
      next: d => { this.tl = d.timeline || []; setTimeout(() => this.renderCharts(), 100); },
      error: () => {}
    });

    this.ts.getRoaming(m, r).subscribe({
      next: d => this.roams = d.events || [], error: () => {}
    });
  }

  // ── Chart.js ────────────────────────────────────────
  private loadCjs(): Promise<void> {
    if (this.cjs) return Promise.resolve();
    return new Promise(res => {
      if (typeof Chart !== "undefined") { this.cjs = true; res(); return; }
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js";
      s.onload = () => { this.cjs = true; res(); };
      document.head.appendChild(s);
    });
  }

  private killCharts() { this.charts.forEach(c => { try { c.destroy(); } catch (e) {} }); this.charts = []; }

  private renderCharts() {
    if (!this.cjs || !this.tl.length) return;
    this.killCharts();
    const labels = this.tl.map(t => this.fmtT(t.timestamp));
    const gc = "#2A2A2A", tc = "#504848";
    const base = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: true, labels: { color: "#706868", font: { size: 10, family: "JetBrains Mono" } } } },
      scales: {
        x: { ticks: { color: tc, font: { size: 9, family: "JetBrains Mono" }, maxTicksLimit: 12 }, grid: { color: gc } },
        y: { ticks: { color: tc, font: { size: 10, family: "JetBrains Mono" } }, grid: { color: gc } },
      },
    };
    // spanGaps:false makes Chart.js break the line at null values (disconnect gaps)
    const ln = (d: (number|null)[], label: string, color: string, fill = false) => ({
      label, data: d, borderColor: color, backgroundColor: fill ? color + "22" : undefined,
      fill, tension: 0.3, pointRadius: 1, borderWidth: 2, spanGaps: false,
    });

    if (this.qCv?.nativeElement) {
      this.charts.push(new Chart(this.qCv.nativeElement, {
        type: "line",
        data: { labels, datasets: [ln(this.tl.map(t => t.quality_score ?? null), "Quality Score", "#C8102E", true)] },
        options: { ...base, scales: { ...base.scales, y: { ...base.scales.y, min: 0, max: 100 } } },
      }));
    }
    if (this.rCv?.nativeElement) {
      this.charts.push(new Chart(this.rCv.nativeElement, {
        type: "line",
        data: { labels, datasets: [ln(this.tl.map(t => t.rssi_dbm ?? null), "RSSI (dBm)", "#34C759"), ln(this.tl.map(t => t.snr_db ?? null), "SNR (dB)", "#E8A838")] },
        options: base,
      }));
    }
    if (this.dCv?.nativeElement) {
      this.charts.push(new Chart(this.dCv.nativeElement, {
        type: "line",
        data: { labels, datasets: [ln(this.tl.map(t => t.data_rate_mbps ?? null), "Data Rate (Mbps)", "#9B72CF", true)] },
        options: base,
      }));
    }
    if (this.aCv?.nativeElement) {
      // Filter out gap points (null quality_score) from scatter chart
      const realPoints = this.tl.filter(t => t.quality_score != null);
      const aps = [...new Set(realPoints.map(t => t.ap_name))];
      const ac = ["#C8102E", "#34C759", "#E8A838", "#E07830", "#9B72CF", "#5A9BD5"];
      this.charts.push(new Chart(this.aCv.nativeElement, {
        type: "scatter",
        data: {
          datasets: aps.map((ap, i) => ({
            label: ap,
            data: realPoints.filter(t => t.ap_name === ap).map(t => ({ x: this.tl.indexOf(t), y: t.quality_score })),
            backgroundColor: ac[i % ac.length], pointRadius: 4, pointStyle: "rectRounded",
          })),
        },
        options: {
          ...base,
          scales: {
            x: { ticks: { color: tc, font: { size: 9, family: "JetBrains Mono" }, callback: (v: any) => labels[v] || "" }, grid: { color: gc } },
            y: { ticks: { color: tc, font: { family: "JetBrains Mono" } }, grid: { color: gc }, min: 0, max: 100, title: { display: true, text: "Quality", color: tc, font: { family: "JetBrains Mono" } } },
          },
        },
      }));
    }
  }

  // ── Helpers ─────────────────────────────────────────
  qc(s: number): string { return s >= 80 ? "#34C759" : s >= 60 ? "#5A9BD5" : s >= 40 ? "#E8A838" : s >= 20 ? "#E07830" : "#C8102E"; }
  rc(r: number): string { return r >= -55 ? "#34C759" : r >= -67 ? "#5A9BD5" : r >= -72 ? "#E8A838" : "#C8102E"; }
  snrc(s: number): string { return s > 25 ? "#34C759" : s > 15 ? "#E8A838" : "#C8102E"; }

  fmtT(ts: any): string {
    if (!ts) return "";
    const d = new Date(typeof ts === "string" ? ts : ts.$date || ts);
    return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }

  fmtDT(ts: any): string {
    if (!ts) return "";
    const d = new Date(typeof ts === "string" ? ts : ts.$date || ts);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) + " " +
      d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
}