import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

export type DashboardSection =
  | 'tableau-de-bord'
  | 'nouveau-dossier'
  | 'analyse-ia'
  | 'cas-ftusa'
  | 'referentiel-ftusa'
  | 'regles-parametres'
  | 'statistiques'
  | 'historique'
  | 'administration';

export interface NavItem {
  icone: string;
  libelle: string;
  section: DashboardSection;
  actif?: boolean;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent {
  @Input() ouverte = true;
  @Output() fermer = new EventEmitter<void>();
  @Output() sectionChange = new EventEmitter<DashboardSection>();

  itemActif: DashboardSection = 'tableau-de-bord';

  navItems: NavItem[] = [
    { icone: '🏠', libelle: 'Tableau de bord', section: 'tableau-de-bord' },
    { icone: '📄', libelle: 'Nouveau dossier', section: 'nouveau-dossier' },
    { icone: '🤖', libelle: 'Analyse IA', section: 'analyse-ia' },
    { icone: '📚', libelle: 'Référentiel FTUSA', section: 'referentiel-ftusa' },
    { icone: '⚙️', libelle: 'Règles & Paramètres', section: 'regles-parametres' },
    { icone: '📊', libelle: 'Statistiques', section: 'statistiques' },
    { icone: '🕘', libelle: 'Historique', section: 'historique' },
    { icone: '🛠️', libelle: 'Administration', section: 'administration' },
  ];

  choisir(item: NavItem): void {
    this.itemActif = item.section;
    this.sectionChange.emit(item.section);
    this.fermer.emit();
  }
}
