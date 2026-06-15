import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { SolicitationWizardComponent } from './solicitation-wizard.component';

/**
 * P1.5 — Step 1 reactive-forms gate (ADR-0015 D4).
 * step1Form invalid → Next disabled; valid → enabled.
 */
describe('SolicitationWizardComponent (Step 1 reactive forms)', () => {
  let fixture: ComponentFixture<SolicitationWizardComponent>;
  let component: SolicitationWizardComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SolicitationWizardComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(SolicitationWizardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  function nextButton(): HTMLButtonElement | null {
    const buttons = fixture.nativeElement.querySelectorAll('button');
    return Array.from(buttons as NodeListOf<HTMLButtonElement>)
      .find((b) => b.textContent?.includes('Next')) ?? null;
  }

  it('starts invalid — title and naics are empty', () => {
    expect(component.step1Form.valid).toBeFalse();
    expect(component.isStep1ContextReady()).toBeFalse();
  });

  it('disables Next on step 0 while step1Form is invalid', () => {
    const btn = nextButton();
    expect(btn).not.toBeNull();
    expect(btn!.disabled).toBeTrue();
  });

  it('enables Next once the 5 hard-required fields are filled', () => {
    component.step1Form.patchValue({
      title: 'Cloud Managed Services BPA',
      agencyId: 'GSA-FAS',
      naics: '541512',
      setAside: 'SDVOSB',
      contractType: 'FFP',
    });
    fixture.detectChanges();
    expect(component.step1Form.valid).toBeTrue();
    expect(nextButton()!.disabled).toBeFalse();
  });

  it('keeps the legacy model object in sync with form edits', () => {
    component.step1Form.patchValue({ title: 'Synced title', naics: '541511' });
    expect(component.model.title).toBe('Synced title');
    expect(component.model.naics).toBe('541511');
  });

  it('draftMeta maps form values with null fallbacks (ADR-0015 D3)', () => {
    component.step1Form.patchValue({
      naics: '541512',
      setAside: 'SDVOSB',
      contractType: 'FFP',
      agencySupplement: '',
      periodOfPerformance: '',
      placeOfPerformance: '',
      evalApproach: 'LPTA',
      keyPersonnel: '',
    });
    expect(component.draftMeta).toEqual({
      naics: '541512',
      setAside: 'SDVOSB',
      contractType: 'FFP',
      agencySupplement: null,
      periodOfPerformance: null,
      placeOfPerformance: null,
      evalApproach: 'LPTA',
      keyPersonnel: null,
    });
  });
});

/**
 * P4.3 — Step 12 critic render (warn-only invariant).
 */
describe('SolicitationWizardComponent (Step 12 critic)', () => {
  let fixture: ComponentFixture<SolicitationWizardComponent>;
  let component: SolicitationWizardComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SolicitationWizardComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(SolicitationWizardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  function warnReport(): any {
    return {
      solicitation_id: 'sol-1',
      run_id: 'sol-1:critic:req-1',
      lm_alignment: {
        mismatches: [], overall_severity: 'info',
        model: 'amazon.nova-lite-v1:0', input_tokens: 0, output_tokens: 0,
      },
      set_aside_consistency: {
        mismatches: [{
          set_aside: 'SDVOSB', expected_reps: ['52.219-27'], actual_reps: [],
          missing: ['52.219-27'], extra: [], severity: 'warn',
        }],
        overall_severity: 'warn',
      },
      clin_coverage: {
        gaps: [{ clin_id: '0002', missing_in: ['F'], severity: 'warn' }],
        overall_severity: 'warn',
      },
      overall_severity: 'warn',
      blocks_submit: false,
      model_used: 'amazon.nova-lite-v1:0',
      timestamp: '2026-06-11T12:00:00Z',
    };
  }

  it('renders the three sub-reports inline at Step 12', () => {
    component.step = 11;
    component.criticReport = warnReport();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Set-aside ↔ Section K (warn)');
    expect(text).toContain('Section K missing 52.219-27');
    expect(text).toContain('CLIN 0002 not referenced in Section F');
    expect(text).toContain('L ↔ M alignment (info)');
    expect(text).toContain('blocks_submit=false');
  });

  it('critic warnings never disable the Step 13 submit path', () => {
    component.step = 12;
    component.criticReport = warnReport();
    fixture.detectChanges();
    const submitBtn = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Submit for internal review'))!;
    expect(submitBtn).toBeDefined();
    // Only HITL-flagged sections gate submit — critic warn alone does not.
    expect(submitBtn.disabled).toBeFalse();
  });

  it('maps sections to wizard steps for the Fix links', () => {
    expect(component.stepForSection('K')).toBe(8);
    expect(component.stepForSection('F')).toBe(4);
    expect(component.stepForSection('L')).toBe(9);
  });
});
