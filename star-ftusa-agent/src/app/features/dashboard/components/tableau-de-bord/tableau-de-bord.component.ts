import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DossierService } from '../../../../core/services/dossier.service';
import { KpiTableauBord, RepartitionResultat, TopCasFtusa } from '../../../../core/models/dossier.model';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';

@Component({
  selector: 'app-tableau-de-bord',
  standalone: true,
  imports: [CommonModule, PanelCardComponent],
  templateUrl: './tableau-de-bord.component.html',
  styleUrl: './tableau-de-bord.component.scss',
})
export class TableauDeBordComponent implements OnInit {
  kpi?: KpiTableauBord;
  repartition: RepartitionResultat[] = [];
  topCas: TopCasFtusa[] = [];

  constructor(private readonly dossierService: DossierService) {}

  ngOnInit(): void {
    this.dossierService.getKpiTableauBord().subscribe((k) => (this.kpi = k));
    this.dossierService.getRepartitionResultats().subscribe((r) => (this.repartition = r));
    this.dossierService.getTopCasFtusa().subscribe((t) => (this.topCas = t));
  }

  get maxTopCas(): number {
    return Math.max(...this.topCas.map((c) => c.nombre), 1);
  }

  /** Builds the conic-gradient string for the donut chart. */
  get donutGradient(): string {
    let acc = 0;
    const stops = this.repartition.map((r) => {
      const start = acc;
      acc += r.valeurPct;
      return `${r.couleur} ${start}% ${acc}%`;
    });
    return `conic-gradient(${stops.join(', ')})`;
  }
}
