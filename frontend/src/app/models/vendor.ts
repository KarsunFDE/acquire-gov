/**
 * Vendor (offeror / contractor).
 *
 * Referenced by Proposal, Award, Cpar. Uses DUNS + UEI + CAGE
 * identifiers (SAM.gov entity model).
 */
export interface CparAggregateRating {
  exceptional: number;
  veryGood: number;
  satisfactory: number;
  marginal: number;
  unsatisfactory: number;
  totalReports: number;
}

export interface Vendor {
  id: string;
  duns: string;
  uei: string;
  cage: string;
  name: string;
  naicsCodes: string[];
  setAsides: ('SDVOSB' | 'WOSB' | 'HUBZONE' | '8A' | 'SMALL_BUSINESS')[];
  registeredAt: string;
  /** Rolled CPAR ratings across all contracts (computed) */
  pastPerformanceAvg: CparAggregateRating;
}
