import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

/**
 * System Configuration (sys_admin only).
 *
 * Per feature-inventory-target.md line 332 + brownfield-debt.md Item 7:
 * "available vector stores: pinecone, atlas" — the lie made visible.
 * `pinecone-client==5.0.0` is in requirements.txt but `import pinecone`
 * exists nowhere; this admin screen lists pinecone as an available
 * option, reinforcing the deception. Cohort discovers in W2 Mon.
 *
 * Also surfaces Item 11 (image-pin status):
 * ai-orchestrator hand-pinned, other 4 Dockerfiles on :latest.
 */
@Component({
  selector: 'app-admin-config',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>System configuration</h2>
        <div class="subtitle">Tenant settings · vector store · clause library refresh · image pin status</div>
      </div>
    </div>

    <div class="two-col">
      <div class="card">
        <h3>Vector store</h3>
        <label><span class="label-text">Active vector store</span>
          <select [(ngModel)]="vectorStore">
            <!-- Item 7: pinecone listed in requirements.txt but the
                 import statement exists nowhere in services/ai-orchestrator.
                 The cohort discovers in W2 Mon when Atlas Vector Search
                 work begins. -->
            <option value="atlas">MongoDB Atlas Vector Search (in use)</option>
            <option value="pinecone">Pinecone</option>
            <option value="pgvector">Postgres pgvector</option>
          </select>
        </label>
        <p style="font-size:0.8rem;color:var(--color-fg-muted)">
          Available vector stores: pinecone, atlas
        </p>
        <button (click)="refreshClauseLibrary()">Refresh clause library</button>
      </div>

      <div class="card">
        <h3>Container image pins</h3>
        <table>
          <thead><tr><th>Service</th><th>Tag</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td>api-gateway</td><td><code>:latest</code></td><td><span class="badge urgent">UNPINNED</span></td></tr>
            <tr><td>solicitation-service</td><td><code>:latest</code></td><td><span class="badge urgent">UNPINNED</span></td></tr>
            <tr><td>evaluation-service</td><td><code>:latest</code></td><td><span class="badge urgent">UNPINNED</span></td></tr>
            <tr><td>ai-orchestrator</td><td><code>python:3.11-slim</code></td><td><span class="badge satisfactory">HAND-PINNED 2026-Q1</span></td></tr>
            <tr><td>frontend (build)</td><td><code>node:latest</code></td><td><span class="badge urgent">UNPINNED</span></td></tr>
            <tr><td>frontend (runtime)</td><td><code>nginx:latest</code></td><td><span class="badge urgent">UNPINNED</span></td></tr>
          </tbody>
        </table>
        <p style="font-size:0.8rem;color:var(--color-fg-muted)">
          Item 11 (OWASP LLM03 Supply Chain) — modernized in W4 Wed.
        </p>
      </div>
    </div>

    <div class="card">
      <h3>NAICS lookup</h3>
      <input placeholder="e.g., 541512" [(ngModel)]="naicsQ"/>
      <p *ngIf="naicsQ">{{ naicsQ }} — Computer Systems Design Services</p>
    </div>
  `,
})
export class AdminConfigComponent {
  vectorStore = 'atlas';
  naicsQ = '';

  refreshClauseLibrary(): void {
    alert('Clause library refresh triggered. RAG re-embedding in background.');
  }
}
