import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormBuilder,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router } from '@angular/router';
import { SolicitationService } from '../../services/solicitation.service';
import {
  BatchPerSectionDecision,
  DraftSectionResponse,
  FARClauseReference,
  PartIIClauseList,
  PendingToolCall,
  SectionAudit,
  Solicitation,
  SolicitationCreate,
  SolicitationDraftBundle,
  SolicitationSections,
} from '../../models/solicitation';
import { SectionCardComponent } from './section-card.component';

/**
 * Multi-step Solicitation Drafting Wizard.
 *
 * M2 C15: expanded from 5 steps to the full FAR 15.204-1 UCF (13 steps,
 * Sections A–M, splitting Section I as retrieved-only). Per-section
 * provenance + citations + audit-trail link live in `section-card`
 * (sub-component); the wizard owns the step layout, navigation, the cross-
 * section consistency check (Step 12 — FAR 15.204-5 L↔M alignment), and
 * the hard-gate publish modal on Step 13 (FAR 5.705, ADR-0008 D4).
 *
 * Wizard text-only sections (A, B, D-G, J, K) are human-authored; sections
 * C, H, L, M are AI-drafted via section-card → SolicitationService.draftSection.
 * Section I is retrieved-only (FAR Part 52 clause list, presented as a
 * read-only list at Step 7).
 *
 * Spec: docs/specs/m2-grounded-retrieval/ui-far-sections.md (§3 layout, §4 shell, §5 state
 * machine, §6 HITL, §11 RBAC, §12 lean-corpus banner).
 *
 * Brownfield artifacts still surfaced on this page (M1 baseline):
 * Item 4 (no Pydantic schema on AI output), Item 5 (legacy LLMChain in
 * orchestrator), Item 9 (no sanitization on description field). Legacy
 * direct AI-draft buttons removed — replaced by section-card.
 */
