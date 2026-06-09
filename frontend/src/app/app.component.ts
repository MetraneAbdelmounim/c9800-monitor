import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router, NavigationEnd } from '@angular/router';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { filter } from 'rxjs/operators';
import { WlcService } from './services/wlc.service';
import { AuthService } from './services/auth.service';
import { ThemeService } from './services/theme.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit, OnDestroy {
  healthy = false;
  hideChrome = false;
  private iv: any;

  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);
  private router = inject(Router);

  navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '▦' },
    { path: '/access-points', label: 'Access Points', icon: '▲' },
    { path: '/map', label: 'AP Map', icon: '⌖' },
    { path: '/clients', label: 'Clients', icon: '○' },
    { path: '/client-experience', label: 'Experience', icon: '◈' },
    { path: '/wlans', label: 'WLANs', icon: '◉' },
    { path: '/tracking', label: 'Tracking', icon: '◔' },
    { path: '/trends', label: 'Trends', icon: '📈' },
    { path: '/roaming-graph', label: 'Roaming Graph', icon: '⬡' },
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
    { path: '/settings', label: 'WLC Settings', icon: '⚒' },
  ];

  constructor(private http: HttpClient, private wlc: WlcService) {}

  ngOnInit() {
    this.updateChromeVisibility(this.router.url);
    this.router.events
      .pipe(filter(e => e instanceof NavigationEnd))
      .subscribe(e => this.updateChromeVisibility((e as NavigationEnd).urlAfterRedirects));
    this.check();
    this.iv = setInterval(() => this.check(), 30000);
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
    this.hideChrome = url.startsWith('/login');
  }
}
