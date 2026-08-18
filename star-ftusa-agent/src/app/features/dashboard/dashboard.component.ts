import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TableauDeBordComponent } from './components/tableau-de-bord/tableau-de-bord.component';
import { NouveauDossierComponent } from './components/nouveau-dossier/nouveau-dossier.component';
import { AnalyseIaCoursComponent } from './components/analyse-ia-cours/analyse-ia-cours.component';
import { ResultatAnalyseComponent } from './components/resultat-analyse/resultat-analyse.component';
import { DetailsTechniquesComponent } from './components/details-techniques/details-techniques.component';
import { ValidationGestionnaireComponent } from './components/validation-gestionnaire/validation-gestionnaire.component';
import { HistoriqueDossiersComponent } from './components/historique-dossiers/historique-dossiers.component';
import { StatistiquesFtusaComponent } from './components/statistiques-ftusa/statistiques-ftusa.component';
import { InterfaceMobileComponent } from './components/interface-mobile/interface-mobile.component';
import { NavigationService } from '../../core/services/navigation.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    TableauDeBordComponent,
    NouveauDossierComponent,
    AnalyseIaCoursComponent,
    ResultatAnalyseComponent,
    DetailsTechniquesComponent,
    ValidationGestionnaireComponent,
    HistoriqueDossiersComponent,
    StatistiquesFtusaComponent,
    InterfaceMobileComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  readonly sectionActive$;

  constructor(private readonly navigationService: NavigationService) {
    this.sectionActive$ = this.navigationService.sectionActive$;
  }
}
