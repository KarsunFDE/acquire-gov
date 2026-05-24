import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FIXTURE_MODIFICATIONS, FIXTURE_DELIVERABLES, FIXTURE_AWARD } from '../../services/mock-fixtures';
import { ContractModification, Deliverable } from '../../models/award';

/**
 * Contract Administration (FAR Part 42).
 *
 * Modifications (bilateral / unilateral), CDRL deliverable status,
 * QASP surveillance findings, invoice acceptance. Touches Item 3
 * (deliverable status calls evaluation-service → solicitation-service)
 * and Item 6 (correlation-id mismatch).
 */
@Component({
  selector: 'app-contract-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Contract administration — {{ award?.contractNumber }}</h2>
        <div class="subtitle">FAR Part 42 · Mods · CDRL · QASP</div>
      </div>
      <a [routerLink]="['/contracts', contractId, 'cpars']"><button class="secondary">CPAR reviews →</button></a>
    </div>

    <div class="two-col">
      <div class="card">
        <h3>Contract modifications</h3>
        <table>
          <thead>
            <tr><th>#</th><th>Type</th><th>Effective</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let m of mods">
              <td><strong>{{ m.modNumber }}</strong></td>
              <td><span class="badge" [class.review]="m.type === 'bilateral'">{{ m.type }}</span></td>
              <td>{{ m.effectiveAt | date:'shortDate' }}</td>
              <td>{{ m.changeDescription }}</td>
            </tr>
          </tbody>
        </table>
        <h4 style="margin-top:1rem">Issue new modification</h4>
        <label><span class="label-text">Mod number</span>
          <input [(ngModel)]="newMod.modNumber" placeholder="P00003"/>
        </label>
        <label><span class="label-text">Type</span>
          <select [(ngModel)]="newMod.type">
            <option value="bilateral">Bilateral</option>
            <option value="unilateral">Unilateral</option>
          </select>
        </label>
        <label><span class="label-text">Description</span>
          <textarea rows="2" [(ngModel)]="newMod.changeDescription"></textarea>
        </label>
        <button (click)="issueMod()" [disabled]="!newMod.modNumber">Issue modification</button>
      </div>

      <div class="card">
        <h3>CDRL deliverables</h3>
        <table>
          <thead>
            <tr><th>CDRL</th><th>Title</th><th>Due</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let d of deliverables">
              <td><code>{{ d.cdrlNumber }}</code></td>
              <td>{{ d.title }}</td>
              <td>{{ d.dueAt | date:'shortDate' }}</td>
              <td><span class="badge" [ngClass]="badgeFor(d.status)">{{ d.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h3>QASP surveillance log</h3>
      <p>Quality Assurance Surveillance Plan findings. Each finding triggers a
        notification to PM + CO; severity ≥ HIGH escalates to a Finding entity.</p>
      <p><em>Empty — no QASP findings this period.</em></p>
    </div>
  `,
})
export class ContractAdminComponent implements OnInit {
  contractId = 'ctr-0001';
  award = FIXTURE_AWARD;
  mods: ContractModification[] = [];
  deliverables: Deliverable[] = [];

  newMod: Partial<ContractModification> = { type: 'bilateral', modNumber: '', changeDescription: '' };

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.contractId = this.route.snapshot.params['id'] || 'ctr-0001';
    this.mods = FIXTURE_MODIFICATIONS.filter((m) => m.contractId === this.contractId);
    this.deliverables = FIXTURE_DELIVERABLES.filter((d) => d.contractId === this.contractId);
  }

  issueMod(): void {
    const m: ContractModification = {
      id: `mod-${Date.now()}`,
      contractId: this.contractId,
      modNumber: this.newMod.modNumber!,
      type: this.newMod.type as 'bilateral' | 'unilateral',
      changeDescription: this.newMod.changeDescription ?? '',
      effectiveAt: new Date().toISOString(),
      signedBy: 'co-current',
    };
    this.mods = [...this.mods, m];
    this.newMod = { type: 'bilateral', modNumber: '', changeDescription: '' };
  }

  badgeFor(status: string): string {
    if (status === 'ACCEPTED') return 'published';
    if (status === 'SUBMITTED') return 'review';
    if (status === 'REJECTED') return 'urgent';
    return 'draft';
  }
}
