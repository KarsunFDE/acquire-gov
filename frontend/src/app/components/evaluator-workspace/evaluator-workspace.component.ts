import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_EVALUATION, FIXTURE_PROPOSALS, FIXTURE_SCORES } from '../../services/mock-fixtures';
import { EvaluationScore } from '../../models/evaluation';

/**
 * Evaluator Workspace (TEP member view).
 *
 * Assigned proposals only (Section M factor-by-factor; narrative
 * required). Mirrors FAR 15.305 evaluation discipline + Item 3
 * surface (evaluator-agent calling solicitation-service for proposal
 * text is the canonical circuit-breaker reproducer).
 */
@Component({
  selector: 'app-evaluator-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Evaluator workspace</h2>
        <div class="subtitle">{{ role.current.displayName }} · Eval {{ evaluation.id }} · FAR 15.305</div>
      </div>
      <a [routerLink]="['/evaluation', evaluation.id, 'consensus']"><button class="secondary">Consensus view →</button></a>
    </div>

    <div class="card">
      <h3>Factor scoring</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Score each proposal against each Section M factor. Narrative required
        for any rating other than Satisfactory.
      </p>
      <table>
        <thead>
          <tr>
            <th>Proposal</th>
            <th *ngFor="let f of evaluation.factors">
              {{ f.name }}<br><small>{{ f.sectionM }} · {{ f.weight }}%</small>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let p of proposals">
            <td><strong>{{ p.vendorName }}</strong></td>
            <td *ngFor="let f of evaluation.factors">
              <select [(ngModel)]="scoreFor(p.id, f.id).score">
                <option [ngValue]="9">Exceptional (9-10)</option>
                <option [ngValue]="7">Very Good (7-8)</option>
                <option [ngValue]="5">Satisfactory (5-6)</option>
                <option [ngValue]="3">Marginal (3-4)</option>
                <option [ngValue]="1">Unsatisfactory (1-2)</option>
              </select>
              <textarea rows="2" [(ngModel)]="scoreFor(p.id, f.id).narrative"
                        style="margin-top:0.25rem;font-size:0.8rem"
                        placeholder="Narrative…"></textarea>
            </td>
          </tr>
        </tbody>
      </table>
      <button style="margin-top:1rem">Submit scores</button>
    </div>
  `,
})
export class EvaluatorWorkspaceComponent {
  evaluation = FIXTURE_EVALUATION;
  proposals = FIXTURE_PROPOSALS;
  scoreCache: Record<string, EvaluationScore> = {};

  constructor(public role: RoleService) {
    // Seed editable cache from fixture
    FIXTURE_SCORES.forEach((s) => {
      this.scoreCache[`${s.proposalId}:${s.factorId}`] = { ...s };
    });
  }

  scoreFor(proposalId: string, factorId: string): EvaluationScore {
    const key = `${proposalId}:${factorId}`;
    if (!this.scoreCache[key]) {
      this.scoreCache[key] = {
        evaluatorId: 'ev-current',
        evaluatorName: this.role.current.displayName,
        proposalId,
        factorId,
        score: 5,
        narrative: '',
        submittedAt: '',
      };
    }
    return this.scoreCache[key];
  }
}
