import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { AnalyseIaService } from '../../../../core/services/analyse-ia.service';
import { DetailsTechniquesAnalyse } from '../../../../core/models/analyse-ia.model';

@Component({
  selector: 'app-details-techniques',
  standalone: true,
  imports: [CommonModule, PanelCardComponent],
  templateUrl: './details-techniques.component.html',
  styleUrl: './details-techniques.component.scss',
})
export class DetailsTechniquesComponent implements OnInit {
  details?: DetailsTechniquesAnalyse;

  constructor(private readonly analyseIaService: AnalyseIaService) {}

  ngOnInit(): void {
    this.analyseIaService.getDetailsTechniques().subscribe((d) => (this.details = d));
  }
}
