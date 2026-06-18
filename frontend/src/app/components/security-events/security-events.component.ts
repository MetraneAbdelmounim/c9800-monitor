import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { EventService } from '../../services/event.service';
import { EventItem, EventList } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';
import { ChartComponent } from '../chart/chart.component';

const SEV = [['critical', '#C8102E'], ['high', '#E07830'], ['medium', '#E8A838'], ['low', '#5A9BD5']];
const CAT = [['security', '#C8102E'], ['rf', '#5A9BD5'], ['client', '#9B72CF']];

@Component({
  selector: 'app-security-events',
  standalone: true,
  imports: [CommonModule, SpinnerComponent, ChartComponent],
  templateUrl: './security-events.component.html',
  styleUrl: './security-events.component.css',
})
export class SecurityEventsComponent implements OnInit, OnDestroy {
  private svc = inject(EventService);

  data: EventList | null = null;
  error = '';
  showAcked = false;
  selected = new Set<string>();
  acking = false;
  private iv: any;

  // List ⇄ Charts view
  view: 'list' | 'charts' = 'list';
  readonly barOptions = { indexAxis: 'y', plugins: { legend: { display: false } } };
  severityData: any = { labels: [], datasets: [] };
  categoryData: any = { labels: [], datasets: [] };
  typeData: any = { labels: [], datasets: [] };

  ngOnInit() {
    this.load();
    this.iv = setInterval(() => this.load(), 30000);
  }
  ngOnDestroy() { clearInterval(this.iv); }

  load() {
    this.svc.list(this.showAcked).subscribe({
      next: d => {
        this.data = d;
        this.error = '';
        // drop selections that no longer exist
        const ids = new Set(d.events.map(e => e.id));
        this.selected.forEach(id => { if (!ids.has(id)) this.selected.delete(id); });
        this.buildCharts();
      },
      error: e => this.error = e?.error?.error || 'Failed to load events',
    });
  }

  /** Recompute chart datasets once per load (stable refs → no re-render churn). */
  private buildCharts() {
    const evs = this.data?.events || [];
    const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
    this.severityData = {
      labels: SEV.map(s => cap(s[0])),
      datasets: [{ data: SEV.map(s => evs.filter(e => e.severity === s[0]).length),
        backgroundColor: SEV.map(s => s[1]), borderWidth: 0 }],
    };
    this.categoryData = {
      labels: CAT.map(c => cap(c[0])),
      datasets: [{ data: CAT.map(c => evs.filter(e => e.category === c[0]).length),
        backgroundColor: CAT.map(c => c[1]), borderWidth: 0 }],
    };
    const m = new Map<string, number>();
    for (const e of evs) { const k = e.type.replace(/_/g, ' '); m.set(k, (m.get(k) || 0) + 1); }
    const top = [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
    this.typeData = {
      labels: top.map(t => t[0]),
      datasets: [{ label: 'Events', data: top.map(t => t[1]), backgroundColor: '#3E6BB0', borderRadius: 4 }],
    };
  }

  toggleShowAcked() { this.showAcked = !this.showAcked; this.load(); }

  isSelected(id: string) { return this.selected.has(id); }
  toggleSelect(id: string) {
    this.selected.has(id) ? this.selected.delete(id) : this.selected.add(id);
  }
  get allSelected(): boolean {
    const ev = this.data?.events || [];
    return ev.length > 0 && ev.every(e => this.selected.has(e.id));
  }
  toggleSelectAll() {
    const ev = this.data?.events || [];
    if (this.allSelected) this.selected.clear();
    else ev.forEach(e => this.selected.add(e.id));
  }

  ackSelected() {
    if (!this.selected.size) return;
    this.acking = true;
    this.svc.ack([...this.selected]).subscribe({
      next: () => { this.selected.clear(); this.acking = false; this.load(); },
      error: () => { this.acking = false; this.error = 'Acknowledge failed'; },
    });
  }
  ackAll() {
    this.acking = true;
    this.svc.ackAll().subscribe({
      next: () => { this.selected.clear(); this.acking = false; this.load(); },
      error: () => { this.acking = false; this.error = 'Acknowledge failed'; },
    });
  }

  sevColor(s: string): string {
    return { critical: '#C8102E', high: '#E07830', medium: '#E8A838', low: '#5A9BD5' }[s] || 'var(--text-3)';
  }
  catLabel(c: EventItem): string {
    return c.type.replace(/_/g, ' ');
  }

  /** Relative "11m ago" style from an ISO timestamp. */
  timeAgo(iso?: string): string {
    if (!iso) return '';
    const t = Date.parse(iso);
    if (isNaN(t)) return '';
    const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  }

  trackById = (_: number, e: EventItem) => e.id;
}
