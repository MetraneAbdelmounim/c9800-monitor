import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { EventService } from '../../services/event.service';
import { EventItem, EventList } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-security-events',
  standalone: true,
  imports: [CommonModule, SpinnerComponent],
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
      },
      error: e => this.error = e?.error?.error || 'Failed to load events',
    });
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
