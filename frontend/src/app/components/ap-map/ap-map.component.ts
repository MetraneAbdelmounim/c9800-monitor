import {
  Component, OnInit, OnDestroy, AfterViewInit, ViewChild, ElementRef, HostListener, inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WlcService } from '../../services/wlc.service';
import { MapService } from '../../services/map.service';
import { AuthService } from '../../services/auth.service';
import { TrackingService, GraphLink } from '../../services/tracking.service';
import { AccessPoint, WirelessClient, FloorSummary, Floor, ApPlacement } from '../../models/models';
import { SpinnerComponent } from '../spinner/spinner.component';

interface Marker {
  p: ApPlacement;
  ap?: AccessPoint;
  clients: number;
  cls: 'up' | 'down' | 'warn' | 'unknown';
  channel: number;
  located: boolean;
}
interface ApAgg { count: number; rssiSum: number; rssiN: number; chan: Record<number, number>; }
interface RoamLine { x1: number; y1: number; x2: number; y2: number; w: number; color: string; count: number; mx: number; my: number; }
interface CoverageCircle { x: number; y: number; color: string; channel: number; warn: boolean; }

@Component({
  selector: 'app-ap-map',
  standalone: true,
  imports: [CommonModule, FormsModule, SpinnerComponent],
  templateUrl: './ap-map.component.html',
  styleUrl: './ap-map.component.css',
})
export class ApMapComponent implements OnInit, OnDestroy, AfterViewInit {
  @ViewChild('mapArea') mapArea?: ElementRef<HTMLElement>;
  @ViewChild('heatCanvas') heatCanvas?: ElementRef<HTMLCanvasElement>;

  private wlc = inject(WlcService);
  private map = inject(MapService);
  private track = inject(TrackingService);
  readonly auth = inject(AuthService);

  // Floors
  floors: FloorSummary[] = [];
  currentFloorId: string | null = null;
  currentFloor: Floor | null = null;
  private floorCache = new Map<string, Floor>();

  // Placements (working copy for the current floor)
  placements: ApPlacement[] = [];
  dirty = false;

  // Live AP data
  private aps: AccessPoint[] = [];
  private apByMac = new Map<string, AccessPoint>();
  private clients: WirelessClient[] = [];
  private apAgg: Record<string, ApAgg> = {};
  private clientCountByAp: Record<string, number> = {};

  // Layers (view mode)
  showHeatmap = false;
  showRoaming = false;
  showCoverage = false;
  private roamLinks: GraphLink[] = [];
  private roamLoaded = false;

  // Locator
  locateQuery = '';
  locatedApName: string | null = null;
  locateMsg = '';

  // UI state
  loading = true;
  error = '';
  editMode = false;
  armedMac: string | null = null;
  private dragMac: string | null = null;
  private dragMoved = false;
  selected: Marker | null = null;

  // Add-floor form
  showFloorForm = false;
  newFloor = { name: '', building: '' };
  pendingImage = '';
  saving = false;

  private iv: any;

  ngOnInit() {
    this.loadFloors();
    this.loadLive();
    this.iv = setInterval(() => { if (!this.editMode) this.loadLive(); }, 15000);
  }
  ngAfterViewInit() { this.scheduleHeatRedraw(); }
  ngOnDestroy() { clearInterval(this.iv); }

  @HostListener('window:resize') onResize() { this.scheduleHeatRedraw(); }

  get isAdmin(): boolean { return this.auth.hasRole('admin'); }

  // ── Floor list / selection ───────────────────────────
  get buildings(): { name: string; floors: FloorSummary[] }[] {
    const groups = new Map<string, FloorSummary[]>();
    for (const f of this.floors) {
      const b = f.building || 'Unassigned';
      (groups.get(b) || groups.set(b, []).get(b)!).push(f);
    }
    return [...groups.entries()].map(([name, floors]) => ({ name, floors }));
  }

  loadFloors(selectId?: string) {
    this.map.listFloors().subscribe({
      next: r => {
        this.floors = r.floors || [];
        const target = selectId
          || (this.currentFloorId && this.floors.some(f => f.id === this.currentFloorId) ? this.currentFloorId : null)
          || (this.floors[0]?.id ?? null);
        if (target) this.selectFloor(target);
        else { this.currentFloorId = null; this.currentFloor = null; this.placements = []; this.loading = false; }
      },
      error: () => { this.error = 'Failed to load floors'; this.loading = false; },
    });
  }

