import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map, shareReplay, of } from 'rxjs';
import { BehaviorSubject } from 'rxjs';
import {
  DetailsTechniquesAnalyse,
  EtapeAnalyse,
  ReponseApiAnalyseComplete,
  ResultatAnalyseIA,
} from '../models/analyse-ia.model';
import { CirconstancesVehicule, AutresElements } from '../models/circonstance.model';
import { environment } from '../../../environments/environment';

const ETAPES_MOCK: EtapeAnalyse[] = [
  { ordre: 1, libelle: 'OCR constat', statut: 'attente' },
  { ordre: 2, libelle: 'Lecture circonstances', statut: 'attente' },
  { ordre: 3, libelle: 'Analyse croquis', statut: 'attente' },
  { ordre: 4, libelle: 'Analyse photos', statut: 'attente' },
  { ordre: 5, libelle: 'IA - Recherche cas FTUSA', statut: 'attente' },
];

const DETAILS_VIDES: DetailsTechniquesAnalyse = {
  idAnalyse: '',
  modeleIA: '',
  dateAnalyse: '',
  dureeAnalyse: '00:00:00',
  sourcesUtilisees: [],
  reglesAppliquees: 0,
  scoreSimilariteCas: 0,
  nombreCasSimilaires: 0,
};

const CIRCONSTANCES_A_MOCK: CirconstancesVehicule = {
  vehicule: 'A',
  options: [],
};

const CIRCONSTANCES_B_MOCK: CirconstancesVehicule = {
  vehicule: 'B',
  options: [],
};

const AUTRES_ELEMENTS_MOCK: AutresElements = {
  signalisation: '',
  typeDeRoute: '',
  conditionsMeteo: '',
  etatChaussee: '',
  visibilite: '',
  observations: '',
};

@Injectable({ providedIn: 'root' })
export class AnalyseIaService {
  private readonly apiUrl = `${environment.apiUrl}/api/constats/analyser`;

  /** Résultat de la dernière analyse réelle, mis en cache pour que
   * ResultatAnalyseComponent puisse le relire sans relancer l'appel. */
  private dernierResultat$?: Observable<ResultatAnalyseIA>;
  private readonly detailsTechniquesSubject = new BehaviorSubject<DetailsTechniquesAnalyse>(DETAILS_VIDES);

  constructor(private readonly http: HttpClient) {}

  getEtapesAnalyse(): Observable<EtapeAnalyse[]> {
    return of(ETAPES_MOCK);
  }

  /**
   * Envoie le constat (PDF) au backend et retourne le résultat au format
   * attendu par l'interface existante (ResultatAnalyseIA). L'appel réel
   * est mis en cache (shareReplay) pour que getResultatAnalyse() puisse
   * le relire ensuite sans relancer l'analyse.
   */
  analyserConstat(
    fichierConstat: File,
    numeroSinistre: string,
    page = 0,
    colGauche: 'A' | 'B' = 'A'
  ): Observable<ResultatAnalyseIA> {
    const formData = new FormData();
    formData.append('fichier', fichierConstat, fichierConstat.name);

    const params = { page: page.toString(), colGauche, numeroSinistre };

    this.dernierResultat$ = this.http
      .post<ReponseApiAnalyseComplete>(this.apiUrl, formData, { params })
      .pipe(
        map((r) => {
          this.detailsTechniquesSubject.next(this.mapReponseApiVersDetails(r));
          return this.mapReponseApiVersModele(r);
        }),
        shareReplay(1)
      );

    return this.dernierResultat$;
  }

  /** Relit le résultat de la dernière analyse réelle lancée via
   * analyserConstat(). Si aucune analyse n'a encore été lancée dans cette
   * session, retombe sur un résultat vide plutôt que de planter. */
  getResultatAnalyse(): Observable<ResultatAnalyseIA> {
    if (this.dernierResultat$) {
      return this.dernierResultat$;
    }
    return of({
      casPropose: 0,
      titreCas: '—',
      regleAppliquee: 'Aucune analyse lancée',
      justification: '',
      responsabiliteA: 0,
      responsabiliteB: 0,
      niveauConfiance: 0,
      elementsClesUtilises: [],
    });
  }

  getDetailsTechniques(): Observable<DetailsTechniquesAnalyse> {
    return this.detailsTechniquesSubject.asObservable();
  }

  getCirconstancesVehiculeA(): Observable<CirconstancesVehicule> {
    return of(CIRCONSTANCES_A_MOCK);
  }

  getCirconstancesVehiculeB(): Observable<CirconstancesVehicule> {
    return of(CIRCONSTANCES_B_MOCK);
  }

  getAutresElements(): Observable<AutresElements> {
    return of(AUTRES_ELEMENTS_MOCK);
  }

  private mapReponseApiVersModele(r: ReponseApiAnalyseComplete): ResultatAnalyseIA {
    return {
      casPropose: Number(r.casId) || 0,
      titreCas: `Cas N° ${r.casId}`,
      regleAppliquee: r.titre,
      justification: r.justification,
      responsabiliteA: r.responsabiliteA ?? 0,
      responsabiliteB: r.responsabiliteB ?? 0,
      niveauConfiance: r.niveauConfiance,
      elementsClesUtilises: [
        ...r.circonstancesA.map((n) => `A: circonstance ${n}`),
        ...r.circonstancesB.map((n) => `B: circonstance ${n}`),
      ],
      croquisImageBase64: r.croquisImageBase64,
      croquis: r.croquis ?? null,
    };
  }

  private mapReponseApiVersDetails(r: ReponseApiAnalyseComplete): DetailsTechniquesAnalyse {
    return {
      idAnalyse: r.idAnalyse,
      modeleIA: r.modeleIA,
      dateAnalyse: r.dateAnalyse,
      dureeAnalyse: r.dureeAnalyse,
      sourcesUtilisees: r.sourcesUtilisees,
      reglesAppliquees: r.reglesAppliquees,
      scoreSimilariteCas: r.scoreSimilariteCas,
      nombreCasSimilaires: r.nombreCasSimilaires,
    };
  }
}
