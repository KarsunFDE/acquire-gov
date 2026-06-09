import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { environment } from '../../environments/environment';
import { RoleService } from './role.service';

/**
 * Locked /ingest/document request + response shapes — see
 * docs/specs/m2-ui-far-sections.md §2 (LOCKED INTERFACES) and
 * docs/specs/m2-retrieval-pipeline.md.
 */
export interface IngestMetadata {
  source_doc_name: string;
  far_part?: string;
  far_section?: string;
  snapshot_date: string;
  doc_class: 'synthetic_solicitation' | 'far_reference' | 'agency_template';
}

export type IngestFormat = 'md' | 'txt' | 'pdf' | 'json-prechunked';

export interface IngestResponse {
  document_id: string;
  chunks_inserted: number;
  flagged_chunks: string[];
  duration_ms: number;
}

export interface IngestErrorBody {
  error: string;
  flagged_chunk_ids?: string[];
  [k: string]: unknown;
}

/**
 * Ingest service — wraps POST /ingest/document on the ai-orchestrator.
 *
 * M2 C16. The corpus track (C12) owns the live endpoint. While the
 * pipeline-track endpoint is still being wired, `useMockIngest = true`
 * (default) returns a canned success shape so the admin UI is exercisable
 * end-to-end against the in-browser stub.
 *
 * Tenant: derived from the active RoleService profile's agencyId; the
 * orchestrator enforces tenant isolation server-side (ADR-0008 D2 / D3).
 */
@Injectable({ providedIn: 'root' })
export class IngestService {
  private readonly endpoint = `${environment.apiGatewayUrl}/api/ai/ingest/document`;

  /** Defaults to `true` until C12 endpoint is live. Flip via console for E2E smoke. */
  useMockIngest = true;

  constructor(private http: HttpClient, private role: RoleService) {}

  /**
   * Upload a corpus document. Form-data per the locked interface.
   * Returns the success body or rethrows on 413 / 422 / 429 / 503.
   */
  uploadDocument(
    file: File,
    format: IngestFormat,
    metadata: IngestMetadata,
  ): Observable<IngestResponse> {
    if (this.useMockIngest) {
      return of(this.mockResponse(file));
    }
    const form = new FormData();
    form.append('file', file);
    form.append('format', format);
    form.append('metadata', JSON.stringify(metadata));
    const tenantId = this.role.current.agencyId || 'agency-test';
    const headers = new HttpHeaders({
      'X-Tenant-ID': tenantId,
    });
    return this.http.post<IngestResponse>(this.endpoint, form, { headers });
  }

  private mockResponse(file: File): IngestResponse {
    return {
      document_id: 'doc-' + this.uuidV4(),
      chunks_inserted: Math.max(1, Math.round(file.size / 1024)),
      flagged_chunks: [],
      duration_ms: 1234,
    };
  }

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
