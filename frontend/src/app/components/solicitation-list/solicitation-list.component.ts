import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Solicitation } from '../../models/solicitation';

/**
 * Solicitation list view.
 *
 * ⚠ DELIBERATE BROWNFIELD DEBT — Item 8 in docs/brownfield-debt.md ⚠
 *
 * This component hardcodes `http://localhost:8081/api/solicitations` —
 * bypassing the API gateway at :8080. Compare with
 * {@link ../../services/solicitation.service.ts} which uses
 * `environment.apiGatewayUrl`.
 *
 * The hardcode was introduced "temporarily" by a developer who couldn't
 * get the gateway running locally and was never reverted. Cohort fixes
 * in W4 Tue API modernization patterns.
 */
@Component({
  selector: 'app-solicitation-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <h2>Solicitations</h2>
    <p>
      <a routerLink="/solicitations/new"><button>+ New solicitation</button></a>
    </p>
    <div *ngIf="loading">Loading…</div>
    <div *ngIf="error" style="color: crimson">{{ error }}</div>
    <table *ngIf="!loading && !error">
      <thead>
        <tr><th>Title</th><th>Agency</th><th>Status</th><th>ID</th></tr>
      </thead>
      <tbody>
        <tr *ngFor="let s of solicitations">
          <td>{{ s.title }}</td>
          <td>{{ s.agencyId }}</td>
          <td>{{ s.status }}</td>
          <td><code>{{ s.id }}</code></td>
        </tr>
        <tr *ngIf="solicitations.length === 0">
          <td colspan="4"><em>No solicitations yet. Create one!</em></td>
        </tr>
      </tbody>
    </table>
  `,
})
export class SolicitationListComponent implements OnInit {
  // ⚠ Item 8 — hardcoded URL bypasses the API gateway at :8080.
  private apiUrl = 'http://localhost:8081/api/solicitations';

  solicitations: Solicitation[] = [];
  loading = true;
  error: string | null = null;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<Solicitation[]>(this.apiUrl).subscribe({
      next: (data) => {
        this.solicitations = data || [];
        this.loading = false;
      },
      error: (err) => {
        this.error = `Failed to load solicitations: ${err.message ?? err}`;
        this.loading = false;
      },
    });
  }
}
