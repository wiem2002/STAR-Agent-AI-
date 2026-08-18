import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { AnalyseIaService } from '../../../../core/services/analyse-ia.service';
import { DossierService } from '../../../../core/services/dossier.service';
import { DossierHistorique } from '../../../../core/models/dossier.model';
import { NavigationService } from '../../../../core/services/navigation.service';
import { ResultatAnalyseIA } from '../../../../core/models/analyse-ia.model';

@Component({
  selector: 'app-resultat-analyse',
  standalone: true,
  imports: [CommonModule, PanelCardComponent],
  templateUrl: './resultat-analyse.component.html',
  styleUrl: './resultat-analyse.component.scss',
})
export class ResultatAnalyseComponent implements OnInit {
  resultat?: ResultatAnalyseIA;

  constructor(
    private readonly analyseIaService: AnalyseIaService,
    private readonly dossierService: DossierService
    , private readonly navigationService: NavigationService
  ) {}

  ngOnInit(): void {
    this.analyseIaService.getResultatAnalyse().subscribe((r) => (this.resultat = r));
  }

  choisirDecision(decision: DossierHistorique['decision']): void {
    if (!this.resultat) return;
    // For the mock, create a dossier historique entry and add it
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
    // Prefill validation screen and navigate there
    this.dossierService.setPendingValidation(this.resultat);
    this.navigationService.setSection('regles-parametres');
  }

  suivant(): void {
    if (!this.resultat) return;
    // set pending validation and go to the next UI step (croquis/photos)
    this.dossierService.setPendingValidation(this.resultat);
    // navigate directly to the validation interface
    this.navigationService.setSection('regles-parametres');
  }
}
