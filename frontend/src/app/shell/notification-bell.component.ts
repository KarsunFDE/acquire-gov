import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { NotificationService } from '../services/notification.service';
import { Notification } from '../models/notification';

@Component({
  selector: 'app-notification-bell',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <button class="bell-button" (click)="toggle()" [attr.aria-expanded]="open">
      ▣
      <span class="bell-badge" *ngIf="unread() > 0">{{ unread() }}</span>
    </button>

    <aside class="notification-drawer" *ngIf="open" role="dialog">
      <header>
        <strong>Notifications</strong>
        <button class="secondary" (click)="markAll()" style="background:transparent;color:white;border-color:white">Mark all read</button>
      </header>
      <div style="overflow-y:auto;flex:1">
        <ng-container *ngIf="items().length > 0; else none">
          <div class="item" *ngFor="let n of items()"
               [class.unread]="!n.readAt"
               (click)="onClick(n)">
            <h4>{{ n.title }}</h4>
            <p>{{ n.body }}</p>
            <small style="color:var(--color-fg-muted)">{{ n.createdAt | date:'short' }} · {{ n.kind }}</small>
          </div>
        </ng-container>
        <ng-template #none>
          <div class="empty-state" style="margin:1rem">No notifications.</div>
        </ng-template>
      </div>
    </aside>
  `,
})
export class NotificationBellComponent {
  open = false;
  private cache: Notification[] = [];

  constructor(private svc: NotificationService) {
    svc.items$.subscribe((list) => (this.cache = list));
  }

  items(): Notification[] {
    return this.cache;
  }

  unread(): number {
    return this.cache.filter((n) => !n.readAt).length;
  }

  toggle(): void {
    this.open = !this.open;
  }

  onClick(n: Notification): void {
    this.svc.markRead(n.id);
    // Drawer stays open; clicking a row is implicit ack. Router link
    // would close the drawer — left as instructor-led UX iteration.
  }

  markAll(): void {
    this.svc.markAllRead();
  }
}
