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
}

export interface DetailsTechniquesAnalyse {
  idAnalyse: string;
  modeleIA: string;
  dateAnalyse: string;
  dureeAnalyse: string;
  sourcesUtilisees: string;
  reglesAppliquees: number;
  scoreSimilariteCas: number;
  nombreCasSimilaires: number;
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
