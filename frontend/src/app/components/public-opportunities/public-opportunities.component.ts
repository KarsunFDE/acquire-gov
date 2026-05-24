import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';
import { Solicitation } from '../../models/solicitation';

/**
 * Public Opportunity Search (SAM.gov-style).
 *
 * Surface for Debt Item 1 (JWT-skip on /api/public/**) and Item 10
 * (cross-tenant listing). Public + all roles can view; unauthenticated
 * visitors land here on `/public/opportunities`.
 *
 * Facet filters mirror SAM.gov: NAICS, set-aside, agency, posted-date,
 * notice type.
 */
@Component({
  selector: 'app-public-opportunities',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Federal contract opportunities</h2>
        <div class="subtitle">SAM.gov-style search · public read-only · ~24k notices monthly</div>
      </div>
    </div>

    <div class="two-col" style="grid-template-columns:240px 1fr">
      <div class="card">
        <h3>Filters</h3>
        <label><span class="label-text">Keyword</span>
          <input [(ngModel)]="q" placeholder="e.g., cloud"/>
        </label>
        <label><span class="label-text">NAICS</span>
          <input [(ngModel)]="naics"/>
        </label>
        <label><span class="label-text">Notice type</span>
          <select [(ngModel)]="noticeType">
            <option value="">Any</option>
            <option value="RFP">RFP</option>
            <option value="RFI">RFI</option>
            <option value="SOURCES_SOUGHT">Sources Sought</option>
            <option value="RFQ">RFQ</option>
            <option value="COMBINED_SYNOPSIS">Combined Synopsis</option>
          </select>
        </label>
        <label><span class="label-text">Set-aside</span>
          <select [(ngModel)]="setAside">
            <option value="">Any</option>
            <option value="FULL_AND_OPEN">Full &amp; Open</option>
            <option value="SMALL_BUSINESS">Small Business</option>
            <option value="8A">8(a)</option>
            <option value="SDVOSB">SDVOSB</option>
            <option value="WOSB">WOSB</option>
            <option value="HUBZONE">HUBZone</option>
          </select>
        </label>
        <button (click)="resetFilters()" class="secondary">Reset</button>
      </div>

      <div>
        <p style="color:var(--color-fg-muted);font-size:0.85rem">
          {{ filtered().length }} of {{ FIXTURE_SOLICITATIONS.length }} opportunities
        </p>
        <div class="card" *ngFor="let s of filtered()">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <h3 style="margin-bottom:0.25rem">
                <a [routerLink]="['/public/opportunities', s.id]">{{ s.title }}</a>
              </h3>
              <div style="font-size:0.8rem;color:var(--color-fg-muted)">
                {{ s.noticeType }} · {{ s.agencyId }} · NAICS {{ s.naics }} ·
                {{ s.setAside }} · Ceiling \${{ (s.ceilingValue || 0).toLocaleString() }}
              </div>
            </div>
            <span class="badge" [ngClass]="(s.status || '').toLowerCase()">{{ s.status }}</span>
          </div>
          <p style="margin-top:0.5rem">{{ s.description }}</p>
          <div style="font-size:0.8rem">
            Proposals due:
            <strong>{{ s.proposalsDueAt ? (s.proposalsDueAt | date:'medium') : '—' }}</strong>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class PublicOpportunitiesComponent {
  FIXTURE_SOLICITATIONS = FIXTURE_SOLICITATIONS;
  q = '';
  naics = '';
  noticeType = '';
  setAside = '';

  filtered(): Solicitation[] {
    const q = this.q.toLowerCase();
    return FIXTURE_SOLICITATIONS.filter((s) => {
      if (q && !s.title.toLowerCase().includes(q) && !s.description.toLowerCase().includes(q)) return false;
      if (this.naics && s.naics !== this.naics) return false;
      if (this.noticeType && s.noticeType !== this.noticeType) return false;
      if (this.setAside && s.setAside !== this.setAside) return false;
      return s.status !== 'INTERNAL_REVIEW' && s.status !== 'DRAFT';
    });
  }

  resetFilters(): void {
    this.q = '';
    this.naics = '';
    this.noticeType = '';
    this.setAside = '';
  }
}
