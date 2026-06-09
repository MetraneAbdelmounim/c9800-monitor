import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { SettingsService, WlcSettings, ConnectionTestResult, DemoModeStatus, SetupStatus, CleanupSettings, CleanupSchedule } from '../../services/settings.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
})
export class SettingsComponent implements OnInit {
  private svc = inject(SettingsService);
  private route = inject(ActivatedRoute);

  // Server state
  current = signal<WlcSettings | null>(null);
  demo = signal<DemoModeStatus | null>(null);
  setup = signal<SetupStatus | null>(null);
  demoSaving = signal(false);
  demoError = signal<string | null>(null);
  loading = signal(true);
  loadError = signal<string | null>(null);

  // Show the first-run banner if explicitly invoked or if setup isn't done yet.
  readonly showSetupBanner = signal(false);

  // Form state
  vendor = 'cisco';
  host = '';
  port: number = 443;
  username = '';
  password = '';      // empty = unchanged
  verifySsl = false;

  // UI state
  saving = signal(false);
  testing = signal(false);
  saveError = signal<string | null>(null);
  saveSuccess = signal<string | null>(null);
  testResult = signal<ConnectionTestResult | null>(null);

  // ── Data-cleanup state ───────────────────────────────
  cleanup = signal<CleanupSettings | null>(null);
  clEnabled = false;
  clSchedule: CleanupSchedule = 'weekly';
  clRetention = 7;
  clSaving = signal(false);
  clRunning = signal(false);
  clError = signal<string | null>(null);
  clMsg = signal<string | null>(null);

  readonly scheduleOptions: { value: CleanupSchedule; label: string }[] = [
    { value: '5min', label: 'Every 5 minutes' },
    { value: 'hourly', label: 'Every hour' },
    { value: 'daily', label: 'Every day (midnight)' },
    { value: 'weekly', label: 'Every Sunday (midnight)' },
    { value: 'monthly', label: 'Every month (1st)' },
  ];

  ngOnInit() {
    this.loadDemo();
    this.load();
    this.loadCleanup();
    this.loadSetupStatus(this.route.snapshot.queryParamMap.get('initial') === '1');
  }

  // ── Cleanup ──────────────────────────────────────────
  loadCleanup() {
    this.svc.getCleanup().subscribe({
      next: c => {
        this.cleanup.set(c);
        this.clEnabled = c.enabled;
        this.clSchedule = c.schedule;
        this.clRetention = c.retention_days;
      },
      error: () => this.cleanup.set(null),
    });
  }

  saveCleanup() {
    this.clError.set(null);
    this.clMsg.set(null);
    if (this.clRetention < 0) { this.clError.set('Retention days cannot be negative'); return; }
    this.clSaving.set(true);
    this.svc.saveCleanup({
      enabled: this.clEnabled,
      schedule: this.clSchedule,
      retention_days: Math.floor(this.clRetention),
    }).subscribe({
      next: c => { this.cleanup.set(c); this.clSaving.set(false); this.clMsg.set('Cleanup schedule saved.'); },
      error: err => { this.clSaving.set(false); this.clError.set(err?.error?.error || 'Failed to save cleanup settings'); },
    });
  }

  runCleanupNow() {
    if (!confirm(this.clRetention > 0
      ? `Delete tracking/roaming records older than ${this.clRetention} day(s) now?`
      : 'Delete ALL tracking/roaming history now?')) return;
    this.clError.set(null);
    this.clMsg.set(null);
    this.clRunning.set(true);
    this.svc.runCleanup().subscribe({
      next: r => { this.clRunning.set(false); this.clMsg.set(`Removed ${r.deleted} record(s).`); this.loadCleanup(); },
      error: err => { this.clRunning.set(false); this.clError.set(err?.error?.error || 'Cleanup failed'); },
    });
  }

  cleanupTotal(): number {
    const s = this.cleanup()?.stats;
    if (!s) return 0;
    return Object.values(s).reduce((a, b) => a + (b || 0), 0);
  }

  loadSetupStatus(forceBanner = false) {
    this.svc.getSetupStatus().subscribe({
      next: s => {
        this.setup.set(s);
        this.showSetupBanner.set(forceBanner || !s.setup_complete);
      },
      error: () => this.setup.set(null),
    });
  }

  loadDemo() {
    this.svc.getDemoMode().subscribe({
      next: r => this.demo.set(r),
      error: () => this.demo.set(null),
    });
  }

  toggleDemoMode(enabled: boolean) {
    this.demoError.set(null);
    this.demoSaving.set(true);
    this.svc.setDemoMode(enabled).subscribe({
      next: () => {
        this.demoSaving.set(false);
        this.loadDemo();
        // The live client just got swapped — reload WLC settings view too,
        // so the user sees the right source pill / state.
        this.load();
      },
      error: err => {
        this.demoSaving.set(false);
        this.demoError.set(err?.error?.error || 'Failed to update demo mode');
      },
    });
  }

  resetDemoOverride() {
    this.demoError.set(null);
    this.demoSaving.set(true);
    this.svc.resetDemoMode().subscribe({
      next: () => {
        this.demoSaving.set(false);
        this.loadDemo();
        this.load();
      },
      error: err => {
        this.demoSaving.set(false);
        this.demoError.set(err?.error?.error || 'Failed to reset override');
      },
    });
  }

  load() {
    this.loading.set(true);
    this.loadError.set(null);
    this.svc.getWlc().subscribe({
      next: s => {
        this.current.set(s);
        this.vendor = s.vendor || 'cisco';
        this.host = s.host;
        this.port = s.port;
        this.username = s.username;
        this.verifySsl = s.verify_ssl;
        this.password = '';
        this.loading.set(false);
      },
      error: err => {
        this.loadError.set(err?.error?.error || 'Failed to load WLC settings');
        this.loading.set(false);
      },
    });
  }

  testConnection() {
    this.testResult.set(null);
    this.testing.set(true);
    this.svc.testWlc({
      vendor: this.vendor,
      host: this.host.trim(),
      port: this.port,
      username: this.username.trim(),
      password: this.password,        // backend reuses stored one if empty
      verify_ssl: this.verifySsl,
    }).subscribe({
      next: r => { this.testResult.set(r); this.testing.set(false); },
      error: err => {
        this.testResult.set({
          ok: false,
          error: err?.error?.error || err?.message || 'Request failed',
          tested_host: this.host,
          tested_port: this.port,
        });
        this.testing.set(false);
      },
    });
  }

  save() {
    this.saveError.set(null);
    this.saveSuccess.set(null);
    if (!this.host.trim()) { this.saveError.set('Host is required'); return; }
    if (!this.port || this.port < 1 || this.port > 65535) {
      this.saveError.set('Port must be 1–65535'); return;
    }
    this.saving.set(true);
    this.svc.updateWlc({
      vendor: this.vendor,
      host: this.host.trim(),
      port: this.port,
      username: this.username.trim(),
      password: this.password || undefined,
      verify_ssl: this.verifySsl,
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.saveSuccess.set('WLC settings saved and live client reloaded.');
        this.password = '';
        this.load();
        // Setup might have just been marked complete by the backend.
        this.loadSetupStatus(false);
      },
      error: err => {
        this.saving.set(false);
        this.saveError.set(err?.error?.error || 'Failed to save settings');
      },
    });
  }

  dirty(): boolean {
    const c = this.current();
    if (!c) return false;
    return (
      this.vendor !== (c.vendor || 'cisco') ||
      this.host !== c.host ||
      this.port !== c.port ||
      this.username !== c.username ||
      this.verifySsl !== c.verify_ssl ||
      this.password.length > 0
    );
  }
}
