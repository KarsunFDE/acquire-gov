import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DraftSectionCitation } from '../../models/solicitation';

/**
 * Expandable citation row list for a grounded AI-drafted section.
 *
 * Renders up to 5 citations from the /draft-solicitation/section response,
 * each collapsible to reveal the source chunk text. Spec:
 * docs/specs/m2-ui-far-sections.md §4 (per-section UI shell) + §9.
 *
 * The component is presentation-only — the authoritative gate decision lives
 * in the parent section-card via `gate_decision` (ADR-0007 D2).
 */
@Component({
  selector: 'app-citation-list',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="citation-list" *ngIf="citations?.length">
      <div class="citation-list-header">
        Citations (top {{ visible().length }} of {{ citations.length }})
      </div>
      <ol>
        <li *ngFor="let c of visible(); let i = index" class="citation-row">
          <div class="citation-line">
            <span class="cite-loc">
              FAR Part {{ c.far_part }} &sect; {{ c.far_section }}
              <span class="cite-clause" *ngIf="c.far_clause">({{ c.far_clause }})</span>
            </span>
            <span class="cite-snapshot">snapshot {{ c.snapshot_date }}</span>
            <span class="cite-score">{{ c.relevance_score | number:'1.2-2' }}</span>
            <button class="citation-toggle" type="button"
                    (click)="toggle(i)" [attr.aria-expanded]="expanded[i]">
              {{ expanded[i] ? '▾' : '▸' }} text
            </button>
          </div>
          <pre *ngIf="expanded[i]" class="citation-text">{{ c.text }}</pre>
        </li>
      </ol>
    </div>
  `,
  styles: [`
    .citation-list {
      margin-top: 0.75rem;
      border-top: 1px dashed var(--color-border);
      padding-top: 0.5rem;
    }
    .citation-list-header {
      font-size: 0.8rem;
      color: var(--color-fg-muted);
      margin-bottom: 0.35rem;
    }
    ol { margin: 0; padding-left: 1.25rem; }
    .citation-row { font-size: 0.85rem; margin-bottom: 0.25rem; }
    .citation-line { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
    .cite-loc { font-weight: 600; }
    .cite-clause { font-weight: 400; color: var(--color-fg-muted); margin-left: 0.25rem; }
    .cite-snapshot { color: var(--color-fg-muted); font-size: 0.75rem; }
    .cite-score {
      background: var(--color-bg);
      border: 1px solid var(--color-border);
      border-radius: 3px;
      padding: 0 0.3rem;
      font-variant-numeric: tabular-nums;
      font-size: 0.75rem;
    }
    .citation-toggle {
      background: transparent;
      color: var(--color-accent);
      border: none;
      padding: 0;
      cursor: pointer;
      font-size: 0.8rem;
    }
    .citation-text {
      background: var(--color-bg);
      border-left: 3px solid var(--color-border);
      padding: 0.4rem 0.6rem;
      margin: 0.25rem 0 0.5rem 0;
      font-size: 0.8rem;
      white-space: pre-wrap;
    }
  `],
})
export class CitationListComponent {
  @Input() citations: DraftSectionCitation[] = [];
  /** Cap at 5 per the spec (top-5 surfaced; full list available in audit_log). */
  @Input() maxVisible = 5;

  expanded: Record<number, boolean> = {};

  visible(): DraftSectionCitation[] {
    return (this.citations ?? []).slice(0, this.maxVisible);
  }

  toggle(i: number): void {
    this.expanded[i] = !this.expanded[i];
  }
}
