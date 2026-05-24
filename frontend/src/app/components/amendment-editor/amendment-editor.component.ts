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
      <button (click)="issue()" [disabled]="!draft.changeSummary">Issue amendment</button>

      <div *ngIf="impactPrediction" class="card" style="background:var(--color-bg);margin-top:1rem">
        <strong>Predicted vendor impact:</strong>
        <ul>
          <li>{{ impactPrediction.vendorsAffected }} vendors with proposals-in-progress must re-acknowledge</li>
          <li>Estimated schedule effect: +{{ impactPrediction.scheduleDeltaDays }} days</li>
          <li>{{ impactPrediction.likelyQna }} additional Q&amp;A submissions expected</li>
        </ul>
      </div>
    </div>
  `,
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

  issue(): void {
    // Stubbed — would call AmendmentService.issue().
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
