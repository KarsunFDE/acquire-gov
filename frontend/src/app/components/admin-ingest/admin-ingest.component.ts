import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  IngestFormat,
  IngestMetadata,
  IngestResponse,
  IngestService,
} from '../../services/ingest.service';

/**
 * Admin Ingest UI — upload a corpus document to the orchestrator.
 *
 * Route: /admin/ingest (role-guarded sys_admin only — see app.routes.ts).
 * Spec: docs/specs/m2-grounded-retrieval/ui-far-sections.md §10 + §10.1 error states.
 *
 * Wraps IngestService.uploadDocument (POST /ingest/document, owned by
 * the corpus track C12). Tenant is derived from the active role profile;
 * orchestrator enforces isolation server-side (ADR-0008 D2/D3).
 *
 * Recent-uploads list (§10.2) is omitted — depends on a GET /ingest/recent
 * endpoint that is `Open — owner TBD` in spec §17.
 */
@Component({
  selector: 'app-admin-ingest',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>Admin · Corpus ingest</h2>
        <div class="subtitle">
          POST /ingest/document — orchestrator-backed corpus loader (ADR-0008 D2)
        </div>
      </div>
    </div>

    <div class="card">
      <h3>Upload corpus document</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Synthetic + FedRAMP-safe content only. Tenant resolves from the active
        role profile; cross-tenant ingest is rejected server-side.
      </p>

      <label>
        <span class="label-text">Source document name</span>
        <input type="text" name="sourceDocName" [(ngModel)]="metadata.source_doc_name"
               placeholder="e.g., SOL-GSA-001-cloud-services.md"/>
      </label>

      <div class="two-col">
        <label>
          <span class="label-text">Format</span>
          <select name="format" [(ngModel)]="format">
            <option value="md">Markdown (.md)</option>
            <option value="txt">Plain text (.txt)</option>
            <option value="pdf">PDF (.pdf)</option>
            <option value="json-prechunked">JSON pre-chunked</option>
          </select>
        </label>
        <label>
          <span class="label-text">Doc class</span>
          <select name="docClass" [(ngModel)]="metadata.doc_class">
            <option value="synthetic_solicitation">Synthetic solicitation</option>
            <option value="far_reference">FAR reference</option>
            <option value="agency_template">Agency template</option>
          </select>
        </label>
        <label>
          <span class="label-text">FAR part (optional)</span>
          <select name="farPart" [(ngModel)]="metadata.far_part">
            <option [ngValue]="undefined">—</option>
            <option value="I">I</option>
            <option value="II">II</option>
            <option value="III">III</option>
            <option value="IV">IV</option>
          </select>
        </label>
        <label>
          <span class="label-text">FAR section (optional)</span>
          <input type="text" name="farSection" [(ngModel)]="metadata.far_section"
                 placeholder="e.g., L, M, 52.215-1"/>
        </label>
        <label>
          <span class="label-text">Snapshot date</span>
          <input type="date" name="snapshotDate" [(ngModel)]="metadata.snapshot_date"/>
        </label>
      </div>

      <label>
        <span class="label-text">File</span>
        <input type="file" #fileInput (change)="onFileSelected($event)"/>
      </label>

      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;align-items:center">
        <button (click)="upload()" [disabled]="!canUpload() || uploading">
          {{ uploading ? 'Uploading…' : 'Upload' }}
        </button>
        <button class="secondary" (click)="resetForm()" type="button">Reset</button>
      </div>

      <div *ngIf="errorMessage" class="error-text">{{ errorMessage }}</div>
      <div *ngIf="flaggedChunkIds.length > 0" class="flagged-list">
        <strong>Flagged chunks (held for review):</strong>
        <ul>
          <li *ngFor="let id of flaggedChunkIds"><code>{{ id }}</code></li>
        </ul>
      </div>
    </div>

    <div class="card" *ngIf="lastResponse">
      <h3>Upload result</h3>
      <table>
        <tbody>
          <tr><th>document_id</th><td><code>{{ lastResponse.document_id }}</code></td></tr>
          <tr><th>chunks_inserted</th><td>{{ lastResponse.chunks_inserted }}</td></tr>
          <tr><th>flagged_chunks</th><td>{{ lastResponse.flagged_chunks.length }}</td></tr>
          <tr><th>duration_ms</th><td>{{ lastResponse.duration_ms }} ms</td></tr>
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .error-text {
      color: var(--color-danger);
      background: #fdecea;
      border: 1px solid #f4a09b;
      padding: 0.5rem 0.75rem;
      border-radius: 4px;
      margin-top: 0.5rem;
      font-size: 0.85rem;
    }
    .flagged-list {
      margin-top: 0.5rem;
      background: #fff4e5;
      border: 1px solid #f3c089;
      padding: 0.5rem 0.75rem;
      border-radius: 4px;
      font-size: 0.85rem;
    }
    .flagged-list ul { margin: 0.25rem 0 0 1.25rem; }
  `],
})
export class AdminIngestComponent {
  file: File | null = null;
  format: IngestFormat = 'md';
  metadata: IngestMetadata = {
    source_doc_name: '',
    snapshot_date: new Date().toISOString().slice(0, 10),
    doc_class: 'synthetic_solicitation',
  };

  uploading = false;
  errorMessage: string | null = null;
  flaggedChunkIds: string[] = [];
  lastResponse: IngestResponse | null = null;

  constructor(private ingest: IngestService) {}

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.file = input.files && input.files.length > 0 ? input.files[0] : null;
    if (this.file && !this.metadata.source_doc_name) {
      this.metadata.source_doc_name = this.file.name;
    }
  }

  canUpload(): boolean {
    return !!(this.file && this.metadata.source_doc_name.trim() && this.metadata.snapshot_date);
  }

  upload(): void {
    if (!this.file || !this.canUpload()) return;
    this.uploading = true;
    this.errorMessage = null;
    this.flaggedChunkIds = [];
    this.lastResponse = null;
    this.ingest.uploadDocument(this.file, this.format, { ...this.metadata }).subscribe({
      next: (resp) => {
        this.uploading = false;
        this.lastResponse = resp;
        if (resp.flagged_chunks.length > 0) {
          this.flaggedChunkIds = resp.flagged_chunks;
        }
      },
      error: (err) => {
        this.uploading = false;
        this.errorMessage = this.errorFor(err?.status);
        const body = err?.error;
        if (body && Array.isArray(body.flagged_chunk_ids)) {
          this.flaggedChunkIds = body.flagged_chunk_ids;
        }
      },
    });
  }

  /** Spec §10.1 inline error states — no toasts; localised to form. */
  private errorFor(status?: number): string {
    switch (status) {
      case 413: return 'File too large (10MB limit).';
      case 422: return 'Content flagged for review — see flagged_chunks list.';
      case 429: return 'Rate limited; try again shortly.';
      case 503: return 'Ingest service temporarily unavailable.';
      default:  return 'Upload failed. Check the file and try again.';
    }
  }

  resetForm(): void {
    this.file = null;
    this.metadata = {
      source_doc_name: '',
      snapshot_date: new Date().toISOString().slice(0, 10),
      doc_class: 'synthetic_solicitation',
    };
    this.errorMessage = null;
    this.flaggedChunkIds = [];
    this.lastResponse = null;
  }
}
