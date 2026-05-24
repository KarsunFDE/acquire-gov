import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { RoleService } from './role.service';
import { Role } from '../models/roles';

/**
 * Route guard factory — restricts a route to a role-allow-list.
 *
 * Usage in `app.routes.ts`:
 *   { path: 'admin/users', loadComponent: () => …, canMatch: [roleGuard('sys_admin')] }
 *
 * Unauthorized requests redirect to `/dashboard` (or `/public/opportunities`
 * if the active role is `public`).
 */
export const roleGuard =
  (...allowed: Role[]): CanMatchFn =>
  () => {
    const role = inject(RoleService);
    const router = inject(Router);
    if (role.hasAny(...allowed)) {
      return true;
    }
    const fallback = role.currentRole === 'public' ? '/public/opportunities' : '/dashboard';
    return router.createUrlTree([fallback]);
  };
