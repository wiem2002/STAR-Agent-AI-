import type { CroquisAnalyse } from './croquis.model';

export interface EtapeAnalyse {
  ordre: number;
  libelle: string;
  statut: 'termine' | 'en-cours' | 'attente';
}

export interface ResultatAnalyseIA {
  casPropose: number;
  titreCas: string;
  regleAppliquee: string;
  justification: string;
  responsabiliteA: number;
  responsabiliteB: number;
  niveauConfiance: number;
  elementsClesUtilises: string[];
  croquisImageBase64?: string | null;
  croquis?: CroquisAnalyse | null;
}

export interface DetailsTechniquesAnalyse {
  idAnalyse: string;
  modeleIA: string;
  dateAnalyse: string;
  dureeAnalyse: string;
  sourcesUtilisees: string[];
  reglesAppliquees: number;
  scoreSimilariteCas: number;
  nombreCasSimilaires: number;
}

export interface ReponseApiAnalyseComplete {
  circonstancesA: number[];
  circonstancesB: number[];
  casId: string;
  titre: string;
  responsabiliteA: number | null;
  responsabiliteB: number | null;
  niveauConfiance: number;
  aValider: boolean;
  justification: string;
  idAnalyse: string;
  modeleIA: string;
  dateAnalyse: string;
  dureeAnalyse: string;
  sourcesUtilisees: string[];
  reglesAppliquees: number;
  scoreSimilariteCas: number;
  nombreCasSimilaires: number;
  croquisImageBase64?: string | null;
  croquis?: CroquisAnalyse | null;
}

export interface PhotoDommage {
  vehicule: 'A' | 'B';
  url: string;
}

export interface RepartitionCasFtusa {
  cas: string;
  pourcentage: number;
  couleur: string;
}

export interface PointEvolutionPrecision {
  mois: string;
  valeur: number;
}
