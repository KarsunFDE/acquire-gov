import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ROLE_PROFILES } from '../../models/roles';

interface AdminUser {
  id: string;
  email: string;
  roles: string[];
  agencyId: string;
  mfaEnrolled: boolean;
  lastLogin: string;
}

/**
 * User &amp; Role Admin (sys_admin only).
 *
 * Provision / deprovision users; assign tenant + role; force MFA
 * reset. FedRAMP AC-2. Touches Item 1 (sys_admin actions still
 * permit unsigned JWTs on /api/public/**) + Item 10 (cross-tenant).
 */
@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>User &amp; Role administration</h2>
        <div class="subtitle">FedRAMP AC-2 · cross-tenant · MFA enforcement</div>
      </div>
    </div>

    <div class="card">
      <h3>Provisioned users</h3>
      <table>
        <thead>
          <tr><th>Email</th><th>Agency</th><th>Roles</th><th>MFA</th><th>Last login</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let u of users">
            <td>{{ u.email }}</td>
            <td>{{ u.agencyId }}</td>
            <td>
              <span class="badge review" *ngFor="let r of u.roles">{{ r }}</span>
            </td>
            <td>
              <span class="badge" [class.published]="u.mfaEnrolled" [class.urgent]="!u.mfaEnrolled">
                {{ u.mfaEnrolled ? 'Enrolled' : 'Not enrolled' }}
              </span>
            </td>
            <td>{{ u.lastLogin | date:'short' }}</td>
            <td>
              <button class="secondary" (click)="forceMfaReset(u)">Force MFA reset</button>
              <button class="secondary" (click)="deprovision(u)">Deprovision</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>Provision new user</h3>
      <label><span class="label-text">Email</span>
        <input [(ngModel)]="newUser.email"/>
      </label>
      <label><span class="label-text">Agency</span>
        <input [(ngModel)]="newUser.agencyId"/>
      </label>
      <label><span class="label-text">Role</span>
        <select [(ngModel)]="newUser.role">
          <option *ngFor="let r of roles" [value]="r.role">{{ r.displayName }}</option>
        </select>
      </label>
      <button (click)="provision()" [disabled]="!newUser.email">Provision</button>
    </div>
  `,
})
export class AdminUsersComponent {
  roles = ROLE_PROFILES.filter((r) => r.role !== 'public');

  users: AdminUser[] = [
    { id: 'u-1', email: 'd.reeves@gsa.gov', roles: ['contracting_officer'], agencyId: 'GSA-FAS', mfaEnrolled: true, lastLogin: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString() },
    { id: 'u-2', email: 'm.ortiz@gsa.gov', roles: ['contract_specialist'], agencyId: 'GSA-FAS', mfaEnrolled: true, lastLogin: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString() },
    { id: 'u-3', email: 'p.shah@gsa.gov', roles: ['program_manager'], agencyId: 'GSA-FAS', mfaEnrolled: true, lastLogin: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString() },
    { id: 'u-4', email: 'allen@gsa.gov', roles: ['evaluator'], agencyId: 'GSA-FAS', mfaEnrolled: true, lastLogin: new Date(Date.now() - 1000 * 60 * 60 * 24 * 4).toISOString() },
    { id: 'u-5', email: 'park@oig.gov', roles: ['oig_reviewer'], agencyId: 'GSA-OIG', mfaEnrolled: true, lastLogin: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString() },
    { id: 'u-6', email: 'temp.contractor@vendor.com', roles: ['vendor'], agencyId: 'EXTERNAL', mfaEnrolled: false, lastLogin: new Date(Date.now() - 1000 * 60 * 60 * 24 * 90).toISOString() },
  ];

  newUser = { email: '', agencyId: 'GSA-FAS', role: 'contract_specialist' };

  provision(): void {
    this.users = [...this.users, {
      id: `u-${Date.now()}`,
      email: this.newUser.email,
      agencyId: this.newUser.agencyId,
      roles: [this.newUser.role],
      mfaEnrolled: false,
      lastLogin: 'never',
    }];
    this.newUser = { email: '', agencyId: 'GSA-FAS', role: 'contract_specialist' };
  }

  forceMfaReset(u: AdminUser): void {
    u.mfaEnrolled = false;
  }

  deprovision(u: AdminUser): void {
    this.users = this.users.filter((x) => x.id !== u.id);
  }
}
