import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { Role, RoleProfile, ROLE_PROFILES } from '../models/roles';

const STORAGE_KEY = 'acquire-gov:active-role';

/**
 * Mock role-switcher.
 *
 * Production resolves role from validated JWT (`role` claim) in the
 * API gateway. acquire-gov main currently has Debt Item 1 (JWT
 * signature-skip on `/api/public/*`) — the cohort discovers and fixes
 * this in W4 Wed (OWASP LLM07/LLM08).
 *
 * For instructor-driven demos, role switching is local-only via this
 * service. Backend trust is `X-Mock-Role` header in dev (mirrored on
 * the legacy `solicitation-service` for the W4 walkthrough); never use
 * in production.
 */
@Injectable({ providedIn: 'root' })
export class RoleService {
  private readonly subject: BehaviorSubject<RoleProfile>;
  readonly profile$: Observable<RoleProfile>;

  constructor() {
    const stored = typeof localStorage !== 'undefined'
      ? localStorage.getItem(STORAGE_KEY)
      : null;
    const initial = ROLE_PROFILES.find((p) => p.role === stored)
      ?? ROLE_PROFILES.find((p) => p.role === 'contracting_officer')!;
    this.subject = new BehaviorSubject<RoleProfile>(initial);
    this.profile$ = this.subject.asObservable();
  }

  get current(): RoleProfile {
    return this.subject.value;
  }

  get currentRole(): Role {
    return this.subject.value.role;
  }

  switch(role: Role): void {
    const next = ROLE_PROFILES.find((p) => p.role === role);
    if (!next) {
      return;
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, role);
    }
    this.subject.next(next);
  }

  hasAny(...roles: Role[]): boolean {
    return roles.includes(this.subject.value.role);
  }
}
