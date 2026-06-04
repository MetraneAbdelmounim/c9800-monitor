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
  radioUp(r: RfRadio): boolean { return r.channel > 0; }
  trackByConflict = (_: number, c: RfConflict) => c.type + c.band + c.channel;
}
