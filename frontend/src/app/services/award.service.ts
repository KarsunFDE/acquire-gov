import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Award, ContractModification, Deliverable, Cpar } from '../models/award';

@Injectable({ providedIn: 'root' })
export class AwardService {
  constructor(private http: HttpClient) {}

  get(id: string): Observable<Award> {
    return this.http.get<Award>(`${environment.apiGatewayUrl}/api/awards/${id}`);
  }

  requestDebrief(id: string, reason: string): Observable<void> {
    return this.http.post<void>(
      `${environment.apiGatewayUrl}/api/awards/${id}/debrief-request`,
      { reason },
    );
  }

  // — Contract administration (FAR Part 42)

  contractModifications(contractId: string): Observable<ContractModification[]> {
    return this.http.get<ContractModification[]>(
      `${environment.apiGatewayUrl}/api/contracts/${contractId}/modifications`,
    );
  }

  issueModification(
    contractId: string,
    mod: Partial<ContractModification>,
  ): Observable<ContractModification> {
    return this.http.post<ContractModification>(
      `${environment.apiGatewayUrl}/api/contracts/${contractId}/modifications`,
      mod,
    );
  }

  deliverables(contractId: string): Observable<Deliverable[]> {
    return this.http.get<Deliverable[]>(
      `${environment.apiGatewayUrl}/api/contracts/${contractId}/deliverables`,
    );
  }

  cpars(contractId: string): Observable<Cpar[]> {
    return this.http.get<Cpar[]>(
      `${environment.apiGatewayUrl}/api/contracts/${contractId}/cpars`,
    );
  }

  submitRebuttal(contractId: string, cparId: string, rebuttal: string): Observable<Cpar> {
    return this.http.post<Cpar>(
      `${environment.apiGatewayUrl}/api/contracts/${contractId}/cpars/${cparId}/rebuttal`,
      { rebuttal },
    );
  }
}
