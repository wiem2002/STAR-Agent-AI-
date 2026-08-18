"""Moteur de décision FTUSA -- déterministe, sans LLM à l'exécution."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResultatMatching:
    cas_id: str
    titre: str
    famille: str
    responsabilite: dict
    confiance: float
    conditions_matchees: dict
    notes: list = field(default_factory=list)
    a_valider: bool = False


class MoteurFTUSA:
    SEUIL_CONFIANCE_AUTO = 0.85

    def __init__(self, chemin_bareme):
        with open(chemin_bareme, encoding="utf-8") as f:
            self.bareme = json.load(f)
        self.cas = self.bareme["cas"]
        self.collisions_multi = self.bareme["collisions_multi_vehicules"]

    def determiner_cas(self, faits):
        if faits.get("nombre_vehicules") == ">=3" or faits.get("nombre_vehicules", 2) >= 3:
            return self._determiner_collision_multi(faits)

        candidats = []
        for cas in self.cas:
            for exception in cas.get("exceptions", []):
                if self._match(faits, exception["conditions"]):
                    candidats.append(ResultatMatching(
                        cas_id=exception["id"], titre=exception["titre"], famille=cas["famille"],
                        responsabilite=exception["responsabilite"], confiance=1.0,
                        conditions_matchees=exception["conditions"], notes=exception.get("notes", []),
                    ))
            jeux_conditions = cas.get("conditions_alt") or [cas.get("conditions", {})]
            for jeu in jeux_conditions:
                if jeu and self._match(faits, jeu):
                    candidats.append(ResultatMatching(
                        cas_id=cas["id"], titre=cas["titre"], famille=cas["famille"],
                        responsabilite=cas["responsabilite"], confiance=1.0,
                        conditions_matchees=jeu, notes=cas.get("notes", []),
                    ))

        if candidats:
            meilleur = max(candidats, key=lambda c: len(c.conditions_matchees))
            meilleur.a_valider = len(candidats) > 1 and self._ambigu(candidats)
            return meilleur

        return self._meilleur_match_partiel(faits)

    @staticmethod
    def _match(faits, conditions):
        for cle, valeur_attendue in conditions.items():
            valeur_faits = faits.get(cle)
            if isinstance(valeur_attendue, list):
                if not isinstance(valeur_faits, list):
                    return False
                if not all(a in valeur_faits for a in valeur_attendue):
                    return False
            else:
                if valeur_faits != valeur_attendue:
                    return False
        return True

    @staticmethod
    def _score_partiel(faits, conditions):
        if not conditions:
            return 0.0
        matches = 0
        for cle, valeur_attendue in conditions.items():
            valeur_faits = faits.get(cle)
            if isinstance(valeur_attendue, list):
                if isinstance(valeur_faits, list) and any(a in valeur_faits for a in valeur_attendue):
                    matches += 1
            elif valeur_faits == valeur_attendue:
                matches += 1
        return matches / len(conditions)

    def _meilleur_match_partiel(self, faits):
        meilleur_score, meilleur_cas, meilleur_jeu = 0.0, None, {}
        for cas in self.cas:
            jeux_conditions = cas.get("conditions_alt") or [cas.get("conditions", {})]
            for jeu in jeux_conditions:
                score = self._score_partiel(faits, jeu)
                if score > meilleur_score:
                    meilleur_score, meilleur_cas, meilleur_jeu = score, cas, jeu

        if meilleur_cas is None:
            return ResultatMatching(
                cas_id="hors-bareme", titre="Aucun cas du barème ne correspond aux faits extraits",
                famille="indetermine", responsabilite={"X": 0.5, "Y": 0.5}, confiance=0.0,
                conditions_matchees={},
                notes=["Cas non prévu dans le barème : à traiter selon les règles du droit commun."],
                a_valider=True,
            )

        return ResultatMatching(
            cas_id=meilleur_cas["id"], titre=meilleur_cas["titre"], famille=meilleur_cas["famille"],
            responsabilite=meilleur_cas["responsabilite"], confiance=round(meilleur_score, 2),
            conditions_matchees=meilleur_jeu, notes=meilleur_cas.get("notes", []), a_valider=True,
        )

    @staticmethod
    def _ambigu(candidats):
        max_specificite = max(len(c.conditions_matchees) for c in candidats)
        meilleurs = [c for c in candidats if len(c.conditions_matchees) == max_specificite]
        return len({c.cas_id for c in meilleurs}) > 1

    def _determiner_collision_multi(self, faits):
        type_collision = faits.get("type_collision")
        for cas in self.collisions_multi:
            if cas["id"] == type_collision:
                return ResultatMatching(
                    cas_id=cas["id"], titre=cas["titre"], famille="collision_multi_vehicules",
                    responsabilite={}, confiance=1.0 if type_collision else 0.0,
                    conditions_matchees={"type_collision": type_collision}, notes=[cas["regle"]],
                    a_valider=type_collision is None,
                )
        return ResultatMatching(
            cas_id="multi-indetermine", titre="Collision à 3+ véhicules de type indéterminé",
            famille="collision_multi_vehicules", responsabilite={}, confiance=0.0,
            conditions_matchees={},
            notes=["Le type de collision multi-véhicules n'a pas pu être déterminé automatiquement."],
            a_valider=True,
        )
