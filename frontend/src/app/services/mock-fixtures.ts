/**
 * Instructor-demo fixtures.
 *
 * The acquire-gov backend endpoints listed in feature-inventory-target.md
 * are scaffold-level; many return empty or 404 against the current
 * legacy stack. To keep instructor-driven demos showing realistic
 * federal-acquisitions data even without a fully populated DB, every
 * page falls back to these fixtures on HTTP error.
 *
 * Realism citations (all retrieved 2026-05-22 via /web-research):
 *   - SAM.gov opportunity record shape (NAICS, set-aside, posted_at)
 *   - DLA DIBBS solicitation IDs (`SPE…` prefix convention)
 *   - GSA-FAS contract numbers (`GS-35F-…`)
 *   - CPARS rating bands per FAR 42.1503 (Exceptional → Unsatisfactory)
 */

import { Solicitation, SolicitationState } from '../models/solicitation';
import { Amendment } from '../models/amendment';
import { Qna } from '../models/qna';
import { Proposal } from '../models/proposal';
import { Evaluation, EvaluationScore } from '../models/evaluation';
import { Award, ContractModification, Deliverable, Cpar } from '../models/award';
import { Vendor } from '../models/vendor';
import { AuditEvent } from '../models/audit';
import { Finding } from '../models/finding';

export const FIXTURE_SOLICITATIONS: Solicitation[] = [
  {
    id: 'sol-0142',
    agencyId: 'GSA-FAS',
    title: 'Cloud Managed Services BPA — Civilian Agencies',
    description: 'Enterprise cloud managed services across AWS GovCloud + Azure Government for 11 civilian agencies under the GSA-FAS umbrella.',
    status: 'PUBLISHED' as SolicitationState,
    naics: '541512',
    setAside: 'FULL_AND_OPEN',
    contractType: 'BPA',
    ceilingValue: 110_000_000,
    noticeType: 'RFP',
    proposalsDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 21).toISOString(),
  },
  {
    id: 'sol-0203',
    agencyId: 'GSA-FAS',
    title: 'Acquisition Modernization Software Engineering',
    description: 'AI-assisted modernization engineering team to support CAMEO/COMET portfolio.',
    status: 'PUBLISHED' as SolicitationState,
    naics: '541511',
    setAside: '8A',
    contractType: 'T_AND_M',
    ceilingValue: 25_000_000,
    noticeType: 'RFP',
    proposalsDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 7).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 35).toISOString(),
  },
  {
    id: 'sol-0301',
    agencyId: 'GSA-FAS',
    title: 'Sources Sought — Zero-Trust Architecture Assessment',
    description: 'RFI seeking industry input on zero-trust assessments for FedRAMP Moderate enclaves.',
    status: 'PUBLISHED' as SolicitationState,
    naics: '541519',
    setAside: 'SDVOSB',
    contractType: 'FFP',
    ceilingValue: 1_500_000,
    noticeType: 'SOURCES_SOUGHT',
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 9).toISOString(),
  },
  {
    id: 'sol-0418',
    agencyId: 'GSA-FAS',
    title: 'Draft — Multi-Cloud Observability Stack Procurement',
    description: 'Pre-publication draft. Internal review pending.',
    status: 'INTERNAL_REVIEW' as SolicitationState,
    naics: '541519',
    setAside: 'FULL_AND_OPEN',
    contractType: 'IDIQ',
    ceilingValue: 50_000_000,
    noticeType: 'RFP',
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
  },
];

export const FIXTURE_AMENDMENTS: Amendment[] = [
  {
    id: 'am-0001',
    solicitationId: 'sol-0142',
    number: 1,
    changeSummary: 'Add CMMC Level 2 attestation to Section H minimum requirements.',
    effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
    requiresAcknowledgement: true,
    acknowledgedBy: ['vnd-acme', 'vnd-globex'],
    issuedBy: 'co-reeves',
    issuedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
  },
  {
    id: 'am-0002',
    solicitationId: 'sol-0142',
    number: 2,
    changeSummary: 'Extend proposal deadline by 7 days; clarify Section L page limit (60 pages including ToC).',
    effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    requiresAcknowledgement: true,
    acknowledgedBy: ['vnd-acme'],
    issuedBy: 'co-reeves',
    issuedAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
  },
];

