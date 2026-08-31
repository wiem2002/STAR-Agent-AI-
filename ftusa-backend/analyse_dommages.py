"""
Pipeline de détection de dommages véhicule.

Niveau 1 — YOLOv11 segmentation (harpreetsahota/car-dd-segmentation-yolov11)
Niveau 2 — VLM Qwen2-VL-2B (optionnel, enrichit si GPU disponible)
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import traceback
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# ── Pondérations de sévérité ────────────────────────────────────────────────
_POIDS_SEVERITE: Dict[str, float] = {
    "dent":          2.5,
    "scratch":       1.0,
    "crack":         2.0,
    "glass shatter": 3.5,
    "lamp broken":   2.8,
    "tire flat":     3.0,
}

# ── Traduction YOLO → français ──────────────────────────────────────────────
_LABEL_FR: Dict[str, str] = {
    "dent":          "enfoncement",
    "scratch":       "rayure",
    "crack":         "fissure",
    "glass shatter": "vitre brisée",
    "lamp broken":   "optique cassée",
    "tire flat":     "pneu à plat",
}

# ── Genre et article des pièces (pour accord grammatical correct) ───────────
# Format : (article_défini, article_élision, genre)
#   article_défini   : "le" / "la" / "les"
#   article_élision  : "l'" si commence par voyelle, sinon même que article_défini
#   genre            : "m" / "f"
_GENRE_PIECES: Dict[str, Tuple[str, str, str]] = {
    "pare-chocs avant":         ("le",  "le",  "m"),
    "pare-chocs avant gauche":  ("le",  "le",  "m"),
    "pare-chocs avant droit":   ("le",  "le",  "m"),
    "pare-chocs arrière":       ("le",  "le",  "m"),
    "pare-chocs arrière gauche":("le",  "le",  "m"),
    "pare-chocs arrière droit": ("le",  "le",  "m"),
    "capot":                    ("le",  "le",  "m"),
    "coffre / hayon":           ("le",  "le",  "m"),
    "toit":                     ("le",  "le",  "m"),
    "bas de caisse":            ("le",  "le",  "m"),
    "pare-brise":               ("le",  "le",  "m"),
    "feu arrière gauche":       ("le",  "le",  "m"),
    "feu arrière droit":        ("le",  "le",  "m"),
    "phare avant gauche":       ("le",  "le",  "m"),
    "phare avant droit":        ("le",  "le",  "m"),
    "lunette arrière":          ("la",  "la",  "f"),
    "aile avant":               ("l'",  "l'",  "f"),
    "aile avant gauche":        ("l'",  "l'",  "f"),
    "aile avant droite":        ("l'",  "l'",  "f"),
    "aile arrière":             ("l'",  "l'",  "f"),
    "aile arrière gauche":      ("l'",  "l'",  "f"),
    "aile arrière droite":      ("l'",  "l'",  "f"),
    "portière":                 ("la",  "la",  "f"),
    "portière avant":           ("la",  "la",  "f"),
    "portière arrière":         ("la",  "la",  "f"),
    "vitre latérale":           ("la",  "la",  "f"),
    "carrosserie":              ("la",  "la",  "f"),
    "zone arrière du véhicule": ("la",  "la",  "f"),
    "zone avant du véhicule":   ("la",  "la",  "f"),
    "zone latérale du véhicule":("la",  "la",  "f"),
}

# Pneus — masculin
for _k in ["pneu avant gauche","pneu avant droit","pneu arrière gauche","pneu arrière droit"]:
    _GENRE_PIECES[_k] = ("le", "le", "m")


def _article(piece: str) -> str:
    """Retourne l'article défini correct pour une pièce (avec élision)."""
    info = _GENRE_PIECES.get(piece)
    if info:
        return info[1]          # article avec élision déjà inclus
    # Fallback : si commence par voyelle → l', sinon le
    return "l'" if piece and piece[0].lower() in "aeiouéèêë" else "le"


