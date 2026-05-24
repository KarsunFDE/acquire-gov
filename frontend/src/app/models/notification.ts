/**
 * In-app notification (bell + drawer surface).
 *
 * Source events mapped in feature-inventory-target.md notification
 * surfaces table. Item 6 (inconsistent correlation IDs) bites because
 * the notification log uses a different correlation ID than the
 * originating service request.
 */
export type NotificationKind =
  | 'SOLICITATION_PUBLISHED'
  | 'AMENDMENT_ISSUED'
  | 'PROPOSAL_RECEIVED'
  | 'EVALUATION_DUE'
  | 'AWARD_DECISION'
  | 'CPAR_WINDOW_OPEN'
  | 'QASP_FINDING'
  | 'DEBRIEF_REQUESTED'
  | 'OIG_FINDING_OPENED';

export interface Notification {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  recipientRole: string;
  link: string;                    // router link
  createdAt: string;               // ISO
  readAt: string | null;
}
