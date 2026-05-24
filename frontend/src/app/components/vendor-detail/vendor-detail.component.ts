import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FIXTURE_VENDORS, FIXTURE_CPARS, FIXTURE_AWARD } from '../../services/mock-fixtures';
import { Vendor } from '../../models/vendor';

/**
 * Vendor detail with past CPARs (CPARS/PPIRS-style record).
 */
@Component({
  selector: 'app-vendor-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>{{ vendor?.name }}</h2>
        <div class="subtitle">DUNS {{ vendor?.duns }} · UEI {{ vendor?.uei }} · CAGE {{ vendor?.cage }}</div>
      </div>
      <a routerLink="/vendors"><button class="secondary">← Directory</button></a>
    </div>

    <div class="two-col">
      <div class="card">
        <h3>Entity profile</h3>
        <table>
          <tbody>
            <tr><th>NAICS codes</th><td>{{ vendor?.naicsCodes?.join(', ') }}</td></tr>
            <tr><th>Set-asides</th><td>{{ vendor?.setAsides?.join(', ') }}</td></tr>
            <tr><th>Registered</th><td>{{ vendor?.registeredAt | date:'mediumDate' }}</td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h3>Past performance rollup</h3>
        <table>
          <tbody>
            <tr><th>Exceptional</th><td>{{ vendor?.pastPerformanceAvg?.exceptional }}</td></tr>
            <tr><th>Very Good</th><td>{{ vendor?.pastPerformanceAvg?.veryGood }}</td></tr>
            <tr><th>Satisfactory</th><td>{{ vendor?.pastPerformanceAvg?.satisfactory }}</td></tr>
            <tr><th>Marginal</th><td>{{ vendor?.pastPerformanceAvg?.marginal }}</td></tr>
            <tr><th>Unsatisfactory</th><td>{{ vendor?.pastPerformanceAvg?.unsatisfactory }}</td></tr>
            <tr><th>Total reports</th><td>{{ vendor?.pastPerformanceAvg?.totalReports }}</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h3>Recent CPARs</h3>
      <ul *ngIf="cpars().length > 0; else noCpars">
        <li *ngFor="let c of cpars()">
          <a [routerLink]="['/contracts', c.contractId, 'cpars']">
            {{ c.period }} CPAR · Contract {{ c.contractId }}
          </a>
          — {{ c.overallNarrative }}
        </li>
      </ul>
      <ng-template #noCpars><div class="empty-state">No CPARs on file.</div></ng-template>
    </div>
  `,
})
export class VendorDetailComponent implements OnInit {
  vendor: Vendor | null = null;
  id = '';

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.params['id'];
    this.vendor = FIXTURE_VENDORS.find((v) => v.id === this.id) ?? FIXTURE_VENDORS[0];
  }

  cpars() {
    if (FIXTURE_AWARD.winningVendorId === this.vendor?.id) {
      return FIXTURE_CPARS;
    }
    return [];
  }
}
