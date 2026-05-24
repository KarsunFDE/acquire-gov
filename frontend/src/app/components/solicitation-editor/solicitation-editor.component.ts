import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Solicitation } from '../../models/solicitation';
import { FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';

/**
 * Pre-publication editor for a draft Solicitation.
 *
 * Includes a side-panel clause-library lookup (RAG over FAR/DFARS),
 * which is the W2 anchor surface (hybrid lexical + vector). The
 * search input here is the W2 Wed retrieval-boundary work surface
 * — must filter by agency_id (Item 10).
 */
@Component({
  selector: 'app-solicitation-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>{{ solicitation?.title || 'Draft solicitation' }}</h2>
        <div class="subtitle">
          <span class="badge" [ngClass]="(solicitation?.status || 'draft').toLowerCase()">{{ solicitation?.status }}</span>
          · NAICS {{ solicitation?.naics }} · {{ solicitation?.contractType }}
        </div>
      </div>
      <div>
        <a [routerLink]="['/solicitations', id, 'amendments']"><button class="secondary">Amendments</button></a>
        <a [routerLink]="['/solicitations', id, 'qa']"><button class="secondary">Q&amp;A triage</button></a>
        <a [routerLink]="['/solicitations', id, 'proposals']"><button class="secondary">Proposals</button></a>
      </div>
    </div>

    <div class="two-col">
      <div>
        <div class="card">
          <h3>Section C — Statement of Work</h3>
          <textarea rows="8" [(ngModel)]="sectionC"></textarea>
        </div>
        <div class="card">
          <h3>Section L — Instructions to Offerors</h3>
          <textarea rows="8" [(ngModel)]="sectionL"></textarea>
        </div>
        <div class="card">
          <h3>Section M — Evaluation Factors</h3>
          <textarea rows="6" [(ngModel)]="sectionM"></textarea>
        </div>
      </div>

      <div>
        <div class="card">
          <h3>Clause library (RAG)</h3>
          <p style="font-size:0.8rem;color:var(--color-fg-muted)">
            Hybrid lexical + Atlas Vector Search over FAR/DFARS.
            <em>Filtered by agency_id — Item 10 surface.</em>
          </p>
          <input [(ngModel)]="clauseQuery" (keyup.enter)="searchClauses()" placeholder="e.g., 52.212-4 commercial items"/>
          <button (click)="searchClauses()" style="margin-top:0.5rem">Search</button>
          <ul *ngIf="clauseResults.length > 0">
            <li *ngFor="let c of clauseResults">
              <strong>{{ c.id }}</strong> — {{ c.title }}
              <button class="secondary" style="font-size:0.75rem;padding:0.1rem 0.35rem">Insert</button>
            </li>
          </ul>
        </div>

        <div class="card">
          <h3>State transition</h3>
          <select [(ngModel)]="targetState">
            <option value="DRAFT">DRAFT</option>
            <option value="INTERNAL_REVIEW">INTERNAL_REVIEW</option>
            <option value="READY_TO_PUBLISH">READY_TO_PUBLISH</option>
            <option value="PUBLISHED">PUBLISHED (CO only)</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>
          <button style="margin-top:0.5rem">Transition</button>
          <p style="font-size:0.75rem;color:var(--color-fg-muted);margin-top:0.5rem">
            ⚠ Transitions audit-logged (Item 2 race surface).
          </p>
        </div>
      </div>
    </div>
  `,
})
export class SolicitationEditorComponent implements OnInit {
  id = '';
  solicitation: Solicitation | null = null;
  sectionC = '';
  sectionL = '';
  sectionM = '';
  clauseQuery = '';
  clauseResults: { id: string; title: string }[] = [];
  targetState = 'INTERNAL_REVIEW';

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.params['id'];
    this.solicitation = FIXTURE_SOLICITATIONS.find((s) => s.id === this.id)
      ?? FIXTURE_SOLICITATIONS[0];
    this.sectionC = `C.1 SCOPE. ${this.solicitation.description}`;
    this.sectionL = 'L.5.2 Volume I (Technical) — 60 pages…';
    this.sectionM = 'M.3.1 Technical Approach (40%)\nM.3.2 Management Approach (25%)\nM.3.3 Past Performance (20%)\nM.3.4 Price (15%)';
  }

  searchClauses(): void {
    // Stub — in W2, hits POST /rag/clause-search.
    const q = this.clauseQuery.toLowerCase();
    this.clauseResults = [
      { id: '52.212-4', title: 'Contract Terms and Conditions—Commercial Items' },
      { id: '52.204-21', title: 'Basic Safeguarding of Covered Contractor Information Systems' },
      { id: '52.219-14', title: 'Limitations on Subcontracting' },
    ].filter((c) => !q || c.id.includes(q) || c.title.toLowerCase().includes(q));
  }
}
