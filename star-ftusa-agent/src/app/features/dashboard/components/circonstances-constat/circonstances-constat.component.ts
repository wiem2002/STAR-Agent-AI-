import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { AnalyseIaService } from '../../../../core/services/analyse-ia.service';
import { AutresElements, CirconstancesVehicule } from '../../../../core/models/circonstance.model';

@Component({
  selector: 'app-circonstances-constat',
  standalone: true,
  imports: [CommonModule, PanelCardComponent],
  templateUrl: './circonstances-constat.component.html',
  styleUrl: './circonstances-constat.component.scss',
})
export class CirconstancesConstatComponent implements OnInit {
  circonstancesA?: CirconstancesVehicule;
  circonstancesB?: CirconstancesVehicule;
  autresElements?: AutresElements;

  constructor(private readonly analyseIaService: AnalyseIaService) {}

  ngOnInit(): void {
    this.analyseIaService.getCirconstancesVehiculeA().subscribe((c) => (this.circonstancesA = c));
    this.analyseIaService.getCirconstancesVehiculeB().subscribe((c) => (this.circonstancesB = c));
    this.analyseIaService.getAutresElements().subscribe((a) => (this.autresElements = a));
  }
}
