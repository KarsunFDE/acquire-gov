import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_AWARD } from '../../services/mock-fixtures';
import { Award } from '../../models/award';

/**
 * Award Record (FAR 5.705 postaward publicizing).
 *
 * Visible to CO + PM (full record) + vendor (their own award).
 * Vendor can request debrief within 5-day window (FAR 15.506).
 */
@Component({
  selector: 'app-award-record',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Award {{ award?.id }}</h2>
        <div class="subtitle">Contract {{ award?.contractNumber }} · FAR 5.705 postaward publicizing</div>
      </div>
      <a [routerLink]="['/contracts', 'ctr-0001', 'admin']" *ngIf="role.currentRole !== 'vendor'">
        <button class="secondary">Contract administration →</button>
      </a>
    </div>

    <div class="two-col">
      <div class="card">
        <h3>Award notice</h3>
        <table>
          <tbody>
            <tr><th>Winning vendor</th><td>{{ award?.winningVendorName }}</td></tr>
            <tr><th>Contract number</th><td><code>{{ award?.contractNumber }}</code></td></tr>
            <tr><th>Awarded</th><td>{{ award?.awardedAt | date:'medium' }}</td></tr>
            <tr><th>Ceiling value</th><td>\${{ (award?.ceilingValue || 0).toLocaleString() }}</td></tr>
            <tr><th>Debrief window closes</th><td>{{ award?.debriefDeadline | date:'medium' }}</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card" *ngIf="role.currentRole === 'vendor'">
        <h3>Request debrief (FAR 15.506)</h3>
        <p style="font-size:0.85rem;color:var(--color-fg-muted)">
          5 business days from award notice. Required: rationale + specific factor questions.
        </p>
        <textarea rows="4" [(ngModel)]="debriefReason"
                  placeholder="Specific factors on which you seek explanation…"></textarea>
        <button (click)="requestDebrief()" [disabled]="!debriefReason">Submit debrief request</button>
        <div *ngIf="submitted" style="color:var(--color-success);margin-top:0.5rem">
          ✓ Debrief request submitted. CO will respond within 5 business days.
        </div>
      </div>

      <div class="card" *ngIf="role.currentRole !== 'vendor'">
        <h3>Unsuccessful offeror notifications</h3>
        <ul>
          <li>Globex Federal Systems — sent {{ award?.awardedAt | date:'shortDate' }}</li>
          <li>Initech Cloud Services — sent {{ award?.awardedAt | date:'shortDate' }}</li>
        </ul>
      </div>
    </div>
  `,
})
export class AwardRecordComponent implements OnInit {
  award: Award | null = null;
  debriefReason = '';
  submitted = false;

  constructor(public role: RoleService, private route: ActivatedRoute) {}

  ngOnInit(): void {
    // Single-award fixture for cohort demo
    this.award = FIXTURE_AWARD;
  }

  requestDebrief(): void {
    this.submitted = true;
    this.debriefReason = '';
  }
}
