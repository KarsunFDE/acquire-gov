import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Finding, FindingSeverity, FindingStatus } from '../../models/finding';
import { FIXTURE_FINDINGS } from '../../services/mock-fixtures';

/**
 * OIG Findings Tracker (oig_reviewer + sys_admin).
 *
 * Open findings, attached evidence requests, remediation status,
 * due dates. Meta-mirror of W6 Client Deliverability per
 * feature-inventory-target.md line 391-394: the cohort's runbook +
 * ADR catalog + eval report are themselves modeled as Findings
 * against acquire-gov (incl. Item 12 — repo's own lint debt).
 *
 * Realism: mirrors GSA OIG A210064 Contract Administration Audit pattern.
 */
@Component({
  selector: 'app-findings-tracker',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>OIG findings tracker</h2>
        <div class="subtitle">GSA OIG audit pattern · meta-runbook surface (W6)</div>
      </div>
      <button (click)="toggleNew()">+ Open finding</button>
    </div>

    <div class="card" *ngIf="newFormOpen">
      <h3>Open new finding</h3>
      <label><span class="label-text">Title</span>
        <input [(ngModel)]="draft.title"/>
      </label>
      <div class="two-col" style="grid-template-columns:1fr 1fr 1fr">
        <label><span class="label-text">Scope</span>
          <select [(ngModel)]="draft.scope">
            <option value="CONTRACT">Contract</option>
            <option value="VENDOR">Vendor</option>
            <option value="PLATFORM">Platform (acquire-gov)</option>
          </select>
        </label>
        <label><span class="label-text">Scope ID</span>
          <input [(ngModel)]="draft.scopeId"/>
        </label>
        <label><span class="label-text">Severity</span>
          <select [(ngModel)]="draft.severity">
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MODERATE">Moderate</option>
            <option value="LOW">Low</option>
            <option value="INFORMATIONAL">Informational</option>
          </select>
        </label>
      </div>
      <label><span class="label-text">Finding type (e.g., AC-2 access control)</span>
        <input [(ngModel)]="draft.findingType"/>
      </label>
      <label><span class="label-text">Description</span>
        <textarea rows="4" [(ngModel)]="draft.description"></textarea>
      </label>
      <button (click)="openFinding()">Open finding</button>
    </div>

    <div class="kpi-grid">
      <div class="kpi-tile">
        <div class="kpi-value">{{ countBy('OPEN') }}</div>
        <div class="kpi-label">Open</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ countBy('IN_REMEDIATION') }}</div>
        <div class="kpi-label">In remediation</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ countBy('CLOSED') }}</div>
        <div class="kpi-label">Closed</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ overdueCount() }}</div>
        <div class="kpi-label">Past due</div>
      </div>
    </div>

    <table>
      <thead>
        <tr><th>ID</th><th>Title</th><th>Scope</th><th>Severity</th><th>Status</th><th>Due</th><th>Evidence</th></tr>
      </thead>
      <tbody>
        <tr *ngFor="let f of findings">
          <td><code>{{ f.id }}</code></td>
          <td>{{ f.title }}<br><small>{{ f.findingType }}</small></td>
          <td>{{ f.scope }} · {{ f.scopeId }}</td>
          <td><span class="badge" [ngClass]="sevClass(f.severity)">{{ f.severity }}</span></td>
          <td><span class="badge" [ngClass]="statusClass(f.status)">{{ f.status }}</span></td>
          <td>{{ f.remediationDueAt | date:'shortDate' }}</td>
          <td>
            {{ f.evidenceRequests.length }} requested<br>
            <small>{{ fulfilled(f) }} fulfilled</small>
          </td>
        </tr>
      </tbody>
    </table>
  `,
})
export class FindingsTrackerComponent implements OnInit {
  findings: Finding[] = [];
  newFormOpen = false;
  draft: Partial<Finding> = {
    title: '',
    scope: 'PLATFORM',
    scopeId: 'acquire-gov',
    severity: 'MODERATE',
    findingType: '',
    description: '',
  };

  ngOnInit(): void {
    this.findings = [...FIXTURE_FINDINGS];
  }

  toggleNew(): void {
    this.newFormOpen = !this.newFormOpen;
  }

  openFinding(): void {
    const f: Finding = {
      id: `F-${new Date().getFullYear()}-${String(this.findings.length + 1).padStart(4, '0')}`,
      scope: this.draft.scope ?? 'PLATFORM',
      scopeId: this.draft.scopeId ?? 'acquire-gov',
      title: this.draft.title ?? '',
      findingType: this.draft.findingType ?? '',
      severity: this.draft.severity ?? 'MODERATE',
      status: 'OPEN',
      openedBy: 'oig-park',
      openedAt: new Date().toISOString(),
      remediationDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
      evidenceRequests: [],
      description: this.draft.description ?? '',
    };
    this.findings = [f, ...this.findings];
    this.newFormOpen = false;
    this.draft.title = '';
    this.draft.description = '';
  }

  countBy(s: FindingStatus): number {
    return this.findings.filter((f) => f.status === s).length;
  }

  overdueCount(): number {
    const now = Date.now();
    return this.findings.filter((f) =>
      new Date(f.remediationDueAt).getTime() < now && f.status !== 'CLOSED',
    ).length;
  }

  fulfilled(f: Finding): number {
    return f.evidenceRequests.filter((e) => e.fulfilledAt).length;
  }

  sevClass(s: FindingSeverity): string {
    if (s === 'CRITICAL' || s === 'HIGH') return 'urgent';
    if (s === 'MODERATE') return 'amended';
    return 'satisfactory';
  }

  statusClass(s: FindingStatus): string {
    if (s === 'CLOSED') return 'published';
    if (s === 'IN_REMEDIATION') return 'amended';
    return 'urgent';
  }
}
