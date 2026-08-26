export interface DommageDetecte {
  type: string;
  confiance: number;
  pourcentage_surface_image: number;
  piece_touchee: string;
  nature: string;
}

export interface EvaluationSeverite {
  score_indicatif: number;
  niveau: string;
}

export interface DamageReport {
  vehicule: 'A' | 'B';
  source: 'modele_specialise' | 'vlm_local_fallback';
  dommages: DommageDetecte[];
  evaluation_severite: EvaluationSeverite;
  description: string;
}
