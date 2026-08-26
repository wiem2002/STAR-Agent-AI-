import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { FileDropZoneComponent } from '../../../../shared/components/file-drop-zone/file-drop-zone.component';
import { NavigationService } from '../../../../core/services/navigation.service';
import { DossierCourantService } from '../../../../core/services/dossier-courant.service';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

type Onglet = 'pieces' | 'analyse';

@Component({
  selector: 'app-nouveau-dossier',
  standalone: true,
  imports: [CommonModule, PanelCardComponent, FileDropZoneComponent],
  templateUrl: './nouveau-dossier.component.html',
  styleUrl: './nouveau-dossier.component.scss',
})
export class NouveauDossierComponent {
  ongletActif: Onglet = 'pieces';
  erreur: string | null = null;

  constat: File | null = null;
  photosA: File[] = [];
  photosB: File[] = [];

  previewUrl: SafeResourceUrl | null = null;
  private rawPreviewUrl: string | null = null;

  constructor(
    private readonly navigationService: NavigationService,
    private readonly dossierCourantService: DossierCourantService,
    private readonly sanitizer: DomSanitizer,
  ) {}

  get peutContinuer(): boolean {
    return !!this.constat && this.photosA.length > 0 && this.photosB.length > 0;
  }

  onConstatChange(fichiers: File[]): void {
    this.constat = fichiers[0] ?? null;
    this._refreshPreview();
  }

  onPhotosAChange(fichiers: File[]): void {
    this.photosA = fichiers;
  }

  onPhotosBChange(fichiers: File[]): void {
    this.photosB = fichiers;
  }

  choisirOnglet(onglet: Onglet): void {
    this.ongletActif = onglet;
  }

  suivant(): void {
    this.erreur = null;
    if (!this.constat) {
      this.erreur = 'Ajoutez le constat amiable (PDF ou image) avant de continuer.';
      return;
    }
    if (!this.photosA.length) {
      this.erreur = 'Ajoutez au moins une photo du véhicule A.';
      return;
    }
    if (!this.photosB.length) {
      this.erreur = 'Ajoutez au moins une photo du véhicule B.';
      return;
    }
    this.ongletActif = 'analyse';
  }

  lancerAnalyse(): void {
    if (!this.constat) return;
    this.dossierCourantService.definirConstat(this.constat);
    this.dossierCourantService.definirPhotosA(this.photosA);
    this.dossierCourantService.definirPhotosB(this.photosB);
    this.navigationService.setSection('analyse-ia');
  }

  ngOnDestroy(): void {
    this._revokePreview();
  }

  private _refreshPreview(): void {
    this._revokePreview();
    if (this.constat) {
      try {
        this.rawPreviewUrl = URL.createObjectURL(this.constat);
        this.previewUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.rawPreviewUrl);
      } catch {
        this.previewUrl = null;
      }
    }
  }

  private _revokePreview(): void {
    if (this.rawPreviewUrl) {
      try { URL.revokeObjectURL(this.rawPreviewUrl); } catch { /* noop */ }
      this.rawPreviewUrl = null;
      this.previewUrl = null;
    }
  }
}
