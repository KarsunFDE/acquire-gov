import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { SolicitationService } from '../../services/solicitation.service';
import { Solicitation, SolicitationCreate, SolicitationSections } from '../../models/solicitation';

/**
 * Multi-step Solicitation Drafting Wizard.
 *
 * Steps mirror FAR 15.204 RFP structure (Sections A–M, skipping I).
 * Step 1: Basics (title, agency, NAICS, set-aside, type, ceiling)
 * Step 2: Section C — Statement of Work (AI-drafted via /draft-solicitation)
 * Step 3: Section L — Instructions to Offerors (AI-drafted)
 * Step 4: Section M — Evaluation Factors
 * Step 5: Review + transition to INTERNAL_REVIEW
 *
 * Touches Item 4 (no Pydantic schema on AI output), Item 5 (legacy
 * LLMChain wired into the AI-orchestrator drafter), Item 9 (no
 * sanitization on description field).
 */
@Component({
  selector: 'app-solicitation-wizard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>New solicitation — drafting wizard</h2>
        <div class="subtitle">FAR 15.204 Sections A–M · AI-assisted</div>
      </div>
    </div>

    <div class="stepper">
      <span class="step" *ngFor="let s of steps; let i = index"
            [class.active]="i === step"
            [class.complete]="i < step">{{ i + 1 }}. {{ s }}</span>
    </div>

    <!-- Step 1: Basics -->
    <div class="card" *ngIf="step === 0">
      <h3>1. Basics</h3>
      <label><span class="label-text">Title</span>
        <input name="title" [(ngModel)]="model.title" placeholder="e.g., Cloud Managed Services BPA"/>
      </label>
      <div class="two-col">
        <label><span class="label-text">Agency ID</span>
          <input name="agencyId" [(ngModel)]="model.agencyId" placeholder="GSA-FAS"/>
        </label>
        <label><span class="label-text">NAICS</span>
          <input name="naics" [(ngModel)]="model.naics" placeholder="541512"/>
        </label>
        <label><span class="label-text">Set-aside</span>
          <select name="setAside" [(ngModel)]="model.setAside">
            <option value="FULL_AND_OPEN">Full and Open</option>
            <option value="SMALL_BUSINESS">Small Business</option>
            <option value="8A">8(a)</option>
            <option value="SDVOSB">SDVOSB</option>
            <option value="WOSB">WOSB</option>
            <option value="HUBZONE">HUBZone</option>
          </select>
        </label>
        <label><span class="label-text">Contract type</span>
          <select name="contractType" [(ngModel)]="model.contractType">
            <option value="FFP">Firm Fixed Price</option>
            <option value="CPFF">Cost Plus Fixed Fee</option>
            <option value="T_AND_M">T&amp;M</option>
            <option value="IDIQ">IDIQ</option>
            <option value="BPA">BPA</option>
          </select>
        </label>
        <label><span class="label-text">Notice type</span>
          <select name="noticeType" [(ngModel)]="model.noticeType">
            <option value="RFI">RFI</option>
            <option value="SOURCES_SOUGHT">Sources Sought</option>
            <option value="RFP">RFP</option>
            <option value="RFQ">RFQ</option>
            <option value="COMBINED_SYNOPSIS">Combined Synopsis/Solicitation</option>
          </select>
        </label>
        <label><span class="label-text">Ceiling ($)</span>
          <input name="ceiling" type="number" [(ngModel)]="model.ceilingValue"/>
        </label>
      </div>
      <label><span class="label-text">Description (public-facing)</span>
        <textarea name="description" rows="4" [(ngModel)]="model.description"
                  placeholder="Public solicitation description (rendered raw — see Debt Item 9)"></textarea>
      </label>
    </div>

    <!-- Step 2: Section C -->
    <div class="card" *ngIf="step === 1">
      <h3>2. Section C — Statement of Work</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        AI-drafted via <code>POST /draft-solicitation</code> (ai-orchestrator).
        ⚠ Debt Item 4 (no Pydantic schema), Item 5 (legacy LLMChain.run wired here).
      </p>
      <button class="secondary" (click)="aiDraft('sectionC')">▦ AI-draft Section C</button>
      <textarea name="sectionC" rows="10" [(ngModel)]="sections.sectionC"
                style="margin-top:0.5rem"></textarea>
    </div>

    <!-- Step 3: Section L -->
    <div class="card" *ngIf="step === 2">
      <h3>3. Section L — Instructions to Offerors</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Per AFARS Chapter 9 templates. Page limits, format, submission method.
      </p>
      <button class="secondary" (click)="aiDraft('sectionL')">▦ AI-draft Section L</button>
      <textarea name="sectionL" rows="10" [(ngModel)]="sections.sectionL"
                style="margin-top:0.5rem"></textarea>
    </div>

    <!-- Step 4: Section M -->
    <div class="card" *ngIf="step === 3">
      <h3>4. Section M — Evaluation Factors</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        FAR 15.305. Factor weights must sum to 100.
      </p>
      <textarea name="sectionM" rows="10" [(ngModel)]="sections.sectionM"
                placeholder="M.3.1 Technical Approach (40%)&#10;M.3.2 Management Approach (25%)&#10;M.3.3 Past Performance (20%)&#10;M.3.4 Price (15%)"></textarea>
    </div>

    <!-- Step 5: Review -->
    <div class="card" *ngIf="step === 4">
      <h3>5. Review &amp; submit for internal review</h3>
      <p>Submitting transitions the solicitation to <code>INTERNAL_REVIEW</code>.
         CO sign-off required before publication.</p>
      <table>
        <tbody>
          <tr><th>Title</th><td>{{ model.title || '—' }}</td></tr>
          <tr><th>Agency / NAICS</th><td>{{ model.agencyId }} / {{ model.naics }}</td></tr>
          <tr><th>Set-aside / Type</th><td>{{ model.setAside }} / {{ model.contractType }}</td></tr>
          <tr><th>Ceiling</th><td>\${{ model.ceilingValue?.toLocaleString() || '—' }}</td></tr>
          <tr><th>Section C length</th><td>{{ (sections.sectionC || '').length }} chars</td></tr>
          <tr><th>Section L length</th><td>{{ (sections.sectionL || '').length }} chars</td></tr>
          <tr><th>Section M length</th><td>{{ (sections.sectionM || '').length }} chars</td></tr>
        </tbody>
      </table>
    </div>

    <div style="margin-top:1rem;display:flex;gap:0.5rem;justify-content:space-between">
      <button class="secondary" (click)="back()" [disabled]="step === 0">← Back</button>
      <div>
        <button *ngIf="step < steps.length - 1" (click)="next()">Next →</button>
        <button *ngIf="step === steps.length - 1" (click)="submit()" [disabled]="submitting">
          {{ submitting ? 'Submitting…' : 'Submit for internal review' }}
        </button>
      </div>
    </div>
    <div *ngIf="error" class="error-text">{{ error }}</div>
  `,
})
export class SolicitationWizardComponent {
  steps = ['Basics', 'Section C', 'Section L', 'Section M', 'Review'];
  step = 0;
  submitting = false;
  error: string | null = null;

  model: SolicitationCreate = {
    agencyId: 'GSA-FAS',
    title: '',
    description: '',
    status: 'DRAFT',
    naics: '',
    setAside: 'FULL_AND_OPEN',
    contractType: 'FFP',
    noticeType: 'RFP',
    ceilingValue: undefined,
  };

  sections: SolicitationSections = {};

  constructor(private svc: SolicitationService, private router: Router) {}

  back(): void {
    if (this.step > 0) this.step--;
  }

  next(): void {
    if (this.step < this.steps.length - 1) this.step++;
  }

  aiDraft(section: 'sectionC' | 'sectionL'): void {
    // Stubbed — in W2 this hits POST /draft-solicitation through the
    // gateway. For instructor demo, populate plausible placeholder text.
    if (section === 'sectionC') {
      this.sections.sectionC = `C.1 SCOPE. The Contractor shall provide enterprise cloud managed services to support ${this.model.agencyId || 'the agency'} mission applications across AWS GovCloud and Azure Government, in accordance with FedRAMP Moderate baseline controls and NIST SP 800-53 Rev. 5.\n\nC.2 BACKGROUND. ${this.model.description || '[description not yet entered]'}\n\nC.3 TASKS.\nTask 1: Service Operations\nTask 2: Continuous Monitoring\nTask 3: Incident Response\n\n[AI-DRAFTED placeholder — to be reviewed by CS / CO before publication. Item 4 / Item 5 surface.]`;
    } else {
      this.sections.sectionL = `L.1 GENERAL INSTRUCTIONS. Proposals shall be submitted electronically via SAM.gov by the date and time specified in Section A.\n\nL.5.2 VOLUME I — TECHNICAL. 60-page limit including table of contents; 12-pt Times New Roman; FedRAMP boundary diagrams required.\n\nL.5.3 VOLUME II — PAST PERFORMANCE. Three references within the last 5 years; CPARS extracts accepted.\n\nL.5.4 VOLUME III — PRICE. Fully burdened labor rates by year; option periods priced.\n\n[AI-DRAFTED placeholder.]`;
    }
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
      error: (err) => {
        // Brownfield reality: create may fail; for instructor demo, still
        // route to the editor as if it succeeded.
        this.submitting = false;
        this.router.navigate(['/solicitations']);
      },
    });
  }
}