def _accorde(piece: str, adjectif_m: str, adjectif_f: str) -> str:
    """Retourne l'adjectif accordé selon le genre de la pièce."""
    info = _GENRE_PIECES.get(piece)
    genre = info[2] if info else "m"
    return adjectif_f if genre == "f" else adjectif_m


_SEUIL_SURFACE_TIRE_FLAT = 3.0

_MODEL_DOMMAGES = None
_VLM_MODEL      = None
_VLM_PROCESSOR  = None


# ── Chargement des modèles ───────────────────────────────────────────────────

def charger_modele_dommages():
    global _MODEL_DOMMAGES
    if _MODEL_DOMMAGES is not None:
        return _MODEL_DOMMAGES
    try:
        from huggingface_hub import hf_hub_download
        from ultralytics import YOLO
        weights_path = hf_hub_download(
            repo_id="harpreetsahota/car-dd-segmentation-yolov11",
            filename="best.pt",
        )
        _MODEL_DOMMAGES = YOLO(weights_path)
        print("[DOMMAGES] Modèle YOLO chargé :", weights_path)
    except Exception as e:
        print(f"[DOMMAGES] Impossible de charger YOLO : {e}")
        _MODEL_DOMMAGES = None
    return _MODEL_DOMMAGES


def _charger_vlm() -> Tuple[Any, Any]:
    global _VLM_MODEL, _VLM_PROCESSOR
    if _VLM_MODEL is not None:
        return _VLM_MODEL, _VLM_PROCESSOR
    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        model_id = "Qwen/Qwen2-VL-2B-Instruct"
        print(f"[DOMMAGES] Chargement VLM {model_id}…")
        _VLM_PROCESSOR = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        _VLM_MODEL = Qwen2VLForConditionalGeneration.from_pretrained(
            model_id, torch_dtype="auto", device_map="auto", trust_remote_code=True,
        )
        print("[DOMMAGES] VLM chargé.")
    except Exception as e:
        print(f"[DOMMAGES] VLM indisponible : {e}")
        _VLM_MODEL = None
        _VLM_PROCESSOR = None
    return _VLM_MODEL, _VLM_PROCESSOR


# ── Utilitaires image ────────────────────────────────────────────────────────

