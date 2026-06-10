import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  Solicitation,
  SolicitationCreate,
  DraftSectionRequest,
  DraftSectionResponse,
} from '../models/solicitation';
import { RoleService } from './role.service';

/**
 * Solicitation service — the "right" way to talk to the backend.
 *
 * Goes through the API gateway (environment.apiGatewayUrl). The cohort
 * compares this with `solicitation-list.component.ts`, which hardcodes
 * `http://localhost:8081` and bypasses the gateway (Item 8).
 *
 * M2 C15: adds `draftSection()` → POST /draft-solicitation/section on the
 * ai-orchestrator. While the pipeline track is still wiring the live
 * endpoint, `useMockAI` (default `true`) returns a canned response shape
 * that matches the locked interface from
 * docs/specs/m2-grounded-retrieval/ui-far-sections.md §2 / m2-retrieval-pipeline.md.
 */
@Injectable({ providedIn: 'root' })
export class SolicitationService {
  private readonly baseUrl = `${environment.apiGatewayUrl}/api/solicitations`;
  private readonly draftUrl = `${environment.apiGatewayUrl}/api/ai/draft-solicitation/section`;

  /**
   * When `true`, draftSection() returns a canned mock that conforms to the
   * locked /draft-solicitation/section response shape. Default `true` until
   * the orchestrator endpoint (C9) ships and pipeline track flips this off.
   * Toggle in tests or browser console for end-to-end smoke against real backend.
   */
  useMockAI = true;

  constructor(private http: HttpClient, private role: RoleService) {}

  list(): Observable<Solicitation[]> {
    return this.http.get<Solicitation[]>(this.baseUrl);
  }

  get(id: string): Observable<Solicitation> {
    return this.http.get<Solicitation>(`${this.baseUrl}/${id}`);
  }

  create(req: SolicitationCreate): Observable<Solicitation> {
    return this.http.post<Solicitation>(this.baseUrl, req);
  }

  /**
   * Calls the grounded section-drafting endpoint. UI generates the
   * X-Request-ID (uuid v4) client-side; orchestrator echoes it back on
   * `request_id` for audit_log correlation (ADR-0008 D3).
   */
  draftSection(
    solicitationId: string,
    sectionId: string,
    opts?: { query?: string; constraints?: string },
  ): Observable<DraftSectionResponse> {
    const requestId = this.uuidV4();
    const tenantId = this.role.current.agencyId || 'agency-test';
    const body: DraftSectionRequest = {
      section_id: sectionId,
      solicitation_id: solicitationId,
      query: opts?.query,
      constraints: opts?.constraints,
    };
    if (this.useMockAI) {
      return of(this.mockDraftResponse(sectionId, requestId));
    }
    const headers = new HttpHeaders({
      'X-Tenant-ID': tenantId,
      'X-Request-ID': requestId,
    });
    return this.http.post<DraftSectionResponse>(this.draftUrl, body, { headers });
  }

  /**
   * Mock response shaped to the locked interface from
   * docs/specs/m2-grounded-retrieval/ui-far-sections.md §4.2. Canned text + 2 citations + pass gate.
   * The pipeline-restart agent flips `useMockAI=false` and removes this when
   * the live /draft-solicitation/section endpoint lands.
   */
  private mockDraftResponse(sectionId: string, requestId: string): DraftSectionResponse {
    const sec = sectionId.toUpperCase();
    const cannedTextBySection: Record<string, string> = {
      C: 'C.1 SCOPE. The Contractor shall provide enterprise services in accordance with FedRAMP Moderate baseline controls and NIST SP 800-53 Rev. 5.\n\nC.2 TASKS.\nTask 1: Service Operations\nTask 2: Continuous Monitoring\nTask 3: Incident Response',
      H: 'H.1 SPECIAL CONTRACT REQUIREMENTS. (a) Security clearance: Public Trust minimum. (b) Key personnel: positions designated under FAR 52.215-22. (c) Place of performance: contractor or government facility per task order.',
      L: 'L.1 GENERAL INSTRUCTIONS. Proposals shall be submitted electronically via SAM.gov by the date and time specified in Section A.\n\nL.5.2 VOLUME I — TECHNICAL. 60-page limit including table of contents; 12-pt Times New Roman.',
      M: 'M.1 BASIS FOR AWARD. Best-value tradeoff under FAR 15.101-1.\n\nM.3 EVALUATION FACTORS.\nM.3.1 Technical Approach (40%)\nM.3.2 Management Approach (25%)\nM.3.3 Past Performance (20%)\nM.3.4 Price (15%)',
    };
    const sectionText =
      cannedTextBySection[sec] ??
      `[MOCK] Draft for Section ${sec} — connect orchestrator (C9) to replace this canned text.`;
    return {
      outcome: 'draft_returned',
      section_text: sectionText,
      section_id: sec,
      citations: [
        {
          chunk_id: 'mock-1',
          text: 'Volume I shall not exceed 60 pages …',
          far_part: 'IV',
          far_section: 'L',
          far_clause: '52.215-1',
          snapshot_date: '2026-06-01',
          relevance_score: 0.74,
        },
        {
          chunk_id: 'mock-2',
          text: 'Best-value tradeoff process under FAR 15.101-1 …',
          far_part: 'I',
          far_section: '15.101-1',
          far_clause: '15.101-1',
          snapshot_date: '2026-06-01',
          relevance_score: 0.68,
        },
      ],
      gate_decision: 'pass',
      requires_human_review: false,
      rerank_top_score: 0.74,
      request_id: requestId,
    };
  }

  /** RFC 4122 v4 — minimal in-browser generator; orchestrator echoes it back. */
  private uuidV4(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}
