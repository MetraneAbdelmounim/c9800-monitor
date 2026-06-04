import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { SettingsService, WlcSettings, ConnectionTestResult, DemoModeStatus, SetupStatus } from '../../services/settings.service';

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

  ngOnInit() {
    this.loadDemo();
    this.load();
    this.loadSetupStatus(this.route.snapshot.queryParamMap.get('initial') === '1');
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
      this.host !== c.host ||
      this.port !== c.port ||
      this.username !== c.username ||
      this.verifySsl !== c.verify_ssl ||
      this.password.length > 0
    );
  }
}
