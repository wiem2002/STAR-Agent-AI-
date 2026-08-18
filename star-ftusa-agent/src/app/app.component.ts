import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SidebarComponent } from './shared/components/sidebar/sidebar.component';
import { TopbarComponent } from './shared/components/topbar/topbar.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { DashboardSection } from './shared/components/sidebar/sidebar.component';
import { NavigationService } from './core/services/navigation.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, SidebarComponent, TopbarComponent, DashboardComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  sidebarOuverte = false;

  constructor(private readonly navigationService: NavigationService) {}

  basculerSidebar(): void {
    this.sidebarOuverte = !this.sidebarOuverte;
  }

  fermerSidebar(): void {
    this.sidebarOuverte = false;
  }

  changerSection(section: DashboardSection): void {
    this.navigationService.setSection(section);
  }
}
