import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CitationListComponent } from './citation-list.component';
import { SolicitationService } from '../../services/solicitation.service';
import {
  DraftSectionCitation,
  DraftSectionResponse,
  GateDecision,
  SectionAudit,
  SectionProvenance,
} from '../../models/solicitation';

/**
 * Per-section UI shell for AI-drafted FAR sections (C, H, L, M).
 *
 * Spec: docs/specs/m2-grounded-retrieval/ui-far-sections.md §4 (shell), §5 (provenance state
 * machine), §6.1 (soft-gate badges), §6.3 (error-state inline messages),
 * §12 (lean-corpus L/M banner).
 *
 * Provenance transitions are handled here:
 *   null     → human     when user types in empty section
 *   any      → ai        when AI-draft returns draft_returned
 *   ai       → ai-edited when user edits ≥1 char of AI text
 *   any      → null      on Reset
 *
 * The component is presentation-only for the gate decision: the badge is
 * authoritative via `gate_decision` from the backend (ADR-0007 D2); the
 * confidence dots (rerank_top_score → ●●●○○) never override the badge.
 */
@Component({
  selector: 'app-section-card',
  standalone: true,
  imports: [CommonModule, FormsModule, CitationListComponent],
  template: `
    <div class="section-card card">
      <div class="section-card-header">
        <div>
          <h3>Section {{ sectionLetter }} — {{ sectionTitle }}</h3>
          <div class="section-meta">
            <span class="prov-badge" [ngClass]="provenanceClass()">
              {{ provenanceLabel() }}
            </span>
            <span *ngIf="audit?.lastEditedAt" class="last-edited">
              last edited {{ audit?.lastEditedAt | date:'short' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Lean-corpus L/M caveat banner (spec §12). Dismissible via localStorage. -->
      <div *ngIf="showLeanCorpusBanner" class="lean-corpus-banner">
        <span>
          <strong>Note:</strong> grounding corpus currently covers FAR Parts I+II.
          Drafts for Section L/M may surface lower confidence until corpus
          expansion (Phase 1.5).
        </span>
        <button type="button" class="banner-dismiss" (click)="dismissLeanCorpusBanner()">
          Dismiss
        </button>
      </div>

      <textarea
        rows="10"
        [ngModel]="text"
        (ngModelChange)="onTextChange($event)"
        [placeholder]="placeholder">
      </textarea>

      <div class="section-actions">
        <button class="secondary" (click)="onAiDraft()"
                [disabled]="drafting || !step1Ready"
                [title]="step1Ready ? '' : 'Complete Step 1 first'">
          {{ drafting ? 'Drafting…' : '▦ AI-draft Section ' + sectionLetter }}
        </button>
        <button class="secondary" (click)="onReset()" [disabled]="!text">
          Reset to empty
        </button>
      </div>

      <!-- AI-drafted shell: confidence dots + gate badge + citations + audit link. -->
      <div *ngIf="lastResponse" class="ai-shell">
        <div class="gate-row">
          <span class="confidence-dots" [title]="'rerank_top_score ' + (lastResponse.rerank_top_score ?? 'null')">
            {{ confidenceDots() }}
          </span>
          <span class="gate-badge" [ngClass]="gateClass()">{{ gateLabel() }}</span>
          <span *ngIf="requiresReview" class="reviewed-toggle">
            <label>
              <input type="checkbox" [(ngModel)]="reviewed" name="reviewed-{{ sectionLetter }}"/>
              CO reviewed
            </label>
          </span>
        </div>

        <div *ngIf="lastResponse.gate_decision === 'withhold'" class="gate-banner gate-banner--withhold">
          Insufficient grounding — text withheld. Type the section manually or
          re-draft with a refined query.
        </div>
        <div *ngIf="lastResponse.gate_decision === 'rerank_unavailable_passthrough'"
             class="gate-banner gate-banner--degraded">
          Degraded mode (rerank unavailable) — review every citation before
          using this draft.
        </div>

        <!-- ADR-0015 D5 — drafted with soft-missing Step 1 context. -->
        <div *ngIf="lastResponse.degraded_context?.length" class="gate-banner gate-banner--degraded">
          ⚠ Drafted without {{ lastResponse.degraded_context!.join(', ') }}.
          Retrieval quality may be lower — fill in Step 1 and re-draft for the
          fully-grounded version.
        </div>

        <app-citation-list [citations]="lastResponse.citations"></app-citation-list>

        <div class="audit-link">
          Audit trail:
          <a [attr.href]="'/audit/' + lastResponse.request_id">
            request_id <code>{{ lastResponse.request_id }}</code>
          </a>
        </div>
      </div>

      <!-- Inline error states (spec §6.3) — no toasts; localised to card. -->
      <div *ngIf="errorMessage" class="error-text">{{ errorMessage }}</div>
    </div>
  `,
  styles: [`
    .section-card { padding: 1rem; }
    .section-card-header { display: flex; justify-content: space-between; align-items: flex-start; }
    .section-card-header h3 { margin: 0 0 0.25rem 0; }
    .section-meta { display: flex; gap: 0.75rem; align-items: center; font-size: 0.8rem; }
    .last-edited { color: var(--color-fg-muted); }

    .prov-badge {
      display: inline-block;
      padding: 0.1rem 0.5rem;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.4px;
      text-transform: uppercase;
      color: white;
      background: #999;
    }
    .prov-badge.provenance--human    { background: #555; }            /* grey 600 */
    .prov-badge.provenance--ai       { background: #1565c0; }         /* blue 600 */
    .prov-badge.provenance--ai-edited{ background: #6d2bb6; }         /* violet 600 */
    .prov-badge.provenance--empty    { background: #b0b0b0; color: #333; }

    .section-actions { margin-top: 0.5rem; display: flex; gap: 0.5rem; }

    .ai-shell {
      margin-top: 0.75rem;
      padding-top: 0.5rem;
      border-top: 1px solid var(--color-border);
    }
    .gate-row { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
    .confidence-dots { font-size: 1.1rem; letter-spacing: 1px; color: var(--color-accent); }
    .gate-badge {
      display: inline-block;
      padding: 0.15rem 0.6rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
      color: white;
    }
    .gate--pass     { background: var(--color-success); }      /* green 600 */
    .gate--hitl     { background: var(--color-warning); }      /* amber 600 */
    .gate--withhold { background: var(--color-danger); }       /* red 600 */
    .gate--degraded { background: #ef6c00; }                   /* orange 500 */

    .reviewed-toggle label { font-size: 0.8rem; display: flex; gap: 0.3rem; align-items: center; }
    .reviewed-toggle input { width: auto; }

    .gate-banner {
      margin: 0.5rem 0;
      padding: 0.5rem 0.75rem;
      border-radius: 4px;
      font-size: 0.85rem;
    }
    .gate-banner--withhold { background: #fdecea; color: #8b1a17; border: 1px solid #f4a09b; }
    .gate-banner--degraded { background: #fff4e5; color: #7a3e00; border: 1px solid #f3c089; }

    .lean-corpus-banner {
      display: flex;
      gap: 0.5rem;
      align-items: center;
      justify-content: space-between;
      background: #e7f2fb;
      color: #154a7a;
      border: 1px solid #b8d6ef;
      border-radius: 4px;
      padding: 0.5rem 0.75rem;
      margin-bottom: 0.5rem;
      font-size: 0.85rem;
    }
    .banner-dismiss {
      background: transparent;
      border: 1px solid transparent;
      color: #154a7a;
      cursor: pointer;
      font-size: 0.75rem;
    }
    .banner-dismiss:hover { border-color: #b8d6ef; }

    .audit-link { font-size: 0.8rem; color: var(--color-fg-muted); margin-top: 0.4rem; }
    .audit-link code { font-size: 0.75rem; }

    .error-text { color: var(--color-danger); font-size: 0.85rem; margin-top: 0.5rem; }
  `],
})
export class SectionCardComponent implements OnInit {
  /** 'C' | 'H' | 'L' | 'M' (drafted sections only). */
  @Input({ required: true }) sectionLetter!: string;
  @Input({ required: true }) sectionTitle!: string;
  @Input({ required: true }) solicitationId!: string;
  @Input() placeholder = '';
  @Input() text: string = '';
  @Input() audit: SectionAudit | undefined;
  /** Step 1 reactive-forms validity gate (ADR-0015 D4) — parent wizard binds
   * [step1Ready]="isStep1ContextReady()". AI-draft is disabled until true. */
  @Input() step1Ready = false;
  /** Step 1 metadata the wizard injects into the draft payload (ADR-0015 D3). */
  @Input() draftMeta: {
    naics?: string | null;
    setAside?: string | null;
    contractType?: string | null;
    agencySupplement?: string | null;
  } = {};

