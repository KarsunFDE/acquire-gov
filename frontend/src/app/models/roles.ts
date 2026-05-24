/**
 * Federal acquisitions role model.
 *
 * Mirrors the JWT `role` claim defined in feature-inventory-target.md
 * personas table. FedRAMP RBAC AC-2/AC-5 (least-privilege +
 * separation-of-duties).
 *
 * NOTE: this is a mock role-switcher for cohort instructor demos.
 * Production RBAC resolves role from validated JWT in the API gateway
 * (which today has Debt Item 1 — JWT signature-skip on `/api/public/*`).
 */
export type Role =
  | 'contracting_officer'
  | 'contract_specialist'
  | 'program_manager'
  | 'ssa'
  | 'evaluator'
  | 'vendor'
  | 'oig_reviewer'
  | 'sys_admin'
  | 'public';

export interface RoleProfile {
  role: Role;
  displayName: string;
  agencyId: string | null;   // null for sys_admin (cross-tenant) and public
  vendorDuns?: string;       // only present for `vendor`
  /** FAR/FedRAMP authority notes shown in role-switcher tooltip. */
  authorityNote: string;
}

export const ROLE_PROFILES: RoleProfile[] = [
  {
    role: 'contracting_officer',
    displayName: 'Dana Reeves (CO, GSA-FAS)',
    agencyId: 'GSA-FAS',
    authorityNote: 'Sign award, issue amendment, terminate contract (FAR 1.602-1).',
  },
  {
    role: 'contract_specialist',
    displayName: 'Miguel Ortiz (CS, GSA-FAS)',
    agencyId: 'GSA-FAS',
    authorityNote: 'Draft solicitations; cannot sign award (FAR 1.603).',
  },
  {
    role: 'program_manager',
    displayName: 'Priya Shah (PM, GSA-FAS)',
    agencyId: 'GSA-FAS',
    authorityNote: 'Requirements + CPAR draft (FAR 42.1503).',
  },
  {
    role: 'ssa',
    displayName: 'Col. Whitfield (SSA, GSA-FAS)',
    agencyId: 'GSA-FAS',
    authorityNote: 'Source Selection Authority — final award (FAR 15.303(b)(6)).',
  },
  {
    role: 'evaluator',
    displayName: 'Dr. Allen (TEP evaluator, GSA-FAS)',
    agencyId: 'GSA-FAS',
    authorityNote: 'Score assigned proposals against Section M (FAR 15.305).',
  },
  {
    role: 'vendor',
    displayName: 'Acme Federal LLC (DUNS 12-345-6789)',
    agencyId: null,
    vendorDuns: '123456789',
    authorityNote: 'Submit proposals; rebuttal on CPAR (FAR 42.1503(d)).',
  },
  {
    role: 'oig_reviewer',
    displayName: 'Inspector Park (OIG)',
    agencyId: 'GSA-OIG',
    authorityNote: 'Read-only across tenants; open findings.',
  },
  {
    role: 'sys_admin',
    displayName: 'Root (sys_admin)',
    agencyId: null,
    authorityNote: 'Cross-tenant admin; provisioning + key rotation.',
  },
  {
    role: 'public',
    displayName: 'Unauthenticated visitor',
    agencyId: null,
    authorityNote: 'Read-only on /public/* (Item 1 surface).',
  },
];
