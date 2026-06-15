export interface Solicitation {
  id: string;
  agencyId: string;
  title: string;
  description: string;
  status: string;
  createdAt?: string;
  updatedAt?: string;
  // — Expanded fields (multi-step drafting wizard, FAR 15.204 Sections A–M)
  naics?: string;
  setAside?: '' | 'SDVOSB' | 'WOSB' | 'HUBZONE' | '8A' | 'SMALL_BUSINESS' | 'FULL_AND_OPEN';
  contractType?: 'FFP' | 'CPFF' | 'T_AND_M' | 'IDIQ' | 'BPA';
  ceilingValue?: number;
  /** DEMO-REDESIGN-spec §4 — richer draft context (drives C/F/L/M). */
  periodOfPerformance?: string;
  placeOfPerformance?: string;
  evalApproach?: 'LPTA' | 'TRADEOFF';
  keyPersonnel?: string;
  /** Solicitation type per FAR Subpart 15.2 / SAM.gov categories. */
  noticeType?: 'RFI' | 'SOURCES_SOUGHT' | 'RFP' | 'RFQ' | 'COMBINED_SYNOPSIS';
  /** Section content keyed by FAR 15.204 part: A through M (skipping I per convention). */
  sections?: SolicitationSections;
  /** ISO timestamp; vendors locked at this time. */
  proposalsDueAt?: string;
}

/**
 * Per-section provenance + audit shape — defined by M2 UI spec
 * (docs/specs/m2-grounded-retrieval/ui-far-sections.md §8), consumed by solicitation-service for
 * its Postgres migration. SHAPE is owned here; backend persistence is a
 * follow-up Flyway migration on the SB 2.7.18 service (W4 modernization is
 * Phase 2; do not pre-do).
 */
export type SectionProvenance = 'human' | 'ai' | 'ai-edited' | null;

export type GateDecision =
  | 'pass'
  | 'hitl'
  | 'withhold'
  | 'rerank_unavailable_passthrough';

export interface SectionAudit {
  provenance: SectionProvenance;
  /** Correlates to audit_log.request_id (ADR-0008 D3). */
  aiRequestId?: string | null;
  /** Checkpoint thread id of the last agent run — survives wizard refresh so
   * an interrupted run can be resumed or abandoned (ADR-0012 D8). */
  runId?: string | null;
  lastEditedAt?: string;
  lastEditedBy?: string;
  /** Last `rerank_top_score` seen for this section (presentation only — gate authority is `lastGateDecision`). */
  lastRerankTopScore?: number | null;
  lastGateDecision?: GateDecision | null;
}

export interface SolicitationSections {
  sectionA?: string;   sectionAAudit?: SectionAudit;
  sectionB?: string;   sectionBAudit?: SectionAudit;
  sectionC?: string;   sectionCAudit?: SectionAudit;
  sectionD?: string;   sectionDAudit?: SectionAudit;
  sectionE?: string;   sectionEAudit?: SectionAudit;
  sectionF?: string;   sectionFAudit?: SectionAudit;
  sectionG?: string;   sectionGAudit?: SectionAudit;
  sectionH?: string;   sectionHAudit?: SectionAudit;
  // Section I intentionally absent — retrieved-only (FAR Part 52 clause list), not edited.
  sectionJ?: string;   sectionJAudit?: SectionAudit;
  sectionK?: string;   sectionKAudit?: SectionAudit;
  sectionL?: string;   sectionLAudit?: SectionAudit;
  sectionM?: string;   sectionMAudit?: SectionAudit;
}

export interface SolicitationCreate {
  agencyId: string;
  title: string;
  description: string;
  status?: string;
  naics?: string;
  setAside?: string;
  contractType?: string;
  /** Agency FAR supplement (e.g., GSAM, DFARS) — soft-required draft context (ADR-0015 D3). */
  agencySupplement?: string;
  ceilingValue?: number;
  /** DEMO-REDESIGN-spec §4 — richer draft context. */
  periodOfPerformance?: string;
  placeOfPerformance?: string;
  evalApproach?: string;
  keyPersonnel?: string;
  noticeType?: string;
  sections?: SolicitationSections;
  proposalsDueAt?: string;
}

/** Workflow 1 state machine (feature-inventory-target.md). */
export type SolicitationState =
  | 'DRAFT'
  | 'INTERNAL_REVIEW'
  | 'READY_TO_PUBLISH'
  | 'PUBLISHED'
  | 'AMENDED'
  | 'CLOSED'
  | 'CANCELLED';

/**
 * Response from POST /draft-solicitation/section (orchestrator).
 *
 * Locked interface — see docs/specs/m2-grounded-retrieval/retrieval-pipeline.md §2 and
 * docs/specs/m2-grounded-retrieval/ui-far-sections.md §2. UI generates X-Request-ID
 * (uuid v4) client-side and passes it on the header; orchestrator
 * echoes it back on `request_id`.
 */
export interface DraftSectionRequest {
  section_id: string;          // 'A'..'M' (excluding 'I')
  solicitation_id: string;
  /** Step 1 metadata (ADR-0015 D3) — tier-validated by backend preflight. */
  naics?: string | null;
  set_aside?: string | null;
  contract_type?: string | null;
  agency_supplement?: string | null;
  query?: string;
  constraints?: string;
}

