import { Injectable } from '@angular/core';
import { Observable, BehaviorSubject, map } from 'rxjs';
import { ResultatAnalyseIA } from '../models/analyse-ia.model';
import {
  DossierHistorique,
  KpiTableauBord,
  RepartitionResultat,
  TopCasFtusa,
} from '../models/dossier.model';

const HISTORIQUE_INITIAL: DossierHistorique[] = [
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
  private readonly historiqueSubject = new BehaviorSubject<DossierHistorique[]>(HISTORIQUE_INITIAL);
  private readonly pendingValidationSubject = new BehaviorSubject<ResultatAnalyseIA | null>(null);

  getPendingValidation(): Observable<ResultatAnalyseIA | null> {
    return this.pendingValidationSubject.asObservable();
  }

  setPendingValidation(r: ResultatAnalyseIA | null): void {
    this.pendingValidationSubject.next(r);
  }

  getHistorique(): Observable<DossierHistorique[]> {
    return this.historiqueSubject.asObservable();
  }

  ajouterDossier(dossier: DossierHistorique): void {
    const current = this.historiqueSubject.value.slice();
    current.unshift(dossier);
    this.historiqueSubject.next(current);
  }

  // ── KPIs calculés dynamiquement depuis l'historique ─────────────────────

  getKpiTableauBord(): Observable<KpiTableauBord> {
    return this.historiqueSubject.pipe(
      map(h => this._calculerKpi(h))
    );
  }

  getRepartitionResultats(): Observable<RepartitionResultat[]> {
    return this.historiqueSubject.pipe(
      map(h => this._calculerRepartition(h))
    );
  }

  getTopCasFtusa(): Observable<TopCasFtusa[]> {
    return this.historiqueSubject.pipe(
      map(h => this._calculerTopCas(h))
    );
  }

  // ── Calculs ──────────────────────────────────────────────────────────────

  private _calculerKpi(h: DossierHistorique[]): KpiTableauBord {
    const total = h.length;
    const enAttente = h.filter(d => d.statut === 'En attente').length;
    const clos = h.filter(d => d.statut === 'Clôturé').length;
    const aValider = h.filter(d => d.decision === 'À valider').length;

    const confianceMoy = total > 0
      ? Math.round(h.reduce((s, d) => s + d.confiance, 0) / total)
      : 0;

    // Calcul temps moyen fictif basé sur la confiance (placeholder réaliste)
    const minutesMoy = total > 0 ? Math.max(1, Math.round(15 - confianceMoy / 10)) : 0;
    const mm = String(minutesMoy).padStart(2, '0');

    return {
      dossiersTotaux: total,
      dossiersTotauxVariation: `${total} dossier(s)`,
      enAttenteAnalyse: enAttente,
      enAttenteVariation: `${enAttente} en attente`,
      iaEnCours: 0,
      iaEnCoursVariation: 'Temps réel',
      aValiderFaibleConfiance: aValider,
      aValiderVariation: `${aValider} à valider`,
      tempsMoyenTraitement: `${mm}:00 min`,
      tempsMoyenVariation: 'Estimation',
      tauxPrecisionIA: confianceMoy,
      tauxPrecisionVariation: `${confianceMoy}%`,
      dossiersTraitesCeMois: clos,
      dossiersTraitesVariation: `${clos} clôturé(s)`,
      dossiersClosCeMois: clos,
      dossiersClosVariation: `${clos} ce mois`,
    };
  }

  private _calculerRepartition(h: DossierHistorique[]): RepartitionResultat[] {
    const total = h.length || 1;
    const compter = (dec: string) =>
      Math.round((h.filter(d => d.decision === dec).length / total) * 100);

    const acceptes = compter('Accepté');
    const modifies = compter('Modifié');
    const refuses  = compter('Refusé');
    const attente  = Math.max(0, 100 - acceptes - modifies - refuses);

    return [
      { label: 'Acceptés',   valeurPct: acceptes, couleur: 'var(--star-green-500)' },
      { label: 'Modifiés',   valeurPct: modifies, couleur: 'var(--star-amber)' },
      { label: 'Refusés',    valeurPct: refuses,  couleur: 'var(--star-red)' },
      { label: 'En attente', valeurPct: attente,  couleur: 'var(--star-slate)' },
    ];
  }

  private _calculerTopCas(h: DossierHistorique[]): TopCasFtusa[] {
    const comptage: Record<number, number> = {};
    for (const d of h) {
      comptage[d.casIA] = (comptage[d.casIA] || 0) + 1;
    }
    return Object.entries(comptage)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([cas, nombre]) => ({ cas: `Cas ${cas}`, nombre }));
  }
}