  @Output() textChange = new EventEmitter<string>();
  @Output() auditChange = new EventEmitter<SectionAudit>();

  drafting = false;
  errorMessage: string | null = null;
  lastResponse: DraftSectionResponse | null = null;
  reviewed = false;

  /** Lean-corpus banner: only L/M, dismissible via localStorage. */
  showLeanCorpusBanner = false;
  private static readonly LEAN_BANNER_KEY = 'ui.lean-corpus-banner-dismissed:v1';

  constructor(private svc: SolicitationService) {}

  ngOnInit(): void {
    // Initial provenance: if there is text but no audit, treat as 'human'
    // (cohort may have typed in a section before audit was wired).
    if (this.text && !this.audit) {
      this.emitAudit({ provenance: 'human' });
    }
  }

  provenanceClass(): string {
    const p = this.audit?.provenance;
    if (!p) return 'provenance--empty';
    return `provenance--${p}`;
  }

  provenanceLabel(): string {
    switch (this.audit?.provenance) {
      case 'human':     return 'Human';
      case 'ai':        return 'AI';
      case 'ai-edited': return 'AI-edited';
      default:          return 'Empty';
    }
  }

  /** Spec §5 user-typing trigger: null → 'human' first character; ai → ai-edited if user edits an AI draft. */
  onTextChange(next: string): void {
    const prev = this.text;
    this.text = next;
    this.textChange.emit(next);
    const currentProv = this.audit?.provenance ?? null;
    if (!next) {
      // Tracked separately by Reset; an empty result of editing is treated
      // as user-cleared so set provenance back to null.
      this.emitAudit({ provenance: null });
      return;
    }
    if (currentProv === null) {
      this.emitAudit({ provenance: 'human' });
    } else if (currentProv === 'ai' && next !== prev) {
      this.emitAudit({ provenance: 'ai-edited' });
    }
    // 'ai-edited' and 'human' remain stable under further edits.
  }

