import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { SiteContextService } from '../../services/site-context.service';
import { SpinnerComponent } from '../spinner/spinner.component';

interface SiteCard {
  id: string; name: string; location: string; reachable: boolean;
  total_aps: number; online_aps: number; clients: number; cpu: number; mem: number;
  alerts: number; updated_at: string | null;
}
interface Overview {
  totals: { sites: number; sites_online: number; total_aps: number; online_aps: number; clients: number; alerts: number };
  sites: SiteCard[];
}

@Component({
  selector: 'app-overview',
  standalone: true,
  imports: [CommonModule, SpinnerComponent],
  templateUrl: './overview.component.html',
  styleUrl: './overview.component.css',
})
export class OverviewComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private router = inject(Router);
  private siteCtx = inject(SiteContextService);

  data = signal<Overview | null>(null);
  error = signal('');
  private iv: any;

  ngOnInit() {
    this.load();
    this.iv = setInterval(() => this.load(), 20000);
  }
  ngOnDestroy() { clearInterval(this.iv); }

  load() {
    this.http.get<Overview>('/api/overview').subscribe({
      next: d => { this.data.set(d); this.error.set(''); },
      error: () => this.error.set('Failed to load overview'),
    });
  }

  open(s: SiteCard) {
    this.siteCtx.setSite(s.id);
    this.router.navigate(['/dashboard']);
  }

  health(s: SiteCard): 'down' | 'warn' | 'ok' {
    if (!s.reachable) return 'down';
    if (s.alerts > 0 || (s.total_aps && s.online_aps < s.total_aps)) return 'warn';
    return 'ok';
  }
}