/** ── M1 Phase 3 — batch coordinator types (ADR-0014; design ref §18.12.2) ── */

export interface BatchDraftRequest {
  solicitation_id: string;
  naics?: string | null;
  set_aside?: string | null;
  contract_type?: string | null;
  agency_supplement?: string | null;
  /** DEMO-REDESIGN-spec §4 — optional richer context. */
  period_of_performance?: string | null;
  place_of_performance?: string | null;
  eval_approach?: string | null;
  key_personnel?: string | null;
  user_constraints_by_section?: Record<string, string>;
  provenances: Record<string, string | null>;
  part_iii_attachments?: PartIIIAttachmentMeta[];
}

export interface PartIIIAttachmentMeta {
  title: string;
  date?: string | null;
  page_count?: number | null;
  filename?: string | null;
}

export interface FARClauseReference {
  citation: string;
  title: string;
  prescription: string;
}

export interface PartIIClauseList {
  clauses_by_reference: FARClauseReference[];
  source: 'far_snapshot_index';
  snapshot_date: string;
  resolved_for: Record<string, string | null>;
}

export interface PartResult {
  part: 'I' | 'II' | 'III' | 'IV';
  kind: 'llm_drafted' | 'programmatic_resolved' | 'wizard_provided';
  sections: Record<string, DraftSectionResponse | PartIIClauseList | PartIIIAttachmentMeta[] | null>;
}

export interface SolicitationDraftBundle {
  solicitation_id: string;
  parts: Partial<Record<'I' | 'II' | 'III' | 'IV', PartResult>>;
  overall_outcome: 'batch_completed' | 'batch_interrupted';
  consistency_report: unknown | null;
  pending_interrupts: PendingToolCall[];
  request_id: string;
  batch_run_id: string;
}

export interface BatchPerSectionDecision {
  section_id: 'C' | 'H' | 'L' | 'M';
  decision: 'approve' | 'edit' | 'reject';
  edited_args?: Record<string, unknown> | null;
  reason?: string | null;
}

/** ── M1 Phase 4 — consistency critic types (ADR-0013 D6) ── */

export type CriticSeverity = 'info' | 'warn' | 'fail';

export interface LMMismatch {
  type: 'l_without_m' | 'm_without_l' | 'weak_mapping';
  l_instruction: string | null;
  m_factor: string | null;
  severity: CriticSeverity;
  rationale: string;
}

export interface LMAlignmentReport {
  mismatches: LMMismatch[];
  overall_severity: CriticSeverity;
  model: string;
  input_tokens: number;
  output_tokens: number;
}

export interface SetAsideMismatch {
  set_aside: string;
  expected_reps: string[];
  actual_reps: string[];
  missing: string[];
  extra: string[];
  severity: CriticSeverity;
}

export interface SetAsideConsistencyReport {
  mismatches: SetAsideMismatch[];
  overall_severity: CriticSeverity;
}

export interface CLINGap {
  clin_id: string;
  missing_in: ('C' | 'F' | 'L')[];
  severity: CriticSeverity;
}

export interface CLINCoverageReport {
  gaps: CLINGap[];
  overall_severity: CriticSeverity;
}

export interface ConsistencyReport {
  solicitation_id: string;
  run_id: string;
  lm_alignment: LMAlignmentReport;
  set_aside_consistency: SetAsideConsistencyReport;
  clin_coverage: CLINCoverageReport;
  overall_severity: CriticSeverity;
  blocks_submit: boolean; // Phase 1: always false
  model_used: string | null;
  timestamp: string;
  /** Known issue: critic model loops; backend returns a skipped report
   *  instead of failing. CO must review manually when true. */
  critic_skipped?: boolean;
  skip_reason?: string | null;
}

export interface CriticRequest {
  solicitation_id: string;
  sections: Record<string, string | null>;
  set_aside?: string | null;
}

export interface DraftSectionCitation {
  chunk_id: string;
  text: string;
  far_part: string;
  far_section: string;
  far_clause: string;
  snapshot_date: string;
  relevance_score: number;
}

/**
 * Pending HITL tool call — populated when outcome === 'interrupted'
 * (ADR-0012 D6/D8; resume surface lands Phase 2).
 */
export interface PendingToolCall {
  tool_name: string;
  args: Record<string, unknown>;
  reason: string;
}

export interface DraftSectionResponse {
  /**
   * M1 contract (design ref §4.1): 'hitl_pending' is REMOVED — 'interrupted'
   * replaces it (breaking literal change; design ref §14.1).
   */
  outcome:
    | 'draft_returned'
    | 'interrupted'
    | 'withheld'
    | 'citation_verification_failed';
  section_text: string | null;
  section_id: string;
  citations: DraftSectionCitation[];
  gate_decision: GateDecision;
  requires_human_review: boolean;
  rerank_top_score: number | null;
  request_id: string;
  /** Checkpoint thread id — `${solicitation_id}:${section_id}:${request_id}`. */
  run_id?: string;
  pending_tool_call?: PendingToolCall | null;
  /** Soft-missing Step 1 fields the draft ran without (ADR-0015 D5). */
  degraded_context?: string[];
}
