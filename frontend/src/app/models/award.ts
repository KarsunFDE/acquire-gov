/**
 * Post-award data model (FAR 5.705 publicizing + FAR Part 42 admin).
 */

export interface Award {
  id: string;
  evaluationId: string;
  solicitationId: string;
  winningVendorId: string;
  winningVendorName: string;
  contractNumber: string;
  awardedAt: string;
  ceilingValue: number;
  /** Debrief request window per FAR 15.506 — 5 days. */
  debriefDeadline: string;
}

export interface ContractModification {
  id: string;
  contractId: string;
  modNumber: string;               // e.g., P00001, A00001
  type: 'bilateral' | 'unilateral';
  changeDescription: string;
  effectiveAt: string;
  signedBy: string;
}

export interface Deliverable {
  id: string;
  contractId: string;
  cdrlNumber: string;              // Contract Data Requirements List
  title: string;
  dueAt: string;
  status: 'PENDING' | 'SUBMITTED' | 'ACCEPTED' | 'REJECTED';
  acceptedBy: string | null;
}

/**
 * Contractor Performance Assessment Report (FAR 42.1503).
 * Six rating dimensions per CPARS Guidance.
 */
export type CparRating = 'EXCEPTIONAL' | 'VERY_GOOD' | 'SATISFACTORY' | 'MARGINAL' | 'UNSATISFACTORY';

export interface CparFactor {
  factor: 'QUALITY' | 'SCHEDULE' | 'COST_CONTROL' | 'MANAGEMENT' | 'SMALL_BUSINESS' | 'REGULATORY_COMPLIANCE';
  rating: CparRating;
  narrative: string;
}

export interface Cpar {
  id: string;
  contractId: string;
  period: 'INTERIM' | 'FINAL';
  ratings: CparFactor[];
  overallNarrative: string;
  vendorRebuttal: string | null;
  /** 60-day window per FAR 42.1503(d). */
  rebuttalDeadline: string;
  status: 'DRAFT' | 'AWAITING_VENDOR_REVIEW' | 'PUBLISHED';
}
