import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_AMENDMENTS, FIXTURE_SOLICITATIONS, FIXTURE_PROPOSALS } from '../../services/mock-fixtures';
import { Amendment } from '../../models/amendment';

/**
 * Amendment Editor (FAR 15.206).
 *
 * CO-only. AI drafts amendment narrative + predicts vendor-impact
 * (re-acknowledgement count, schedule effect). CO must approve
 * before publish — this is the W3 Wed HITL #4 (multi-agent handoffs)
 * touchpoint per CLAUDE.md.
 *
 * M2 C17: hard-gate amendment modal — FAR 15.206 (Amending the
 * Solicitation). Issuing an amendment is a statutorily-reserved CO
 * act; UI requires explicit text-confirmation friction. ADR-0008 D4
 * defines the locked surface; full LangGraph interrupt wiring lands
 * in M3 (m2-rollout.md M2-10 deferred), publish/amend modal stays.
 */
@Component({
  selector: 'app-amendment-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Amendments — {{ solicitationTitle() }}</h2>
        <div class="subtitle">FAR 15.206 · CO-only issuance · vendor acknowledgement required</div>
      </div>
      <a [routerLink]="['/solicitations', solicitationId, 'edit']"><button class="secondary">← Back to solicitation</button></a>
    </div>

    <div class="card" *ngIf="role.currentRole !== 'contracting_officer'">
      <p>You are not the Contracting Officer for this solicitation; amendments are read-only.</p>
    </div>

    <div class="card">
      <h3>Existing amendments</h3>
      <table>
        <thead>
          <tr>
            <th>#</th><th>Effective</th><th>Summary</th><th>Acks</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let a of amendments">
            <td>{{ a.number.toString().padStart(4, '0') }}</td>
            <td>{{ a.effectiveAt | date:'mediumDate' }}</td>
            <td>{{ a.changeSummary }}</td>
            <td>{{ a.acknowledgedBy.length }} / {{ totalProposalCount() }}</td>
          </tr>
          <tr *ngIf="amendments.length === 0">
            <td colspan="4"><em>No amendments issued.</em></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card" *ngIf="role.currentRole === 'contracting_officer'">
      <h3>Issue new amendment</h3>

      <div class="hitl-banner">
        <strong>HITL gate (W3 #4):</strong> AI drafts amendment + predicts vendor impact;
        CO approval required before publish. Per FAR 15.206 — amendment changes scope/deadline,
        all vendors with proposals-in-progress must re-acknowledge.
      </div>

      <label><span class="label-text">Change summary</span>
        <textarea rows="3" [(ngModel)]="draft.changeSummary"
                  placeholder="Brief description of the change (rendered raw — Item 9)"></textarea>
      </label>
      <label><span class="label-text">Effective date</span>
        <input type="date" [(ngModel)]="draft.effectiveAt"/>
      </label>
      <label style="display:flex;align-items:center;gap:0.5rem">
        <input type="checkbox" [(ngModel)]="draft.requiresAcknowledgement" style="width:auto"/>
        <span class="label-text" style="margin:0">Requires vendor acknowledgement</span>
      </label>

      <button class="secondary" (click)="aiDraft()" style="margin-right:0.5rem">▦ AI-draft amendment narrative</button>
      <button (click)="openIssueModal()" [disabled]="!draft.changeSummary">Issue amendment</button>

      <div *ngIf="impactPrediction" class="card" style="background:var(--color-bg);margin-top:1rem">
        <strong>Predicted vendor impact:</strong>
        <ul>
          <li>{{ impactPrediction.vendorsAffected }} vendors with proposals-in-progress must re-acknowledge</li>
          <li>Estimated schedule effect: +{{ impactPrediction.scheduleDeltaDays }} days</li>
          <li>{{ impactPrediction.likelyQna }} additional Q&amp;A submissions expected</li>
        </ul>
      </div>
    </div>

    <!-- Hard-gate amendment modal — FAR 15.206 (Amending the Solicitation).
         M2 C17 / ADR-0008 D4. Phase 1 is client-side friction; M3 wires the
         LangGraph interrupt round-trip. SSA / award sign-off is the M3 forward-ref
         stub at the bottom. -->
    <div class="modal-backdrop" *ngIf="showIssueModal" (click)="closeIssueModal()">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="amend-modal-title"
           (click)="$event.stopPropagation()">
        <h3 id="amend-modal-title">Hard gate — Issue amendment</h3>
        <p>
          Per <a href="https://www.acquisition.gov/far/15.206" target="_blank" rel="noopener">FAR 15.206</a>
          (Amending the Solicitation), an amendment is a statutorily-reserved act of the
          Contracting Officer. The amendment will be published to all vendors with
          proposals-in-progress and re-acknowledgement will be required.
        </p>
        <p>
          <strong>Amendment rationale (required):</strong>
        </p>
        <textarea rows="3" [(ngModel)]="amendRationale" name="amendRationale"
                  placeholder="Why is this amendment necessary? (e.g., scope clarification, schedule change, requirement update)"></textarea>
        <label style="display:flex;align-items:flex-start;gap:0.5rem;margin-top:0.75rem">
          <input type="checkbox" [(ngModel)]="amendApprovalChecked" name="amendApproval" style="width:auto;margin-top:0.2rem"/>
          <span class="label-text" style="margin:0">I am the Contracting Officer and I approve this amendment.</span>
        </label>
        <div style="margin-top:1rem;display:flex;gap:0.5rem;justify-content:flex-end">
          <button class="secondary" (click)="closeIssueModal()">Cancel</button>
          <button (click)="confirmIssue()"
                  [disabled]="!amendApprovalChecked || !amendRationale.trim()">
            Confirm + issue amendment
          </button>
        </div>
        <p style="font-size:0.75rem;color:var(--color-fg-muted);margin-top:0.75rem">
          Backend HITL middleware (LangGraph interrupt) lands in M3 — this modal is the Phase 1
          client-side gate. Approval is logged to the audit_log on issuance.
        </p>
      </div>
    </div>

    <!-- M3 forward-ref stubs (SSA / award). Disabled with explanatory tooltip.
         Kept inline next to amend so the cohort sees the full hard-gate surface
         in one place. FAR 15.308 (SSA decision document) wiring lands in M3. -->
    <div class="card" *ngIf="role.currentRole === 'contracting_officer'" style="border-style:dashed;opacity:0.85">
      <h3>Source-selection authority + award (M3)</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Statutorily-reserved CO acts — FAR 15.308 (SSA decision document) and FAR award
        signature flow. M3 — agentic workflow proposes; signing requires CO present.
      </p>
      <button class="secondary" disabled
              title="M3 — agentic workflow approves; signs require CO present.">
        Sign SSA decision document (M3 — disabled)
      </button>
      <button class="secondary" disabled
              title="M3 — agentic workflow approves; signs require CO present."
              style="margin-left:0.5rem">
        Sign award (M3 — disabled)
      </button>
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
    .modal textarea, .modal input { width: 100%; }
  `],
})
export class AmendmentEditorComponent implements OnInit {
  solicitationId = '';
  amendments: Amendment[] = [];

  draft = {
    changeSummary: '',
    effectiveAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 3).toISOString().slice(0, 10),
    requiresAcknowledgement: true,
  };

  impactPrediction: { vendorsAffected: number; scheduleDeltaDays: number; likelyQna: number } | null = null;

  // FAR 15.206 hard-gate modal state (M2 C17).
  showIssueModal = false;
  amendApprovalChecked = false;
  amendRationale = '';

  constructor(private route: ActivatedRoute, public role: RoleService) {}

  ngOnInit(): void {
    this.solicitationId = this.route.snapshot.params['id'];
    this.amendments = FIXTURE_AMENDMENTS.filter((a) => a.solicitationId === this.solicitationId);
  }

  solicitationTitle(): string {
    return FIXTURE_SOLICITATIONS.find((s) => s.id === this.solicitationId)?.title ?? this.solicitationId;
  }

  totalProposalCount(): number {
    return FIXTURE_PROPOSALS.filter((p) => p.solicitationId === this.solicitationId).length;
  }

  aiDraft(): void {
    // Stubbed — W3 multi-agent flow predicts impact then drafts text.
    this.draft.changeSummary =
      `Per FAR 15.206, this amendment ${this.draft.changeSummary || 'modifies the solicitation'} ` +
      `effective ${this.draft.effectiveAt}. Vendors with proposals-in-progress must acknowledge ` +
      `prior to the revised deadline.`;
    this.impactPrediction = {
      vendorsAffected: this.totalProposalCount(),
      scheduleDeltaDays: 7,
      likelyQna: 4,
    };
  }

  openIssueModal(): void {
    this.amendApprovalChecked = false;
    this.amendRationale = '';
    this.showIssueModal = true;
  }

  closeIssueModal(): void {
    this.showIssueModal = false;
  }

  confirmIssue(): void {
    // FAR 15.206 hard-gate: the CO approval checkbox + rationale text are
    // verified again here; template-level `disabled` is presentation only.
    if (!this.amendApprovalChecked || !this.amendRationale.trim()) {
      return;
    }
    this.showIssueModal = false;
    this.issue();
  }

  issue(): void {
    // Stubbed — would call AmendmentService.issue() with amendRationale +
    // approval marker in the body so backend can persist the audit_log row.
    const next: Amendment = {
      id: `am-new-${Date.now()}`,
      solicitationId: this.solicitationId,
      number: this.amendments.length + 1,
      changeSummary: this.draft.changeSummary,
      effectiveAt: new Date(this.draft.effectiveAt).toISOString(),
      requiresAcknowledgement: this.draft.requiresAcknowledgement,
      acknowledgedBy: [],
      issuedBy: 'co-current',
      issuedAt: new Date().toISOString(),
    };
    this.amendments = [...this.amendments, next];
    this.draft.changeSummary = '';
    this.impactPrediction = null;
  }
}
