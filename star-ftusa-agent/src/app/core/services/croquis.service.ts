import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CroquisAnalyse, CorrectionCroquis } from '../models/croquis.model';

@Injectable({ providedIn: 'root' })
export class CroquisService {
  private readonly apiUrl = `${environment.apiUrl}/api/constats`;

  constructor(private readonly http: HttpClient) {}

  getCroquisDetecte(numeroSinistre: string): Observable<CroquisAnalyse> {
    return this.http
      .get<CroquisAnalyse>(`${this.apiUrl}/${encodeURIComponent(numeroSinistre)}/croquis`)
      .pipe(tap((croquis) => console.log('[CROQUIS_DEBUG] frontend=', croquis)));
  }

  envoyerCorrection(correction: CorrectionCroquis): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(
      `${this.apiUrl}/${encodeURIComponent(correction.numeroSinistre)}/croquis/correction`,
      correction
    );
  }
}