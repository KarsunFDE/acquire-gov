import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { RoleService } from '../services/role.service';
import { Role, RoleProfile } from '../models/roles';

interface NavLink {
  label: string;
  route: string;
  roles: Role[];           // empty = visible to all authenticated
}
interface NavGroup {
  title: string;
  links: NavLink[];
}

const ALL_AUTHENTICATED: Role[] = [
  'contracting_officer', 'contract_specialist', 'program_manager',
  'ssa', 'evaluator', 'vendor', 'oig_reviewer', 'sys_admin',
];

const NAV: NavGroup[] = [
  {
    title: 'Workspace',
    links: [
      { label: 'Officer Dashboard', route: '/dashboard', roles: ['contracting_officer', 'contract_specialist', 'program_manager', 'ssa'] },
      { label: 'Evaluator Workspace', route: '/evaluation/workspace', roles: ['evaluator', 'contracting_officer'] },
      { label: 'Vendor Portal', route: '/vendor/proposals', roles: ['vendor'] },
    ],
  },
  {
    title: 'Solicitations',
    links: [
      { label: 'Solicitations Index', route: '/solicitations', roles: ['contracting_officer', 'contract_specialist', 'program_manager'] },
      { label: 'New Solicitation', route: '/solicitations/new', roles: ['contracting_officer', 'contract_specialist'] },
      { label: 'Public Opportunity Search', route: '/public/opportunities', roles: [] },
    ],
  },
  {
    title: 'Source Selection',
    links: [
      { label: 'Consensus + SSDD', route: '/evaluation/eval-0142/consensus', roles: ['ssa', 'contracting_officer'] },
    ],
  },
  {
    title: 'Post-Award',
    links: [
      { label: 'Award Record', route: '/awards/aw-2026-001', roles: ['contracting_officer', 'program_manager', 'vendor'] },
      { label: 'Contract Admin', route: '/contracts/ctr-0001/admin', roles: ['contracting_officer', 'program_manager'] },
      { label: 'CPAR Reviews', route: '/contracts/ctr-0001/cpars', roles: ['contracting_officer', 'program_manager', 'vendor'] },
    ],
  },
  {
    title: 'Reports',
    links: [
      { label: 'All Reports', route: '/reports', roles: ['contracting_officer', 'program_manager', 'ssa', 'sys_admin', 'oig_reviewer'] },
    ],
  },
  {
    title: 'Vendors',
    links: [
      { label: 'Vendor Directory', route: '/vendors', roles: ['contracting_officer', 'contract_specialist', 'evaluator', 'program_manager'] },
    ],
  },
  {
    title: 'Admin',
    links: [
      { label: 'User & Role Admin', route: '/admin/users', roles: ['sys_admin'] },
      { label: 'System Config', route: '/admin/config', roles: ['sys_admin'] },
      { label: 'Audit Log Search', route: '/admin/audit', roles: ['sys_admin', 'oig_reviewer'] },
      { label: 'OIG Findings Tracker', route: '/admin/findings', roles: ['sys_admin', 'oig_reviewer'] },
    ],
  },
];

@Component({
  selector: 'app-sidebar-nav',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <nav class="sidebar">
      <ng-container *ngFor="let group of visibleGroups()">
        <div class="sidebar-section-title">{{ group.title }}</div>
        <a *ngFor="let link of group.links"
           [routerLink]="link.route"
           routerLinkActive="active">{{ link.label }}</a>
      </ng-container>
    </nav>
  `,
})
export class SidebarNavComponent {
  constructor(public role: RoleService) {}

  visibleGroups(): NavGroup[] {
    const current = this.role.currentRole;
    return NAV
      .map((g) => ({
        ...g,
        links: g.links.filter((l) =>
          l.roles.length === 0 || l.roles.includes(current) || current === 'sys_admin',
        ),
      }))
      .filter((g) => g.links.length > 0);
  }
}
