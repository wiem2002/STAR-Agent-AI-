import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-file-drop-zone',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './file-drop-zone.component.html',
  styleUrl: './file-drop-zone.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FileDropZoneComponent {
  @Input() label = 'Ajouter un fichier';
  @Input() accept = 'application/pdf,image/*';
  @Input() multiple = false;
  @Input() icone = '📎';
  @Output() filesChange = new EventEmitter<File[]>();

  fichiers: File[] = [];
  survol = false;

  constructor(private readonly cdr: ChangeDetectorRef) {}

  ouvrir(input: HTMLInputElement): void {
    input.click();
  }

  onFichiers(event: Event): void {
    const input = event.target as HTMLInputElement;
    this._ajouter(Array.from(input.files ?? []));
    input.value = '';
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.survol = false;
    this._ajouter(Array.from(event.dataTransfer?.files ?? []));
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.survol = true;
  }

  onDragLeave(): void {
    this.survol = false;
  }

  retirer(index: number): void {
    this.fichiers = this.fichiers.filter((_, i) => i !== index);
    this.filesChange.emit(this.fichiers);
    this.cdr.markForCheck();
  }

  miniature(fichier: File): string | null {
    if (!fichier.type.startsWith('image/')) return null;
    return URL.createObjectURL(fichier);
  }

  formaterTaille(taille: number): string {
    if (taille < 1024) return `${taille} o`;
    const ko = taille / 1024;
    return ko < 1024 ? `${ko.toFixed(1)} Ko` : `${(ko / 1024).toFixed(1)} Mo`;
  }

  private _ajouter(nouveaux: File[]): void {
    const acceptTypes = this.accept.split(',').map(t => t.trim());
    const filtres = nouveaux.filter(f =>
      acceptTypes.some(t => t === f.type || (t.endsWith('/*') && f.type.startsWith(t.replace('/*', '/'))))
    );
    this.fichiers = this.multiple ? [...this.fichiers, ...filtres] : filtres.slice(0, 1);
    this.filesChange.emit(this.fichiers);
    this.cdr.markForCheck();
  }
}
