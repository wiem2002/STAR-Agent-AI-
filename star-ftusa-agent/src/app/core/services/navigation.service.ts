import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { DashboardSection } from '../../shared/components/sidebar/sidebar.component';

@Injectable({
  providedIn: 'root',
})
export class NavigationService {
  private readonly sectionActiveSubject = new BehaviorSubject<DashboardSection>('tableau-de-bord');

  readonly sectionActive$ = this.sectionActiveSubject.asObservable();

  setSection(section: DashboardSection): void {
    this.sectionActiveSubject.next(section);
  }
}