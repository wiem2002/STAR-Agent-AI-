export type TypeIntersectionCroquis = 'carrefour' | 'T' | 'ligne-droite' | 'rond-point';

export type OrientationRueCroquis = 'horizontale' | 'verticale';

export interface PositionCroquis {
  x: number;
  y: number;
}

export interface VehiculeCroquis {
  id: 'A' | 'B';
  x: number;
  y: number;
  angle: number;
}

export interface RueCroquis {
  nom: string;
  orientation: OrientationRueCroquis;
}

export interface CroquisAnalyse {
  numeroSinistre: string;
  typeIntersection: TypeIntersectionCroquis;
  rues: RueCroquis[];
  panneauStop: boolean;
  panneauStopPosition: PositionCroquis | null;
  vehicules: VehiculeCroquis[];
  confiance: number;
  imageBase64?: string;
}

export interface CorrectionCroquis {
  numeroSinistre: string;
  vehiculeId: 'A' | 'B';
  xCorrige: number;
  yCorrige: number;
  angleCorrige: number;
}