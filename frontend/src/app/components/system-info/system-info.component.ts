import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WlcService } from '../../services/wlc.service';
import { SystemInfo, CpuUsage, MemoryUsage, HealthCheck } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

@Component({
  selector: 'app-system-info', standalone: true, imports: [CommonModule, SpinnerComponent],
  templateUrl: './system-info.component.html', styleUrl: './system-info.component.css'
})
export class SystemInfoComponent implements OnInit, OnDestroy {
  system: SystemInfo | null = null;
  cpu: CpuUsage | null = null;
  memory: MemoryUsage | null = null;
  health: HealthCheck | null = null;
  interfaces: any = null;
  rf: any = null;
  private iv: any;
  constructor(private wlc: WlcService) {}
  ngOnInit() { this.load(); this.iv = setInterval(() => this.load(), 10000); }
  ngOnDestroy() { clearInterval(this.iv); }
  load() {
    this.wlc.getSystemInfo().subscribe(d => this.system = d);
    this.wlc.getCpu().subscribe(d => this.cpu = d);
    this.wlc.getMemory().subscribe(d => this.memory = d);
    this.wlc.getHealth().subscribe(d => this.health = d);
    this.wlc.getInterfaces().subscribe(d => this.interfaces = d);
    this.wlc.getRf().subscribe(d => this.rf = d);
  }
  gaugeColor(v: number): string { return v < 50 ? '#34C759' : v < 80 ? '#E8A838' : '#C8102E'; }
}
