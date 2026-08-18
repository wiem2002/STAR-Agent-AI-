import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-mobile-nav',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mobile-nav.component.html',
  styleUrl: './mobile-nav.component.scss',
})
export class MobileNavComponent {
  navItems = [
    { icone: '🏠', libelle: 'Tableau de bord', actif: true },
    { icone: '📄', libelle: 'Nouveau dossier' },
    { icone: '🤖', libelle: 'Analyse IA' },
    { icone: '📚', libelle: 'Référentiel FTUSA' },
    { icone: '⚙️', libelle: 'Règles & Paramètres' },
    { icone: '📊', libelle: 'Statistiques' },
    { icone: '🕘', libelle: 'Historique' },
    { icone: '🛠️', libelle: 'Administration' },
  ];
}
