/**
 * OIG-style audit finding (GSA OIG A210064 Contract Administration Audit pattern).
 *
 * The meta-joke per feature-inventory-target.md line 333: the cohort's
 * own CI lint-skip (Debt Item 12) can be opened as a finding against
 * the acquire-gov repo itself. This surface IS the W6 runbook substrate.
 */
export type FindingSeverity = 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW' | 'INFORMATIONAL';
export type FindingStatus = 'OPEN' | 'EVIDENCE_REQUESTED' | 'IN_REMEDIATION' | 'CLOSED' | 'ACCEPTED_RISK';

export interface EvidenceRequest {
  id: string;
  requestedBy: string;
  requestedAt: string;
  description: string;
  fulfilledAt: string | null;
}

export interface Finding {
  id: string;
  /** Findings can be opened against contracts, vendors, or the platform itself. */
  scope: 'CONTRACT' | 'VENDOR' | 'PLATFORM';
  scopeId: string;
  title: string;
  findingType: string;             // e.g., "AC-2 access control"
  severity: FindingSeverity;
  status: FindingStatus;
  openedBy: string;
  openedAt: string;
  remediationDueAt: string;
  evidenceRequests: EvidenceRequest[];
  description: string;
}
