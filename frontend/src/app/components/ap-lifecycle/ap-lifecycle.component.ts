import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LifecycleService, LifecycleData, LcAp } from '../../services/lifecycle.service';
import { AuthService } from '../../services/auth.service';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-ap-lifecycle',
  standalone: true,
  imports: [CommonModule, FormsModule, SpinnerComponent],
  templateUrl: './ap-lifecycle.component.html',
  styleUrl: './ap-lifecycle.component.css',
})
export class ApLifecycleComponent implements OnInit {
  private svc = inject(LifecycleService);
  readonly auth = inject(AuthService);

  data: LifecycleData | null = null;
  error = '';
  refreshing = false;
  targetInput = '';
  saving = false;
  savedMsg = '';

  ngOnInit() { this.load(); }

  get isAdmin(): boolean { return this.auth.hasRole('admin'); }

  load() {
    this.refreshing = true;
    this.svc.get().subscribe({
      next: d => { this.data = d; this.targetInput = d.target || ''; this.error = ''; this.refreshing = false; },
      error: e => { this.error = e?.error?.error || 'Failed to load AP lifecycle'; this.refreshing = false; },
    });
  }

  saveTarget() {
    this.saving = true; this.savedMsg = '';
    this.svc.setTarget(this.targetInput.trim()).subscribe({
      next: () => { this.saving = false; this.savedMsg = 'Target version saved.'; this.load(); },
      error: () => { this.saving = false; this.error = 'Failed to save target'; },
    });
  }

  compliancePct(): number {
    const s = this.data?.summary;
    return s && s.total ? Math.round((s.compliant / s.total) * 100) : 0;
  }
  versionPct(count: number): number {
    const t = this.data?.summary.total || 0;
    return t ? (count / t) * 100 : 0;
  }
  isTarget(v: string): boolean { return !!this.data?.target && v === this.data.target; }

  stateClass(s: string): string {
    const x = (s || '').toLowerCase();
    if (x.includes('registered') || x.includes('run') || x.includes('online') || x.includes('connected')) return 'up';
    if (x.includes('down') || x.includes('disabled') || x.includes('offline') || x.includes('disconnect')) return 'down';
    return 'warn';
  }
  uptime(sec: number): string {
    if (!sec || sec <= 0) return '—';
    const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }
  trackByMac = (_: number, a: LcAp) => a.mac;
}
