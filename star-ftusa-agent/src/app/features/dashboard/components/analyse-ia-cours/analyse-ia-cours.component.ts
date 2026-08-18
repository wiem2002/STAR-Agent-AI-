import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { AnalyseIaService } from '../../../../core/services/analyse-ia.service';
import { DossierCourantService } from '../../../../core/services/dossier-courant.service';
import { DossierService } from '../../../../core/services/dossier.service';
import { DossierHistorique } from '../../../../core/models/dossier.model';
import { EtapeAnalyse } from '../../../../core/models/analyse-ia.model';
import { ResultatAnalyseComponent } from '../resultat-analyse/resultat-analyse.component';
import { Subscription, interval } from 'rxjs';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-analyse-ia-cours',
  standalone: true,
  imports: [CommonModule, PanelCardComponent, ResultatAnalyseComponent],
  templateUrl: './analyse-ia-cours.component.html',
  styleUrl: './analyse-ia-cours.component.scss',
})
export class AnalyseIaCoursComponent implements OnInit, OnDestroy {
  etapes: EtapeAnalyse[] = [];
  progression = 0;
  analyseTerminee = false;
  erreur: string | null = null;

  photos = [1, 2, 3, 4];
  private progressionSubscription?: Subscription;
  private appelEnCoursSubscription?: Subscription;
  private constatSubscription?: Subscription;
  private resultatSubscription?: Subscription;

  previewUrl: SafeResourceUrl | null = null;
  private rawPreviewUrl: string | null = null;

  // Sketch flags derived from the analysis justification / éléments clés
  sketchShowA = false;
  sketchShowB = false;
  sketchShowStop = false;

  constructor(
    private readonly analyseIaService: AnalyseIaService,
    private readonly dossierCourantService: DossierCourantService
    , private readonly sanitizer: DomSanitizer
    , private readonly dossierService: DossierService
  ) {}

  ngOnInit(): void {
    this.analyseIaService.getEtapesAnalyse().subscribe((e) => {
      this.etapes = e;
      this.demarrerAnalyseReelle();
    });

    // Subscribe to the uploaded constat to show preview in this view
    this.constatSubscription = this.dossierCourantService.constat$.subscribe((f) => {
      // revoke previous
      if (this.rawPreviewUrl) {
        try {
          URL.revokeObjectURL(this.rawPreviewUrl);
        } catch (e) {}
        this.rawPreviewUrl = null;
        this.previewUrl = null;
      }

      if (f) {
        try {
          this.rawPreviewUrl = URL.createObjectURL(f);
          this.previewUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.rawPreviewUrl);
        } catch (e) {
          this.previewUrl = null;
          this.rawPreviewUrl = null;
        }
      }
    });

    // Subscribe to the analysis result to update the croquis markers
    this.resultatSubscription = this.analyseIaService.getResultatAnalyse().subscribe((r) => {
      // Reset
      this.sketchShowA = false;
      this.sketchShowB = false;
      this.sketchShowStop = false;

      // Use elementsClesUtilises and justification to decide what to show
      const elems = r.elementsClesUtilises || [];
      // Simple heuristics: if any element starts with 'A:' show A, 'B:' show B
      if (elems.some((s) => s.startsWith('A:'))) this.sketchShowA = true;
      if (elems.some((s) => s.startsWith('B:'))) this.sketchShowB = true;
      // If justification mentions 'STOP' or 'stop', show stop sign
      if ((r.justification || '').toLowerCase().includes('stop')) this.sketchShowStop = true;
    });
  }

  ngOnDestroy(): void {
    this.progressionSubscription?.unsubscribe();
    this.appelEnCoursSubscription?.unsubscribe();
    this.constatSubscription?.unsubscribe();
    this.resultatSubscription?.unsubscribe();
    if (this.rawPreviewUrl) {
      try {
        URL.revokeObjectURL(this.rawPreviewUrl);
      } catch (e) {}
      this.rawPreviewUrl = null;
      this.previewUrl = null;
    }
  }

  annulerAnalyse(): void {
    this.progressionSubscription?.unsubscribe();
    this.appelEnCoursSubscription?.unsubscribe();
  }

  private demarrerAnalyseReelle(): void {
    this.analyseTerminee = false;
    this.erreur = null;
    this.progression = 0;

    const constat = this.dossierCourantService.constatActuel;

    if (!constat) {
      this.erreur = "Aucun constat trouvé. Retourne à l'étape précédente et ajoute un fichier PDF.";
      return;
    }

    // Anime les étapes visuellement pendant que l'appel réel tourne en
    // arrière-plan (le backend ne renvoie pas de progression granulaire,
    // donc on avance étape par étape jusqu'à ~90%, puis on saute à 100%
    // seulement quand la vraie réponse de l'API arrive).
    this.progressionSubscription = interval(600).subscribe(() => {
      if (this.progression < 90) {
        this.progression += 5;
        this.mettreAJourEtapeCourante();
      }
    });

    this.appelEnCoursSubscription = this.analyseIaService
      .analyserConstat(constat)
      .subscribe({
        next: (result) => {
          this.terminerAnalyse();
          // Add to history (mock) after analysis completes
          const dateAccident = new Date().toLocaleDateString('fr-FR');
          const nouveau: DossierHistorique = {
            numeroSinistre: `AUTO/${Date.now()}`,
            dateAccident,
            casIA: result.casPropose || 0,
            confiance: result.niveauConfiance || 0,
            decision: result.niveauConfiance > 80 ? 'Accepté' : 'À valider',
            responsabiliteA: result.responsabiliteA || 0,
            responsabiliteB: result.responsabiliteB || 0,
            statut: result.niveauConfiance > 80 ? 'Clôturé' : 'En attente',
          };
          this.dossierService.ajouterDossier(nouveau);
        },
        error: (err) => {
          this.progressionSubscription?.unsubscribe();
          this.erreur =
            "Erreur lors de l'analyse du constat. Vérifie que le service d'analyse est démarré, puis réessaie.";
          console.error(err);
        },
      });
  }

  private mettreAJourEtapeCourante(): void {
    const indexEnCours = Math.min(
      Math.floor((this.progression / 100) * this.etapes.length),
      this.etapes.length - 1
    );

    this.etapes = this.etapes.map((etape, index) => {
      if (index < indexEnCours) {
        return { ...etape, statut: 'termine' };
      }
      if (index === indexEnCours) {
        return { ...etape, statut: 'en-cours' };
      }
      return { ...etape, statut: 'attente' };
    });
  }

  private terminerAnalyse(): void {
    this.progressionSubscription?.unsubscribe();
    this.progression = 100;
    this.etapes = this.etapes.map((etape) => ({ ...etape, statut: 'termine' }));
    this.analyseTerminee = true;
  }
}
