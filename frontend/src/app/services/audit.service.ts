import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuditEvent, AuditSearchFilter } from '../models/audit';

@Injectable({ providedIn: 'root' })
export class AuditService {
  constructor(private http: HttpClient) {}

  search(filter: AuditSearchFilter): Observable<AuditEvent[]> {
    let params = new HttpParams();
    (Object.keys(filter) as (keyof AuditSearchFilter)[]).forEach((key) => {
      const value = filter[key];
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    });
    return this.http.get<AuditEvent[]>(
      `${environment.apiGatewayUrl}/api/audit-events`,
      { params },
    );
  }
}
