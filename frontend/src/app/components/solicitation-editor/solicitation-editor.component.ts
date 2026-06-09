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
          <button style="margin-top:0.5rem" (click)="onTransition()">Transition</button>
          <p style="font-size:0.75rem;color:var(--color-fg-muted);margin-top:0.5rem">
            ⚠ Transitions audit-logged (Item 2 race surface).
          </p>
        </div>
      </div>
    </div>

    <!-- Hard-gate publish modal — FAR 5.705 (Dissemination of synopses).
         M2 C17 / ADR-0008 D4. Phase 1 client-side friction only; M3 wires
         the LangGraph interrupt round-trip on top. The PUBLISHED transition
         is statutorily-reserved CO act (FAR 1.602-1). -->
    <div class="modal-backdrop" *ngIf="showPublishModal" (click)="closePublishModal()">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="pub-modal-title"
           (click)="$event.stopPropagation()">
        <h3 id="pub-modal-title">Hard gate — Publish solicitation</h3>
        <p>
          Per <a href="https://www.acquisition.gov/far/5.705" target="_blank" rel="noopener">FAR 5.705</a>
          (Dissemination of synopses) and FAR 1.602-1 (CO authority), publishing a
          solicitation makes it visible on SAM.gov and binds the agency to its terms.
          This action is statutorily reserved to the Contracting Officer.
        </p>
        <label style="display:flex;align-items:flex-start;gap:0.5rem;margin-top:0.75rem">
          <input type="checkbox" [(ngModel)]="publishApprovalChecked" name="pubApproval" style="width:auto;margin-top:0.2rem"/>
          <span class="label-text" style="margin:0">I am the Contracting Officer and I approve publication of this solicitation.</span>
        </label>
        <div style="margin-top:1rem;display:flex;gap:0.5rem;justify-content:flex-end">
          <button class="secondary" (click)="closePublishModal()">Cancel</button>
          <button (click)="confirmPublish()" [disabled]="!publishApprovalChecked">
            Confirm + publish
          </button>
        </div>
        <p style="font-size:0.75rem;color:var(--color-fg-muted);margin-top:0.75rem">
          Backend HITL middleware (LangGraph interrupt) lands in M3 — this modal is
          the Phase 1 client-side gate.
        </p>
      </div>
    </div>
  `,
  styles: [`
    .modal-backdrop {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.45);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000;
    }
    .modal {
      background: var(--color-surface);
      border: 1px solid var(--color-border-strong);
      border-radius: 6px;
      padding: 1.25rem;
      max-width: 540px;
      width: 92vw;
      box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }
    .modal h3 { margin-top: 0; color: var(--color-danger); }
  `],
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

  // FAR 5.705 hard-gate publish modal (M2 C17).
  showPublishModal = false;
  publishApprovalChecked = false;

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.params['id'];
    this.solicitation = FIXTURE_SOLICITATIONS.find((s) => s.id === this.id)
      ?? FIXTURE_SOLICITATIONS[0];
    this.sectionC = `C.1 SCOPE. ${this.solicitation.description}`;
    this.sectionL = 'L.5.2 Volume I (Technical) — 60 pages…';
    this.sectionM = 'M.3.1 Technical Approach (40%)\nM.3.2 Management Approach (25%)\nM.3.3 Past Performance (20%)\nM.3.4 Price (15%)';
  }

  /** Routes the user through the hard-gate modal when transitioning to PUBLISHED. */
  onTransition(): void {
    if (this.targetState === 'PUBLISHED') {
      this.publishApprovalChecked = false;
      this.showPublishModal = true;
      return;
    }
    // Other transitions audit-log directly (Item 2 race surface preserved).
    this.applyTransition();
  }

  closePublishModal(): void {
    this.showPublishModal = false;
  }

  confirmPublish(): void {
    // FAR 5.705 hard-gate: re-verify the CO checkbox at the call site;
    // template `disabled` is presentation-only.
    if (!this.publishApprovalChecked) {
      return;
    }
    this.showPublishModal = false;
    this.applyTransition();
  }

  private applyTransition(): void {
    if (this.solicitation) {
      this.solicitation.status = this.targetState;
    }
    // Stub — would call SolicitationService transition endpoint here.
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
