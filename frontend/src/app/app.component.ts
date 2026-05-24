import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { SidebarNavComponent } from './shell/sidebar-nav.component';
import { RoleSwitcherComponent } from './shell/role-switcher.component';
import { NotificationBellComponent } from './shell/notification-bell.component';
import { RoleService } from './services/role.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    SidebarNavComponent,
    RoleSwitcherComponent,
    NotificationBellComponent,
  ],
  template: `
    <div class="app-shell">
      <header class="topbar">
        <div>
          <h1>acquire-gov
            <span class="agency-badge" *ngIf="role.current.agencyId">{{ role.current.agencyId }}</span>
          </h1>
        </div>
        <div class="topbar-actions">
          <app-role-switcher></app-role-switcher>
          <app-notification-bell></app-notification-bell>
        </div>
      </header>
      <app-sidebar-nav></app-sidebar-nav>
      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
})
export class AppComponent {
  constructor(public role: RoleService) {}
}