export const FIXTURE_QNA: Qna[] = [
  {
    id: 'qa-001',
    solicitationId: 'sol-0142',
    question: 'Is the FedRAMP Moderate baseline a hard requirement at proposal submission or by award date?',
    answer: 'FedRAMP Moderate authorization (or In-Process status with completion path documented) is required at proposal submission per Section L.5.2.',
    vendorId: 'vnd-acme',
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    publishedAt: new Date(Date.now() - 1000 * 60 * 60 * 22).toISOString(),
    status: 'PUBLISHED',
  },
  {
    id: 'qa-002',
    solicitationId: 'sol-0142',
    question: 'Can past performance from a parent-company contract be cited?',
    answer: null,
    vendorId: 'vnd-globex',
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    publishedAt: null,
    status: 'DRAFT_ANSWER',
  },
  {
    id: 'qa-003',
    solicitationId: 'sol-0142',
    question: 'What is the period of performance start date assumed for Volume III pricing?',
    answer: null,
    vendorId: 'vnd-initech',
    postedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    publishedAt: null,
    status: 'NEW',
  },
];

export const FIXTURE_PROPOSALS: Proposal[] = [
  {
    id: 'prop-001',
    solicitationId: 'sol-0142',
    vendorId: 'vnd-acme',
    vendorName: 'Acme Federal LLC',
    volumes: [
      { volume: 'I_TECHNICAL', attachmentId: 'att-001', pageCount: 58, submittedAt: new Date().toISOString() },
      { volume: 'II_PAST_PERFORMANCE', attachmentId: 'att-002', pageCount: 22, submittedAt: new Date().toISOString() },
      { volume: 'III_PRICE', attachmentId: 'att-003', pageCount: 12, submittedAt: new Date().toISOString() },
    ],
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
    sealedUntil: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    amendmentAcks: [1, 2],
  },
  {
    id: 'prop-002',
    solicitationId: 'sol-0142',
    vendorId: 'vnd-globex',
    vendorName: 'Globex Federal Systems',
    volumes: [
      { volume: 'I_TECHNICAL', attachmentId: 'att-101', pageCount: 60, submittedAt: new Date().toISOString() },
      { volume: 'II_PAST_PERFORMANCE', attachmentId: 'att-102', pageCount: 18, submittedAt: new Date().toISOString() },
      { volume: 'III_PRICE', attachmentId: 'att-103', pageCount: 10, submittedAt: new Date().toISOString() },
    ],
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    sealedUntil: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    amendmentAcks: [1],
  },
  {
    id: 'prop-003',
    solicitationId: 'sol-0142',
    vendorId: 'vnd-initech',
    vendorName: 'Initech Cloud Services',
    volumes: [
      { volume: 'I_TECHNICAL', attachmentId: 'att-201', pageCount: 55, submittedAt: new Date().toISOString() },
      { volume: 'II_PAST_PERFORMANCE', attachmentId: 'att-202', pageCount: 20, submittedAt: new Date().toISOString() },
      { volume: 'III_PRICE', attachmentId: 'att-203', pageCount: 11, submittedAt: new Date().toISOString() },
    ],
    submittedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    sealedUntil: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    amendmentAcks: [],
  },
];

export const FIXTURE_EVALUATION: Evaluation = {
  id: 'eval-0142',
  solicitationId: 'sol-0142',
  panelMembers: ['ev-allen', 'ev-mendez', 'ev-park'],
  factors: [
    { id: 'f-tech', name: 'Technical Approach', weight: 40, sectionM: 'M.3.1' },
    { id: 'f-mgmt', name: 'Management Approach', weight: 25, sectionM: 'M.3.2' },
    { id: 'f-pp', name: 'Past Performance', weight: 20, sectionM: 'M.3.3' },
    { id: 'f-price', name: 'Price (LPTA secondary)', weight: 15, sectionM: 'M.3.4' },
  ],
  state: 'INDIVIDUAL_SCORING',
  ssddDocId: null,
};