  selectFloor(id: string) {
    this.currentFloorId = id;
    this.selected = null;
    this.armedMac = null;
    this.dirty = false;
    this.locatedApName = null;
    this.locateMsg = '';
    const cached = this.floorCache.get(id);
    if (cached) { this.currentFloor = cached; this.scheduleHeatRedraw(); }
    else {
      this.map.getFloor(id).subscribe({
        next: f => { this.floorCache.set(id, f); if (this.currentFloorId === id) { this.currentFloor = f; this.scheduleHeatRedraw(); } },
        error: () => this.error = 'Failed to load floor plan',
      });
    }
    this.map.getPlacements(id).subscribe({
      next: r => { if (this.currentFloorId === id) this.placements = r.placements || []; this.loading = false; this.scheduleHeatRedraw(); },
      error: () => { this.placements = []; this.loading = false; },
    });
  }

  // ── Live AP / client data ────────────────────────────
  private loadLive() {
    this.wlc.getAllAps().subscribe({
      next: aps => {
        this.aps = aps;
        this.apByMac.clear();
        for (const ap of aps) {
          if (ap.wtp_mac) this.apByMac.set(ap.wtp_mac.toLowerCase(), ap);
          if (ap.mac) this.apByMac.set(ap.mac.toLowerCase(), ap);
        }
        this.scheduleHeatRedraw();
      },
      error: () => {},
    });
    this.wlc.getClientDetails().subscribe({
      next: d => {
        this.clients = d.clients || [];
        const agg: Record<string, ApAgg> = {};
        const counts: Record<string, number> = {};
        for (const c of this.clients) {
          if (!c.ap_name) continue;
          counts[c.ap_name] = (counts[c.ap_name] || 0) + 1;
          const a = agg[c.ap_name] || (agg[c.ap_name] = { count: 0, rssiSum: 0, rssiN: 0, chan: {} });
          a.count++;
          if (c.rssi_dbm) { a.rssiSum += c.rssi_dbm; a.rssiN++; }
          if (c.channel) a.chan[c.channel] = (a.chan[c.channel] || 0) + 1;
        }
        this.apAgg = agg;
        this.clientCountByAp = counts;
        this.scheduleHeatRedraw();
      },
      error: () => {},
    });
  }

  private avgRssi(apName: string): number {
    const a = this.apAgg[apName];
    return a && a.rssiN ? Math.round(a.rssiSum / a.rssiN) : 0;
  }
  private channelOf(apName: string): number {
    const a = this.apAgg[apName];
    if (!a) return 0;
    let best = 0, bestN = -1;
    for (const [ch, n] of Object.entries(a.chan)) if (n > bestN) { bestN = n; best = +ch; }
    return best;
  }

  // ── Derived rendering data ───────────────────────────
  get markers(): Marker[] {
    return this.placements.map(p => {
      const ap = this.apByMac.get((p.ap_mac || '').toLowerCase());
      const name = ap?.name || p.ap_name;
      return {
        p, ap,
        clients: ap ? (this.clientCountByAp[ap.name] || 0) : 0,
        cls: this.stateClass(ap),
        channel: this.channelOf(name),
        located: !!this.locatedApName && name?.toLowerCase() === this.locatedApName,
      };
    });
  }

  get unplacedAps(): AccessPoint[] {
    const placed = new Set(this.placements.map(p => (p.ap_mac || '').toLowerCase()));
    return this.aps
      .filter(ap => !placed.has((ap.wtp_mac || '').toLowerCase()))
      .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
  }

  private posByApName(): Record<string, { x: number; y: number }> {
    const m: Record<string, { x: number; y: number }> = {};
    for (const p of this.placements) {
      const ap = this.apByMac.get((p.ap_mac || '').toLowerCase());
      const name = (ap?.name || p.ap_name || '').toLowerCase();
      if (name) m[name] = { x: p.x, y: p.y };
    }
    return m;
  }

  get roamLines(): RoamLine[] {
    if (!this.showRoaming) return [];
    const pos = this.posByApName();
    const lines: RoamLine[] = [];
    for (const l of this.roamLinks) {
      const a = pos[(l.source || '').toLowerCase()];
      const b = pos[(l.target || '').toLowerCase()];
      if (!a || !b) continue;
      lines.push({
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2,
        w: Math.min(6, 1 + l.count / 3),
        color: l.count > 5 ? '#C8102E' : '#E8A838',
        count: l.count,
      });
    }
    return lines;
  }

