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
