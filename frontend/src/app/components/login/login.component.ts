import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { catchError, of, switchMap } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { SettingsService } from '../../services/settings.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  username = '';
  password = '';
  error = '';
  loading = false;

  constructor(
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
    private settings: SettingsService,
  ) {}

  submit() {
    if (!this.username || !this.password) {
      this.error = 'Username and password required';
      return;
    }
    this.error = '';
    this.loading = true;
    this.auth.login(this.username.trim(), this.password)
      .pipe(
        switchMap(res => {
          // If the user must rotate their password, skip the setup probe.
          if (res.user.must_change_password) {
            return of({ user: res.user, setup_complete: true });
          }
          return this.settings.getSetupStatus().pipe(
            // Setup probe failures shouldn't block login.
            catchError(() => of({ setup_complete: true, demo_mode: false, user_count: 0 })),
            switchMap(s => of({ user: res.user, setup_complete: s.setup_complete })),
          );
        })
      )
      .subscribe({
        next: ({ user, setup_complete }) => {
          // 1) Forced password change wins over everything.
          if (user.must_change_password) {
            this.router.navigateByUrl('/profile?forced=1');
            return;
          }
          // 2) Admin first-run → onboarding on the settings page.
          if (user.role === 'admin' && !setup_complete) {
            this.router.navigateByUrl('/settings?initial=1');
            return;
          }
          // 3) Normal flow: respect returnUrl, else dashboard.
          const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') || '/dashboard';
          this.router.navigateByUrl(returnUrl);
        },
        error: err => {
          this.loading = false;
          this.error = err?.error?.error || 'Login failed';
        }
      });
  }
}
