import { Routes } from '@angular/router';
import { SolicitationListComponent } from './components/solicitation-list/solicitation-list.component';
import { SolicitationCreateComponent } from './components/solicitation-create/solicitation-create.component';
import { EvaluationPanelComponent } from './components/evaluation-panel/evaluation-panel.component';

export const routes: Routes = [
  { path: '', redirectTo: 'solicitations', pathMatch: 'full' },
  { path: 'solicitations', component: SolicitationListComponent },
  { path: 'solicitations/new', component: SolicitationCreateComponent },
  { path: 'evaluations', component: EvaluationPanelComponent },
  // ⚠ DELIBERATE — Item 8 reinforcement:
  //   /reports is in the nav (app.component.ts) but the target component
  //   doesn't exist. Clicking it produces a "Cannot match any routes" error.
];
