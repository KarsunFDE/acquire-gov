import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_EVALUATION, FIXTURE_PROPOSALS, FIXTURE_SCORES } from '../../services/mock-fixtures';
import { EvaluationFactor } from '../../models/evaluation';

/**
 * Source Selection Tradeoff + SSDD draft (FAR 15.308).
 *
 * SSA-only gate. AI drafts SSDD tradeoff narrative; SSA reviews + signs.
 * SSA authority cannot delegate (FAR 15.303(b)(6)). This is the
 * W3 LangGraph HITL #5 deep-dive surface — interrupt-before-node at
 * "consensus complete" and "award ready".
 */
@Component({
  selector: 'app-consensus-ssdd',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Source selection — tradeoff &amp; SSDD</h2>
        <div class="subtitle">FAR 15.308 · SSA authority non-delegable</div>
      </div>
      <a routerLink="/evaluation/workspace"><button class="secondary">← Evaluator workspace</button></a>
    </div>

    <div class="hitl-banner">
      <strong>HITL gate (W3 #5 — LangGraph deep-dive):</strong>
      AI drafts SSDD tradeoff narrative; SSA must review &amp; sign.
      LangGraph interrupt-before-node fires at "award ready".
    </div>

    <div class="card">
      <h3>Tradeoff matrix</h3>
      <table>
        <thead>
          <tr>
            <th>Proposal</th>
            <th *ngFor="let f of evaluation.factors">{{ f.name }} <small>({{ f.weight }}%)</small></th>
            <th>Weighted total</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let p of proposals">
            <td><strong>{{ p.vendorName }}</strong></td>
            <td *ngFor="let f of evaluation.factors">{{ avgScore(p.id, f.id) | number:'1.0-1' }}</td>
            <td><strong>{{ weighted(p.id) | number:'1.0-2' }}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>SSDD draft (AI-assisted)</h3>
      <button class="secondary" (click)="aiDraft()">▦ AI-draft SSDD narrative</button>
      <textarea rows="10" [(ngModel)]="ssddNarrative" style="margin-top:0.5rem"></textarea>
      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;align-items:center">
        <button [disabled]="role.currentRole !== 'ssa'" (click)="sign()">
          ✓ SSA sign &amp; record award
        </button>
        <small *ngIf="role.currentRole !== 'ssa'" style="color:var(--color-fg-muted)">
          Only the SSA can sign (FAR 15.303(b)(6)).
        </small>
      </div>
      <div *ngIf="signed" class="card" style="background:var(--color-bg);margin-top:1rem">
        <strong>✓ Award recorded:</strong> {{ winningName() }} —
        <a routerLink="/awards/aw-2026-001">aw-2026-001</a>
      </div>
    </div>
  `,
})
export class ConsensusSsddComponent {
  evaluation = FIXTURE_EVALUATION;
  proposals = FIXTURE_PROPOSALS;
  ssddNarrative = '';
  signed = false;

  constructor(public role: RoleService, route: ActivatedRoute) {
    // Route param `solId` reserved for multi-evaluation routing.
  }

  avgScore(proposalId: string, factorId: string): number {
    const matches = FIXTURE_SCORES.filter((s) => s.proposalId === proposalId && s.factorId === factorId);
    if (!matches.length) return 5;
    return matches.reduce((sum, s) => sum + s.score, 0) / matches.length;
  }

  weighted(proposalId: string): number {
    return this.evaluation.factors.reduce(
      (sum: number, f: EvaluationFactor) => sum + this.avgScore(proposalId, f.id) * (f.weight / 100),
      0,
    );
  }

  aiDraft(): void {
    const best = this.proposals
      .map((p) => ({ id: p.id, name: p.vendorName, score: this.weighted(p.id) }))
      .sort((a, b) => b.score - a.score)[0];
    this.ssddNarrative =
      `Source Selection Decision Document (SSDD)\n\n` +
      `Pursuant to FAR 15.308, the Source Selection Authority has determined that ` +
      `${best.name} represents the best value to the Government under the ` +
      `evaluation criteria of Section M. The weighted technical score of ` +
      `${best.score.toFixed(2)} is consistent with the tradeoff analysis between ` +
      `technical capability, past performance, and price.\n\n` +
      `[AI-DRAFTED — SSA must review for factual accuracy. Item 4 (no Pydantic schema), Item 5 (legacy LLMChain).]`;
  }

  sign(): void {
    if (this.role.currentRole !== 'ssa') return;
    this.signed = true;
  }

  winningName(): string {
    const best = this.proposals
      .map((p) => ({ id: p.id, name: p.vendorName, score: this.weighted(p.id) }))
      .sort((a, b) => b.score - a.score)[0];
    return best?.name ?? '—';
  }
}
