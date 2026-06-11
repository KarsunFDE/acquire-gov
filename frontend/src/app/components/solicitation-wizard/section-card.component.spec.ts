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

/**
 * P2.4 — HITL interrupt surface (ADR-0012 D6/D8).
 */
describe('SectionCardComponent (HITL interrupt panel)', () => {
  let fixture: ComponentFixture<SectionCardComponent>;
  let component: SectionCardComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SectionCardComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(SectionCardComponent);
    component = fixture.componentInstance;
    component.sectionLetter = 'L';
    component.sectionTitle = 'Instructions to Offerors';
    component.solicitationId = 'draft-test';
    component.step1Ready = true;
    fixture.detectChanges();
  });

  function interruptedResponse(): DraftSectionResponse {
    return {
      outcome: 'interrupted',
      section_text: null,
      section_id: 'L',
      citations: [],
      gate_decision: 'hitl',
      requires_human_review: true,
      rerank_top_score: 0.45,
      request_id: 'req-int-1',
      run_id: 'sol-1:L:req-int-1',
      pending_tool_call: {
        tool_name: 'compute_gate_decision',
        args: { rerank_top_score: 0.45 },
        reason: 'rerank_top_score 0.45 in [0.40, 0.55) — CO review required',
      },
      degraded_context: [],
    };
  }

  it('renders the Pending CO decision panel with 3 decision buttons + discard', () => {
    component.lastResponse = interruptedResponse();
    (component as any).handleResponse(component.lastResponse);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Pending CO decision');
    expect(text).toContain('CO review required');
    const labels = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).map((b) => b.textContent?.trim());
    expect(labels).toContain('Approve');
    expect(labels).toContain('Edit constraints');
    expect(labels).toContain('Reject');
    expect(labels).toContain('Discard AI-draft');
  });

  it('persists runId into SectionAudit on interrupt (survives refresh)', () => {
    let emitted: any = null;
    component.auditChange.subscribe((a: any) => (emitted = a));
    component.lastResponse = interruptedResponse();
    (component as any).handleResponse(component.lastResponse);
    expect(emitted.runId).toBe('sol-1:L:req-int-1');
    expect(emitted.provenance).toBeNull(); // transitional — no provenance flip
  });

  it('does not render the panel when outcome is draft_returned', () => {
    component.lastResponse = {
      ...interruptedResponse(),
      outcome: 'draft_returned',
      section_text: 'text',
      pending_tool_call: null,
    };
    (component as any).handleResponse(component.lastResponse);
    fixture.detectChanges();
    expect(component.pendingInterrupt).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Pending CO decision');
  });
});
