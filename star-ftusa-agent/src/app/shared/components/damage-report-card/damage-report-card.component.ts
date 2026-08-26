import { Component, Input } from '@angular/core';
import { CommonModule, TitleCasePipe } from '@angular/common';
import { DamageReport } from '../../../core/models/damage-report.model';

@Component({
  selector: 'app-damage-report-card',
  standalone: true,
  imports: [CommonModule, TitleCasePipe],
  templateUrl: './damage-report-card.component.html',
  styleUrl: './damage-report-card.component.scss',
})
export class DamageReportCardComponent {
  @Input() rapport: DamageReport | null = null;
  @Input() chargement = false;
  @Input() vehicule: 'A' | 'B' = 'A';

  get niveauClass(): string {
    const n = this.rapport?.evaluation_severite?.niveau?.toLowerCase() ?? '';
    if (n.includes('léger') || n.includes('leger')) return 'badge--leger';
    if (n.includes('modéré') || n.includes('modere')) return 'badge--modere';
    if (n.includes('important') || n.includes('grave')) return 'badge--important';
    return 'badge--inconnu';
  }

  get estFallback(): boolean {
    return this.rapport?.source === 'vlm_local_fallback';
  }
}
