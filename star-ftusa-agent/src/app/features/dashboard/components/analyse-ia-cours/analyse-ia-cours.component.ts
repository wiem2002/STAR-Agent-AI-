import { Component, OnDestroy, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule, TitleCasePipe } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { AnalyseIaService } from '../../../../core/services/analyse-ia.service';
import { DossierCourantService } from '../../../../core/services/dossier-courant.service';
import { DossierService } from '../../../../core/services/dossier.service';
import { DossierHistorique } from '../../../../core/models/dossier.model';
import { EtapeAnalyse, ResultatAnalyseIA } from '../../../../core/models/analyse-ia.model';
import { CroquisAnalyse, VehiculeCroquis } from '../../../../core/models/croquis.model';
import { ResultatAnalyseComponent } from '../resultat-analyse/resultat-analyse.component';
import { Subscription, interval } from 'rxjs';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-analyse-ia-cours',
  standalone: true,
  imports: [CommonModule, TitleCasePipe, PanelCardComponent, ResultatAnalyseComponent],
  templateUrl: './analyse-ia-cours.component.html',
  styleUrl: './analyse-ia-cours.component.scss',
})
export class AnalyseIaCoursComponent implements OnInit, OnDestroy {
  etapes: EtapeAnalyse[] = [];
  progression = 0;
  analyseTerminee = false;
  erreur: string | null = null;

  photos = [1, 2, 3, 4];
  photoUrls: { src: string; label: string }[] = [];
  private photoObjectUrls: string[] = [];
  private progressionSubscription?: Subscription;
  private appelEnCoursSubscription?: Subscription;
  private constatSubscription?: Subscription;

  previewUrl: SafeResourceUrl | null = null;
  private rawPreviewUrl: string | null = null;

  croquisDetecte: CroquisAnalyse | null = null;

  constructor(
    private readonly analyseIaService: AnalyseIaService,
    private readonly dossierCourantService: DossierCourantService,
    private readonly sanitizer: DomSanitizer,
    private readonly dossierService: DossierService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.analyseIaService.getEtapesAnalyse().subscribe((e) => {
      this.etapes = e;
      this.demarrerAnalyseReelle();
    });

    this.constatSubscription = this.dossierCourantService.constat$.subscribe((f) => {
      if (this.rawPreviewUrl) {
        try { URL.revokeObjectURL(this.rawPreviewUrl); } catch (e) {}
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

    // Charger les vraies photos uploadées
    this._chargerPhotos();
  }

  private _chargerPhotos(): void {
    this.photoObjectUrls.forEach(u => { try { URL.revokeObjectURL(u); } catch { /* noop */ } });
    this.photoObjectUrls = [];

    const toutes: { fichier: File; label: string }[] = [
      ...this.dossierCourantService.photosAActuelles.map(f => ({ fichier: f, label: 'A' })),
      ...this.dossierCourantService.photosBActuelles.map(f => ({ fichier: f, label: 'B' })),
    ];

    this.photoUrls = toutes.map(({ fichier, label }) => {
      const src = URL.createObjectURL(fichier);
      this.photoObjectUrls.push(src);
      return { src, label };
    });

    this.photos = this.photoUrls.map((_, i) => i + 1);
    this.cdr.markForCheck();
  }

  ngOnDestroy(): void {
    this.progressionSubscription?.unsubscribe();
    this.appelEnCoursSubscription?.unsubscribe();
    this.constatSubscription?.unsubscribe();
    if (this.rawPreviewUrl) {
      try { URL.revokeObjectURL(this.rawPreviewUrl); } catch (e) {}
      this.rawPreviewUrl = null;
      this.previewUrl = null;
    }
    this.photoObjectUrls.forEach(u => { try { URL.revokeObjectURL(u); } catch { /* noop */ } });
    this.photoObjectUrls = [];
  }

  annulerAnalyse(): void {
    this.progressionSubscription?.unsubscribe();
    this.appelEnCoursSubscription?.unsubscribe();
  }

  private demarrerAnalyseReelle(): void {
    this.analyseTerminee = false;
    this.erreur = null;
    this.progression = 0;
    this.croquisDetecte = null;

    const constat = this.dossierCourantService.constatActuel;
    const numeroSinistre = this.dossierCourantService.numeroSinistreActuel;

    if (!constat) {
      this.erreur = "Aucun constat trouvé. Retourne à l'étape précédente et ajoute un fichier PDF.";
      return;
    }

    if (!numeroSinistre) {
      this.erreur = "Aucun numéro de sinistre temporaire n'est disponible pour ce dossier.";
      return;
    }

    this.progressionSubscription = interval(600).subscribe(() => {
      if (this.progression < 90) {
        this.progression += 5;
        this.mettreAJourEtapeCourante();
      }
    });

    this.appelEnCoursSubscription = this.analyseIaService
      .analyserConstat(constat, numeroSinistre)
      .subscribe({
        next: (result) => {
          this.croquisDetecte = this.construireCroquisAffichage(result, numeroSinistre);
          this.cdr.detectChanges();
          this.terminerAnalyse();

          const dateAccident = new Date().toLocaleDateString('fr-FR');
          const nouveau: DossierHistorique = {
            numeroSinistre,
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

  get croquisImageSrc(): string | null {
    const image = this.croquisDetecte?.imageBase64;
    if (!image) {
      return null;
    }
    return image.startsWith('data:') ? image : `data:image/png;base64,${image}`;
  }

  get vehiculesCroquis(): VehiculeCroquis[] {
    return this.croquisDetecte?.vehicules ?? [];
  }

  get typeIntersectionCroquis(): CroquisAnalyse['typeIntersection'] {
    return this.croquisDetecte?.typeIntersection ?? 'ligne-droite';
  }

  get panneauStopPositionStyle(): Record<string, string> | null {
    const position = this.croquisDetecte?.panneauStopPosition;
    if (!this.croquisDetecte?.panneauStop || !position) {
      return null;
    }
    return {
      left: `${position.x * 100}%`,
      top: `${position.y * 100}%`,
    };
  }

  vehiculeStyle(vehicule: VehiculeCroquis): Record<string, string> {
    return {
      left: `${vehicule.x * 100}%`,
      top: `${vehicule.y * 100}%`,
      transform: `translate(-50%, -50%) rotate(${vehicule.angle}deg)`,
    };
  }

  private construireCroquisAffichage(result: ResultatAnalyseIA, numeroSinistre: string): CroquisAnalyse {
    if (result.croquis?.vehicules?.length) {
      return {
        ...result.croquis,
        imageBase64: result.croquis.imageBase64 || result.croquisImageBase64 || undefined,
      };
    }

    const showStop = (result.justification || '').toLowerCase().includes('stop');

    return {
      numeroSinistre,
      typeIntersection: 'ligne-droite',
      rues: [],
      panneauStop: showStop,
      panneauStopPosition: showStop ? { x: 0.8, y: 0.22 } : null,
      vehicules: [
        { id: 'A', x: 0.66, y: 0.5, angle: 0 },
        { id: 'B', x: 0.34, y: 0.5, angle: 0 },
      ],
      confiance: 0.5,
      imageBase64: result.croquisImageBase64 ?? undefined,
    };
  }
}
