import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { Notification } from '../models/notification';

/**
 * In-app notification bus (bell icon + drawer).
 *
 * Per feature-inventory-target.md notification table. Item 6
 * (correlation-ID mismatch) is reinforced by the fact that this
 * client-side mock generates its own UUID independent of the
 * triggering service-side correlation ID.
 */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly subject = new BehaviorSubject<Notification[]>(this.seed());
  readonly items$: Observable<Notification[]> = this.subject.asObservable();

  markRead(id: string): void {
    this.subject.next(
      this.subject.value.map((n) =>
        n.id === id ? { ...n, readAt: new Date().toISOString() } : n,
      ),
    );
  }

  markAllRead(): void {
    const ts = new Date().toISOString();
    this.subject.next(
      this.subject.value.map((n) => ({ ...n, readAt: n.readAt ?? ts })),
    );
  }

  unreadCount(): number {
    return this.subject.value.filter((n) => !n.readAt).length;
  }

  private seed(): Notification[] {
    return [
      {
        id: 'n-1001',
        kind: 'AMENDMENT_ISSUED',
        title: 'Amendment 0002 issued — RFP-GSA-25-AM-0142',
        body: 'CO Reeves issued Amendment 0002 (deadline extension). Vendor acknowledgement required.',
        recipientRole: 'contracting_officer',
        link: '/solicitations/sol-0142/amendments',
        createdAt: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1002',
        kind: 'PROPOSAL_RECEIVED',
        title: '3 proposals received — RFP-GSA-25-IT-0203',
        body: 'Sealed until proposal deadline 2026-06-12 17:00 ET.',
        recipientRole: 'contracting_officer',
        link: '/solicitations/sol-0203/proposals',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1003',
        kind: 'EVALUATION_DUE',
        title: 'Section M scoring due in 5 days',
        body: 'Evaluation EVAL-2026-0142 — 3 of 6 factors scored.',
        recipientRole: 'evaluator',
        link: '/evaluation/workspace',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1004',
        kind: 'CPAR_WINDOW_OPEN',
        title: 'CPAR rebuttal window open — Contract GS-35F-0001V',
        body: 'Vendor has 60 days to submit rebuttal per FAR 42.1503(d).',
        recipientRole: 'vendor',
        link: '/contracts/ctr-0001/cpars',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1005',
        kind: 'OIG_FINDING_OPENED',
        title: 'OIG Finding F-2026-0007 opened',
        body: 'AC-2 access-control finding — evidence requested.',
        recipientRole: 'oig_reviewer',
        link: '/admin/findings',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
        readAt: new Date(Date.now() - 1000 * 60 * 60 * 47).toISOString(),
      },
    ];
  }
}
