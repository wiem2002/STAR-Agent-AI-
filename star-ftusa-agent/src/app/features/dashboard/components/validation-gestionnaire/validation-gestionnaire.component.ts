import { Component, OnInit } from '@angular/core';
import { DossierService } from '../../../../core/services/dossier.service';
import { NavigationService } from '../../../../core/services/navigation.service';
import { ResultatAnalyseIA } from '../../../../core/models/analyse-ia.model';
import { DossierHistorique } from '../../../../core/models/dossier.model';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';

type Decision = 'accepter' | 'modifier' | 'autre-cas';

@Component({
  selector: 'app-validation-gestionnaire',
  standalone: true,
  imports: [CommonModule, FormsModule, PanelCardComponent],
  templateUrl: './validation-gestionnaire.component.html',
  styleUrl: './validation-gestionnaire.component.scss',
})
export class ValidationGestionnaireComponent {
  casPropose = 0;
  confianceIA = 0;
  private currentResultat: ResultatAnalyseIA | null = null;

  decision: Decision = 'accepter';
  responsabiliteA = 100;
  responsabiliteB = 0;
  commentaire = '';

  get commentaireLongueur(): number {
    return this.commentaire.length;
  }
  constructor(
    private readonly dossierService: DossierService,
    public readonly navigationService: NavigationService
  ) {}

  ngOnInit(): void {
    this.dossierService.getPendingValidation().subscribe((r) => {
      this.currentResultat = r;
      if (r) {
        this.casPropose = r.casPropose || 0;
        this.confianceIA = r.niveauConfiance || 0;
        this.responsabiliteA = r.responsabiliteA || 0;
        this.responsabiliteB = r.responsabiliteB || 0;
      }
    });
  }

  validerEtCloturer(): void {
    // Simule la validation : ajoute au historique et retourne au formulaire
    if (!this.currentResultat) return;
    const dossier: DossierHistorique = {
      numeroSinistre: `VALID/${Date.now()}`,
      dateAccident: new Date().toLocaleDateString('fr-FR'),
      casIA: this.casPropose,
      confiance: this.confianceIA,
      decision: this.decision === 'accepter' ? 'Accepté' : this.decision === 'modifier' ? 'Modifié' : 'Refusé',
      responsabiliteA: this.responsabiliteA,
      responsabiliteB: this.responsabiliteB,
      statut: 'Clôturé',
    };
    this.dossierService.ajouterDossier(dossier);
    // Clear pending and go back to new dossier
    this.dossierService.setPendingValidation(null);
    this.navigationService.setSection('nouveau-dossier');
  }
}
