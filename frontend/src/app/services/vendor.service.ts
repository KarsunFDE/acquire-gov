import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Vendor } from '../models/vendor';

@Injectable({ providedIn: 'root' })
export class VendorService {
  constructor(private http: HttpClient) {}

  list(): Observable<Vendor[]> {
    return this.http.get<Vendor[]>(`${environment.apiGatewayUrl}/api/vendors`);
  }

  get(id: string): Observable<Vendor> {
    return this.http.get<Vendor>(`${environment.apiGatewayUrl}/api/vendors/${id}`);
  }
}
