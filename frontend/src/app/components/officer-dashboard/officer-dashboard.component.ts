import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_SOLICITATIONS, FIXTURE_AMENDMENTS, FIXTURE_CPARS, FIXTURE_FINDINGS } from '../../services/mock-fixtures';
import { NotificationService } from '../../services/notification.service';

/**
 * Officer Dashboard — role-aware landing for CO / CS / PM / SSA.
 *
 * Per feature-inventory-target.md: KPI tiles for open solicitations,
 * proposals awaiting eval, amendments due, CPARs due in 30 days.
 * Touches Item 8 (hardcoded URL lives in the solicitation-list
 * component referenced below) — keeping the localized teaching
 * artifact intact.
 */
@Component({
  selector: 'app-officer-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>{{ greeting() }}</h2>
        <div class="subtitle">{{ role.current.displayName }} · {{ role.current.authorityNote }}</div>
      </div>
      <div>
        <a routerLink="/solicitations/new"><button>+ New solicitation</button></a>
      </div>
    </div>

    <section class="kpi-grid">
      <div class="kpi-tile">
        <div class="kpi-value">{{ openSolicitations() }}</div>
        <div class="kpi-label">Open solicitations</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ proposalsAwaitingEval() }}</div>
        <div class="kpi-label">Proposals awaiting eval</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ amendmentsPending() }}</div>
        <div class="kpi-label">Amendments unack'd</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ cparsDue() }}</div>
        <div class="kpi-label">CPARs due ≤ 30 d</div>
      </div>
      <div class="kpi-tile">
        <div class="kpi-value">{{ openFindings() }}</div>
        <div class="kpi-label">Open OIG findings</div>
      </div>
    </section>

    <div class="two-col">
      <div class="card">
        <h3>Workload pipeline</h3>
        <table>
          <thead><tr><th>Solicitation</th><th>State</th><th>Due</th></tr></thead>
          <tbody>
            <tr *ngFor="let s of pipeline()">
              <td>
                <a [routerLink]="['/solicitations', s.id, 'edit']">{{ s.title }}</a>
                <div style="font-size:0.75rem;color:var(--color-fg-muted)">{{ s.noticeType }} · NAICS {{ s.naics }}</div>
              </td>
              <td><span class="badge" [ngClass]="(s.status || '').toLowerCase()">{{ s.status }}</span></td>
              <td>{{ s.proposalsDueAt ? (s.proposalsDueAt | date:'mediumDate') : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h3>Recent activity</h3>
        <ul>
          <li *ngFor="let n of recent()">
            <strong>{{ n.title }}</strong>
            <div style="font-size:0.85rem;color:var(--color-fg-muted)">{{ n.body }} · {{ n.createdAt | date:'short' }}</div>
          </li>
        </ul>
      </div>
    </div>

    <div class="card" style="margin-top:1rem">
      <h3>Quick links</h3>
      <p>
        <a routerLink="/solicitations">All solicitations</a> ·
        <a routerLink="/reports">All reports</a> ·
        <a routerLink="/vendors">Vendor directory</a> ·
        <a routerLink="/admin/audit">Audit log search</a>
      </p>
      <p style="font-size:0.8rem;color:var(--color-fg-muted)">
        ⚠ Legacy solicitation-list (Debt Item 8) is still wired at
        <a routerLink="/solicitations">/solicitations</a> — preserved
        as the W4 Tue API-modernization teaching artifact.
      </p>
    </div>
  `,
})
export class OfficerDashboardComponent {
  constructor(public role: RoleService, private notif: NotificationService) {}

  greeting(): string {
    const hour = new Date().getHours();
    const time = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    return `${time}, ${this.role.current.displayName.split(' ')[0]}`;
  }

  openSolicitations(): number {
    return FIXTURE_SOLICITATIONS.filter((s) =>
      ['PUBLISHED', 'AMENDED', 'INTERNAL_REVIEW'].includes(s.status as string),
    ).length;
  }

  proposalsAwaitingEval(): number {
    return 3; // matches FIXTURE_PROPOSALS count
  }

  amendmentsPending(): number {
    return FIXTURE_AMENDMENTS.filter((a) => a.requiresAcknowledgement && a.acknowledgedBy.length < 3).length;
  }

  cparsDue(): number {
    return FIXTURE_CPARS.filter((c) => c.status !== 'PUBLISHED').length;
  }

  openFindings(): number {
    return FIXTURE_FINDINGS.filter((f) => ['OPEN', 'EVIDENCE_REQUESTED', 'IN_REMEDIATION'].includes(f.status)).length;
  }

  pipeline() {
    return FIXTURE_SOLICITATIONS.slice(0, 4);
  }

  recent() {
    // Read once from the notification service cache.
    let cache: any[] = [];
    this.notif.items$.subscribe((items) => (cache = items)).unsubscribe();
    return cache.slice(0, 4);
  }
}
