import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Finding } from '../models/finding';

@Injectable({ providedIn: 'root' })
export class FindingService {
  constructor(private http: HttpClient) {}

  list(): Observable<Finding[]> {
    return this.http.get<Finding[]>(`${environment.apiGatewayUrl}/api/findings`);
  }

  open(payload: Partial<Finding>): Observable<Finding> {
    return this.http.post<Finding>(
      `${environment.apiGatewayUrl}/api/findings`,
      payload,
    );
  }
}
