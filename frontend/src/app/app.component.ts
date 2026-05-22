import { Component } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <header>
      <h1>acquire-gov</h1>
      <nav>
        <a routerLink="/solicitations">Solicitations</a>
        <a routerLink="/solicitations/new">New Solicitation</a>
        <a routerLink="/evaluations">Evaluations</a>
        <a routerLink="/reports">Reports</a>  <!-- ⚠ dead route — Item 8 reinforcement -->
      </nav>
    </header>
    <main>
      <router-outlet></router-outlet>
    </main>
  `,
})
export class AppComponent {}