  /** Spec §5 reset: any → null. */
  onReset(): void {
    this.text = '';
    this.textChange.emit('');
    this.lastResponse = null;
    this.errorMessage = null;
    this.reviewed = false;
    this.emitAudit({ provenance: null, aiRequestId: null, lastGateDecision: null, lastRerankTopScore: null });
  }

  /** Spec §5 AI-draft: any → 'ai' (overwrite). */
  onAiDraft(): void {
    this.drafting = true;
    this.errorMessage = null;
    // Lean-corpus banner: first L or M AI-draft per session, if not dismissed.
    if ((this.sectionLetter === 'L' || this.sectionLetter === 'M') && !this.isLeanBannerDismissed()) {
      this.showLeanCorpusBanner = true;
    }
    this.svc.draftSection(this.solicitationId, this.sectionLetter, {
      naics: this.draftMeta.naics,
      setAside: this.draftMeta.setAside,
      contractType: this.draftMeta.contractType,
      agencySupplement: this.draftMeta.agencySupplement,
    }).subscribe({
      next: (resp) => {
        this.drafting = false;
        this.lastResponse = resp;
        this.handleResponse(resp);
      },
      error: (err) => {
        this.drafting = false;
        this.errorMessage = this.errorFor(err?.status);
      },
    });
  }

