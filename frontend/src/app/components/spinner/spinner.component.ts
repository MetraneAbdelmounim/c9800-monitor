import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

/**
 * Centered loading spinner with the ASB navy/red ring.
 * Drop in with *ngIf while data is loading:
 *   <app-spinner *ngIf="loading()"></app-spinner>
 * Use [inline]="true" for a smaller, low-padding variant inside cards.
 */
@Component({
  selector: 'app-spinner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="spinner-wrap" [class.inline]="inline">
      <div class="spinner"></div>
      <div class="spinner-label" *ngIf="label">{{ label }}</div>
    </div>
  `,
  styles: [`
    .spinner-wrap {
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      gap: 14px; width: 100%; min-height: 280px; padding: 48px 20px;
    }
    .spinner-wrap.inline { min-height: 0; padding: 32px 20px; }
    .spinner {
      width: 44px; height: 44px; border-radius: 50%;
      border: 3px solid var(--border, #2A2A2A);
      border-top-color: var(--asb-navy, #1B3A6B);
      border-right-color: var(--asb-red, #C8102E);
      animation: asb-spin 0.8s linear infinite;
    }
    .spinner-label {
      font-size: 12px; font-weight: 600; letter-spacing: 0.4px;
      color: var(--text-3, #706868);
    }
    @keyframes asb-spin { to { transform: rotate(360deg); } }
  `]
})
export class SpinnerComponent {
  @Input() label = 'Loading…';
  @Input() inline = false;
}