def _image_depuis_bytes(image_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Impossible de décoder l'image.")
    return img


def _pourcentage_surface(masque: np.ndarray, h: int, w: int) -> float:
    if masque is None:
        return 0.0
    return round(float(np.count_nonzero(masque)) / max(h * w, 1) * 100, 2)


# ── Détection de la vue (avant / arrière / côté) ────────────────────────────

def _detecter_vue_vehicule(img: np.ndarray) -> str:
    """
    Détecte la vue du véhicule par analyse colorimétrique :
    - Rouge saturé (feux arrière) → "arriere"
    - Zone très lumineuse basse   → "avant"
    - Défaut                      → "cote"
    """
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Feux arrière : rouge vif
    mask_r1 = cv2.inRange(hsv, np.array([0,   120, 80]),  np.array([10,  255, 255]))
    mask_r2 = cv2.inRange(hsv, np.array([165, 120, 80]),  np.array([179, 255, 255]))
    mask_rouge = cv2.bitwise_or(mask_r1, mask_r2)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_rouge = cv2.morphologyEx(mask_rouge, cv2.MORPH_OPEN, k)
    pct_rouge = np.count_nonzero(mask_rouge) / (h * w) * 100

    # Phares avant : zone très lumineuse, peu saturée, dans la moitié basse
    mask_blanc = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([179, 60, 255]))
    mask_blanc[: h // 2, :] = 0
    pct_blanc = np.count_nonzero(mask_blanc) / (h * w) * 100

    print(f"[VUE] rouge={pct_rouge:.2f}%  blanc={pct_blanc:.2f}%")

    if pct_rouge > 0.8:
        return "arriere"
    if pct_blanc > 1.5:
        return "avant"
    return "cote"


# ── Déduction de la pièce touchée ───────────────────────────────────────────

def _deduire_piece_depuis_vue(
    vue: str,
    box_xyxy: List[float],
    img_w: int,
    img_h: int,
    label: str,
    confiance_yolo: float,
) -> Tuple[str, float]:
    """
    Retourne (pièce, confiance_piece).
    confiance_piece < 0.5 → on utilisera une zone générique dans la description.

    Logique de seuils revue :
    - vue "arriere" :
        cy < 0.40          → coffre / hayon
        0.40 ≤ cy < 0.65   → aile arrière (avec côté si cx excentré)
        cy ≥ 0.65          → pare-chocs arrière
      MAIS si cx est très central (0.30-0.70) et cy ≥ 0.50 → pare-chocs arrière
      (l'enfoncement central bas = toujours le bouclier)
    - vue "avant" :
        cy < 0.40          → capot
        0.40 ≤ cy < 0.65   → aile avant (avec côté)
        cy ≥ 0.65          → pare-chocs avant
    - vue "cote" :
        cy < 0.30          → toit
        0.30 ≤ cy < 0.65   → portière avant/arrière
        cy ≥ 0.65          → bas de caisse
    """
    if len(box_xyxy) < 4:
        return "carrosserie", 0.4

    x1, y1, x2, y2 = box_xyxy[:4]
    cx = (x1 + x2) / 2 / max(img_w, 1)
    cy = (y1 + y2) / 2 / max(img_h, 1)

    # ── Cas spéciaux par type de dommage ──────────────────────────────────
    if label == "tire flat":
        cote = "droit" if cx > 0.5 else "gauche"
        face = "arrière" if vue == "arriere" else ("avant" if vue == "avant" else "arrière")
        return f"pneu {face} {cote}", 0.80

    if label == "glass shatter":
        if vue == "avant" and cy < 0.55:
            return "pare-brise", 0.85
        if vue == "arriere" and cy < 0.55:
            return "lunette arrière", 0.85
        return "vitre latérale", 0.70

    if label == "lamp broken":
        cote = "droit" if cx > 0.5 else "gauche"
        if vue == "arriere":
            return f"feu arrière {cote}", 0.85
        if vue == "avant":
            return f"phare avant {cote}", 0.85
        return "optique latérale", 0.55

    # ── Vue arrière ───────────────────────────────────────────────────────
    if vue == "arriere":
        # Zone centrale basse → pare-chocs arrière sans ambiguïté
        if cy >= 0.50 and 0.20 <= cx <= 0.80:
            return "pare-chocs arrière", 0.88
        if cy < 0.40:
            return "coffre / hayon", 0.78
        # Zone latérale haute → aile arrière
        if cx < 0.30:
            return "aile arrière gauche", 0.72
        if cx > 0.70:
            return "aile arrière droite", 0.72
        # Zone centrale intermédiaire ambiguë → fallback zone générique
        if cy < 0.65:
            return "zone arrière du véhicule", 0.45
        return "pare-chocs arrière", 0.82

    # ── Vue avant ─────────────────────────────────────────────────────────
    if vue == "avant":
        if cy >= 0.60 and 0.20 <= cx <= 0.80:
            return "pare-chocs avant", 0.88
        if cy < 0.40:
            return "capot", 0.80
        if cx < 0.30:
            return "aile avant gauche", 0.72
        if cx > 0.70:
            return "aile avant droite", 0.72
        if cy < 0.65:
            return "zone avant du véhicule", 0.45
        return "pare-chocs avant", 0.82

    # ── Vue côté ──────────────────────────────────────────────────────────
    if cy < 0.30:
        return "toit", 0.70
    if cy < 0.65:
        face_porte = "avant" if cx < 0.50 else "arrière"
        return f"portière {face_porte}", 0.72
    return "bas de caisse", 0.68


# ── Intensité cohérente avec le niveau de sévérité ──────────────────────────

def _intensite_coherente(pct: float, niveau: str) -> str:
    """
    Produit un adverbe d'intensité cohérent avec le niveau de sévérité affiché.
    Évite de dire "fortement" quand le badge affiche "Dommage Modéré".
    """
    if niveau == "dommage léger":
        return "légèrement"
    if niveau == "dommage important":
        return "très fortement" if pct > 15 else "fortement"
    # dommage modéré
    return "modérément" if pct < 8 else "significativement"


# ── Templates grammaticalement corrects ─────────────────────────────────────

def _construire_phrase(
    label: str,
    piece: str,
    confiance_piece: float,
    pct: float,
    niveau: str,
) -> str:
    """
    Construit une phrase en français grammaticalement correcte.
    Si confiance_piece < 0.5, utilise "dans la zone arrière/avant/latérale"
    au lieu de nommer la pièce directement.
    """
    art = _article(piece)
    intens = _intensite_coherente(pct, niveau)

    if pct < 4:
        etendue = "de faible étendue"
    elif pct < 10:
        etendue = "d'étendue modérée"
    else:
        etendue = "sur une zone étendue"

    # Compléments par niveau
    _complements: Dict[str, Dict[str, str]] = {
        "dommage léger": {
            "dent":          "La déformation reste superficielle et localisée.",
            "scratch":       "L'impact est superficiel, limité à la peinture.",
            "crack":         "La fissure est fine et ne semble pas affecter la structure.",
            "glass shatter": "La zone de bris est limitée, remplacement recommandé.",
            "lamp broken":   "Les dommages sont partiels, remplacement conseillé.",
            "tire flat":     "Le gonflage est insuffisant mais la jante semble intacte.",
        },
        "dommage modéré": {
            "dent":          "La déformation est visible et nécessite une remise en forme.",
            "scratch":       "La rayure atteint le métal et nécessite une réparation peinture.",
            "crack":         "La fissure est significative et peut affecter la solidité de la pièce.",
            "glass shatter": "Le bris est étendu, remplacement immédiat nécessaire.",
            "lamp broken":   "L'optique est fortement endommagée, remplacement obligatoire.",
            "tire flat":     "Le pneu est hors d'usage et la jante pourrait être impactée.",
        },
        "dommage important": {
            "dent":          "La déformation est profonde et étendue, la pièce doit être remplacée.",
            "scratch":       "Les rayures sont profondes et couvrent une grande surface.",
            "crack":         "La fissure est profonde et compromet l'intégrité structurelle.",
            "glass shatter": "Le vitrage est entièrement détruit, remplacement urgent requis.",
            "lamp broken":   "L'optique est détruite, la sécurité lumineuse est compromise.",
            "tire flat":     "Le pneu est complètement à plat et la jante présente des dommages.",
        },
    }
    complement = (
        _complements
        .get(niveau, _complements["dommage modéré"])
        .get(label, "Une expertise complémentaire est recommandée.")
    )

    # Si confiance sur la pièce trop faible → formulation générique
    if confiance_piece < 0.50:
        zone_generique = piece  # déjà une zone générique (ex: "zone arrière du véhicule")
        art = _article(zone_generique)
        if label == "dent":
            return (
                f"Un enfoncement {etendue} a été détecté dans {art} {zone_generique}. "
                f"{complement}"
            )
        if label == "scratch":
            return (
                f"Une rayure {etendue} est visible dans {art} {zone_generique}. "
                f"{complement}"
            )
        return (
            f"Dommage de type {_LABEL_FR.get(label, label)} détecté dans {art} {zone_generique}. "
            f"{complement}"
        )

    # Pièce identifiée avec confiance suffisante
    endommagee = _accorde(piece, "endommagé", "endommagée")

    if label == "dent":
        return (
            f"{art.capitalize()} {piece} est {intens} {endommagee} "
            f"par un enfoncement {etendue}. {complement}"
        )
    if label == "scratch":
        return (
            f"Une rayure {etendue} est visible sur {art} {piece}. "
            f"{complement}"
        )
    if label == "crack":
        return (
            f"Une fissure {etendue} a été détectée sur {art} {piece}. "
            f"{complement}"
        )
    if label == "glass shatter":
        return (
            f"{art.capitalize()} {piece} est brisé{'e' if _genre(piece) == 'f' else ''}, "
            f"avec une zone de bris {etendue}. {complement}"
        )
    if label == "lamp broken":
        return (
            f"{art.capitalize()} {piece} est cassé{'e' if _genre(piece) == 'f' else ''} ou fissuré{'e' if _genre(piece) == 'f' else ''}. "
            f"{complement}"
        )
    if label == "tire flat":
        return (
            f"{art.capitalize()} {piece} présente une déformation importante "
            f"compatible avec un pneu à plat. {complement}"
        )

    return (
        f"Dommage de type {_LABEL_FR.get(label, label)} détecté sur {art} {piece}. "
        f"{complement}"
    )


def _genre(piece: str) -> str:
    info = _GENRE_PIECES.get(piece)
    return info[2] if info else "m"


def _construire_description_yolo(
    detections: List[Dict[str, Any]],
    niveau: str,
) -> str:
    """Génère la description complète en français à partir des détections YOLO."""
    if not detections:
        return (
            "Aucun dommage structurel significatif détecté par le modèle de segmentation. "
            "Une inspection visuelle complémentaire est recommandée."
        )

    # Trier par sévérité × surface décroissant
    triees = sorted(
        detections,
        key=lambda d: _POIDS_SEVERITE.get(d["type"], 1.5) * d.get("pourcentage_surface_image", 0),
        reverse=True,
    )

    phrases = []
    for d in triees[:2]:  # max 2 dommages pour garder la description lisible
        phrase = _construire_phrase(
            label=d["type"],
            piece=d.get("piece_touchee", "carrosserie"),
            confiance_piece=d.get("confiance_piece", 0.6),
            pct=d.get("pourcentage_surface_image", 0.0),
            niveau=niveau,
        )
        phrases.append(phrase)

    return " ".join(phrases)


# ── Fallback CV : détection de dommages sans YOLO ───────────────────────────

def _analyser_deformation_cv(img: np.ndarray, vue: str) -> List[Dict[str, Any]]:
    """
    Détecte les zones de déformation visuelle directement sur l'image
    quand YOLO ne détecte rien. Approche :
    1. Convertit en niveaux de gris + égalisation pour normaliser luminosité
    2. Détecte les contours forts (bords de déformation, cassures de ligne)
    3. Mesure la densité de contours par zone de l'image
    4. Zones à forte densité = zones potentiellement déformées
    """
    h, w = img.shape[:2]

    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Égalisation CLAHE pour gérer les photos sombres/grises
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gris_eq = clahe.apply(gris)

    # Détection de bords — Canny avec seuils adaptés
    blur = cv2.GaussianBlur(gris_eq, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)

    # Supprimer les bords dus au cadre de l'image (5% de marge)
    marge = int(min(h, w) * 0.05)
    edges[:marge, :] = 0
    edges[-marge:, :] = 0
    edges[:, :marge] = 0
    edges[:, -marge:] = 0

    # Divise l'image en grille 3×3 et mesure la densité de bords
    grille_h, grille_w = h // 3, w // 3
    zones_chaudes: List[Tuple[float, int, int]] = []  # (densité, row, col)

    for row in range(3):
        for col in range(3):
            y1, y2 = row * grille_h, (row + 1) * grille_h
            x1, x2 = col * grille_w, (col + 1) * grille_w
            zone_edges = edges[y1:y2, x1:x2]
            densite = np.count_nonzero(zone_edges) / max(zone_edges.size, 1)
            zones_chaudes.append((densite, row, col))

    zones_chaudes.sort(reverse=True)
    if not zones_chaudes:
        return []

    densite_max = zones_chaudes[0][0]
    # Seuil adaptatif : zones au moins à 40% de la densité maximale
    seuil = max(densite_max * 0.40, 0.04)

    detections_cv: List[Dict[str, Any]] = []
    for densite, row, col in zones_chaudes[:3]:
        if densite < seuil:
            break

        # Centre de la zone en coordonnées normalisées
        cx = (col + 0.5) / 3
        cy = (row + 0.5) / 3
        box_xyxy = [
            col * grille_w, row * grille_h,
            (col + 1) * grille_w, (row + 1) * grille_h,
        ]

        pct_surface = round(densite * 100 * 0.8, 2)  # approximation surface
        piece, confiance_piece = _deduire_piece_depuis_vue(
            vue, box_xyxy, w, h, "dent", 0.30
        )

        # Niveau de sévérité basé sur la densité de bords
        if densite > 0.18:
            label_cv = "dent"
            confiance = 0.45
        elif densite > 0.10:
            label_cv = "scratch"
            confiance = 0.38
        else:
            label_cv = "dent"
            confiance = 0.30

        detections_cv.append({
            "type":                      label_cv,
            "confiance":                 confiance,
            "confiance_piece":           confiance_piece * 0.85,  # légère pénalité (CV moins fiable)
            "pourcentage_surface_image": pct_surface,
            "nature":                    _LABEL_FR.get(label_cv, label_cv),
            "piece_touchee":             piece,
            "_source_cv":                True,  # marqueur interne, pas exposé au front
        })

    return detections_cv


def _evaluer_severite_cv(detections_cv: List[Dict[str, Any]], vue: str) -> Dict[str, Any]:
    """
    Évalue la sévérité pour les détections CV.
    Plus prudent que YOLO : on sait qu'il y a de la déformation mais pas
    exactement son type → niveau modéré par défaut sauf si très forte densité.
    """
    if not detections_cv:
        return {"score_indicatif": 0.0, "niveau": "aucun dommage"}

    conf_max = max(d["confiance"] for d in detections_cv)
    pct_max  = max(d["pourcentage_surface_image"] for d in detections_cv)

    if conf_max >= 0.44 and pct_max > 10:
        return {"score_indicatif": 6.5, "niveau": "dommage important"}
    if conf_max >= 0.35 or pct_max > 5:
        return {"score_indicatif": 4.0, "niveau": "dommage modéré"}
    return {"score_indicatif": 2.0, "niveau": "dommage léger"}

def analyser_dommages_yolo(
    model,
    image_bytes: bytes,
    img: Optional[np.ndarray] = None,
    vue: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Exécute YOLO segmentation. img et vue peuvent être passés si déjà calculés."""
    if img is None:
        img = _image_depuis_bytes(image_bytes)
    h, w = img.shape[:2]

    if vue is None:
        vue = _detecter_vue_vehicule(img)
    print(f"[DOMMAGES] Vue détectée : {vue}")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
        cv2.imwrite(tmp_path, img)

    try:
        results = model.predict(tmp_path, conf=0.25, iou=0.45, verbose=False)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    detections: List[Dict[str, Any]] = []
    for r in results:
        names = model.names
        for i, box in enumerate(r.boxes):
            label = names[int(box.cls)].lower()
            confiance_yolo = float(box.conf)
            box_xyxy = box.xyxy[0].tolist()

            masque = None
            if r.masks is not None and i < len(r.masks.data):
                masque_raw = r.masks.data[i].cpu().numpy()
                masque = cv2.resize(masque_raw, (w, h)).astype(np.uint8)

            pct_surface = _pourcentage_surface(masque, h, w)
            piece, confiance_piece = _deduire_piece_depuis_vue(
                vue, box_xyxy, w, h, label, confiance_yolo
            )

            detections.append({
                "type":                      label,
                "confiance":                 round(confiance_yolo, 3),
                "confiance_piece":           round(confiance_piece, 3),
                "pourcentage_surface_image": pct_surface,
                "nature":                    _LABEL_FR.get(label, label),
                "piece_touchee":             piece,
            })

    return detections


def verifier_coherence(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        d for d in detections
        if not (d["type"] == "tire flat" and d["pourcentage_surface_image"] < _SEUIL_SURFACE_TIRE_FLAT)
    ]


def evaluer_severite(detections: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not detections:
        return {"score_indicatif": 0.0, "niveau": "aucun dommage"}

    score = sum(
        _POIDS_SEVERITE.get(d["type"], 1.5) * (d["pourcentage_surface_image"] / 10 + 1)
        for d in detections
    )
    score = round(score, 2)
    niveau = (
        "dommage léger"     if score < 3  else
        "dommage modéré"    if score < 8  else
        "dommage important"
    )
    return {"score_indicatif": score, "niveau": niveau}


# ── VLM enrichissement (optionnel) ───────────────────────────────────────────

def _image_vers_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _appeler_vlm(image_bytes: bytes, prompt: str) -> Optional[str]:
    model, processor = _charger_vlm()
    if model is None or processor is None:
        return None
    try:
        import torch
        from qwen_vl_utils import process_vision_info

        b64 = _image_vers_base64(image_bytes)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": f"data:image/jpeg;base64,{b64}"},
                {"type": "text",  "text": prompt},
            ],
        }]
        text_input = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text_input], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        ).to(model.device)
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=256)
        generated = generated[:, inputs["input_ids"].shape[1]:]
        return processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
    except Exception as e:
        print(f"[VLM] Erreur : {e}")
        return None


def _extraire_json_vlm(texte: str) -> Optional[Dict]:
    if not texte:
        return None
    match = re.search(r"\{.*\}", texte, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def enrichir_avec_vlm(
    image_bytes: bytes,
    detections: List[Dict[str, Any]],
    niveau: str,
) -> Dict[str, Any]:
    """
    Génère la description finale.
    Priorité 1 : description YOLO construite grammaticalement (toujours disponible).
    Priorité 2 : si VLM disponible, remplace par sa description qualitative.
    """
    desc_yolo = _construire_description_yolo(detections, niveau)
    piece_principale = detections[0]["piece_touchee"] if detections else "carrosserie"

    reponse_brute = _appeler_vlm(
        image_bytes,
        (
            "Tu es un expert en sinistres automobiles. "
            "Décris en 1-2 phrases précises le dommage visible sur cette photo "
            "(pièce touchée, nature, intensité). "
            "Réponds UNIQUEMENT avec ce JSON : "
            '{"zone": "<pièce en français>", "description": "<texte en français>"}'
        ),
    )
    parsed = _extraire_json_vlm(reponse_brute) if reponse_brute else None

    if parsed and parsed.get("description"):
        return {
            "piece_touchee": parsed.get("zone", piece_principale),
            "description":   parsed["description"],
            "source":        "modele_specialise",
        }

    return {
        "piece_touchee": piece_principale,
        "description":   desc_yolo,
        "source":        "modele_specialise",
    }


# ── Pipeline complet ──────────────────────────────────────────────────────────

def diagnostic_complet(model, image_bytes: bytes, vehicule: str) -> Dict[str, Any]:
    img = _image_depuis_bytes(image_bytes)
    vue = _detecter_vue_vehicule(img)

    # Niveau 1 : YOLO
    detections: List[Dict[str, Any]] = []
    source_detection = "modele_specialise"

    if model is not None:
        try:
            detections_brutes = analyser_dommages_yolo(model, image_bytes, img=img, vue=vue)
            detections = verifier_coherence(detections_brutes)
            print(f"[DOMMAGES] YOLO : {len(detections)} détection(s)")
        except Exception as e:
            print(f"[DOMMAGES] YOLO échoué : {e}")
            traceback.print_exc()
            detections = []

    # Niveau 2 : fallback CV si YOLO ne détecte rien
    if not detections:
        print("[DOMMAGES] YOLO sans résultat → fallback CV")
        detections_cv = _analyser_deformation_cv(img, vue)
        if detections_cv:
            detections = detections_cv
            source_detection = "vlm_local_fallback"
            evaluation = _evaluer_severite_cv(detections_cv, vue)
            print(f"[DOMMAGES] CV fallback : {len(detections)} zone(s), niveau={evaluation['niveau']}")
        else:
            evaluation = {"score_indicatif": 0.0, "niveau": "aucun dommage"}
    else:
        evaluation = evaluer_severite(detections)

    enrichissement = enrichir_avec_vlm(image_bytes, detections, evaluation["niveau"])

    return {
        "vehicule":            vehicule,
        "source":              enrichissement.get("source", source_detection),
        "dommages":            [{k: v for k, v in d.items() if k != "_source_cv"} for d in detections],
        "evaluation_severite": evaluation,
        "description":         enrichissement["description"],
    }