  get coverageCircles(): CoverageCircle[] {
    if (!this.showCoverage) return [];
    const circles = this.markers
      .filter(m => m.channel > 0)
      .map(m => ({ x: m.p.x, y: m.p.y, channel: m.channel, color: this.channelColor(m.channel), warn: false }));
    // flag co-channel neighbours (same channel, close together)
    for (let i = 0; i < circles.length; i++)
      for (let j = i + 1; j < circles.length; j++)
        if (circles[i].channel === circles[j].channel) {
          const d = Math.hypot(circles[i].x - circles[j].x, circles[i].y - circles[j].y);
          if (d < 22) { circles[i].warn = true; circles[j].warn = true; }
        }
    return circles;
  }

  stateClass(ap?: AccessPoint): Marker['cls'] {
    if (!ap) return 'unknown';
    const s = (ap.state || '').toLowerCase();
    if (s.includes('registered') || s.includes('run')) return 'up';
    if (s.includes('down') || s.includes('disabled')) return 'down';
    return 'warn';
  }

  // ── Layer toggles ────────────────────────────────────
  toggleHeatmap() { this.showHeatmap = !this.showHeatmap; this.scheduleHeatRedraw(); }
  toggleCoverage() { this.showCoverage = !this.showCoverage; }
  toggleRoaming() {
    this.showRoaming = !this.showRoaming;
    if (this.showRoaming && !this.roamLoaded) this.loadRoaming();
  }
  private loadRoaming() {
    this.track.getRoamingGraph('last24h').subscribe({
      next: g => { this.roamLinks = g.links || []; this.roamLoaded = true; },
      error: () => { this.roamLinks = []; },
    });
  }

  // ── Locator ──────────────────────────────────────────
  locate() {
    const q = this.locateQuery.trim().toLowerCase();
    this.locatedApName = null;
    this.locateMsg = '';
    if (!q) return;
    const c = this.clients.find(x =>
      (x.mac || '').toLowerCase().includes(q) ||
      (x.ip || '').toLowerCase().includes(q) ||
      (x.hostname || '').toLowerCase().includes(q) ||
      (x.username || '').toLowerCase().includes(q));
    if (!c) { this.locateMsg = 'No connected client matches that.'; return; }
    if (!c.ap_name) { this.locateMsg = `${c.hostname || c.mac}: AP unknown.`; return; }
    const onThisFloor = this.placements.some(p => {
      const ap = this.apByMac.get((p.ap_mac || '').toLowerCase());
      return (ap?.name || p.ap_name || '').toLowerCase() === c.ap_name.toLowerCase();
    });
    this.locatedApName = c.ap_name.toLowerCase();
    this.locateMsg = onThisFloor
      ? `${c.hostname || c.mac} → ${c.ap_name} (${c.band}, ${c.rssi_dbm} dBm)`
      : `${c.hostname || c.mac} is on ${c.ap_name}, which isn't placed on this floor.`;
  }
  clearLocate() { this.locateQuery = ''; this.locatedApName = null; this.locateMsg = ''; }

  // ── Edit mode ────────────────────────────────────────
  toggleEdit() {
    this.editMode = !this.editMode;
    this.armedMac = null;
    this.selected = null;
    if (this.editMode) {
      this.showHeatmap = this.showRoaming = this.showCoverage = false;
      this.scheduleHeatRedraw();
      this.loadLive();
    }
  }
  armAp(ap: AccessPoint) { this.armedMac = this.armedMac === ap.wtp_mac ? null : ap.wtp_mac; }

  removePlacement(mac: string) {
    this.placements = this.placements.filter(p => p.ap_mac !== mac);
    this.dirty = true;
    if (this.selected?.p.ap_mac === mac) this.selected = null;
  }

