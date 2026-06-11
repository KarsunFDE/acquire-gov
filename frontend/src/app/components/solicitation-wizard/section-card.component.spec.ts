import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { SectionCardComponent } from './section-card.component';
import { DraftSectionResponse } from '../../models/solicitation';

/**
 * P1.6 — AI-draft button gate ([step1Ready]) + degraded_context banner
 * (ADR-0015 D4/D5).
 */
describe('SectionCardComponent (step1Ready gate + degraded banner)', () => {
  let fixture: ComponentFixture<SectionCardComponent>;
  let component: SectionCardComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SectionCardComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(SectionCardComponent);
    component = fixture.componentInstance;
    component.sectionLetter = 'C';
    component.sectionTitle = 'Statement of Work';
    component.solicitationId = 'draft-test';
    fixture.detectChanges();
  });

  function aiDraftButton(): HTMLButtonElement {
    const buttons = fixture.nativeElement.querySelectorAll('button');
    return Array.from(buttons as NodeListOf<HTMLButtonElement>)
      .find((b) => b.textContent?.includes('AI-draft'))!;
  }

  it('disables AI-draft with tooltip when step1Ready=false (default)', () => {
    const btn = aiDraftButton();
    expect(btn.disabled).toBeTrue();
    expect(btn.title).toContain('Complete Step 1 first');
  });

  it('enables AI-draft when step1Ready=true', () => {
    component.step1Ready = true;
    fixture.detectChanges();
    expect(aiDraftButton().disabled).toBeFalse();
  });

  it('renders the degraded_context warn banner when fields were missing', () => {
    component.lastResponse = {
      outcome: 'draft_returned',
      section_text: 'text',
      section_id: 'L',
      citations: [],
      gate_decision: 'pass',
      requires_human_review: false,
      rerank_top_score: 0.8,
      request_id: 'req-1',
      run_id: 'sol:L:req-1',
      degraded_context: ['agency_supplement'],
    } as DraftSectionResponse;
    fixture.detectChanges();
    const banner = fixture.nativeElement.textContent as string;
    expect(banner).toContain('Drafted without agency_supplement');
  });

  it('does not render the degraded banner when degraded_context is empty', () => {
    component.lastResponse = {
      outcome: 'draft_returned',
      section_text: 'text',
      section_id: 'C',
      citations: [],
      gate_decision: 'pass',
      requires_human_review: false,
      rerank_top_score: 0.8,
      request_id: 'req-2',
      run_id: 'sol:C:req-2',
      degraded_context: [],
    } as DraftSectionResponse;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('Drafted without');
  });
});
