import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';
import { DamageReport } from '../models/damage-report.model';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class DommagesService {
  private readonly apiUrl = `${environment.apiUrl}/api/dommages/analyser`;

  constructor(private readonly http: HttpClient) {}

  /**
   * Envoie une photo au backend et retourne le rapport de dommages.
   * @param photo   Fichier image (jpg/png/webp)
   * @param vehicule "A" ou "B"
   */
  analyserPhoto(photo: File, vehicule: 'A' | 'B'): Observable<DamageReport> {
    const form = new FormData();
    form.append('photo', photo, photo.name);
    form.append('vehicule', vehicule);

    return this.http
      .post<DamageReport>(this.apiUrl, form)
      .pipe(
        catchError((err) => {
          const msg = err?.error?.detail ?? 'Analyse indisponible, réessayez.';
          return throwError(() => new Error(msg));
        }),
      );
  }
}
