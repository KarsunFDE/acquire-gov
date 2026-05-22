import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Solicitation, SolicitationCreate } from '../models/solicitation';

/**
 * Solicitation service — the "right" way to talk to the backend.
 *
 * Goes through the API gateway (environment.apiGatewayUrl). The cohort
 * compares this with `solicitation-list.component.ts`, which hardcodes
 * `http://localhost:8081` and bypasses the gateway (Item 8).
 */
@Injectable({ providedIn: 'root' })
export class SolicitationService {
  private readonly baseUrl = `${environment.apiGatewayUrl}/api/solicitations`;

  constructor(private http: HttpClient) {}

  list(): Observable<Solicitation[]> {
    return this.http.get<Solicitation[]>(this.baseUrl);
  }

  get(id: string): Observable<Solicitation> {
    return this.http.get<Solicitation>(`${this.baseUrl}/${id}`);
  }

  create(req: SolicitationCreate): Observable<Solicitation> {
    return this.http.post<Solicitation>(this.baseUrl, req);
  }
}
