import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { PiecesJointesDossier } from '../models/nouveau-dossier.model';

@Injectable({ providedIn: 'root' })
export class DossierCourantService {
  private readonly constatSubject = new BehaviorSubject<File | null>(null);
  readonly constat$ = this.constatSubject.asObservable();

  private readonly numeroSinistreSubject = new BehaviorSubject<string | null>(null);
  readonly numeroSinistre$ = this.numeroSinistreSubject.asObservable();

  private readonly photosSubject = new BehaviorSubject<File[]>([]);
  readonly photos$ = this.photosSubject.asObservable();

  private readonly photosASubject = new BehaviorSubject<File[]>([]);
  readonly photosA$ = this.photosASubject.asObservable();

  private readonly photosBSubject = new BehaviorSubject<File[]>([]);
  readonly photosB$ = this.photosBSubject.asObservable();

  definirConstat(fichier: File): void {
    this.constatSubject.next(fichier);
    this.numeroSinistreSubject.next(this.genererNumeroSinistre());
  }

  definirPhotos(fichiers: File[]): void {
    this.photosSubject.next(fichiers);
  }

  definirPhotosA(fichiers: File[]): void {
    this.photosASubject.next(fichiers);
    // Merge A+B into legacy photos$ for backward compat
    this.photosSubject.next([...fichiers, ...this.photosBSubject.value]);
  }

  definirPhotosB(fichiers: File[]): void {
    this.photosBSubject.next(fichiers);
    this.photosSubject.next([...this.photosASubject.value, ...fichiers]);
  }

  get piecesJointes(): PiecesJointesDossier {
    return {
      constat: this.constatSubject.value,
      photosVehiculeA: this.photosASubject.value,
      photosVehiculeB: this.photosBSubject.value,
    };
  }

  get constatActuel(): File | null {
    return this.constatSubject.value;
  }

  get numeroSinistreActuel(): string | null {
    return this.numeroSinistreSubject.value;
  }

  get photosActuelles(): File[] {
    return this.photosSubject.value;
  }

  get photosAActuelles(): File[] {
    return this.photosASubject.value;
  }

  get photosBActuelles(): File[] {
    return this.photosBSubject.value;
  }

  reinitialiser(): void {
    this.constatSubject.next(null);
    this.numeroSinistreSubject.next(null);
    this.photosSubject.next([]);
    this.photosASubject.next([]);
    this.photosBSubject.next([]);
  }

  private genererNumeroSinistre(): string {
    const alea = Math.random().toString(36).slice(2, 8).toUpperCase();
    return `TMP-${Date.now()}-${alea}`;
  }
}