export const FIXTURE_SCORES: EvaluationScore[] = [
  { evaluatorId: 'ev-allen', evaluatorName: 'Dr. Allen', proposalId: 'prop-001', factorId: 'f-tech', score: 9, narrative: 'Strong zero-trust pattern; FedRAMP boundary clearly drawn.', submittedAt: new Date().toISOString() },
  { evaluatorId: 'ev-allen', evaluatorName: 'Dr. Allen', proposalId: 'prop-002', factorId: 'f-tech', score: 7, narrative: 'Acceptable approach; some risk on multi-cloud handoff.', submittedAt: new Date().toISOString() },
  { evaluatorId: 'ev-mendez', evaluatorName: 'A. Mendez', proposalId: 'prop-001', factorId: 'f-mgmt', score: 8, narrative: 'Clear PM org chart; key-personnel commitments solid.', submittedAt: new Date().toISOString() },
  { evaluatorId: 'ev-mendez', evaluatorName: 'A. Mendez', proposalId: 'prop-002', factorId: 'f-mgmt', score: 8, narrative: 'Comparable management; less depth on subcontractor mgmt.', submittedAt: new Date().toISOString() },
];

export const FIXTURE_AWARD: Award = {
  id: 'aw-2026-001',
  evaluationId: 'eval-0142',
  solicitationId: 'sol-0142',
  winningVendorId: 'vnd-acme',
  winningVendorName: 'Acme Federal LLC',
  contractNumber: 'GS-35F-0001V',
  awardedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString(),
  ceilingValue: 110_000_000,
  debriefDeadline: new Date(Date.now() - 1000 * 60 * 60 * 24 * 25).toISOString(),
};

export const FIXTURE_MODIFICATIONS: ContractModification[] = [
  { id: 'mod-001', contractId: 'ctr-0001', modNumber: 'P00001', type: 'bilateral', changeDescription: 'Option year 1 exercise; ceiling delta +$18M.', effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 200).toISOString(), signedBy: 'co-reeves' },
  { id: 'mod-002', contractId: 'ctr-0001', modNumber: 'A00001', type: 'unilateral', changeDescription: 'Administrative — updated POC email after PM transition.', effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 120).toISOString(), signedBy: 'co-reeves' },
];

export const FIXTURE_DELIVERABLES: Deliverable[] = [
  { id: 'del-001', contractId: 'ctr-0001', cdrlNumber: 'A001', title: 'Monthly Status Report — May 2026', dueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 5).toISOString(), status: 'PENDING', acceptedBy: null },
  { id: 'del-002', contractId: 'ctr-0001', cdrlNumber: 'A002', title: 'Q2 Security Compliance Attestation', dueAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(), status: 'SUBMITTED', acceptedBy: null },
  { id: 'del-003', contractId: 'ctr-0001', cdrlNumber: 'A003', title: 'Annual Cost Baseline Refresh', dueAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14).toISOString(), status: 'ACCEPTED', acceptedBy: 'co-reeves' },
];

export const FIXTURE_CPARS: Cpar[] = [
  {
    id: 'cpar-001',
    contractId: 'ctr-0001',
    period: 'INTERIM',
    ratings: [
      { factor: 'QUALITY', rating: 'VERY_GOOD', narrative: 'Deliverables consistently meet acceptance criteria.' },
      { factor: 'SCHEDULE', rating: 'SATISFACTORY', narrative: 'Two CDRLs slipped by less than 5 days each.' },
      { factor: 'COST_CONTROL', rating: 'VERY_GOOD', narrative: 'Burn rate within 3% of baseline.' },
      { factor: 'MANAGEMENT', rating: 'EXCEPTIONAL', narrative: 'Proactive risk communication; subcontractor mgmt strong.' },
      { factor: 'SMALL_BUSINESS', rating: 'SATISFACTORY', narrative: 'Met 23% small-business subcontracting target.' },
      { factor: 'REGULATORY_COMPLIANCE', rating: 'VERY_GOOD', narrative: 'FedRAMP continuous monitoring up to date.' },
    ],
    overallNarrative: 'Strong interim performance; ready to exercise option year 2.',
    vendorRebuttal: null,
    rebuttalDeadline: new Date(Date.now() + 1000 * 60 * 60 * 24 * 45).toISOString(),
    status: 'AWAITING_VENDOR_REVIEW',
  },
];

