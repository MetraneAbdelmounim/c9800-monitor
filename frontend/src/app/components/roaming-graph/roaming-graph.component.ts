import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { TrackingService, GraphNode, GraphLink, GraphData } from "../../services/tracking.service";
import { SpinnerComponent } from "../spinner/spinner.component";

declare var d3: any;

@Component({
  selector: "app-roaming-graph", standalone: true,
  imports: [CommonModule, FormsModule, SpinnerComponent],
  template: `
<div style="max-width:1400px">
  <h1 style="font-size:22px;font-weight:800;color:var(--text-1)">Roaming Graph</h1>
  <p style="font-size:12px;color:var(--text-muted);margin:2px 0 20px">Network graph of client roaming paths between access points</p>

  <div style="display:flex;gap:12px;margin-bottom:16px;align-items:center;flex-wrap:wrap">
    <div style="flex:1;min-width:200px;position:relative">
      <input type="text" [(ngModel)]="macFilter" (ngModelChange)="onFilterChange()"
        placeholder="Filter by client MAC (empty = all clients)..."
        style="width:100%;padding:12px 16px;font-size:13px;font-family:JetBrains Mono,monospace;background:var(--bg-card);border:2px solid var(--border);border-radius:10px;color:var(--text-1);outline:none"/>
    </div>
    <div style="display:flex;gap:4px">
      <button *ngFor="let r of ranges" (click)="setRange(r.v)"
        style="padding:8px 14px;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid var(--border);transition:all .2s"
        [style.background]="range===r.v?'rgba(62,107,176,0.10)':'var(--bg-card)'" [style.color]="range===r.v?'var(--brand-light)':'var(--text-3)'"
        [style.borderColor]="range===r.v?'rgba(62,107,176,0.3)':'var(--border)'">{{r.l}}</button>
    </div>
  </div>

  <!-- Stats bar -->
  <div *ngIf="graphData" style="display:flex;gap:16px;margin-bottom:16px">
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px 18px;display:flex;gap:20px;flex:1;font-size:12px">
      <div><span style="color:var(--text-muted)">APs:</span> <span style="color:#C8102E;font-family:JetBrains Mono,monospace;font-weight:700">{{graphData.nodes.length}}</span></div>
      <div><span style="color:var(--text-muted)">Roaming Paths:</span> <span style="color:#E8A838;font-family:JetBrains Mono,monospace;font-weight:700">{{graphData.links.length}}</span></div>
      <div><span style="color:var(--text-muted)">Total Roams:</span> <span style="color:#34C759;font-family:JetBrains Mono,monospace;font-weight:700">{{totalRoams}}</span></div>
      <div><span style="color:var(--text-muted)">Clients:</span> <span style="color:#5A9BD5;font-family:JetBrains Mono,monospace;font-weight:700">{{uniqueClients}}</span></div>
    </div>
  </div>

  <!-- Legend -->
  <div style="display:flex;gap:16px;margin-bottom:12px;font-size:11px;color:var(--text-3);align-items:center">
    <div style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;border-radius:50%;background:#C8102E;display:inline-block"></span> AP Node (size = client count)</div>
    <div style="display:flex;align-items:center;gap:6px"><span style="width:20px;height:3px;background:#E8A838;display:inline-block;border-radius:2px"></span> Roaming path (thickness = frequency)</div>
    <div style="display:flex;align-items:center;gap:6px"><span style="width:20px;height:3px;background:#C8102E;display:inline-block;border-radius:2px"></span> High-frequency roaming (>5)</div>
  </div>

  <!-- Graph container -->
  <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;overflow:hidden;position:relative">
    <div *ngIf="loading" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;z-index:5;background:rgba(28,28,28,0.8)">
      <app-spinner [inline]="true" label="Loading graph…"></app-spinner>
    </div>
    <div #graphContainer style="width:100%;height:600px"></div>
  </div>

  <!-- Tooltip / detail panel -->
  <div *ngIf="selectedNode" style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:18px 20px;margin-top:16px">
    <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:var(--text-muted);margin-bottom:12px">
      {{selectedNode.type === 'ap' ? 'ACCESS POINT' : 'CLIENT'}} DETAILS
    </div>
    <div style="display:flex;gap:24px;font-size:12px;flex-wrap:wrap">
      <div><span style="color:var(--text-3)">Name:</span> <span style="color:#C8102E;font-family:JetBrains Mono,monospace;font-weight:600">{{selectedNode.label}}</span></div>
      <div *ngIf="selectedNode.client_count"><span style="color:var(--text-3)">Clients:</span> <span style="color:#5A9BD5;font-family:JetBrains Mono,monospace;font-weight:600">{{selectedNode.client_count}}</span></div>
      <div *ngIf="selectedNode.roam_count"><span style="color:var(--text-3)">Roam Events:</span> <span style="color:#E8A838;font-family:JetBrains Mono,monospace;font-weight:600">{{selectedNode.roam_count}}</span></div>
      <div *ngIf="selectedNode.quality_avg"><span style="color:var(--text-3)">Avg Quality:</span> <span style="font-family:JetBrains Mono,monospace;font-weight:600" [style.color]="qc(selectedNode.quality_avg)">{{selectedNode.quality_avg}}</span></div>
    </div>
    <!-- Connected paths -->
    <div *ngIf="selectedLinks.length" style="margin-top:14px">
      <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;color:var(--text-muted);margin-bottom:8px">ROAMING PATHS</div>
      <div *ngFor="let l of selectedLinks" style="display:flex;align-items:center;gap:12px;padding:6px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span style="color:#E07830;font-weight:600;min-width:140px">{{getName(l.source)}}</span>
        <span style="color:var(--text-muted)">&#8596;</span>
        <span style="color:#34C759;font-weight:600;min-width:140px">{{getName(l.target)}}</span>
        <span style="color:#E8A838;font-family:JetBrains Mono,monospace;font-weight:700">{{l.count}}x</span>
        <span *ngIf="l.avg_quality" style="font-family:JetBrains Mono,monospace" [style.color]="qc(l.avg_quality)">Q:{{l.avg_quality}}</span>
      </div>
    </div>
  </div>
</div>`,
  styles: [`
    :host ::ng-deep .graph-tooltip {
      position: absolute; pointer-events: none; z-index: 10;
      background: var(--bg-hover); border: 1px solid #333; border-radius: 8px;
      padding: 8px 12px; font-size: 11px; color: var(--text-1);
      font-family: 'JetBrains Mono', monospace;
      box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
  `]
})
export class RoamingGraphComponent implements OnInit, OnDestroy, AfterViewInit {
  @ViewChild("graphContainer") container!: ElementRef;

