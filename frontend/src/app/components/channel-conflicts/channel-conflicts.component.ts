import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WlcService } from '../../services/wlc.service';
import { RfAnalysis, RfConflict, RfRadio } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

interface SpecBar {
  channel: number; width: number; x: number; w: number; y: number; h: number;
  color: string; count: number; conflicts: number; severity: string; util: number;
}
interface SpecBand { band: string; bars: SpecBar[]; maxCount: number; }

@Component({
  selector: 'app-channel-conflicts',
  standalone: true,
  imports: [CommonModule, SpinnerComponent],
  templateUrl: './channel-conflicts.component.html',
  styleUrl: './channel-conflicts.component.css',
})
export class ChannelConflictsComponent implements OnInit, OnDestroy {
  private wlc = inject(WlcService);

  data: RfAnalysis | null = null;
  error = '';
  private iv: any;

  // Severity filter (medium hidden by default — usually low-impact + numerous)
  show: Record<'critical' | 'high' | 'medium', boolean> = { critical: true, high: true, medium: false };
  // Band tabs + collapsible sections
  readonly bands = ['2.4 GHz', '5 GHz', '6 GHz'];
  bandTab: 'all' | string = 'all';
  collapsed: Record<string, boolean> = {};

  private sevFiltered(): RfConflict[] {
    return this.data ? this.data.conflicts.filter(c => this.show[c.severity]) : [];
  }
  sevCount(s: 'critical' | 'high' | 'medium'): number {
    return this.data ? this.data.conflicts.filter(c => c.severity === s).length : 0;
  }
  toggleSev(s: 'critical' | 'high' | 'medium') { this.show[s] = !this.show[s]; }

  // Clicking a spectrum bar focuses that channel in the card list
  channelFilter: { band: string; channel: number } | null = null;

  setBand(b: string) { this.bandTab = b; this.channelFilter = null; }
  toggleCollapse(b: string) { this.collapsed[b] = !this.collapsed[b]; }

  // ── Spectrum analyzer geometry ───────────────────────
  readonly SPEC_W = 1000;
  readonly SPEC_H = 145;
  private readonly PAD = 24;
  private readonly AXIS = 46;     // space below baseline for channel + width labels
  get baseY(): number { return this.SPEC_H - this.AXIS; }

  get shownSpectrum(): SpecBand[] {
    return this.bandTab === 'all' ? this.spectrum : this.spectrum.filter(s => s.band === this.bandTab);
  }

  get spectrum(): SpecBand[] {
    if (!this.data) return [];
    const out: SpecBand[] = [];
    for (const band of this.bands) {
      const radios = this.data.radios.filter(r => r.band === band && r.channel > 0);
      if (!radios.length) continue;

      const byCh = new Map<number, { count: number; width: number; util: number }>();
      for (const r of radios) {
        const e = byCh.get(r.channel) || { count: 0, width: r.width_mhz || 20, util: 0 };
        e.count++;
        e.width = Math.max(e.width, r.width_mhz || 20);
        e.util = Math.max(e.util, r.utilization);
        byCh.set(r.channel, e);
      }
      // worst severity + conflict count per channel
      const sevByCh = new Map<number, string>();
      const cntByCh = new Map<number, number>();
      const rank: any = { critical: 0, high: 1, medium: 2 };
      for (const c of this.data.conflicts.filter(c => c.band === band)) {
        const ch = c.focal.channel;
        cntByCh.set(ch, (cntByCh.get(ch) || 0) + 1);
        const cur = sevByCh.get(ch);
        if (!cur || rank[c.severity] < rank[cur]) sevByCh.set(ch, c.severity);
      }

      // Evenly-spaced categorical bars (one per occupied channel) — bounded
      // width so they stay readable whether the band has 3 or 25 channels.
      const entries = [...byCh.entries()].sort((a, b) => a[0] - b[0]);
      const n = entries.length;
      const innerW = this.SPEC_W - 2 * this.PAD;
      const innerH = this.SPEC_H - this.AXIS;
      const maxCount = Math.max(...entries.map(([, e]) => e.count));
      const slotW = innerW / n;
      const barW = Math.min(46, slotW * 0.62);

      const bars: SpecBar[] = entries.map(([ch, e], i) => {
        const cx = this.PAD + slotW * i + slotW / 2;
        const h = Math.max(4, (e.count / maxCount) * (innerH - 16));   // headroom for label
        const sev = sevByCh.get(ch);
        return {
          channel: ch, width: e.width, x: cx - barW / 2, w: barW, y: innerH - h, h,
          color: this.sevColor(sev || 'none'),
          count: e.count, conflicts: cntByCh.get(ch) || 0,
          severity: sev || 'none', util: e.util,
        };
      });

      out.push({ band, bars, maxCount });
    }
    return out;
  }

