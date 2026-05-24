/**
 * Audit event — write surface for every state transition.
 *
 * Touches Debt Item 2 (race produces gaps visible in the search view)
 * and Item 6 (correlation ID mismatch breaks cross-service queries).
 */
export interface AuditEvent {
  id: string;
  actorId: string;
  actorName: string;
  agencyId: string;
  action: string;                  // e.g., SOLICITATION.PUBLISH
  objectType: string;
  objectId: string;
  correlationId: string;
  before: unknown | null;
  after: unknown | null;
  ts: string;                      // ISO
}

export interface AuditSearchFilter {
  actor?: string;
  action?: string;
  objectType?: string;
  objectId?: string;
  correlationId?: string;
  from?: string;
  to?: string;
}
