import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-panel-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './panel-card.component.html',
  styleUrl: './panel-card.component.scss',
})
export class PanelCardComponent {
  @Input({ required: true }) numero!: number;
  @Input({ required: true }) titre!: string;
  @Input() spanClass = '';
}
