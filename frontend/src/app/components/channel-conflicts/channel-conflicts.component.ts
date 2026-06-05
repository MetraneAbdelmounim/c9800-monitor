import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WlcService } from '../../services/wlc.service';
import { RfAnalysis, RfConflict, RfRadio } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

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

  setBand(b: string) { this.bandTab = b; }
  toggleCollapse(b: string) { this.collapsed[b] = !this.collapsed[b]; }
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
  conflictsFor(b: string): RfConflict[] { return this.sevFiltered().filter(c => c.band === b); }

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
    return { critical: '#C8102E', high: '#E07830', medium: '#E8A838' }[sev] || 'var(--text-3)';
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
