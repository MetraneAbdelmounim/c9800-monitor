import { Component, Input, Output, EventEmitter, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-paginator',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './paginator.component.html',
  styleUrl: './paginator.component.css',
})
export class PaginatorComponent {
  private _total = signal(0);
  private _pageSize = signal(25);
  private _page = signal(1);

  @Input() set total(v: number) { this._total.set(v || 0); this.clampPage(); }
  @Input() set pageSize(v: number) { this._pageSize.set(v || 25); this.clampPage(); }
  @Input() set page(v: number) { this._page.set(v || 1); this.clampPage(); }
  @Input() pageSizeOptions: number[] = [10, 25, 50, 100, 200];

  @Output() pageChange = new EventEmitter<number>();
  @Output() pageSizeChange = new EventEmitter<number>();

  readonly currentPage = this._page.asReadonly();
  readonly currentSize = this._pageSize.asReadonly();
  readonly totalCount = this._total.asReadonly();

  readonly totalPages = computed(() => {
    const t = this._total(), s = this._pageSize();
    return s > 0 ? Math.max(1, Math.ceil(t / s)) : 1;
  });

  readonly rangeStart = computed(() => {
    if (this._total() === 0) return 0;
    return (this._page() - 1) * this._pageSize() + 1;
  });
  readonly rangeEnd = computed(() => Math.min(this._page() * this._pageSize(), this._total()));

  /** Page numbers around the current one, with '…' markers for gaps. */
  readonly pages = computed<(number | '...')[]>(() => {
    const tp = this.totalPages(), cur = this._page();
    if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1);
    const out: (number | '...')[] = [1];
    const start = Math.max(2, cur - 1);
    const end = Math.min(tp - 1, cur + 1);
    if (start > 2) out.push('...');
    for (let i = start; i <= end; i++) out.push(i);
    if (end < tp - 1) out.push('...');
    out.push(tp);
    return out;
  });

  goTo(p: number | '...') {
    if (p === '...') return;
    const clamped = Math.max(1, Math.min(this.totalPages(), p));
    if (clamped !== this._page()) {
      this._page.set(clamped);
      this.pageChange.emit(clamped);
    }
  }

  prev() { this.goTo(this._page() - 1); }
  next() { this.goTo(this._page() + 1); }

  onSizeChange(s: string | number) {
    const v = +s;
    if (v && v !== this._pageSize()) {
      this._pageSize.set(v);
      this.pageSizeChange.emit(v);
      // Reset to page 1 on size change
      if (this._page() !== 1) {
        this._page.set(1);
        this.pageChange.emit(1);
      }
    }
  }

  private clampPage() {
    const tp = this.totalPages();
    if (this._page() > tp) this._page.set(tp);
    if (this._page() < 1) this._page.set(1);
  }
}
