import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

/**
 * Conserve le fichier du constat sélectionné dans "Nouveau dossier" le temps
 * de naviguer vers l'écran "Analyse IA en cours" (la navigation entre
 * sections se fait sans routing/paramètres, cf. NavigationService).
 */
@Injectable({ providedIn: 'root' })
export class DossierCourantService {
  private readonly constatSubject = new BehaviorSubject<File | null>(null);
  readonly constat$ = this.constatSubject.asObservable();

  private readonly photosSubject = new BehaviorSubject<File[]>([]);
  readonly photos$ = this.photosSubject.asObservable();

  definirConstat(fichier: File): void {
    this.constatSubject.next(fichier);
  }

  definirPhotos(fichiers: File[]): void {
    this.photosSubject.next(fichiers);
  }

  get constatActuel(): File | null {
    return this.constatSubject.value;
  }

  get photosActuelles(): File[] {
    return this.photosSubject.value;
  }

  reinitialiser(): void {
    this.constatSubject.next(null);
    this.photosSubject.next([]);
  }
}
