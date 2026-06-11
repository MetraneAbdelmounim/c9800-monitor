import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { LicenseService, LicenseInfo } from '../../services/license.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-licensing',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './licensing.component.html',
  styleUrl: './licensing.component.css',
})
export class LicensingComponent implements OnInit {
  private svc = inject(LicenseService);
  private auth = inject(AuthService);
  private router = inject(Router);

  info: LicenseInfo | null = null;
  key = '';
  fileName = '';
  busy = false;
  error = '';

  get isAdmin(): boolean { return this.auth.hasRole('admin'); }

  ngOnInit() {
    this.svc.status(true).subscribe({
      next: i => this.info = i,
      error: () => this.info = { valid: false },
    });
  }

  onFile(ev: Event) {
    const input = ev.target as HTMLInputElement;
    const file = input.files && input.files[0];
    if (!file) return;
    this.fileName = file.name;
    const reader = new FileReader();
    reader.onload = () => { this.key = String(reader.result || '').trim(); };
    reader.readAsText(file);
  }

  activate() {
    const key = this.key.trim();
    if (!key) { this.error = 'Paste your license key or choose the license file.'; return; }
    this.busy = true; this.error = '';
    this.svc.activate(key).subscribe({
      next: i => {
        this.busy = false;
        this.info = i;
        if (i.valid) this.router.navigate(['/dashboard']);
        else this.error = i.error || 'License is not valid.';
      },
      error: e => {
        this.busy = false;
        this.error = e?.error?.error || 'Activation failed — check the key and try again.';
      },
    });
  }

  logout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}