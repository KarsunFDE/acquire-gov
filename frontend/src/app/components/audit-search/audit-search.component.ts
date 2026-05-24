import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuditEvent, AuditSearchFilter } from '../../models/audit';
import { FIXTURE_AUDIT_EVENTS } from '../../services/mock-fixtures';

/**
 * Audit Log Search (sys_admin + oig_reviewer).
 *
 * Filter by actor / action / object / correlation_id. Per
 * feature-inventory-target.md and brownfield-debt.md Item 2:
 * race produces missing rows visible here after crash drill.
 * Item 6: correlation-id mismatch breaks cross-service queries.
 *
 * FedRAMP AU controls; GSA OIG audit objectives.
 */
@Component({
  selector: 'app-audit-search',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>Audit log search</h2>
        <div class="subtitle">FedRAMP AU-2/AU-6 · race-gap surface (Item 2) · correlation-ID mismatch surface (Item 6)</div>
      </div>
      <button class="secondary" (click)="exportCsv()">Export CSV</button>
    </div>

    <div class="card">
      <div class="two-col" style="grid-template-columns:repeat(3, 1fr)">
        <label><span class="label-text">Actor</span>
          <input [(ngModel)]="filter.actor" (keyup.enter)="search()" placeholder="e.g., co-reeves"/>
        </label>
        <label><span class="label-text">Action</span>
          <input [(ngModel)]="filter.action" (keyup.enter)="search()" placeholder="SOLICITATION.PUBLISH"/>
        </label>
        <label><span class="label-text">Object ID</span>
          <input [(ngModel)]="filter.objectId" (keyup.enter)="search()" placeholder="sol-0142"/>
        </label>
        <label><span class="label-text">Correlation ID</span>
          <input [(ngModel)]="filter.correlationId" (keyup.enter)="search()" placeholder="r-abc-001"/>
        </label>
        <label><span class="label-text">From</span>
          <input type="date" [(ngModel)]="filter.from" (change)="search()"/>
        </label>
        <label><span class="label-text">To</span>
          <input type="date" [(ngModel)]="filter.to" (change)="search()"/>
        </label>
      </div>
      <button (click)="search()">Search</button>
      <button class="secondary" (click)="reset()">Reset</button>
    </div>

    <p style="color:var(--color-fg-muted);font-size:0.85rem">
      {{ results.length }} events
    </p>

    <table>
      <thead>
        <tr><th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Correlation</th><th>Diff</th></tr>
      </thead>
      <tbody>
        <tr *ngFor="let e of results">
          <td>{{ e.ts | date:'short' }}</td>
          <td>{{ e.actorName }}<br><small>{{ e.actorId }}</small></td>
          <td><code>{{ e.action }}</code></td>
          <td>{{ e.objectType }} <code>{{ e.objectId }}</code></td>
          <td><code style="font-size:0.75rem">{{ e.correlationId }}</code></td>
          <td>
            <details>
              <summary>before/after</summary>
              <pre style="font-size:0.75rem">before: {{ e.before | json }}
after:  {{ e.after | json }}</pre>
            </details>
          </td>
        </tr>
        <tr *ngIf="results.length === 0">
          <td colspan="6"><em>No audit events match.</em></td>
        </tr>
      </tbody>
    </table>
  `,
})
export class AuditSearchComponent implements OnInit {
  filter: AuditSearchFilter = {};
  results: AuditEvent[] = [];

  ngOnInit(): void {
    this.results = [...FIXTURE_AUDIT_EVENTS];
  }

  search(): void {
    this.results = FIXTURE_AUDIT_EVENTS.filter((e) => {
      if (this.filter.actor && !e.actorId.includes(this.filter.actor) && !e.actorName.toLowerCase().includes(this.filter.actor.toLowerCase())) return false;
      if (this.filter.action && !e.action.includes(this.filter.action)) return false;
      if (this.filter.objectId && !e.objectId.includes(this.filter.objectId)) return false;
      if (this.filter.correlationId && !e.correlationId.includes(this.filter.correlationId)) return false;
      return true;
    });
  }

  reset(): void {
    this.filter = {};
    this.results = [...FIXTURE_AUDIT_EVENTS];
  }

  exportCsv(): void {
    alert(`Exporting ${this.results.length} events to CSV (stub).`);
  }
}
