import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { DossierService } from '../../../../core/services/dossier.service';
import { DossierHistorique } from '../../../../core/models/dossier.model';

@Component({
  selector: 'app-historique-dossiers',
  standalone: true,
  imports: [CommonModule, PanelCardComponent],
  templateUrl: './historique-dossiers.component.html',
  styleUrl: './historique-dossiers.component.scss',
})
export class HistoriqueDossiersComponent implements OnInit {
  dossiers: DossierHistorique[] = [];

  constructor(private readonly dossierService: DossierService) {}

  ngOnInit(): void {
    this.dossierService.getHistorique().subscribe((d) => (this.dossiers = d));
  }

  classeStatut(decision: string): string {
    switch (decision) {
      case 'Accepté':
        return 'statut--accepte';
      case 'Modifié':
        return 'statut--modifie';
      case 'Refusé':
        return 'statut--refuse';
      default:
        return 'statut--attente';
    }
  }
}
