import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { StatistiqueService } from '../../../../core/services/statistique.service';
import { PointEvolutionPrecision, RepartitionCasFtusa } from '../../../../core/models/analyse-ia.model';

@Component({
  selector: 'app-statistiques-ftusa',
  standalone: true,
  imports: [CommonModule, PanelCardComponent],
  templateUrl: './statistiques-ftusa.component.html',
  styleUrl: './statistiques-ftusa.component.scss',
})
export class StatistiquesFtusaComponent implements OnInit {
  repartitionCas: RepartitionCasFtusa[] = [];
  evolution: PointEvolutionPrecision[] = [];
  totalDossiers = 0;
  tauxAcceptation = 0;
  tempsMoyen = '';

  constructor(private readonly statistiqueService: StatistiqueService) {}

  ngOnInit(): void {
    this.statistiqueService.getRepartitionCasFtusa().subscribe((r) => (this.repartitionCas = r));
    this.statistiqueService.getEvolutionPrecision().subscribe((e) => (this.evolution = e));
    this.statistiqueService.getTotalDossiersMois().subscribe((t) => (this.totalDossiers = t));
    this.statistiqueService.getTauxAcceptation().subscribe((t) => (this.tauxAcceptation = t));
    this.statistiqueService.getTempsMoyenTraitement().subscribe((t) => (this.tempsMoyen = t));
  }

  get donutGradient(): string {
    let acc = 0;
    const stops = this.repartitionCas.map((r) => {
      const start = acc;
      acc += r.pourcentage;
      return `${r.couleur} ${start}% ${acc}%`;
    });
    return `conic-gradient(${stops.join(', ')})`;
  }

  get maxEvolution(): number {
    return Math.max(...this.evolution.map((p) => p.valeur), 1);
  }

  /** SVG polyline points for the precision evolution line chart. */
  get lignePoints(): string {
    if (!this.evolution.length) return '';
    const w = 260;
    const h = 90;
    const step = w / (this.evolution.length - 1 || 1);
    return this.evolution
      .map((p, i) => {
        const x = i * step;
        const y = h - (p.valeur / this.maxEvolution) * h;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }
}
