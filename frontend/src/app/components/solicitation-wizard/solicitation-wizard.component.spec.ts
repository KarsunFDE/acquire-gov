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
    });
    expect(component.draftMeta).toEqual({
      naics: '541512',
      setAside: 'SDVOSB',
      contractType: 'FFP',
      agencySupplement: null,
    });
  });
});