@Component({
  selector: 'app-solicitation-wizard',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, SectionCardComponent],
  template: `
    <div class="page-header">
      <div>
        <h2>New solicitation — drafting wizard</h2>
        <div class="subtitle">FAR 15.204-1 UCF Sections A–M · grounded AI assist (M2)</div>
      </div>
    </div>

    <div class="stepper">
      <span class="step" *ngFor="let s of steps; let i = index"
            [class.active]="i === step"
            [class.complete]="i < step">{{ i + 1 }}. {{ s }}</span>
    </div>

    <!-- M1 Phase 3 — batch draft all AI Parts (ADR-0014). -->
    <div class="batch-bar card" *ngIf="step > 0">
      <button (click)="onDraftAiParts()"
              [disabled]="batchDrafting || !isStep1ContextReady()"
              [title]="isStep1ContextReady() ? '' : 'Complete Step 1 first'">
        {{ batchDrafting ? 'Drafting AI Parts…' : '▦▦ Draft AI Parts (C · H · L · M)' }}
      </button>
      <span class="step-hint">
        Parts I (C+H) + IV (L+M) draft in parallel; Part II clauses resolve
        programmatically; Part III passes through wizard attachments.
      </span>
      <div *ngIf="batchError" class="error-text">{{ batchError }}</div>

      <!-- Per-Part HITL surface: one pending panel per interrupted Part. -->
      <div *ngIf="batchPendingInterrupts.length" class="batch-hitl">
        <div class="gate-banner gate-banner--hitl"
             *ngFor="let p of batchPendingInterrupts">
          ⏸ <strong>Part {{ p.args['part'] }} pending CO decision</strong>
          (sections {{ asList(p.args['sections']) }}) — {{ p.reason }}
          <span class="hitl-actions" *ngIf="!batchResuming">
            <button (click)="onBatchDecision(p, 'approve')">Approve</button>
            <button class="secondary" (click)="onBatchDecision(p, 'reject')">Reject</button>
          </span>
        </div>
        <div *ngIf="batchResuming" class="step-hint">Resuming batch…</div>
      </div>
    </div>

    <!-- Step 1: Basics — reactive forms (ADR-0015 D4): 5 hard-required
         fields gate Next + every AI-draft button. -->
    <div class="card" *ngIf="step === 0">
      <h3>1. Basics</h3>
      <form [formGroup]="step1Form">
        <label><span class="label-text">Title *</span>
          <input formControlName="title" placeholder="e.g., Cloud Managed Services BPA"/>
        </label>
        <div class="two-col">
          <label><span class="label-text">Agency ID *</span>
            <input formControlName="agencyId" placeholder="GSA-FAS"/>
          </label>
          <label><span class="label-text">NAICS *</span>
            <input formControlName="naics" placeholder="541512"/>
          </label>
          <label><span class="label-text">Set-aside *</span>
            <select formControlName="setAside">
              <option value="FULL_AND_OPEN">Full and Open</option>
              <option value="SMALL_BUSINESS">Small Business</option>
              <option value="8A">8(a)</option>
              <option value="SDVOSB">SDVOSB</option>
              <option value="WOSB">WOSB</option>
              <option value="HUBZONE">HUBZone</option>
            </select>
          </label>
          <label><span class="label-text">Contract type *</span>
            <select formControlName="contractType">
              <option value="FFP">Firm Fixed Price</option>
              <option value="CPFF">Cost Plus Fixed Fee</option>
              <option value="T_AND_M">T&amp;M</option>
              <option value="IDIQ">IDIQ</option>
              <option value="BPA">BPA</option>
            </select>
          </label>
          <label><span class="label-text">Agency FAR supplement</span>
            <input formControlName="agencySupplement" placeholder="GSAM / DFARS (optional — drafts flag if missing)"/>
          </label>
          <label><span class="label-text">Notice type</span>
            <select formControlName="noticeType">
              <option value="RFI">RFI</option>
              <option value="SOURCES_SOUGHT">Sources Sought</option>
              <option value="RFP">RFP</option>
              <option value="RFQ">RFQ</option>
              <option value="COMBINED_SYNOPSIS">Combined Synopsis/Solicitation</option>
            </select>
          </label>
          <label><span class="label-text">Ceiling ($)</span>
            <input type="number" formControlName="ceilingValue"/>
          </label>
        </div>
        <label><span class="label-text">Description (public-facing)</span>
          <textarea rows="4" formControlName="description"
                    placeholder="Public solicitation description (rendered raw — see Debt Item 9)"></textarea>
        </label>
        <p class="step-hint" *ngIf="!step1Form.valid">
          * required before Next — AI drafting needs this context (preflight
          rejects ungrounded requests; ADR-0015).
        </p>
      </form>
    </div>

    <!-- Step 2: Section A — Solicitation/Contract Form (human-only) -->
    <div class="card" *ngIf="step === 1">
      <h3>2. Section A — Solicitation/Contract Form</h3>
      <p class="step-hint">Cover sheet, signature blocks, due date. Human-entered per ADR-0005 D4.</p>
      <textarea name="sectionA" rows="6" [(ngModel)]="sections.sectionA"
                (ngModelChange)="onHumanEdit('A', $event)"
                placeholder="SF 33 / SF 1449 cover content"></textarea>
    </div>

    <!-- Step 3: Section B — Supplies/Services + Prices -->
    <div class="card" *ngIf="step === 2">
      <h3>3. Section B — Supplies/Services + Prices/Costs</h3>
      <p class="step-hint">CLINs, units, ceiling per CLIN, option years. Human-entered.</p>
      <textarea name="sectionB" rows="8" [(ngModel)]="sections.sectionB"
                (ngModelChange)="onHumanEdit('B', $event)"
                placeholder="0001  Cloud managed services — base year  EA  12  $___"></textarea>
    </div>

    <!-- Step 4: Section C — Statement of Work (AI-drafted) -->
    <div class="card" *ngIf="step === 3">
      <app-section-card
        sectionLetter="C"
        sectionTitle="Statement of Work"
        [solicitationId]="solicitationDraftId"
        [step1Ready]="isStep1ContextReady()"
        [draftMeta]="draftMeta"
        [text]="sections.sectionC || ''"
        [audit]="sections.sectionCAudit"
        placeholder="C.1 SCOPE…"
        (textChange)="sections.sectionC = $event"
        (auditChange)="sections.sectionCAudit = $event">
      </app-section-card>
    </div>

    <!-- Step 5: Sections D-G — Packaging / Inspection / Delivery / Admin -->
    <div class="card" *ngIf="step === 4">
      <h3>5. Sections D–G — Packaging · Inspection · Delivery · Admin</h3>
      <p class="step-hint">Standard FAR boilerplate; human-edited or template-pulled.</p>
      <label><span class="label-text">D — Packaging and Marking</span>
        <textarea rows="3" [(ngModel)]="sections.sectionD"
                  (ngModelChange)="onHumanEdit('D', $event)"></textarea>
      </label>
      <label><span class="label-text">E — Inspection and Acceptance</span>
        <textarea rows="3" [(ngModel)]="sections.sectionE"
                  (ngModelChange)="onHumanEdit('E', $event)"></textarea>
      </label>
      <label><span class="label-text">F — Deliveries or Performance</span>
        <textarea rows="3" [(ngModel)]="sections.sectionF"
                  (ngModelChange)="onHumanEdit('F', $event)"></textarea>
      </label>
      <label><span class="label-text">G — Contract Administration Data</span>
        <textarea rows="3" [(ngModel)]="sections.sectionG"
                  (ngModelChange)="onHumanEdit('G', $event)"></textarea>
      </label>
    </div>

    <!-- Step 6: Section H — Special Contract Requirements (AI-drafted) -->
    <div class="card" *ngIf="step === 5">
      <app-section-card
        sectionLetter="H"
        sectionTitle="Special Contract Requirements"
        [solicitationId]="solicitationDraftId"
        [step1Ready]="isStep1ContextReady()"
        [draftMeta]="draftMeta"
        [text]="sections.sectionH || ''"
        [audit]="sections.sectionHAudit"
        placeholder="H.1 SPECIAL REQUIREMENTS…"
        (textChange)="sections.sectionH = $event"
        (auditChange)="sections.sectionHAudit = $event">
      </app-section-card>
    </div>

    <!-- Step 7: Section I — Contract Clauses (retrieved-only) -->
    <div class="card" *ngIf="step === 6">
      <h3>7. Section I — Contract Clauses (Part II)</h3>
      <p class="step-hint">
        Retrieved-only from FAR Part 52 based on contract type, set-aside, and ceiling.
        Not editable per ADR-0005 D4 — clauses are authoritative as published.
      </p>
      <div class="retrieved-clauses" *ngIf="resolvedClauses.length > 0">
        <strong>Resolved clauses (Part II programmatic resolution — ADR-0014 D3):</strong>
        <ul>
          <li *ngFor="let c of resolvedClauses">
            <code>{{ c.citation }}</code> — {{ c.title }}
            <span class="step-hint">({{ c.prescription }})</span>
          </li>
        </ul>
      </div>
      <div class="retrieved-clauses" *ngIf="resolvedClauses.length === 0">
        <strong>Resolved clauses (sample — run "Draft AI Parts" to resolve):</strong>
        <ul>
          <li><code>52.212-4</code> — Contract Terms and Conditions, Commercial Items</li>
          <li><code>52.204-21</code> — Basic Safeguarding of Covered Contractor Info Systems</li>
          <li><code>52.219-14</code> — Limitations on Subcontracting</li>
          <li><code>52.215-1</code> — Instructions to Offerors—Competitive Acquisition</li>
        </ul>
        <p class="step-hint">
          Final clause set resolves on submit; this list is presentation only.
        </p>
      </div>
    </div>

    <!-- Step 8: Section J — Attachments (human; file persistence is M3 open) -->
    <div class="card" *ngIf="step === 7">
      <h3>8. Section J — List of Attachments</h3>
      <p class="step-hint">
        File upload (attachment persistence is an M3 / Phase 1.5 storage open item).
        For now, enumerate attachments by name + reference.
      </p>
      <textarea rows="5" [(ngModel)]="sections.sectionJ"
                (ngModelChange)="onHumanEdit('J', $event)"
                placeholder="J.1 Attachment 1 — Performance Work Statement (PDF)&#10;J.2 Attachment 2 — Pricing Schedule (XLSX)"></textarea>
    </div>

    <!-- Step 9: Section K — Reps + Certs (template) -->
    <div class="card" *ngIf="step === 8">
      <h3>9. Section K — Representations &amp; Certifications</h3>
      <p class="step-hint">
        Reps + Certs are template-driven; retrieval suggests a starter template
        (commercial-items vs. non-commercial baseline).
      </p>
      <textarea rows="8" [(ngModel)]="sections.sectionK"
                (ngModelChange)="onHumanEdit('K', $event)"
                placeholder="K.1 52.204-7 System for Award Management — incorporated by reference&#10;K.2 52.204-26 Covered Telecommunications…"></textarea>
    </div>

    <!-- Step 10: Section L — Instructions to Offerors (AI-drafted, lean corpus caveat) -->
    <div class="card" *ngIf="step === 9">
      <app-section-card
        sectionLetter="L"
        sectionTitle="Instructions to Offerors"
        [solicitationId]="solicitationDraftId"
        [step1Ready]="isStep1ContextReady()"
        [draftMeta]="draftMeta"
        [text]="sections.sectionL || ''"
        [audit]="sections.sectionLAudit"
        placeholder="L.1 GENERAL INSTRUCTIONS…"
        (textChange)="sections.sectionL = $event"
        (auditChange)="sections.sectionLAudit = $event">
      </app-section-card>
    </div>

    <!-- Step 11: Section M — Evaluation Factors (AI-drafted, lean corpus caveat) -->
    <div class="card" *ngIf="step === 10">
      <app-section-card
        sectionLetter="M"
        sectionTitle="Evaluation Factors for Award"
        [solicitationId]="solicitationDraftId"
        [step1Ready]="isStep1ContextReady()"
        [draftMeta]="draftMeta"
        [text]="sections.sectionM || ''"
        [audit]="sections.sectionMAudit"
        placeholder="M.1 BASIS FOR AWARD…"
        (textChange)="sections.sectionM = $event"
        (auditChange)="sections.sectionMAudit = $event">
      </app-section-card>
    </div>

    <!-- Step 12: Review + cross-section consistency check -->
    <div class="card" *ngIf="step === 11">
      <h3>12. Review + cross-section consistency</h3>
      <p class="step-hint">
        FAR 15.204-5: instructions in Section L must align with evaluation factors
        in Section M. Warn-only structural check (Phase 1 heuristic; full check is
        an open item — see spec §17).
      </p>
      <div *ngIf="consistencyWarnings.length > 0" class="consistency-warning">
        <strong>Possible misalignment:</strong>
        <ul>
          <li *ngFor="let w of consistencyWarnings">{{ w }}</li>
        </ul>
      </div>
      <div *ngIf="consistencyWarnings.length === 0" class="consistency-ok">
        No obvious L↔M misalignment detected (heuristic).
      </div>

      <table style="margin-top:0.75rem">
        <tbody>
          <tr><th>Title</th><td>{{ model.title || '—' }}</td></tr>
          <tr><th>Agency / NAICS</th><td>{{ model.agencyId }} / {{ model.naics }}</td></tr>
          <tr><th>Set-aside / Type</th><td>{{ model.setAside }} / {{ model.contractType }}</td></tr>
          <tr><th>Ceiling</th><td>\${{ model.ceilingValue?.toLocaleString() || '—' }}</td></tr>
          <tr><th>Section C length</th><td>{{ (sections.sectionC || '').length }} chars · {{ provenanceFor('C') }}</td></tr>
          <tr><th>Section H length</th><td>{{ (sections.sectionH || '').length }} chars · {{ provenanceFor('H') }}</td></tr>
          <tr><th>Section L length</th><td>{{ (sections.sectionL || '').length }} chars · {{ provenanceFor('L') }}</td></tr>
          <tr><th>Section M length</th><td>{{ (sections.sectionM || '').length }} chars · {{ provenanceFor('M') }}</td></tr>
          <tr><th>Sections needing CO review</th><td>{{ sectionsRequiringReview() }}</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Step 13: Submit for internal review / ready to publish -->
    <div class="card" *ngIf="step === 12">
      <h3>13. Submit for internal review → ready-to-publish</h3>
      <p>
        Submitting transitions the solicitation to <code>INTERNAL_REVIEW</code>
        (and then <code>READY_TO_PUBLISH</code> after CO sign-off). Publication
        itself is gated by the FAR 5.705 modal — see solicitation editor.
      </p>
      <p *ngIf="hasUnreviewedAiSections()" class="step-blocker">
        ⚠ One or more AI-drafted sections are flagged "Needs CO review" and have
        not been ticked off. Step 13 cannot proceed until they are reviewed.
      </p>

      <button (click)="openSubmitModal()"
              [disabled]="submitting || hasUnreviewedAiSections()">
        Submit for internal review
      </button>
      <div *ngIf="error" class="error-text">{{ error }}</div>
    </div>

    <!-- Navigation -->
    <div style="margin-top:1rem;display:flex;gap:0.5rem;justify-content:space-between">
      <button class="secondary" (click)="back()" [disabled]="step === 0">← Back</button>
      <div>
        <button *ngIf="step < steps.length - 1" (click)="next()"
                [disabled]="step === 0 && !step1Form.valid"
                [title]="step === 0 && !step1Form.valid ? 'Complete required Step 1 fields first' : ''">
          Next →
        </button>
      </div>
    </div>

    <!-- Submit-for-review hard-gate modal (FAR 5.705 forward-ref + CO sign-off).
         M2 C17 / ADR-0008 D4. Phase 1 is client-side friction; M3 wires the
         LangGraph interrupt round-trip on top. -->
    <div class="modal-backdrop" *ngIf="showSubmitModal" (click)="closeSubmitModal()">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="sub-modal-title"
           (click)="$event.stopPropagation()">
        <h3 id="sub-modal-title">Hard gate — Submit for internal review</h3>
        <p>
          This transitions the solicitation to <code>INTERNAL_REVIEW</code>. The
          actual PUBLISHED transition (FAR 5.705 dissemination) is the
          statutorily-reserved CO act and triggers a second hard-gate modal at
          publish time in the solicitation editor.
        </p>
        <label style="display:flex;align-items:flex-start;gap:0.5rem;margin-top:0.75rem">
          <input type="checkbox" [(ngModel)]="submitApprovalChecked" name="subApproval" style="width:auto;margin-top:0.2rem"/>
          <span class="label-text" style="margin:0">
            I am the Contracting Officer and I approve this solicitation for
            internal review.
          </span>
        </label>
        <div style="margin-top:1rem;display:flex;gap:0.5rem;justify-content:flex-end">
          <button class="secondary" (click)="closeSubmitModal()">Cancel</button>
          <button (click)="confirmSubmit()" [disabled]="!submitApprovalChecked">
            Confirm + submit
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .step-hint { font-size: 0.85rem; color: var(--color-fg-muted); }
    .batch-bar { display: flex; flex-direction: column; gap: 0.4rem; padding: 0.75rem 1rem; }
    .batch-hitl { display: flex; flex-direction: column; gap: 0.4rem; }
    .gate-banner--hitl {
      background: #fff8e1; color: #6d4c00; border: 1px solid #e6c352;
      padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem;
    }
    .hitl-actions { display: inline-flex; gap: 0.4rem; margin-left: 0.6rem; }
    .retrieved-clauses ul { font-family: monospace; font-size: 0.85rem; }
    .consistency-warning {
      background: #fff4e5; border: 1px solid #f3c089; color: #7a3e00;
      padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem;
    }
    .consistency-ok {
      background: #ecf7ed; border: 1px solid #b6dab8; color: #1b5e20;
      padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem;
    }
    .step-blocker {
      background: #fdecea; border: 1px solid #f4a09b; color: #8b1a17;
      padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem;
    }
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
export class SolicitationWizardComponent {
  steps = [
    'Basics',
    'Sec A — Form',
    'Sec B — Prices',
    'Sec C — SOW',
    'Sec D–G',
    'Sec H — Special',
    'Sec I — Clauses',
    'Sec J — Attach',
    'Sec K — Reps',
    'Sec L — Instr',
    'Sec M — Eval',
    'Review',
    'Submit',
  ];
  step = 0;
  submitting = false;
  error: string | null = null;

  /** Solicitation ID surrogate for draft requests before the create-on-submit. */
  solicitationDraftId = 'draft-' + Math.random().toString(36).slice(2, 10);

  model: SolicitationCreate = {
    agencyId: 'GSA-FAS',
    title: '',
    description: '',
    status: 'DRAFT',
    naics: '',
    setAside: 'FULL_AND_OPEN',
    contractType: 'FFP',
    agencySupplement: '',
    noticeType: 'RFP',
    ceilingValue: undefined,
  };

  /** Step 1 reactive form (ADR-0015 D4) — 5 hard-required fields. */
  step1Form: FormGroup;

  sections: SolicitationSections = {};

  showSubmitModal = false;
  submitApprovalChecked = false;

  constructor(
    private fb: FormBuilder,
    private svc: SolicitationService,
    private router: Router,
  ) {
    this.step1Form = this.fb.group({
      title: ['', Validators.required],
      agencyId: ['GSA-FAS', Validators.required],
      naics: ['', Validators.required],
      setAside: ['FULL_AND_OPEN', Validators.required],
      contractType: ['FFP', Validators.required],
      // optional:
      agencySupplement: [''],
      noticeType: ['RFP'],
      ceilingValue: [null],
      description: [''],
    });
    // Keep the legacy `model` object in sync — review table + submit payload
    // read from it; the form is the single editing surface.
    this.step1Form.valueChanges.subscribe((v) => Object.assign(this.model, v));
  }

  /** AI-draft buttons + Next gate read this (design ref §19.7). */
  isStep1ContextReady(): boolean {
    return this.step1Form.valid;
  }

  /** ── M1 Phase 3 — batch drafting state (ADR-0014) ── */
  batchDrafting = false;
  batchResuming = false;
  batchError: string | null = null;
  batchRunId: string | null = null;
  batchPendingInterrupts: PendingToolCall[] = [];
  resolvedClauses: FARClauseReference[] = [];

  asList(v: unknown): string {
    return Array.isArray(v) ? v.join(', ') : String(v ?? '');
  }

  private currentProvenances(): Record<string, string | null> {
    const out: Record<string, string | null> = {};
    for (const s of ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M']) {
      const audit = (this.sections as any)[`section${s}Audit`] as SectionAudit | undefined;
      out[s] = audit?.provenance ?? null;
    }
    return out;
  }

  onDraftAiParts(): void {
    this.batchDrafting = true;
    this.batchError = null;
    const meta = this.draftMeta;
    this.svc.draftBatch({
      solicitation_id: this.solicitationDraftId,
      naics: meta.naics,
      set_aside: meta.setAside,
      contract_type: meta.contractType,
      agency_supplement: meta.agencySupplement,
      user_constraints_by_section: {},
      provenances: this.currentProvenances(),
      part_iii_attachments: [],
    }).subscribe({
      next: (bundle) => {
        this.batchDrafting = false;
        this.applyBundle(bundle);
      },
      error: (err) => {
        this.batchDrafting = false;
        this.batchError =
          err?.status === 422
            ? 'Batch rejected — complete Step 1 (preflight requires full metadata).'
            : 'Batch drafting failed; draft sections individually or retry.';
      },
    });
  }

  onBatchDecision(p: PendingToolCall, decision: 'approve' | 'reject'): void {
    if (!this.batchRunId) return;
    const sections = (p.args['sections'] as string[]) || [];
    const decisions: BatchPerSectionDecision[] = [
      { section_id: (sections[0] as any) ?? 'L', decision },
    ];
    this.batchResuming = true;
    this.svc.resumeBatch(this.batchRunId, decisions).subscribe({
      next: (bundle) => {
        this.batchResuming = false;
        this.applyBundle(bundle);
      },
      error: () => {
        this.batchResuming = false;
        this.batchError = 'Batch resume failed; retry or draft sections individually.';
      },
    });
  }

  /** Spread a SolicitationDraftBundle into the wizard's section state. */
  private applyBundle(bundle: SolicitationDraftBundle): void {
    this.batchRunId = bundle.batch_run_id;
    this.batchPendingInterrupts =
      bundle.overall_outcome === 'batch_interrupted' ? bundle.pending_interrupts : [];

    for (const part of Object.values(bundle.parts)) {
      if (!part) continue;
      if (part.kind === 'llm_drafted') {
        for (const [sid, raw] of Object.entries(part.sections)) {
          const final = raw as DraftSectionResponse | null;
          if (!final || typeof final !== 'object' || !('outcome' in final)) continue;
          if (final.outcome === 'draft_returned' && final.section_text) {
            (this.sections as any)[`section${sid}`] = final.section_text;
            (this.sections as any)[`section${sid}Audit`] = {
              provenance: 'ai',
              aiRequestId: final.request_id,
              runId: final.run_id ?? null,
              lastEditedAt: new Date().toISOString(),
              lastRerankTopScore: final.rerank_top_score,
              lastGateDecision: final.gate_decision,
            } as SectionAudit;
          }
        }
      } else if (part.kind === 'programmatic_resolved') {
        const clauseList = part.sections['I'] as PartIIClauseList | null;
        this.resolvedClauses = clauseList?.clauses_by_reference ?? [];
      }
      // 'wizard_provided' (Part III) — wizard already owns Section J state.
    }
  }

  /** Step 1 metadata injected into every draftSection payload (ADR-0015 D3). */
  get draftMeta(): {
    naics: string | null;
    setAside: string | null;
    contractType: string | null;
    agencySupplement: string | null;
  } {
    const v = this.step1Form.value;
    return {
      naics: v.naics || null,
      setAside: v.setAside || null,
      contractType: v.contractType || null,
      agencySupplement: v.agencySupplement || null,
    };
  }

  back(): void {
    if (this.step > 0) this.step--;
  }

  next(): void {
    if (this.step < this.steps.length - 1) this.step++;
  }

  /** Human-edited text-only section: spec §5 null→human; subsequent edits preserve provenance. */
  onHumanEdit(sectionLetter: string, text: string): void {
    const key = `section${sectionLetter}` as keyof SolicitationSections;
    const auditKey = `section${sectionLetter}Audit` as keyof SolicitationSections;
    (this.sections as any)[key] = text;
    const existing = (this.sections as any)[auditKey] as SectionAudit | undefined;
    const provenance = !text
      ? null
      : existing?.provenance === 'ai'
        ? 'ai-edited'
        : existing?.provenance ?? 'human';
    (this.sections as any)[auditKey] = {
      provenance,
      aiRequestId: existing?.aiRequestId ?? null,
      lastEditedAt: new Date().toISOString(),
      lastEditedBy: existing?.lastEditedBy,
      lastRerankTopScore: existing?.lastRerankTopScore ?? null,
      lastGateDecision: existing?.lastGateDecision ?? null,
    } as SectionAudit;
  }

  provenanceFor(sectionLetter: string): string {
    const auditKey = `section${sectionLetter}Audit` as keyof SolicitationSections;
    const a = (this.sections as any)[auditKey] as SectionAudit | undefined;
    return a?.provenance ? a.provenance : '—';
  }

  /** Heuristic L↔M consistency check (FAR 15.204-5; warn-only). */
  get consistencyWarnings(): string[] {
    const warnings: string[] = [];
    const l = (this.sections.sectionL ?? '').toLowerCase();
    const m = (this.sections.sectionM ?? '').toLowerCase();
    if (l.length > 0 && m.length > 0) {
      const factors = ['technical', 'past performance', 'price', 'management'];
      for (const f of factors) {
        if (m.includes(f) && !l.includes(f)) {
          warnings.push(`Section M references "${f}" but Section L does not include corresponding instructions.`);
        }
      }
    }
    if (l.length > 0 && m.length === 0) {
      warnings.push('Section L has instructions but Section M evaluation factors are empty.');
    }
    if (l.length === 0 && m.length > 0) {
      warnings.push('Section M evaluation factors are present but Section L instructions are empty.');
    }
    return warnings;
  }

  sectionsRequiringReview(): number {
    const drafted: (keyof SolicitationSections)[] = [
      'sectionCAudit', 'sectionHAudit', 'sectionLAudit', 'sectionMAudit',
    ];
    return drafted.reduce((n, k) => {
      const a = (this.sections as any)[k] as SectionAudit | undefined;
      const gd = a?.lastGateDecision;
      return n + (gd === 'hitl' || gd === 'rerank_unavailable_passthrough' ? 1 : 0);
    }, 0);
  }

  hasUnreviewedAiSections(): boolean {
    return this.sectionsRequiringReview() > 0;
  }

  openSubmitModal(): void {
    this.submitApprovalChecked = false;
    this.showSubmitModal = true;
  }

  closeSubmitModal(): void {
    this.showSubmitModal = false;
  }

  confirmSubmit(): void {
    if (!this.submitApprovalChecked) return;
    this.showSubmitModal = false;
    this.submit();
  }

  submit(): void {
    this.submitting = true;
    this.error = null;
    const payload: SolicitationCreate = {
      ...this.model,
      status: 'INTERNAL_REVIEW',
      sections: this.sections,
    };
    this.svc.create(payload).subscribe({
      next: (s: Solicitation) => {
        this.submitting = false;
        this.router.navigate(['/solicitations', s.id || 'sol-new', 'edit']);
      },
      error: () => {
        // Brownfield reality: create may fail; for instructor demo, still
        // route to the editor as if it succeeded.
        this.submitting = false;
        this.router.navigate(['/solicitations']);
      },
    });
  }
}
