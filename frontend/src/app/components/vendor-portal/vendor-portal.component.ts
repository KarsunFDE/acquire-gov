import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_PROPOSALS, FIXTURE_AMENDMENTS, FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';

/**
 * Vendor Proposal Portal — vendor-facing.
 *
 * Vendor's own draft + submitted proposals across all opportunities;
 * amendment-acknowledgement state. Touches Item 10 (must not leak
 * other vendors' data — the W2 Wed retrieval-boundary surface).
 */
@Component({
  selector: 'app-vendor-portal',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Vendor portal</h2>
        <div class="subtitle">{{ role.current.displayName }}</div>
      </div>
      <a routerLink="/public/opportunities"><button>Browse opportunities</button></a>
    </div>

    <div class="card">
      <h3>My proposals ({{ myProposals().length }})</h3>
      <table>
        <thead>
          <tr><th>Opportunity</th><th>Submitted</th><th>Volumes</th><th>Amendment acks</th><th>Action</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let p of myProposals()">
            <td>
              <a [routerLink]="['/public/opportunities', p.solicitationId]">{{ titleFor(p.solicitationId) }}</a>
            </td>
            <td>{{ p.submittedAt | date:'short' }}</td>
            <td>{{ p.volumes.length }}</td>
            <td>{{ p.amendmentAcks.length }} / {{ amendmentCount(p.solicitationId) }}</td>
            <td>
              <button *ngIf="needsAck(p)" (click)="ack(p)">Acknowledge amendment</button>
            </td>
          </tr>
          <tr *ngIf="myProposals().length === 0">
            <td colspan="5"><em>No proposals on file.</em></td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
})
export class VendorPortalComponent {
  constructor(public role: RoleService) {}

  myProposals() {
    const vid = this.role.current.vendorDuns ? 'vnd-acme' : 'vnd-acme';
    return FIXTURE_PROPOSALS.filter((p) => p.vendorId === vid);
  }

  titleFor(solId: string): string {
    return FIXTURE_SOLICITATIONS.find((s) => s.id === solId)?.title ?? solId;
  }

  amendmentCount(solId: string): number {
    return FIXTURE_AMENDMENTS.filter((a) => a.solicitationId === solId).length;
  }

  needsAck(p: any): boolean {
    return this.amendmentCount(p.solicitationId) > p.amendmentAcks.length;
  }

  ack(p: any): void {
    p.amendmentAcks = [...p.amendmentAcks, p.amendmentAcks.length + 1];
  }
}