  private coordsFromEvent(e: MouseEvent): { x: number; y: number } | null {
    const el = this.mapArea?.nativeElement;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return null;
    return {
      x: Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100)),
      y: Math.max(0, Math.min(100, ((e.clientY - r.top) / r.height) * 100)),
    };
  }

  onMapClick(e: MouseEvent) {
    if (!this.editMode || !this.armedMac || this.dragMoved) { this.dragMoved = false; return; }
    const c = this.coordsFromEvent(e);
    if (!c) return;
    const ap = this.aps.find(a => a.wtp_mac === this.armedMac);
    this.placements = [...this.placements, { ap_mac: this.armedMac, ap_name: ap?.name || '', x: c.x, y: c.y }];
    this.dirty = true;
    this.armedMac = null;
  }

  onMarkerMouseDown(mac: string, e: MouseEvent) {
    if (!this.editMode) return;
    e.stopPropagation();
    this.dragMac = mac;
    this.dragMoved = false;
  }
  onMapMouseMove(e: MouseEvent) {
    if (!this.dragMac) return;
    const c = this.coordsFromEvent(e);
    if (!c) return;
    this.dragMoved = true;
    this.placements = this.placements.map(p => p.ap_mac === this.dragMac ? { ...p, x: c.x, y: c.y } : p);
    this.dirty = true;
  }
  onMapMouseUp() { this.dragMac = null; }

  onMarkerClick(m: Marker, e: MouseEvent) {
    e.stopPropagation();
    if (this.editMode) return;
    this.selected = this.selected?.p.ap_mac === m.p.ap_mac ? null : m;
  }

  save() {
    if (!this.currentFloorId) return;
    this.saving = true;
    this.map.savePlacements(this.currentFloorId, this.placements).subscribe({
      next: () => { this.dirty = false; this.saving = false; },
      error: () => { this.error = 'Failed to save placements'; this.saving = false; },
    });
  }
  discard() { if (this.currentFloorId) this.selectFloor(this.currentFloorId); }

  // ── Floor admin ──────────────────────────────────────
  onFileSelected(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    if (file.size > 9_000_000) { this.error = 'Image too large (max ~9 MB)'; return; }
    const reader = new FileReader();
    reader.onload = () => { this.pendingImage = reader.result as string; };
    reader.readAsDataURL(file);
  }
  createFloor() {
    if (!this.newFloor.name.trim() || !this.pendingImage) return;
    this.saving = true;
    this.map.createFloor({
      name: this.newFloor.name.trim(),
      building: this.newFloor.building.trim(),
      image: this.pendingImage,
    }).subscribe({
      next: f => {
        this.floorCache.set(f.id, f);
        this.showFloorForm = false;
        this.newFloor = { name: '', building: '' };
        this.pendingImage = '';
        this.saving = false;
        this.loadFloors(f.id);
      },
      error: () => { this.error = 'Failed to create floor'; this.saving = false; },
    });
  }
  deleteFloor() {
    if (!this.currentFloorId) return;
    if (!confirm('Delete this floor plan and all its AP placements?')) return;
    const id = this.currentFloorId;
    this.map.deleteFloor(id).subscribe({
      next: () => {
        this.floorCache.delete(id);
        this.currentFloorId = null; this.currentFloor = null; this.placements = []; this.editMode = false;
        this.loadFloors();
      },
      error: () => this.error = 'Failed to delete floor',
    });
  }

  // ── Heatmap rendering ────────────────────────────────
  onImgLoad() { this.scheduleHeatRedraw(); }
  private scheduleHeatRedraw() { setTimeout(() => this.drawHeatmap(), 0); }

  private drawHeatmap() {
    const cv = this.heatCanvas?.nativeElement;
    const area = this.mapArea?.nativeElement;
    if (!cv || !area) return;
    const w = area.clientWidth, h = area.clientHeight;
    if (!w || !h) return;
    cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    if (!this.showHeatmap || this.editMode) return;

    const pts = this.markers
      .filter(m => m.ap)
      .map(m => ({ x: m.p.x / 100 * w, y: m.p.y / 100 * h, rssi: this.avgRssi(m.ap!.name) || -72 }));
    if (!pts.length) return;

    const step = 10;
    const R = Math.max(w, h) * 0.5;       // influence radius
    ctx.filter = 'blur(12px)';
    for (let py = 0; py < h; py += step) {
      for (let px = 0; px < w; px += step) {
        let best = -120;
        for (const p of pts) {
          const d = Math.hypot(px - p.x, py - p.y);
          const est = p.rssi - (d / R) * 38;   // ~38 dB loss across the influence radius
          if (est > best) best = est;
        }
        ctx.fillStyle = this.rssiHeatColor(best);
        ctx.fillRect(px, py, step, step);
      }
    }
    ctx.filter = 'none';
  }

  private rssiHeatColor(d: number): string {
    let r: number, g: number, b: number;
    if (d >= -55) { r = 52; g = 199; b = 89; }
    else if (d >= -67) { r = 120; g = 200; b = 80; }
    else if (d >= -72) { r = 232; g = 168; b = 56; }
    else if (d >= -80) { r = 224; g = 120; b = 48; }
    else { r = 200; g = 16; b = 46; }
    const a = d < -88 ? 0.10 : 0.42;
    return `rgba(${r},${g},${b},${a})`;
  }

  // ── Helpers ──────────────────────────────────────────
  markerColor(cls: Marker['cls']): string {
    return { up: '#34C759', down: '#C8102E', warn: '#E8A838', unknown: '#706868' }[cls];
  }
  channelColor(ch: number): string { return `hsl(${(ch * 47) % 360}, 70%, 55%)`; }
  formatUptime(sec?: number): string {
    if (!sec || sec <= 0) return '—';
    const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }
}
