import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SiteService, SiteTestResult } from '../../services/site.service';
import { Site } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-sites',
  standalone: true,
  imports: [CommonModule, FormsModule, SpinnerComponent],
  templateUrl: './sites.component.html',
  styleUrl: './sites.component.css',
})
export class SitesComponent implements OnInit {
  private svc = inject(SiteService);

  sites = signal<Site[]>([]);
  count = signal(0);
  maxSites = signal<number | null>(null);
  loading = signal(true);
  error = signal('');

  // Form
  formOpen = signal(false);
  editingId = signal<string | null>(null);
  saving = signal(false);
  testing = signal(false);
  testResult = signal<SiteTestResult | null>(null);
  f = { name: '', location: '', host: '', port: 443, username: '', password: '', verify_ssl: false, enabled: true };

  atCap = computed(() => this.maxSites() !== null && this.count() >= (this.maxSites() as number));
  capLabel = computed(() =>
    this.maxSites() === null ? `${this.count()} site(s)` : `${this.count()} / ${this.maxSites()} sites`);

  ngOnInit() { this.load(); }

  load() {
    this.loading.set(true);
    this.svc.list().subscribe({
      next: r => { this.sites.set(r.sites); this.count.set(r.count); this.maxSites.set(r.max_sites); this.loading.set(false); },
      error: e => { this.error.set(e?.error?.error || 'Failed to load sites'); this.loading.set(false); },
    });
  }

  newSite() {
    this.editingId.set(null);
    this.f = { name: '', location: '', host: '', port: 443, username: '', password: '', verify_ssl: false, enabled: true };
    this.testResult.set(null); this.error.set('');
    this.formOpen.set(true);
  }

  edit(s: Site) {
    this.editingId.set(s.id);
    this.f = { name: s.name, location: s.location, host: s.host, port: s.port,
               username: s.username, password: '', verify_ssl: s.verify_ssl, enabled: s.enabled };
    this.testResult.set(null); this.error.set('');
    this.formOpen.set(true);
  }

  cancel() { this.formOpen.set(false); }

  save() {
    const id = this.editingId();
    this.saving.set(true); this.error.set('');
    const payload = { ...this.f };
    const done = {
      next: () => { this.saving.set(false); this.formOpen.set(false); this.load(); },
      error: (e: any) => { this.saving.set(false); this.error.set(e?.error?.error || 'Save failed'); },
    };
    if (id) this.svc.update(id, payload).subscribe(done);
    else this.svc.create(payload).subscribe(done);
  }

  test() {
    this.testing.set(true); this.testResult.set(null);
    this.svc.test({ ...this.f, id: this.editingId() || undefined }).subscribe({
      next: r => { this.testResult.set(r); this.testing.set(false); },
      error: e => { this.testResult.set({ ok: false, error: e?.error?.error || 'Test failed' }); this.testing.set(false); },
    });
  }

  toggleEnabled(s: Site) {
    this.svc.update(s.id, { enabled: !s.enabled }).subscribe({ next: () => this.load() });
  }

  remove(s: Site) {
    if (!confirm(`Delete site "${s.name}"? Its monitoring will stop.`)) return;
    this.svc.remove(s.id).subscribe({ next: () => this.load(), error: () => this.error.set('Delete failed') });
  }

  trackById = (_: number, s: Site) => s.id;
}
