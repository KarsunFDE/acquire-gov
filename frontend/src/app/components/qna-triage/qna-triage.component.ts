import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Qna } from '../../models/qna';
import { FIXTURE_QNA, FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';

/**
 * Q&A Triage workspace (CS, CO).
 *
 * Vendor questions → CS triages → CS drafts answer (AI-assisted via
 * `POST /answer-qa`) → CO approves → published to all registered
 * vendors. W2 RAG-fallback HITL (#2 Thu) lands at the "publish answer"
 * gate. Item 9 (no sanitization) bites when vendor questions contain HTML.
 */
@Component({
  selector: 'app-qna-triage',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Q&amp;A triage — {{ solicitationTitle() }}</h2>
        <div class="subtitle">CS triages · AI-drafts answer · CO approves · published to all registered vendors</div>
      </div>
      <a [routerLink]="['/solicitations', solicitationId, 'edit']"><button class="secondary">← Back to solicitation</button></a>
    </div>

    <div class="hitl-banner">
      <strong>HITL gate (W2 #2 — RAG fallback):</strong>
      AI-drafted answer must be reviewed for clause citations that don't exist + factual drift before CO publishes.
    </div>

    <table>
      <thead>
        <tr><th style="width:32%">Question</th><th>Answer (draft / published)</th><th>Status</th><th>Action</th></tr>
      </thead>
      <tbody>
        <tr *ngFor="let q of qna">
          <td>
            <strong>Q{{ q.id }}</strong>
            <p>{{ q.question }}</p>
            <div style="font-size:0.75rem;color:var(--color-fg-muted)">
              From vendor {{ q.vendorId }} · {{ q.postedAt | date:'short' }}
            </div>
          </td>
          <td>
            <textarea rows="4" [(ngModel)]="q.answer"
                      [disabled]="q.status === 'PUBLISHED'"
                      placeholder="Draft answer here, or use AI-draft below"></textarea>
            <button class="secondary" *ngIf="q.status !== 'PUBLISHED'"
                    (click)="aiDraft(q)" style="margin-top:0.25rem;font-size:0.8rem">▦ AI-draft</button>
          </td>
          <td><span class="badge" [ngClass]="badgeFor(q.status)">{{ q.status }}</span></td>
          <td>
            <button *ngIf="q.status === 'NEW' || q.status === 'TRIAGED'"
                    (click)="triage(q)">Mark drafted</button>
            <button *ngIf="q.status === 'DRAFT_ANSWER'"
                    (click)="sendForApproval(q)">Send for CO approval</button>
            <button *ngIf="q.status === 'AWAITING_CO_APPROVAL'"
                    (click)="publish(q)">Publish</button>
          </td>
        </tr>
      </tbody>
    </table>
  `,
})
export class QnaTriageComponent implements OnInit {
  solicitationId = '';
  qna: Qna[] = [];

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.solicitationId = this.route.snapshot.params['id'];
    this.qna = FIXTURE_QNA
      .filter((q) => q.solicitationId === this.solicitationId)
      .map((q) => ({ ...q }));
  }

  solicitationTitle(): string {
    return FIXTURE_SOLICITATIONS.find((s) => s.id === this.solicitationId)?.title ?? this.solicitationId;
  }

  aiDraft(q: Qna): void {
    q.answer = `Per Section L.5.2, ${q.question.endsWith('?') ? '' : ''}[AI-drafted using FAR/DFARS clause-library RAG; review for fabricated clause IDs before publishing].`;
    q.status = 'DRAFT_ANSWER';
  }

  triage(q: Qna): void { q.status = 'DRAFT_ANSWER'; }

  sendForApproval(q: Qna): void { q.status = 'AWAITING_CO_APPROVAL'; }

  publish(q: Qna): void {
    q.status = 'PUBLISHED';
    q.publishedAt = new Date().toISOString();
  }

  badgeFor(s: string): string {
    if (s === 'PUBLISHED') return 'published';
    if (s === 'AWAITING_CO_APPROVAL') return 'review';
    if (s === 'NEW') return 'urgent';
    return 'draft';
  }
}
