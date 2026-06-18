import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router, NavigationEnd } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { filter } from 'rxjs/operators';
import { WlcService } from './services/wlc.service';
import { AuthService } from './services/auth.service';
import { ThemeService } from './services/theme.service';
import { LicenseService } from './services/license.service';
import { SiteContextService } from './services/site-context.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit, OnDestroy {
  healthy = false;
  hideChrome = false;
  private iv: any;

  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);
  readonly siteCtx = inject(SiteContextService);
  private license = inject(LicenseService);
  private router = inject(Router);

  navItems = [
    { path: '/overview', label: 'Overview', icon: '🌐' },
    { path: '/dashboard', label: 'Dashboard', icon: '▦' },
    { path: '/access-points', label: 'Access Points', icon: '▲' },
    { path: '/map', label: 'AP Map', icon: '⌖' },
    { path: '/clients', label: 'Clients', icon: '○' },
    { path: '/client-experience', label: 'Experience', icon: '◈' },
    { path: '/wlans', label: 'WLANs', icon: '◉' },
    { path: '/tracking', label: 'Tracking', icon: '◔' },
    { path: '/trends', label: 'Trends', icon: '📈' },
    { path: '/roaming-graph', label: 'Roaming Graph', icon: '⬡' },
    { path: '/reports', label: 'Reports', icon: '🧾' },
    { path: '/system', label: 'System', icon: '⚙' },
  ];

  troubleshootNavItems = [
    { path: '/advisor', label: 'Advisor', icon: '💡' },
    { path: '/rf-conflicts', label: 'Ch. Conflicts', icon: '⚡' },
    { path: '/lifecycle', label: 'AP Lifecycle', icon: '↻' },
  ];

  securityNavItems = [
    { path: '/events', label: 'Event Log', icon: '⚠' },
  ];

  adminNavItems = [
    { path: '/admin', label: 'Users', icon: '◆' },
    { path: '/sites', label: 'Sites', icon: '🏢' },
    { path: '/settings', label: 'WLC Settings', icon: '⚒' },
    { path: '/licensing', label: 'License', icon: '🔑' },
  ];

  constructor(private http: HttpClient, private wlc: WlcService) {}

  ngOnInit() {
    this.updateChromeVisibility(this.router.url);
    this.router.events
      .pipe(filter(e => e instanceof NavigationEnd))
      .subscribe(() => {
        this.updateChromeVisibility(this.router.url);
        // Load the site list once the user is authenticated (after login nav).
        if (this.auth.isAuthenticated() && !this.siteCtx.loaded) {
          this.siteCtx.load().subscribe({ error: () => {} });
        }
      });
    if (this.auth.isAuthenticated() && !this.siteCtx.loaded) {
      this.siteCtx.load().subscribe({ error: () => {} });
    }
    this.check();
    this.iv = setInterval(() => this.check(), 30000);
  }

  /** Re-instantiate the current route so its data reloads for the new site. */
  onSiteChange(id: string) {
    this.siteCtx.setSite(id);
    const url = this.router.url.split('?')[0];
    this.router.navigateByUrl('/overview', { skipLocationChange: true })
      .then(() => this.router.navigateByUrl(url));
  }

  ngOnDestroy() { clearInterval(this.iv); }

  check() {
    this.wlc.getHealth().subscribe({
      next: d => this.healthy = d?.status === 'connected',
      error: () => this.healthy = false,
    });
  }

  logout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  private updateChromeVisibility(url: string) {
    // Full-screen (no sidebar) on login, and on the licensing page ONLY while
    // unlicensed (lockdown). A licensed admin revisiting keeps the sidebar.
    const onLicensing = url.startsWith('/licensing');
    this.hideChrome = url.startsWith('/login') || (onLicensing && !this.license.isValid());
  }
}
