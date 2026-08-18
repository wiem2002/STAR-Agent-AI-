import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-topbar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './topbar.component.html',
  styleUrl: './topbar.component.scss',
})
export class TopbarComponent {
  @Output() toggleMenu = new EventEmitter<void>();

  notifications = 12;
  utilisateur = 'Nadia Ben Amor';
  role = 'Gestionnaire sinistres';
}
