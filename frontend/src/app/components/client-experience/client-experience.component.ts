import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WlcService } from '../../services/wlc.service';
import { WirelessClient, ClientStats } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-client-experience', standalone: true,
  imports: [CommonModule, FormsModule, SpinnerComponent],
  templateUrl: './client-experience.component.html',
  styleUrl: './client-experience.component.css'
})
export class ClientExperienceComponent implements OnInit {
  query = '';
  results: WirelessClient[] = [];
  allClients: WirelessClient[] = [];
  selected: WirelessClient | null = null;
  stats: ClientStats | null = null;
  view: 'search' | 'detail' = 'search';
  loading = true;

  constructor(private wlc: WlcService) {}

  ngOnInit() {
    this.wlc.getClientStats().subscribe(d => this.stats = d);
    this.wlc.getClientDetails().subscribe({
      next: d => {
        this.allClients = d.clients;
        this.results = d.clients;
        this.loading = false;
      },
      error: () => this.loading = false,
    });
  }

  onSearch() {
    if (this.query.trim().length >= 2) {
      this.wlc.searchClients(this.query).subscribe(d => this.results = d.clients);
    } else {
      this.results = this.allClients;
    }
  }

  clearSearch() { this.query = ''; this.results = this.allClients; }
  selectClient(c: WirelessClient) { this.selected = c; this.view = 'detail'; }
  goBack() { this.selected = null; this.view = 'search'; }

  rssiColor(r: number): string {
    if (r >= -55) return '#34C759'; if (r >= -67) return '#5A9BD5';
    if (r >= -72) return '#E8A838'; if (r >= -80) return '#E07830'; return '#C8102E';
  }
  qualColor(s: number): string {
    if (s >= 80) return '#34C759'; if (s >= 60) return '#5A9BD5';
    if (s >= 40) return '#E8A838'; if (s >= 20) return '#E07830'; return '#C8102E';
  }
  snrColor(s: number): string { return s > 25 ? '#34C759' : s > 15 ? '#E8A838' : '#C8102E'; }
  retriesColor(r: number): string { return r > 200 ? '#C8102E' : r > 50 ? '#E8A838' : '#34C759'; }
  fmtBytes(b: number): string {
    if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB';
    if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB';
    if (b >= 1024) return (b / 1024).toFixed(0) + ' KB'; return b + ' B';
  }
  fmtDuration(s: number): string {
    const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60);
    return h > 0 ? h + 'h ' + m + 'm' : m + 'm';
  }
  rssiPosition(r: number): number { return Math.min(100, Math.max(0, ((r + 95) / 65) * 100)); }
  qualKeys(): string[] { return this.stats ? Object.keys(this.stats.quality_distribution) : []; }
  qualDistColor(key: string): string {
    const m: {[k:string]:string} = {Excellent:'#34C759',Good:'#5A9BD5',Fair:'#E8A838',Poor:'#E07830',Critical:'#C8102E'};
    return m[key] || '#706868';
  }
  qualDistPct(key: string): number {
    if (!this.stats || !this.stats.total_clients) return 0;
    return (this.stats.quality_distribution[key] / this.stats.total_clients) * 100;
  }
  deviceIcon(type: string): string {
    const m: {[k:string]:string} = {Laptop:'\uD83D\uDCBB',Smartphone:'\uD83D\uDCF1',Tablet:'\uD83D\uDCCB',Desktop:'\uD83D\uDDA5\uFE0F','IoT Sensor':'\uD83D\uDD0C'};
    return m[type] || '\uD83D\uDDA5\uFE0F';
  }
  gaugeArc(pct: number): string { const c = 2 * Math.PI * 40; return (c - (pct / 100) * c).toString(); }
  gaugeDash(): string { return (2 * Math.PI * 40).toString(); }
}