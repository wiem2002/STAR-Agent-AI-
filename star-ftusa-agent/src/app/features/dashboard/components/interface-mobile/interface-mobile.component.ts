import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PanelCardComponent } from '../../../../shared/components/panel-card/panel-card.component';
import { MobileNavComponent } from '../../../../shared/components/mobile-nav/mobile-nav.component';

@Component({
  selector: 'app-interface-mobile',
  standalone: true,
  imports: [CommonModule, PanelCardComponent, MobileNavComponent],
  templateUrl: './interface-mobile.component.html',
  styleUrl: './interface-mobile.component.scss',
})
export class InterfaceMobileComponent {}
