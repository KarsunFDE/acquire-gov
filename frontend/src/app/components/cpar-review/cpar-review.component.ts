import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_CPARS } from '../../services/mock-fixtures';
import { Cpar } from '../../models/award';

/**
 * CPAR Performance Review (FAR 42.1503).
 *
 * Interim + final CPAR with 60-day vendor rebuttal window.
 * 6 rating factors per CPARS Guidance: Quality, Schedule, Cost Control,
 * Management, Small Business, Regulatory Compliance.
 *
 * Touches Item 9 (rebuttal text rendered raw) and Item 2 (state
 * transitions write to audit log — race surface).
 */
@Component({
  selector: 'app-cpar-review',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>CPAR — Contract {{ contractId }}</h2>
        <div class="subtitle">FAR 42.1503 · 60-day rebuttal window per FAR 42.1503(d)</div>
      </div>
      <a [routerLink]="['/contracts', contractId, 'admin']"><button class="secondary">← Contract admin</button></a>
    </div>

    <div class="card" *ngFor="let c of cpars">
      <div style="display:flex;justify-content:space-between">
        <h3>{{ c.period }} CPAR <span class="badge" [ngClass]="badgeFor(c.status)">{{ c.status }}</span></h3>
        <small>Rebuttal due {{ c.rebuttalDeadline | date:'mediumDate' }}</small>
      </div>

      <table>
        <thead>
          <tr><th>Factor</th><th>Rating</th><th>Narrative</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let f of c.ratings">
            <td>{{ pretty(f.factor) }}</td>
            <td><span class="badge" [ngClass]="ratingClass(f.rating)">{{ pretty(f.rating) }}</span></td>
            <td>{{ f.narrative }}</td>
          </tr>
        </tbody>
      </table>

      <div style="margin-top:1rem">
        <strong>Overall narrative:</strong>
        <p>{{ c.overallNarrative }}</p>
      </div>

      <!-- Vendor rebuttal panel — only visible to vendor role -->
      <div *ngIf="role.currentRole === 'vendor' && c.status === 'AWAITING_VENDOR_REVIEW'">
        <h4>Submit rebuttal</h4>
        <p style="font-size:0.85rem;color:var(--color-fg-muted)">
          ⚠ Free-text field, no sanitization (Item 9). Rendered raw in
          published CPAR.
        </p>
        <textarea rows="5" [(ngModel)]="rebuttalDraft[c.id]"
                  placeholder="Vendor rebuttal narrative…"></textarea>
        <button (click)="submitRebuttal(c)" [disabled]="!rebuttalDraft[c.id]">
          Submit rebuttal
        </button>
      </div>

      <div *ngIf="c.vendorRebuttal" class="card" style="background:var(--color-bg)">
        <strong>Vendor rebuttal:</strong>
        <p>{{ c.vendorRebuttal }}</p>
      </div>
    </div>
  `,
})
export class CparReviewComponent implements OnInit {
  contractId = 'ctr-0001';
  cpars: Cpar[] = [];
  rebuttalDraft: Record<string, string> = {};

  constructor(public role: RoleService, private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.contractId = this.route.snapshot.params['id'] || 'ctr-0001';
    this.cpars = FIXTURE_CPARS.filter((c) => c.contractId === this.contractId).map((c) => ({ ...c }));
  }

  submitRebuttal(c: Cpar): void {
    c.vendorRebuttal = this.rebuttalDraft[c.id];
    c.status = 'PUBLISHED';
    this.rebuttalDraft[c.id] = '';
  }

  pretty(s: string): string {
    return s.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
  }

  ratingClass(r: string): string {
    return r.toLowerCase();
  }

  badgeFor(s: string): string {
    if (s === 'PUBLISHED') return 'published';
    if (s === 'AWAITING_VENDOR_REVIEW') return 'review';
    return 'draft';
  }
}