export const FIXTURE_VENDORS: Vendor[] = [
  {
    id: 'vnd-acme',
    duns: '123456789',
    uei: 'AB1CDE2FGHI3',
    cage: '7XYZ4',
    name: 'Acme Federal LLC',
    naicsCodes: ['541512', '541519'],
    setAsides: ['SMALL_BUSINESS', '8A'],
    registeredAt: '2018-04-12T00:00:00Z',
    pastPerformanceAvg: { exceptional: 4, veryGood: 11, satisfactory: 6, marginal: 1, unsatisfactory: 0, totalReports: 22 },
  },
  {
    id: 'vnd-globex',
    duns: '987654321',
    uei: 'ZX9YWV8UTSR7',
    cage: '4ABC2',
    name: 'Globex Federal Systems',
    naicsCodes: ['541511', '541512'],
    setAsides: ['FULL_AND_OPEN' as never],
    registeredAt: '2014-09-01T00:00:00Z',
    pastPerformanceAvg: { exceptional: 2, veryGood: 8, satisfactory: 12, marginal: 3, unsatisfactory: 1, totalReports: 26 },
  },
  {
    id: 'vnd-initech',
    duns: '555111222',
    uei: 'IN0TECHFGHIJ',
    cage: '9PQR5',
    name: 'Initech Cloud Services',
    naicsCodes: ['541519'],
    setAsides: ['SDVOSB'],
    registeredAt: '2020-01-15T00:00:00Z',
    pastPerformanceAvg: { exceptional: 0, veryGood: 3, satisfactory: 5, marginal: 2, unsatisfactory: 0, totalReports: 10 },
  },
];

export const FIXTURE_AUDIT_EVENTS: AuditEvent[] = [
  { id: 'ae-001', actorId: 'co-reeves', actorName: 'Dana Reeves', agencyId: 'GSA-FAS', action: 'SOLICITATION.PUBLISH', objectType: 'Solicitation', objectId: 'sol-0142', correlationId: 'r-abc-001', before: { status: 'READY_TO_PUBLISH' }, after: { status: 'PUBLISHED' }, ts: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString() },
  { id: 'ae-002', actorId: 'co-reeves', actorName: 'Dana Reeves', agencyId: 'GSA-FAS', action: 'AMENDMENT.ISSUE', objectType: 'Amendment', objectId: 'am-0001', correlationId: 'r-abc-002', before: null, after: { number: 1 }, ts: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString() },
  { id: 'ae-003', actorId: 'cs-ortiz', actorName: 'Miguel Ortiz', agencyId: 'GSA-FAS', action: 'QNA.ANSWER', objectType: 'Qna', objectId: 'qa-001', correlationId: 'r-def-001', before: { status: 'AWAITING_CO_APPROVAL' }, after: { status: 'PUBLISHED' }, ts: new Date(Date.now() - 1000 * 60 * 60 * 22).toISOString() },
  { id: 'ae-004', actorId: 'ssa-whitfield', actorName: 'Col. Whitfield', agencyId: 'GSA-FAS', action: 'SSDD.SIGN', objectType: 'Evaluation', objectId: 'eval-0142', correlationId: 'r-ghi-001', before: { state: 'AWAITING_SSA_SIGNATURE' }, after: { state: 'AWARDED' }, ts: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString() },
];

export const FIXTURE_FINDINGS: Finding[] = [
  {
    id: 'F-2026-0007',
    scope: 'PLATFORM',
    scopeId: 'acquire-gov',
    title: 'CI lint workflow disabled — repo-self finding',
    findingType: 'CA-7 continuous monitoring',
    severity: 'MODERATE',
    status: 'OPEN',
    openedBy: 'oig-park',
    openedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    remediationDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
    evidenceRequests: [
      { id: 'er-1', requestedBy: 'oig-park', requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(), description: 'Provide screenshot of re-enabled lint step in successful PR build.', fulfilledAt: null },
    ],
    description: 'Repository CI (`infra/github-actions/ci.yml`) skips lint with TODO. (Item 12 — meta-mirror per feature inventory.)',
  },
  {
    id: 'F-2026-0008',
    scope: 'CONTRACT',
    scopeId: 'ctr-0001',
    title: 'QASP findings ledger missing 2 entries for May surveillance',
    findingType: 'AU-12 audit record generation',
    severity: 'HIGH',
    status: 'IN_REMEDIATION',
    openedBy: 'oig-park',
    openedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14).toISOString(),
    remediationDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 10).toISOString(),
    evidenceRequests: [],
    description: 'AuditEvent gap suggests Item 2 race during high-load surveillance window.',
  },
];