  private handleResponse(resp: DraftSectionResponse): void {
    if (resp.outcome === 'draft_returned' && resp.section_text) {
      this.text = resp.section_text;
      this.textChange.emit(this.text);
      this.emitAudit({
        provenance: 'ai',
        aiRequestId: resp.request_id,
        lastGateDecision: resp.gate_decision,
        lastRerankTopScore: resp.rerank_top_score,
      });
    } else if (resp.outcome === 'withheld' || resp.gate_decision === 'withhold') {
      // Withhold: keep textarea empty/whatever-it-was; surface the banner.
      this.emitAudit({
        provenance: this.audit?.provenance ?? null,
        aiRequestId: resp.request_id,
        lastGateDecision: 'withhold',
        lastRerankTopScore: resp.rerank_top_score,
      });
    } else if (resp.outcome === 'citation_verification_failed') {
      this.errorMessage =
        'Draft generated but citations failed verification — text withheld.';
    } else if (resp.outcome === 'interrupted') {
      // ADR-0012 D6 — run paused on the HITL gate. Phase 2 renders the full
      // "Pending CO decision" panel with approve/edit/reject; Phase 1 keeps
      // the transitional state visible without transitioning provenance.
      this.errorMessage =
        'Draft paused pending CO decision (low retrieval confidence). ' +
        'Resume support arrives with the HITL panel.';
      this.emitAudit({
        provenance: this.audit?.provenance ?? null,
        aiRequestId: resp.request_id,
        lastGateDecision: 'hitl',
        lastRerankTopScore: resp.rerank_top_score,
      });
    } else if (resp.requires_human_review) {
      // Soft-gate HITL: keep returned text if any, but require CO review tick.
      if (resp.section_text) {
        this.text = resp.section_text;
        this.textChange.emit(this.text);
      }
      this.emitAudit({
        provenance: 'ai',
        aiRequestId: resp.request_id,
        lastGateDecision: 'hitl',
        lastRerankTopScore: resp.rerank_top_score,
      });
    }
  }

  get requiresReview(): boolean {
    const gd = this.lastResponse?.gate_decision;
    return gd === 'hitl' || gd === 'rerank_unavailable_passthrough';
  }

  /** Spec §4.2 confidence-dot mapping. Presentation only; gate authority is the badge. */
  confidenceDots(): string {
    const s = this.lastResponse?.rerank_top_score;
    if (s == null) return '○○○○○';
    if (s < 0.40) return '●○○○○';
    if (s < 0.55) return '●●○○○';
    if (s < 0.70) return '●●●○○';
    if (s < 0.85) return '●●●●○';
    return '●●●●●';
  }

  gateClass(): string {
    const gd: GateDecision | undefined = this.lastResponse?.gate_decision;
    switch (gd) {
      case 'pass':                            return 'gate--pass';
      case 'hitl':                            return 'gate--hitl';
      case 'withhold':                        return 'gate--withhold';
      case 'rerank_unavailable_passthrough':  return 'gate--degraded';
      default:                                return '';
    }
  }

  gateLabel(): string {
    const gd: GateDecision | undefined = this.lastResponse?.gate_decision;
    switch (gd) {
      case 'pass':                            return 'Grounded ✓';
      case 'hitl':                            return '⚠ Needs CO review';
      case 'withhold':                        return '⚠ Insufficient grounding — withheld';
      case 'rerank_unavailable_passthrough':  return '⚠ Degraded mode — review every citation';
      default:                                return '';
    }
  }

  private errorFor(status?: number): string {
    switch (status) {
      case 403: return 'Query rejected by content policy. Refine and retry.';
      case 422: return 'Draft generated but citations failed verification — text withheld.';
      case 429: return 'Rate limited; try again shortly.';
      case 503: return 'Drafting service temporarily unavailable. Type the section manually or retry.';
      default:  return 'Drafting service error. Type the section manually or retry.';
    }
  }

  private emitAudit(patch: Partial<SectionAudit>): void {
    const next: SectionAudit = {
      provenance: patch.provenance ?? this.audit?.provenance ?? null,
      aiRequestId: patch.aiRequestId ?? this.audit?.aiRequestId ?? null,
      lastEditedAt: new Date().toISOString(),
      lastEditedBy: this.audit?.lastEditedBy,
      lastRerankTopScore: patch.lastRerankTopScore ?? this.audit?.lastRerankTopScore ?? null,
      lastGateDecision: patch.lastGateDecision ?? this.audit?.lastGateDecision ?? null,
    };
    this.audit = next;
    this.auditChange.emit(next);
  }

  private isLeanBannerDismissed(): boolean {
    try {
      return typeof localStorage !== 'undefined' &&
        localStorage.getItem(SectionCardComponent.LEAN_BANNER_KEY) === '1';
    } catch {
      return false;
    }
  }

  dismissLeanCorpusBanner(): void {
    this.showLeanCorpusBanner = false;
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(SectionCardComponent.LEAN_BANNER_KEY, '1');
      }
    } catch {
      /* swallow — banner stays dismissed for the session only. */
    }
  }
}
