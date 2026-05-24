/**
 * Vendor Q&A on a solicitation.
 *
 * Vendor question → CS triage → CS drafts answer (AI-assisted via
 * `POST /answer-qa`) → CO approves → published to all registered
 * vendors with redaction of proprietary content.
 */
export interface Qna {
  id: string;
  solicitationId: string;
  question: string;
  answer: string | null;
  vendorId: string;                // redacted on publish
  postedAt: string;                // ISO
  publishedAt: string | null;      // ISO
  status: 'NEW' | 'TRIAGED' | 'DRAFT_ANSWER' | 'AWAITING_CO_APPROVAL' | 'PUBLISHED';
}
