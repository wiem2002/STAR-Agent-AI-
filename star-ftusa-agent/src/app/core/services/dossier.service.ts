import { Injectable } from '@angular/core';
import { Observable, of, BehaviorSubject } from 'rxjs';
import { ResultatAnalyseIA } from '../models/analyse-ia.model';
import {
  DossierHistorique,
  KpiTableauBord,
  RepartitionResultat,
  TopCasFtusa,
} from '../models/dossier.model';

const KPI_MOCK: KpiTableauBord = {
  dossiersTotaux: 1248,
  dossiersTotauxVariation: '+12% ce mois',
  enAttenteAnalyse: 82,
  enAttenteVariation: '+5% ce mois',
  iaEnCours: 15,
  iaEnCoursVariation: '-3% ce mois',
  aValiderFaibleConfiance: 23,
  aValiderVariation: '+8% ce mois',
  tempsMoyenTraitement: '06:45 min',
  tempsMoyenVariation: '-15%',
  tauxPrecisionIA: 92.6,
  tauxPrecisionVariation: '+6%',
  dossiersTraitesCeMois: 532,
  dossiersTraitesVariation: '+18%',
  dossiersClosCeMois: 410,
  dossiersClosVariation: '+20%',
};

const REPARTITION_MOCK: RepartitionResultat[] = [
  { label: 'Acceptés', valeurPct: 65, couleur: 'var(--star-green-500)' },
  { label: 'Modifiés', valeurPct: 26, couleur: 'var(--star-amber)' },
  { label: 'Refusés', valeurPct: 8, couleur: 'var(--star-red)' },
  { label: 'En attente', valeurPct: 1, couleur: 'var(--star-slate)' },
];

const TOP_CAS_MOCK: TopCasFtusa[] = [
  { cas: 'Cas 17', nombre: 245 },
  { cas: 'Cas 38', nombre: 198 },
  { cas: 'Cas 25', nombre: 163 },
  { cas: 'Cas 14', nombre: 128 },
  { cas: 'Cas 03', nombre: 97 },
];

const HISTORIQUE_MOCK: DossierHistorique[] = [
  {
    numeroSinistre: '2025/06/000123',
    dateAccident: '02/06/2025',
    casIA: 17,
    confiance: 96,
    decision: 'Accepté',
    responsabiliteA: 100,
    responsabiliteB: 0,
    statut: 'Clôturé',
  },
  {
    numeroSinistre: '2025/06/000122',
    dateAccident: '02/06/2025',
    casIA: 38,
    confiance: 85,
    decision: 'Modifié',
    responsabiliteA: 50,
    responsabiliteB: 50,
    statut: 'Clôturé',
  },
  {
    numeroSinistre: '2025/06/000121',
    dateAccident: '01/06/2025',
    casIA: 25,
    confiance: 78,
    decision: 'Accepté',
    responsabiliteA: 0,
    responsabiliteB: 100,
    statut: 'Clôturé',
  },
  {
    numeroSinistre: '2025/06/000120',
    dateAccident: '31/05/2025',
    casIA: 14,
    confiance: 92,
    decision: 'Accepté',
    responsabiliteA: 100,
    responsabiliteB: 0,
    statut: 'Clôturé',
  },
  {
    numeroSinistre: '2025/06/000119',
    dateAccident: '31/05/2025',
    casIA: 3,
    confiance: 70,
    decision: 'À valider',
    responsabiliteA: 0,
    responsabiliteB: 0,
    statut: 'En attente',
  },
];

@Injectable({ providedIn: 'root' })
export class DossierService {
  private readonly historiqueSubject = new BehaviorSubject<DossierHistorique[]>(HISTORIQUE_MOCK);
  // Pending validation payload used to prefill the validation UI
  private readonly pendingValidationSubject = new BehaviorSubject<ResultatAnalyseIA | null>(null);

  getPendingValidation(): Observable<ResultatAnalyseIA | null> {
    return this.pendingValidationSubject.asObservable();
  }

  setPendingValidation(r: ResultatAnalyseIA | null): void {
    this.pendingValidationSubject.next(r);
  }

  getKpiTableauBord(): Observable<KpiTableauBord> {
    return of(KPI_MOCK);
  }

  getRepartitionResultats(): Observable<RepartitionResultat[]> {
    return of(REPARTITION_MOCK);
  }

  getTopCasFtusa(): Observable<TopCasFtusa[]> {
    return of(TOP_CAS_MOCK);
  }

  getHistorique(): Observable<DossierHistorique[]> {
    return this.historiqueSubject.asObservable();
  }

  /** Ajoute un dossier en tête de l'historique (frontend mock). */
  ajouterDossier(dossier: DossierHistorique): void {
    const current = this.historiqueSubject.value.slice();
    current.unshift(dossier);
    this.historiqueSubject.next(current);
  }
}
