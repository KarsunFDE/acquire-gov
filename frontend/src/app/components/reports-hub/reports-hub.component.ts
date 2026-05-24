import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FIXTURE_SOLICITATIONS, FIXTURE_VENDORS, FIXTURE_AWARD, FIXTURE_MODIFICATIONS, FIXTURE_FINDINGS, FIXTURE_AUDIT_EVENTS } from '../../services/mock-fixtures';

/**
 * Reports + dashboards hub.
 *
 * 5 reports per feature-inventory-target.md "Reports + dashboards":
 *   - Acquisition Pipeline (CO workload; SAM.gov contracting workspace)
 *   - Vendor Past Performance (CPARS/PPIRS rollup)
 *   - Contract Spend by Agency (FPDS-NG shaped)
 *   - OIG Findings Status (GSA OIG audit report patterns)
 *   - Audit-log Activity (FedRAMP AU-2/AU-6)
 *
 * Each renders as a card + a drill-down link. Drill-down route lives
 * at `/reports/:slug` and reuses this same component with a query param.
 */
@Component({
  selector: 'app-reports-hub',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Reports + dashboards</h2>
        <div class="subtitle">FPDS-NG / CPARS / FedRAMP AU-shaped reporting</div>
      </div>
    </div>

    <div class="two-col">
      <div class="card">
        <h3>Acquisition Pipeline</h3>
        <p>Solicitations grouped by state + posted date.</p>
        <table>
          <thead><tr><th>State</th><th>Count</th></tr></thead>
          <tbody>
            <tr *ngFor="let row of pipelineByState()">
              <td>{{ row.state }}</td>
              <td>{{ row.count }}</td>
            </tr>
          </tbody>
        </table>
        <a routerLink="/reports/pipeline">Drill down →</a>
      </div>

      <div class="card">
        <h3>Vendor Past Performance</h3>
        <p>CPARs joined to Vendor; rolled-up ratings by NAICS.</p>
        <table>
          <thead><tr><th>Vendor</th><th>Reports</th><th>Exceptional/Very Good</th></tr></thead>
          <tbody>
            <tr *ngFor="let v of FIXTURE_VENDORS">
              <td>{{ v.name }}</td>
              <td>{{ v.pastPerformanceAvg.totalReports }}</td>
              <td>{{ v.pastPerformanceAvg.exceptional + v.pastPerformanceAvg.veryGood }}</td>
            </tr>
          </tbody>
        </table>
        <a routerLink="/reports/vendor-past-performance">Drill down →</a>
      </div>

      <div class="card">
        <h3>Contract Spend by Agency</h3>
        <p>Awards + ContractMods aggregated (FPDS-NG shape).</p>
        <table>
          <thead><tr><th>Agency</th><th>Ceiling ($M)</th><th>Mods</th></tr></thead>
          <tbody>
            <tr>
              <td>GSA-FAS</td>
              <td>{{ award().ceilingValue / 1_000_000 }}</td>
              <td>{{ FIXTURE_MODIFICATIONS.length }}</td>
            </tr>
          </tbody>
        </table>
        <a routerLink="/reports/contract-spend">Drill down →</a>
      </div>

      <div class="card">
        <h3>OIG Findings Status</h3>
        <p>Findings grouped by status × age.</p>
        <table>
          <thead><tr><th>Severity</th><th>Status</th><th>Due</th></tr></thead>
          <tbody>
            <tr *ngFor="let f of findings()">
              <td><span class="badge" [class.urgent]="f.severity === 'CRITICAL' || f.severity === 'HIGH'">{{ f.severity }}</span></td>
              <td>{{ f.status }}</td>
              <td>{{ f.remediationDueAt | date:'mediumDate' }}</td>
            </tr>
          </tbody>
        </table>
        <a routerLink="/admin/findings">Open the tracker →</a>
      </div>

      <div class="card" style="grid-column:1/-1">
        <h3>Audit-log Activity</h3>
        <p>AuditEvents grouped by actor + action (FedRAMP AU-2/AU-6).
          The race in Item 2 produces gaps visible here.</p>
        <table>
          <thead><tr><th>Actor</th><th>Action</th><th>Object</th><th>Correlation ID</th><th>Time</th></tr></thead>
          <tbody>
            <tr *ngFor="let e of audit()">
              <td>{{ e.actorName }}</td>
              <td>{{ e.action }}</td>
              <td>{{ e.objectType }} {{ e.objectId }}</td>
              <td><code>{{ e.correlationId }}</code></td>
              <td>{{ e.ts | date:'short' }}</td>
            </tr>
          </tbody>
        </table>
        <a routerLink="/admin/audit">Open audit search →</a>
      </div>
    </div>
  `,
})
export class ReportsHubComponent {
  FIXTURE_VENDORS = FIXTURE_VENDORS;
  FIXTURE_MODIFICATIONS = FIXTURE_MODIFICATIONS;

  pipelineByState(): { state: string; count: number }[] {
    const groups: Record<string, number> = {};
    FIXTURE_SOLICITATIONS.forEach((s) => {
      groups[s.status as string] = (groups[s.status as string] ?? 0) + 1;
    });
    return Object.entries(groups).map(([state, count]) => ({ state, count }));
  }

  award() {
    return FIXTURE_AWARD;
  }

  findings() {
    return FIXTURE_FINDINGS;
  }

  audit() {
    return FIXTURE_AUDIT_EVENTS;
  }
}
