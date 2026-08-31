import { Component } from '@angular/core';
import { CommonModule, AsyncPipe } from '@angular/common';
import { Observable, combineLatest, map } from 'rxjs';
import { DossierService } from '../../../../core/services/dossier.service';
import { KpiTableauBord, RepartitionResultat, TopCasFtusa } from '../../../../core/models/dossier.model';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';

interface DashboardData {
  kpi: KpiTableauBord;
  repartition: RepartitionResultat[];
  topCas: TopCasFtusa[];
}

@Component({
  selector: 'app-tableau-de-bord',
  standalone: true,
  imports: [CommonModule, AsyncPipe, PanelCardComponent],
  templateUrl: './tableau-de-bord.component.html',
  styleUrl: './tableau-de-bord.component.scss',
})
export class TableauDeBordComponent {
  readonly data$: Observable<DashboardData>;

  constructor(private readonly dossierService: DossierService) {
    this.data$ = combineLatest({
      kpi:        this.dossierService.getKpiTableauBord(),
      repartition: this.dossierService.getRepartitionResultats(),
      topCas:     this.dossierService.getTopCasFtusa(),
    });
  }

  maxTopCas(topCas: TopCasFtusa[]): number {
    return Math.max(...topCas.map(c => c.nombre), 1);
  }

  donutGradient(repartition: RepartitionResultat[]): string {
    let acc = 0;
    const stops = repartition.map(r => {
      const start = acc;
      acc += r.valeurPct;
      return `${r.couleur} ${start}% ${acc}%`;
    });
    return `conic-gradient(${stops.join(', ')})`;
  }
}
