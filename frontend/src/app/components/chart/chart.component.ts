import {
  Component, ElementRef, Input, ViewChild,
  AfterViewInit, OnChanges, OnDestroy,
} from '@angular/core';

declare var Chart: any;

/**
 * Thin reusable wrapper around Chart.js (loaded globally in index.html).
 * Pass `type`, `data` ({ labels, datasets }) and optional `options`; the
 * component re-renders on input change and themes axes/legend from the active
 * CSS variables so it looks right in both dark and light mode.
 *
 *   <app-chart type="doughnut" [data]="qualityData()"></app-chart>
 */
@Component({
  selector: 'app-chart',
  standalone: true,
  template: '<canvas #c></canvas>',
  styles: [':host{display:block;position:relative;width:100%;height:100%;}'],
})
export class ChartComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() type = 'doughnut';
  @Input() data: any = { labels: [], datasets: [] };
  @Input() options: any = {};

  @ViewChild('c', { static: true }) canvas!: ElementRef<HTMLCanvasElement>;
  private chart: any;

  ngAfterViewInit() { this.render(); }

  ngOnChanges() { if (this.canvas) this.render(); }

  ngOnDestroy() { this.chart?.destroy(); }

  private cssVar(name: string, fallback: string): string {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  private render() {
    if (typeof Chart === 'undefined' || !this.canvas) return;
    this.chart?.destroy();

    const text = this.cssVar('--text-2', '#A8A0A0');
    const grid = this.cssVar('--border', 'rgba(128,128,128,0.18)');
    const isBar = this.type === 'bar';

    const base: any = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: !isBar,
          position: 'bottom',
          labels: { color: text, boxWidth: 12, padding: 12, font: { size: 11 } },
        },
        tooltip: { enabled: true },
      },
      scales: isBar ? {
        x: { ticks: { color: text, font: { size: 10 } }, grid: { color: grid } },
        y: { ticks: { color: text, font: { size: 10 } }, grid: { color: grid }, beginAtZero: true },
      } : {},
    };

    this.chart = new Chart(this.canvas.nativeElement.getContext('2d'), {
      type: this.type,
      data: this.data,
      options: this.deepMerge(base, this.options),
    });
  }

  private deepMerge(a: any, b: any): any {
    if (!b) return a;
    const out = { ...a };
    for (const k of Object.keys(b)) {
      out[k] = b[k] && typeof b[k] === 'object' && !Array.isArray(b[k])
        ? this.deepMerge(a[k] || {}, b[k]) : b[k];
    }
    return out;
  }
}
