import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { NavigationService } from '../../../../core/services/navigation.service';
import { DossierCourantService } from '../../../../core/services/dossier-courant.service';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

type Onglet = 'pieces' | 'analyse';

interface PieceJointeSelectionnee {
  nom: string;
  type: string;
  taille: string;
  fichier: File;
}

@Component({
  selector: 'app-nouveau-dossier',
  standalone: true,
  imports: [CommonModule, FormsModule, PanelCardComponent],
  templateUrl: './nouveau-dossier.component.html',
  styleUrl: './nouveau-dossier.component.scss',
})
export class NouveauDossierComponent {
  ongletActif: Onglet = 'pieces';
  piecesJointes: PieceJointeSelectionnee[] = [];
  erreur: string | null = null;

  private readonly formatsAutorisés = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp'];
  // Preview URL for the uploaded PDF (sanitized for binding)
  previewUrl: SafeResourceUrl | null = null;
  private rawPreviewUrl: string | null = null;

  constructor(
    private readonly navigationService: NavigationService,
    private readonly dossierCourantService: DossierCourantService
    , private readonly sanitizer: DomSanitizer
  ) {}

  choisirOnglet(onglet: Onglet): void {
    this.ongletActif = onglet;
  }

  lancerAnalyse(): void {
    const constat = this.piecesJointes.find((p) => p.type === 'application/pdf');

    if (!constat) {
      this.erreur = "Ajoute le constat au format PDF avant de lancer l'analyse.";
      this.choisirOnglet('pieces');
      return;
    }

    const photos = this.piecesJointes
      .filter((p) => p.type !== 'application/pdf')
      .map((p) => p.fichier);

    this.dossierCourantService.definirConstat(constat.fichier);
    this.dossierCourantService.definirPhotos(photos);

    this.navigationService.setSection('analyse-ia');
  }

  ouvrirSelecteurFichiers(input: HTMLInputElement): void {
    input.click();
  }

  gererFichiers(event: Event): void {
    const input = event.target as HTMLInputElement;
    const fichiers = Array.from(input.files ?? []);
    this.ajouterFichiers(fichiers);
    input.value = '';
  }

  deposerFichiers(event: DragEvent): void {
    event.preventDefault();
    this.ajouterFichiers(Array.from(event.dataTransfer?.files ?? []));
  }

  autoriserDepose(event: DragEvent): void {
    event.preventDefault();
  }

  retirerPiece(piece: PieceJointeSelectionnee): void {
    this.piecesJointes = this.piecesJointes.filter((p) => p !== piece);
    // If we removed the file used for preview, revoke and clear preview
    if (piece.type === 'application/pdf' && this.rawPreviewUrl) {
      try {
        URL.revokeObjectURL(this.rawPreviewUrl);
      } catch (e) {}
      this.rawPreviewUrl = null;
      this.previewUrl = null;
    }
  }

  private ajouterFichiers(fichiers: File[]): void {
    this.erreur = null;

    const nouveauxFichiers = fichiers
      .filter((fichier) => this.formatsAutorisés.includes(fichier.type))
      .map((fichier) => ({
        nom: fichier.name,
        type: fichier.type || 'fichier',
        taille: this.formaterTaille(fichier.size),
        fichier,
      }));

    this.piecesJointes = [...this.piecesJointes, ...nouveauxFichiers];

    // If we have a PDF and no preview yet, create a preview URL
    if (!this.previewUrl) {
      const pdf = this.piecesJointes.find((p) => p.type === 'application/pdf');
      if (pdf) {
        try {
          this.rawPreviewUrl = URL.createObjectURL(pdf.fichier);
          this.previewUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.rawPreviewUrl);
        } catch (e) {
          this.previewUrl = null;
          this.rawPreviewUrl = null;
        }
      }
    }
  }

  ngOnDestroy(): void {
    if (this.rawPreviewUrl) {
      try {
        URL.revokeObjectURL(this.rawPreviewUrl);
      } catch (e) {}
      this.rawPreviewUrl = null;
      this.previewUrl = null;
    }
  }

  private formaterTaille(tailleEnOctets: number): string {
    if (tailleEnOctets < 1024) {
      return `${tailleEnOctets} o`;
    }

    const kiloOctets = tailleEnOctets / 1024;
    if (kiloOctets < 1024) {
      return `${kiloOctets.toFixed(1)} Ko`;
    }

    return `${(kiloOctets / 1024).toFixed(1)} Mo`;
  }
}
