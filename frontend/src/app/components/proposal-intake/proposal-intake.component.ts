import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FIXTURE_PROPOSALS, FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';
import { Proposal } from '../../models/proposal';

/**
 * Proposal Intake — sealed-bid lockbox.
 *
 * Pre-deadline: shows count + submission timestamps only. Volume
 * contents sealed in MongoDB GridFS. Post-deadline, CO clicks
 * "unseal" → atomic + audit-logged (Item 2 race surface — race on
 * crash leaves audit gap). Cross-tenant unsealing must be impossible
 * (Item 10).
 */
@Component({
  selector: 'app-proposal-intake',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Proposal intake — {{ solicitationTitle() }}</h2>
        <div class="subtitle">Sealed until deadline · DLA DIBBS-style sealed-bid lockbox</div>
      </div>
      <a [routerLink]="['/solicitations', solicitationId, 'edit']"><button class="secondary">← Back to solicitation</button></a>
    </div>

    <div class="kpi-grid">
      <div class="kpi-tile">
        <div class="kpi-value">{{ proposals.length }}</div>
        <div class="kpi-label">Proposals submitted</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ totalVolumes() }}</div>
        <div class="kpi-label">Volumes (I/II/III)</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ sealedRemainingDays() }}</div>
        <div class="kpi-label">Days until unseal</div>
      </div>
    </div>

    <div class="card">
      <h3>Submitted proposals</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Contents sealed until {{ proposals[0] && proposals[0].sealedUntil | date:'medium' }}.
        CO will atomically unseal post-deadline.
      </p>
      <table>
        <thead><tr><th>Vendor</th><th>Submitted</th><th>Volumes</th><th>Amendment acks</th></tr></thead>
        <tbody>
          <tr *ngFor="let p of proposals">
            <td>{{ p.vendorName }} <code style="font-size:0.7rem">{{ p.vendorId }}</code></td>
            <td>{{ p.submittedAt | date:'short' }}</td>
            <td>
              <span *ngFor="let v of p.volumes" style="margin-right:0.5rem">
                {{ v.volume.split('_')[0] }} ({{ v.pageCount }}p)
              </span>
            </td>
            <td>{{ p.amendmentAcks.length }}</td>
          </tr>
          <tr *ngIf="proposals.length === 0">
            <td colspan="4"><em>No proposals yet. Visible vendor count: 0.</em></td>
          </tr>
        </tbody>
      </table>
      <button style="margin-top:0.75rem" [disabled]="!unsealReady()">
        {{ unsealReady() ? 'Unseal proposals (CO only)' : 'Sealed until deadline' }}
      </button>
    </div>
  `,
})
export class ProposalIntakeComponent implements OnInit {
  solicitationId = '';
  proposals: Proposal[] = [];

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.solicitationId = this.route.snapshot.params['id'];
    this.proposals = FIXTURE_PROPOSALS.filter((p) => p.solicitationId === this.solicitationId);
  }

  solicitationTitle(): string {
    return FIXTURE_SOLICITATIONS.find((s) => s.id === this.solicitationId)?.title ?? this.solicitationId;
  }

  totalVolumes(): number {
    return this.proposals.reduce((sum, p) => sum + p.volumes.length, 0);
  }

  sealedRemainingDays(): number {
    const p = this.proposals[0];
    if (!p) return 0;
    return Math.max(0, Math.ceil((new Date(p.sealedUntil).getTime() - Date.now()) / (1000 * 60 * 60 * 24)));
  }

  unsealReady(): boolean {
    const p = this.proposals[0];
    return !!p && new Date(p.sealedUntil).getTime() < Date.now();
  }
}
