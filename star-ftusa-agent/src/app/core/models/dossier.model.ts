export type StatutDossier = 'Accepté' | 'Modifié' | 'Refusé' | 'À valider' | 'En attente' | 'Clôturé';

export interface Vehicule {
  immatriculation: string;
  marque: string;
  modele: string;
  assure: string;
}

export interface NouveauDossier {
  numeroSinistre: string;
  dateAccident: string;
  agence: string;
  declarant: string;
  email: string;
  telephone: string;
  vehiculeA: Vehicule;
  vehiculeB: Vehicule;
}

export interface DossierHistorique {
  numeroSinistre: string;
  dateAccident: string;
  casIA: number;
  confiance: number;
  decision: StatutDossier;
  responsabiliteA: number;
  responsabiliteB: number;
  statut: 'Clôturé' | 'En attente';
}

export interface KpiTableauBord {
  dossiersTotaux: number;
  dossiersTotauxVariation: string;
  enAttenteAnalyse: number;
  enAttenteVariation: string;
  iaEnCours: number;
  iaEnCoursVariation: string;
  aValiderFaibleConfiance: number;
  aValiderVariation: string;
  tempsMoyenTraitement: string;
  tempsMoyenVariation: string;
  tauxPrecisionIA: number;
  tauxPrecisionVariation: string;
  dossiersTraitesCeMois: number;
  dossiersTraitesVariation: string;
  dossiersClosCeMois: number;
  dossiersClosVariation: string;
}

export interface RepartitionResultat {
  label: string;
  valeurPct: number;
  couleur: string;
}

export interface TopCasFtusa {
  cas: string;
  nombre: number;
}
