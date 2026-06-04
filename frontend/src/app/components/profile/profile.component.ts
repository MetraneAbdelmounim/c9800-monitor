import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { switchMap } from 'rxjs';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.css',
})
export class ProfileComponent implements OnInit {
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  readonly user = this.auth.user;
  readonly forced = signal(false);

  newPassword = '';
  confirmPassword = '';

  saving = signal(false);
  error = signal<string | null>(null);
  success = signal<string | null>(null);

  ngOnInit() {
    // ?forced=1 means the route was redirected here because of must_change_password
    this.forced.set(
      this.auth.mustChangePassword() ||
      this.route.snapshot.queryParamMap.get('forced') === '1'
    );
  }

  submit() {
    this.error.set(null);
    this.success.set(null);
    if (!this.newPassword) { this.error.set('Password required'); return; }
    if (this.newPassword.length < 8) { this.error.set('Password must be at least 8 characters'); return; }
    if (this.newPassword !== this.confirmPassword) { this.error.set('Passwords do not match'); return; }

    this.saving.set(true);
    // Change pw, then refresh user state so must_change_password is cleared.
    this.auth.changeOwnPassword(this.newPassword)
      .pipe(switchMap(() => this.auth.refreshMe()))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.success.set('Password updated.');
          this.newPassword = '';
          this.confirmPassword = '';
          // If this was a forced flow, send the user onward.
          if (this.forced()) {
            // Admin going through first-run flow → next stop is /settings.
            // Otherwise → dashboard.
            const next = this.auth.hasRole('admin') ? '/settings' : '/dashboard';
            setTimeout(() => this.router.navigateByUrl(next + '?initial=1'), 600);
          }
        },
        error: err => {
          this.saving.set(false);
          this.error.set(err?.error?.error || 'Failed to update password');
        },
      });
  }
}
