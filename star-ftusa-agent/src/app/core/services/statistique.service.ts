import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { PointEvolutionPrecision, RepartitionCasFtusa } from '../models/analyse-ia.model';

const REPARTITION_CAS_MOCK: RepartitionCasFtusa[] = [
  { cas: 'Cas 17', pourcentage: 24, couleur: 'var(--star-green-500)' },
  { cas: 'Cas 38', pourcentage: 19, couleur: 'var(--star-green-300)' },
  { cas: 'Cas 25', pourcentage: 15, couleur: 'var(--star-amber)' },
  { cas: 'Cas 14', pourcentage: 12, couleur: 'var(--star-green-800)' },
  { cas: 'Autres', pourcentage: 30, couleur: 'var(--star-slate)' },
];

const EVOLUTION_PRECISION_MOCK: PointEvolutionPrecision[] = [
  { mois: 'Janv.', valeur: 84 },
  { mois: 'Fév.', valeur: 87 },
  { mois: 'Mars', valeur: 85 },
  { mois: 'Avr.', valeur: 89 },
  { mois: 'Mai', valeur: 91 },
  { mois: 'Juin', valeur: 92.6 },
];

@Injectable({ providedIn: 'root' })
export class StatistiqueService {
  getRepartitionCasFtusa(): Observable<RepartitionCasFtusa[]> {
    return of(REPARTITION_CAS_MOCK);
  }

  getEvolutionPrecision(): Observable<PointEvolutionPrecision[]> {
    return of(EVOLUTION_PRECISION_MOCK);
  }

  getTauxAcceptation(): Observable<number> {
    return of(82);
  }

  getTempsMoyenTraitement(): Observable<string> {
    return of('06:45 min');
  }

  getTotalDossiersMois(): Observable<number> {
    return of(532);
  }
}
