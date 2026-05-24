import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Evaluation, EvaluationScore } from '../models/evaluation';

@Injectable({ providedIn: 'root' })
export class EvaluationService {
  constructor(private http: HttpClient) {}

  get(id: string): Observable<Evaluation> {
    return this.http.get<Evaluation>(
      `${environment.apiGatewayUrl}/api/evaluations/${id}`,
    );
  }

  scores(id: string): Observable<EvaluationScore[]> {
    return this.http.get<EvaluationScore[]>(
      `${environment.apiGatewayUrl}/api/evaluations/${id}/scores`,
    );
  }

  submitScore(id: string, score: Partial<EvaluationScore>): Observable<EvaluationScore> {
    return this.http.post<EvaluationScore>(
      `${environment.apiGatewayUrl}/api/evaluations/${id}/scores`,
      score,
    );
  }

  consensus(id: string): Observable<EvaluationScore[]> {
    return this.http.get<EvaluationScore[]>(
      `${environment.apiGatewayUrl}/api/evaluations/${id}/consensus`,
    );
  }

  /** AI-drafted Source Selection Decision Document narrative (FAR 15.308). */
  draftSsdd(id: string): Observable<{ narrative: string; correlationId: string }> {
    return this.http.post<{ narrative: string; correlationId: string }>(
      `${environment.apiGatewayUrl}/api/ai/eval/ssdd-draft`,
      { evaluationId: id },
    );
  }
}