  macFilter = "";
  range = "last2h";
  graphData: GraphData | null = null;
  selectedNode: GraphNode | null = null;
  selectedLinks: GraphLink[] = [];
  loading = false;
  totalRoams = 0;
  uniqueClients = 0;
  private sim: any;
  private svg: any;
  private iv: any;
  private d3Loaded = false;

  ranges = [
    { l: "1h", v: "last1h" }, { l: "2h", v: "last2h" },
    { l: "6h", v: "last6h" }, { l: "Today", v: "today" },
    { l: "24h", v: "last24h" }, { l: "7d", v: "last7d" },
  ];

  constructor(private ts: TrackingService) {}

  ngOnInit() {
    this.loadD3().then(() => {
      this.load();
      this.iv = setInterval(() => this.load(), 30000);
    });
  }
  ngAfterViewInit() {}
  ngOnDestroy() { clearInterval(this.iv); if (this.sim) this.sim.stop(); }

  setRange(r: string) { this.range = r; this.load(); }
  onFilterChange() { this.load(); }

  private load() {
    this.loading = true;
    const mac = this.macFilter.trim() || undefined;
    this.ts.getRoamingGraph(this.range, mac).subscribe({
      next: d => {
        this.graphData = d;
        this.totalRoams = d.links.reduce((s, l) => s + l.count, 0);
        this.uniqueClients = new Set(d.links.map(l => l.mac).filter(Boolean)).size;
        this.selectedNode = null; this.selectedLinks = [];
        this.loading = false;
        setTimeout(() => this.renderGraph(), 50);
      },
      error: () => { this.loading = false; }
    });
  }

  private loadD3(): Promise<void> {
    if (this.d3Loaded) return Promise.resolve();
    return new Promise(res => {
      if (typeof d3 !== "undefined") { this.d3Loaded = true; res(); return; }
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js";
      s.onload = () => { this.d3Loaded = true; res(); };
      document.head.appendChild(s);
    });
  }

