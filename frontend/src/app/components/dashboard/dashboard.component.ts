import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WlcService } from '../../services/wlc.service';
import { Dashboard } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, SpinnerComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit, OnDestroy {
  data: Dashboard | null = null;
  error = '';
  private interval: any;

  constructor(private wlc: WlcService) {}

  ngOnInit() {
    this.load();
    this.interval = setInterval(() => this.load(), 10000);
  }
  ngOnDestroy() { clearInterval(this.interval); }

  load() {
    this.wlc.getDashboard().subscribe({
      next: d => { this.data = d; this.error = ''; },
      error: e => this.error = 'Failed to load dashboard'
    });
  }

  gaugeColor(pct: number): string {
    if (pct < 50) return '#34C759';
    if (pct < 80) return '#E8A838';
    return '#C8102E';
  }
}
