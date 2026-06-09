import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WlcService } from '../../services/wlc.service';
import { AdvisorResult, Recommendation } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-advisor',
  standalone: true,
  imports: [CommonModule, SpinnerComponent],
  templateUrl: './advisor.component.html',
  styleUrl: './advisor.component.css',
})
export class AdvisorComponent implements OnInit, OnDestroy {
  private wlc = inject(WlcService);
  data: AdvisorResult | null = null;
  error = '';
  refreshing = false;
  private iv: any;

  ngOnInit() {
    this.load();
    this.iv = setInterval(() => this.load(), 60000);
  }
  ngOnDestroy() { clearInterval(this.iv); }

  load() {
    this.refreshing = true;
    this.wlc.getAdvisor().subscribe({
      next: d => { this.data = d; this.error = ''; this.refreshing = false; },
      error: e => { this.error = e?.error?.error || 'Failed to load advisor'; this.refreshing = false; },
    });
  }

  sevColor(s: string): string {
    return ({ critical: '#C8102E', high: '#E07830', medium: '#E8A838',
              low: '#5A9BD5', info: '#706868' } as Record<string, string>)[s] || 'var(--text-3)';
  }
  catIcon(c: string): string {
    return ({ RF: '⚡', Capacity: '▦', Health: '✚', Firmware: '⬆', Coverage: '◉' } as Record<string, string>)[c] || '•';
  }
  trackByRec = (_: number, r: Recommendation) => r.severity + r.title;
}