  private renderGraph() {
    if (!this.d3Loaded || !this.graphData || !this.container?.nativeElement) return;
    const el = this.container.nativeElement;
    el.innerHTML = "";

    const W = el.clientWidth || 900, H = 600;
    const data = this.graphData;
    if (!data.nodes.length) {
      el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:14px">No roaming events in this time range</div>';
      return;
    }

    // Build node map
    const nodeMap = new Map<string, GraphNode>();
    data.nodes.forEach(n => nodeMap.set(n.id, { ...n }));
    const nodes = Array.from(nodeMap.values());
    const links = data.links.map(l => ({
      ...l,
      //@ts-ignore
      source: typeof l.source === "string" ? l.source : l.source.id,
      //@ts-ignore
      target: typeof l.target === "string" ? l.target : l.target.id,
    }));

    // Max values for scaling
    const maxClients = Math.max(1, ...nodes.map(n => n.client_count || 1));
    const maxCount = Math.max(1, ...links.map(l => l.count));

    // SVG
    this.svg = d3.select(el).append("svg")
      .attr("width", W).attr("height", H)
      .style("background", "#141414");

    // Defs for arrow markers
    const defs = this.svg.append("defs");
    defs.append("marker")
      .attr("id", "arrow").attr("viewBox", "0 -5 10 10")
      .attr("refX", 25).attr("refY", 0).attr("markerWidth", 6).attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#8a93a3");

    // Glow filter
    const filter = defs.append("filter").attr("id", "glow");
    filter.append("feGaussianBlur").attr("stdDeviation", "3").attr("result", "blur");
    filter.append("feMerge").selectAll("feMergeNode")
      .data(["blur", "SourceGraphic"]).enter()
      .append("feMergeNode").attr("in", (d: string) => d);

    // Zoom
    const g = this.svg.append("g");
    this.svg.call(d3.zoom().scaleExtent([0.3, 4]).on("zoom", (e: any) => g.attr("transform", e.transform)));

    // Force simulation
    this.sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id((d: any) => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide().radius((d: any) => this.nodeRadius(d, maxClients) + 10));

    // Links
    const link = g.append("g").selectAll("line")
      .data(links).enter().append("line")
      .attr("stroke", (d: any) => d.count > 5 ? "#C8102E" : "#E8A838")
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", (d: any) => Math.max(1.5, Math.min(8, (d.count / maxCount) * 8)))
      .attr("marker-end", "url(#arrow)");

    // Link labels (roam count)
    const linkLabel = g.append("g").selectAll("text")
      .data(links).enter().append("text")
      .text((d: any) => d.count > 1 ? d.count + "x" : "")
      .attr("fill", "#aab2bf").attr("font-size", "9px")
      .attr("font-family", "JetBrains Mono, monospace")
      .attr("text-anchor", "middle").attr("dy", -6);

    // Nodes
    const node = g.append("g").selectAll("g")
      .data(nodes).enter().append("g")
      .style("cursor", "pointer")
      .call(d3.drag()
        .on("start", (e: any, d: any) => { if (!e.active) this.sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (e: any, d: any) => { d.fx = e.x; d.fy = e.y; })
        .on("end", (e: any, d: any) => { if (!e.active) this.sim.alphaTarget(0); d.fx = null; d.fy = null; })
      );

    // Node circles
    node.append("circle")
      .attr("r", (d: any) => this.nodeRadius(d, maxClients))
      .attr("fill", (d: any) => {
        const q = d.quality_avg || 70;
        if (q >= 80) return "#34C759";
        if (q >= 60) return "#5A9BD5";
        if (q >= 40) return "#E8A838";
        return "#C8102E";
      })
      .attr("stroke", "var(--bg-page)").attr("stroke-width", 2)
      .attr("filter", "url(#glow)");

    // Node labels
    node.append("text")
      .text((d: any) => this.shortLabel(d.label))
      .attr("fill", "#ffffff").attr("font-size", "10px")
      .attr("font-family", "JetBrains Mono, monospace").attr("font-weight", "600")
      .attr("text-anchor", "middle").attr("dy", (d: any) => this.nodeRadius(d, maxClients) + 14);

    // Client count inside node
    node.append("text")
      .text((d: any) => d.client_count ? d.client_count : "")
      .attr("fill", "#ffffff").attr("font-size", "11px")
      .attr("font-family", "JetBrains Mono, monospace").attr("font-weight", "800")
      .attr("text-anchor", "middle").attr("dy", 4);

    // Tooltip
    const tooltip = d3.select(el).append("div").attr("class", "graph-tooltip").style("display", "none");

    node.on("mouseover", (e: any, d: any) => {
      tooltip.style("display", "block")
        .html(`<strong>${d.label}</strong><br>Clients: ${d.client_count || 0}<br>Roams: ${d.roam_count || 0}<br>Avg Quality: ${d.quality_avg || '-'}`);
    })
    .on("mousemove", (e: any) => {
      const rect = el.getBoundingClientRect();
      tooltip.style("left", (e.clientX - rect.left + 12) + "px").style("top", (e.clientY - rect.top - 10) + "px");
    })
    .on("mouseout", () => tooltip.style("display", "none"))
    .on("click", (_: any, d: any) => {
      this.selectedNode = d;
      this.selectedLinks = links.filter((l: any) =>
        (typeof l.source === "object" ? l.source.id : l.source) === d.id ||
        (typeof l.target === "object" ? l.target.id : l.target) === d.id
      );
    });

    // Tick
    this.sim.on("tick", () => {
      link.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
      linkLabel.attr("x", (d: any) => (d.source.x + d.target.x) / 2)
        .attr("y", (d: any) => (d.source.y + d.target.y) / 2);
      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });
  }

  private nodeRadius(d: any, maxClients: number): number {
    const base = 16, max = 40;
    return base + ((d.client_count || 1) / maxClients) * (max - base);
  }

  private shortLabel(label: string): string {
    if (!label) return "";
    // Shorten long AP names: "APE437.9FD4.19D8" -> "APE4...19D8"
    if (label.length > 14) return label.slice(0, 5) + ".." + label.slice(-4);
    return label;
  }

  getName(node: any): string {
    return typeof node === "string" ? node : node.label || node.id || "";
  }

  qc(s: number): string {
    return s >= 80 ? "#34C759" : s >= 60 ? "#5A9BD5" : s >= 40 ? "#E8A838" : s >= 20 ? "#E07830" : "#C8102E";
  }
}