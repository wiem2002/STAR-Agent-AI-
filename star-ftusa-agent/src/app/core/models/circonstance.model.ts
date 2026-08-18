export interface OptionCirconstance {
  id: string;
  libelle: string;
  cochee: boolean;
}

export interface CirconstancesVehicule {
  vehicule: 'A' | 'B';
  options: OptionCirconstance[];
}

export interface AutresElements {
  signalisation: string;
  typeDeRoute: string;
  conditionsMeteo: string;
  etatChaussee: string;
  visibilite: string;
  observations: string;
}
