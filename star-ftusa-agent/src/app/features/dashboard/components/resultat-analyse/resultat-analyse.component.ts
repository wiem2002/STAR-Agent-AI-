import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { DamageReportCardComponent } from '../../../../shared/components/damage-report-card/damage-report-card.component';
import { AnalyseIaService } from '../../../../core/services/analyse-ia.service';
import { DossierService } from '../../../../core/services/dossier.service';
import { DossierCourantService } from '../../../../core/services/dossier-courant.service';
import { DommagesService } from '../../../../core/services/dommages.service';
import { NavigationService } from '../../../../core/services/navigation.service';
import { DossierHistorique } from '../../../../core/models/dossier.model';
import { ResultatAnalyseIA } from '../../../../core/models/analyse-ia.model';
import { DamageReport } from '../../../../core/models/damage-report.model';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  selector: 'app-resultat-analyse',
  standalone: true,
  imports: [CommonModule, PanelCardComponent, DamageReportCardComponent],
  templateUrl: './resultat-analyse.component.html',
  styleUrl: './resultat-analyse.component.scss',
})
export class ResultatAnalyseComponent implements OnInit {
  resultat?: ResultatAnalyseIA;
  rapportA: DamageReport | null = null;
  rapportB: DamageReport | null = null;
  chargementDommages = false;
  erreurDommages: string | null = null;

  constructor(
    private readonly analyseIaService: AnalyseIaService,
    private readonly dossierService: DossierService,
    private readonly dossierCourantService: DossierCourantService,
    private readonly dommagesService: DommagesService,
    private readonly navigationService: NavigationService,
  ) {}

  ngOnInit(): void {
    this.analyseIaService.getResultatAnalyse().subscribe((r) => {
      this.resultat = r;
      this._lancerAnalyseDommages();
    });
  }

  private _lancerAnalyseDommages(): void {
    const photosA = this.dossierCourantService.photosAActuelles;
    const photosB = this.dossierCourantService.photosBActuelles;

    // Utilise la première photo de chaque véhicule
    const photoA = photosA[0] ?? null;
    const photoB = photosB[0] ?? null;

    if (!photoA && !photoB) {
      // Aucune photo : état vide, pas de texte en dur
      this.rapportA = null;
      this.rapportB = null;
      return;
    }

    this.chargementDommages = true;
    this.erreurDommages = null;

    const appel$ = forkJoin({
      a: photoA
        ? this.dommagesService.analyserPhoto(photoA, 'A').pipe(catchError(e => of({ _erreur: e.message } as any)))
        : of(null),
      b: photoB
        ? this.dommagesService.analyserPhoto(photoB, 'B').pipe(catchError(e => of({ _erreur: e.message } as any)))
        : of(null),
    });

    appel$.subscribe({
      next: ({ a, b }) => {
        this.chargementDommages = false;

        if (a && !(a as any)._erreur) {
          this.rapportA = a as DamageReport;
        } else {
          this.rapportA = this._rapportErreur('A', (a as any)?._erreur);
        }

        if (b && !(b as any)._erreur) {
          this.rapportB = b as DamageReport;
        } else {
          this.rapportB = this._rapportErreur('B', (b as any)?._erreur);
        }
      },
      error: (err) => {
        this.chargementDommages = false;
        this.erreurDommages = err?.message ?? 'Analyse indisponible, réessayez.';
      },
    });
  }

  /** Rapport d'erreur explicite — aucun texte générique en dur. */
  private _rapportErreur(vehicule: 'A' | 'B', message?: string): DamageReport {
    return {
      vehicule,
      source: 'vlm_local_fallback',
      dommages: [],
      evaluation_severite: { score_indicatif: 0, niveau: 'indéterminé' },
      description: message ?? 'Analyse indisponible, réessayez.',
    };
  }

  suivant(): void {
    if (!this.resultat) return;
    this.dossierService.setPendingValidation(this.resultat);
    this.navigationService.setSection('regles-parametres');
  }

  choisirDecision(decision: DossierHistorique['decision']): void {
    if (!this.resultat) return;
    const nouveau: DossierHistorique = {
      numeroSinistre: `MANUAL/${Date.now()}`,
      dateAccident: new Date().toLocaleDateString('fr-FR'),
      casIA: this.resultat.casPropose || 0,
      confiance: this.resultat.niveauConfiance || 0,
      decision,
      responsabiliteA: this.resultat.responsabiliteA || 0,
      responsabiliteB: this.resultat.responsabiliteB || 0,
      statut: decision === 'Accepté' ? 'Clôturé' : 'En attente',
    };
    this.dossierService.ajouterDossier(nouveau);
    this.dossierService.setPendingValidation(this.resultat);
    this.navigationService.setSection('regles-parametres');
  }
}