  onBarClick(band: string, ch: number) {
    if (this.channelFilter && this.channelFilter.band === band && this.channelFilter.channel === ch) {
      this.channelFilter = null;             // toggle off
    } else {
      this.channelFilter = { band, channel: ch };
      this.bandTab = band;
      this.collapsed[band] = false;
    }
  }
  isBarActive(band: string, ch: number): boolean {
    return !!this.channelFilter && this.channelFilter.band === band && this.channelFilter.channel === ch;
  }
  bandCount(b: string): number { return this.sevFiltered().filter(c => c.band === b).length; }
  shownCount(): number {
    return this.sevFiltered().filter(c => this.bandTab === 'all' || c.band === this.bandTab).length;
  }
  /** Bands that currently have ≥1 conflict (after severity filter), respecting the active tab. */
  get shownBands(): string[] {
    const f = this.sevFiltered();
    return this.bands.filter(b => (this.bandTab === 'all' || this.bandTab === b)
                                  && f.some(c => c.band === b));
  }
  conflictsFor(b: string): RfConflict[] {
    let list = this.sevFiltered().filter(c => c.band === b);
    if (this.channelFilter && this.channelFilter.band === b) {
      list = list.filter(c => c.focal.channel === this.channelFilter!.channel);
    }
    return list;
  }

  /** Map RSSI (-90..-35 dBm) to a 5–100% bar width. */
  signalPct(rssi: number): number {
    return Math.max(5, Math.min(100, Math.round((rssi + 90) / 55 * 100)));
  }
  kindLabel(c: RfConflict): string {
    if (c.type === 'co-channel') return 'Co-channel';
    return c.band === '2.4 GHz' ? 'Adjacent' : 'Overlapping';
  }

  ngOnInit() {
    this.load();
    this.iv = setInterval(() => this.load(), 30000);
  }
  ngOnDestroy() { clearInterval(this.iv); }

  load() {
    this.wlc.getRfAnalysis().subscribe({
      next: d => { this.data = d; this.error = ''; },
      error: e => this.error = e?.error?.error || 'Failed to load RF analysis',
    });
  }

  sevColor(sev: string): string {
    return ({ critical: '#C8102E', high: '#E07830', medium: '#E8A838',
              none: '#3E7D5A' } as Record<string, string>)[sev] || 'var(--text-3)';
  }
  utilColor(u: number): string {
    if (u >= 50) return '#C8102E';
    if (u >= 25) return '#E8A838';
    return 'var(--green)';
  }
  noiseColor(n: number): string {
    // less negative (toward 0) = noisier = worse
    if (n === 0) return 'var(--text-3)';
    if (n >= -85) return '#C8102E';
    if (n >= -90) return '#E8A838';
    return 'var(--green)';
  }
  rssiColor(r: number): string {
    // stronger (less negative) co-channel neighbor = worse interference
    if (r >= -60) return '#C8102E';
    if (r >= -72) return '#E8A838';
    return 'var(--green)';
  }
  trackByConflict = (_: number, c: RfConflict) => c.type + c.focal.mac + c.focal.slot;
}
