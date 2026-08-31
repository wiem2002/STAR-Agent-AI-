"""Extraction du croquis FTUSA (case 13) en sortie JSON.

Stratégie combinée :
  1. Analyse CV de l'image de la case 13 pour détecter lignes de route et
     angles des véhicules (source principale pour le type d'intersection).
  2. Les circonstances FTUSA viennent affiner/valider la détection CV.
  3. Les positions des véhicules A/B sont calculées depuis l'image (OCR +
     détection de boîtes englobantes) avec fallback sémantique.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from analyse_constat import pdf_vers_image


_EASYOCR_READER = None


@dataclass
class DetectionTexte:
    texte: str
    confiance: float
    bbox: np.ndarray


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def _charger_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER
    try:
        import easyocr
    except ImportError as exc:
        raise RuntimeError("easyocr n'est pas installé.") from exc
    _EASYOCR_READER = easyocr.Reader(["fr", "en"], gpu=False)
    return _EASYOCR_READER


def _ocr(image: np.ndarray) -> List[DetectionTexte]:
    reader = _charger_reader()
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gris = cv2.equalizeHist(gris)
    resultat = reader.readtext(gris, detail=1, paragraph=False)
    detections: List[DetectionTexte] = []
    for bbox, texte, confiance in resultat:
        if not texte:
            continue
        detections.append(DetectionTexte(
            texte=str(texte).strip(),
            confiance=float(confiance),
            bbox=np.asarray(bbox, dtype=np.float32),
        ))
    return detections


# ---------------------------------------------------------------------------
# Utilitaires géométriques
# ---------------------------------------------------------------------------

def _normaliser_angle(angle_deg: float) -> float:
    a = angle_deg % 360.0
    return a + 360.0 if a < 0 else a


def _bbox_center(bbox: np.ndarray) -> Tuple[float, float]:
    pts = np.asarray(bbox, dtype=np.float32)
    return float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1]))


def _bbox_angle_deg(bbox: np.ndarray) -> float:
    pts = np.asarray(bbox, dtype=np.float32)
    if pts.shape != (4, 2):
        return 0.0
    dx = float(pts[1][0] - pts[0][0])
    dy = float(pts[1][1] - pts[0][1])
    return math.degrees(math.atan2(dy, dx))


def _orientation_depuis_angle(angle_deg: float) -> str:
    a = angle_deg % 180.0
    if a > 90.0:
        a = 180.0 - a
    return "horizontale" if a <= 45.0 else "verticale"


def _clip_box(x1: int, y1: int, x2: int, y2: int, w: int, h: int) -> Tuple[int, int, int, int]:
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))
    return x1, y1, x2, y2


# ---------------------------------------------------------------------------
# Normalisation du contraste
# ---------------------------------------------------------------------------

def _normaliser_contraste(image: np.ndarray) -> np.ndarray:
    """Applique CLAHE pour normaliser la luminosité (robustesse aux scans sombres/surexposés)."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gris)


# ---------------------------------------------------------------------------
# Extraction de la case 13
# ---------------------------------------------------------------------------

def _normaliser_bytes_vers_image(data: bytes) -> np.ndarray:
    if not data:
        raise ValueError("Aucun contenu fourni.")
    if data[:4] == b"%PDF":
        sortie = pdf_vers_image(data, num_page=0)
        img = cv2.imread(sortie)
        if img is None:
            raise ValueError("Impossible de convertir le PDF en image.")
        return img
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Impossible de décoder l'image.")
    return img


def _detecter_boite_croquis(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Localise la case 13 par analyse des projections horizontales.

    Stratégie calibrée sur la structure réelle du constat FTUSA :
    - Les bordures horizontales fortes (lignes de séparation de cases) sont
      détectées par projection : chaque ligne avec >30% de pixels sombres.
    - La case 13 est délimitée par deux telles bordures successives dans la
      bande [45%, 80%] de la hauteur, avec un espace > 10% de h entre elles.
    - Horizontalement : la case 13 couvre ~70% de la largeur centrée.
    """
    h, w = image.shape[:2]

    gris = _normaliser_contraste(image)
    _, bin_ = cv2.threshold(gris, 100, 255, cv2.THRESH_BINARY_INV)

    # Projection horizontale : nb pixels sombres par ligne
    proj = np.sum(bin_, axis=1) / 255

    # Chercher les lignes fortes (bordures) dans la zone d'intérêt
    y_min = int(0.43 * h)
    y_max = int(0.80 * h)
    seuil = w * 0.25  # au moins 25% de pixels sombres = bordure

    bordures = [y for y in range(y_min, y_max) if proj[y] > seuil]
    if not bordures:
        return None

    # Regrouper les bordures consécutives en bandes
    groupes: List[List[int]] = []
    groupe_courant = [bordures[0]]
    for y in bordures[1:]:
        if y - groupe_courant[-1] <= 4:
            groupe_courant.append(y)
        else:
            groupes.append(groupe_courant)
            groupe_courant = [y]
    groupes.append(groupe_courant)

    # Centre de chaque bande = position de la bordure
    centres = [int(np.mean(g)) for g in groupes]

    # Chercher la paire de bordures avec le plus grand écart
    # (la case 13 est la plus haute zone du document FTUSA)
    min_gap = int(0.15 * h)
    meilleur = None
    meilleur_score = 0

    for i in range(len(centres)):
        for j in range(i + 1, len(centres)):
            gap = centres[j] - centres[i]
            if gap < min_gap:
                continue
            if gap > int(0.26 * h):  # pas plus de 26% de hauteur (case 13 ~22%)
                continue
            # Préférer la zone dans [47%, 72%] du document (position connue case 13)
            cy_norm = (centres[i] + centres[j]) / 2 / h
            # Pénalité si le centre est trop bas (case suivante) ou trop haut
            penalite = abs(cy_norm - 0.59) * 3
            score = gap * max(0.1, 1.0 - penalite)
            if score > meilleur_score:
                meilleur_score = score
                meilleur = (centres[i], centres[j])

    if meilleur is None:
        return None

    y1_case, y2_case = meilleur

    # Largeur : la case 13 occupe environ 70% de la largeur, centrée
    # Détecter les bordures verticales dans cette bande
    bande = bin_[y1_case:y2_case, :]
    proj_v = np.sum(bande, axis=0) / 255
    seuil_v = (y2_case - y1_case) * 0.25

    cols_fortes = [x for x in range(w) if proj_v[x] > seuil_v]
    if cols_fortes:
        x1_case = max(0, min(cols_fortes) - 5)
        x2_case = min(w, max(cols_fortes) + 5)
    else:
        x1_case = int(0.05 * w)
        x2_case = int(0.95 * w)

    print(f"[CROQUIS] Case 13 detectee: ({x1_case},{y1_case})-({x2_case},{y2_case}) "
          f"= {x2_case-x1_case}x{y2_case-y1_case}px "
          f"({x1_case/w*100:.0f}%,{y1_case/h*100:.0f}%)-({x2_case/w*100:.0f}%,{y2_case/h*100:.0f}%)")

    return x1_case, y1_case, x2_case, y2_case


def _recadrer_zone_croquis(image: np.ndarray) -> np.ndarray:
    """
    Recadre précisément la zone de dessin de la case 13.
    Retire le titre 'Croquis de l'accident' (haut) et les bordures (bas/côtés).
    """
    h, w = image.shape[:2]
    box = _detecter_boite_croquis(image)

    if box is None:
        # Repli calibré : case 13 est entre 48% et 70% de la hauteur
        box = (int(0.05 * w), int(0.48 * h), int(0.95 * w), int(0.70 * h))
        print("[CROQUIS] Repli sur coordonnees fixes")

    x1, y1, x2, y2 = _clip_box(*box, w, h)

    # Rogner : enlever titre (haut ~8%), marges latérales légères, bas minimal
    zone_h = y2 - y1
    zone_w = x2 - x1
    marge_top  = int(0.08 * zone_h)   # titre "13. Croquis de l'accident"
    marge_bot  = int(0.02 * zone_h)
    marge_lat  = int(0.01 * zone_w)

    x1, y1, x2, y2 = _clip_box(
        x1 + marge_lat,
        y1 + marge_top,
        x2 - marge_lat,
        y2 - marge_bot,
        w, h,
    )
    return image[y1:y2, x1:x2].copy()


# ---------------------------------------------------------------------------
# Analyse CV de l'image de la case 13
# ---------------------------------------------------------------------------

def _supprimer_grille_pointillee(image: np.ndarray) -> np.ndarray:
    """Supprime la grille pointillée de fond du constat FTUSA."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Seuillage adaptatif pour isoler les traits foncés
    bin_ = cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        21, 8,
    )

    # Morphologie : garde seulement les éléments plus larges que les points
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bin_ = cv2.morphologyEx(bin_, cv2.MORPH_OPEN, kernel_open)

    # Dilate pour reconnecter les traits du dessin
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    bin_ = cv2.dilate(bin_, kernel_dilate, iterations=1)

    return bin_


def _extraire_segments_route(image_bin: np.ndarray, w: int, h: int) -> List[Tuple[float, float, float, float]]:
    """Extrait les segments de route (longues lignes droites = axes routiers)."""
    edges = cv2.Canny(image_bin, 30, 120, apertureSize=3)

    seuil_min_longueur = max(int(w * 0.20), 30)  # au moins 20% de la largeur
    seuil_hough = max(int(seuil_min_longueur * 0.6), 20)

    lignes = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=seuil_hough,
        minLineLength=seuil_min_longueur,
        maxLineGap=int(w * 0.05),
    )

    segments: List[Tuple[float, float, float, float]] = []
    if lignes is not None:
        # HoughLinesP peut retourner (N,1,4) ou (N,4) selon la version OpenCV
        lines_arr = lignes[:, 0, :] if lignes.ndim == 3 else lignes
        for l in lines_arr:
            x1, y1, x2, y2 = map(float, l)
            longueur = math.hypot(x2 - x1, y2 - y1)
            if longueur >= seuil_min_longueur:
                segments.append((x1, y1, x2, y2))
    return segments


def _angle_segment(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def _est_horizontal(angle: float, tolerance: float = 20.0) -> bool:
    a = abs(angle % 180.0)
    if a > 90:
        a = 180 - a
    return a <= tolerance


def _est_vertical(angle: float, tolerance: float = 20.0) -> bool:
    a = abs(angle % 180.0)
    if a > 90:
        a = 180 - a
    return a >= (90 - tolerance)


def _analyser_topologie(
    segments: List[Tuple[float, float, float, float]],
    w: int, h: int,
) -> Tuple[str, float]:
    """
    Analyse la topologie des segments routiers.
    Retourne (type_intersection, confiance).

    Seuils assouplis pour détecter les intersections T avec un court segment vertical
    (dessin manuscrit où la rue secondaire est peu longue).
    """
    if not segments:
        return "ligne-droite", 0.35

    horizontaux = []
    verticaux = []
    obliques = []

    for x1, y1, x2, y2 in segments:
        angle = _angle_segment(x1, y1, x2, y2)
        longueur = math.hypot(x2 - x1, y2 - y1)
        if _est_horizontal(angle):
            horizontaux.append((longueur, x1, y1, x2, y2))
        elif _est_vertical(angle):
            verticaux.append((longueur, x1, y1, x2, y2))
        else:
            obliques.append((longueur, angle))

    long_h = sum(l for l, *_ in horizontaux)
    long_v = sum(l for l, *_ in verticaux)
    long_o = sum(l for l, _ in obliques)
    total = long_h + long_v + long_o + 1e-9

    ratio_h = long_h / total
    ratio_v = long_v / total

    nb_v = len(verticaux)
    max_long_v = max((l for l, *_ in verticaux), default=0)

    print(f"[TOPOLOGIE] ratio_h={ratio_h:.2f} ratio_v={ratio_v:.2f} "
          f"nb_v={nb_v} max_long_v={max_long_v:.0f} h={h}")

    # ─ Carrefour : vertical long couvre bien la hauteur ET horizontal fort
    if ratio_h > 0.25 and ratio_v > 0.20 and max_long_v > h * 0.40:
        return "carrefour", 0.82

    # ─ Intersection T : horizontal dominant + TOUT segment vertical détecté
    #   (même court — rue secondaire dessinée en petit)
    if ratio_h > 0.30 and nb_v >= 1:
        if max_long_v > h * 0.20:   # segment vertical d'au moins 20% de la hauteur
            conf = min(0.80, 0.55 + ratio_h * 0.4 + (max_long_v / h) * 0.3)
            return "T", conf

    # ─ Forte présence d'obliques sur fond horizontal → probable T ou carrefour
    if long_o > long_h * 0.35 and ratio_h > 0.20:
        return "T", 0.55

    # ─ Ligne droite : horizontal dominant, aucun vertical significatif
    if ratio_h > 0.50 and max_long_v < h * 0.15:
        return "ligne-droite", min(0.90, 0.60 + ratio_h * 0.5)

    return "ligne-droite", 0.42


# ---------------------------------------------------------------------------
# Déduction rapide du type d'intersection depuis les circonstances seules
# (sans CV — utilisé dans le chemin critique pour ne pas ralentir la réponse)
# ---------------------------------------------------------------------------

def _type_depuis_circonstances(
    circ_a: Sequence[int],
    circ_b: Sequence[int],
) -> Tuple[str, float]:
    """Retourne (type_intersection, confiance) depuis les circonstances uniquement."""
    toutes = set(circ_a) | set(circ_b)
    if not toutes:
        return "ligne-droite", 0.50

    if toutes & _CIRC_CARREFOUR:
        return "carrefour", 0.90
    if (toutes & _CIRC_VIRAGE) and (toutes & _CIRC_SECONDAIRE):
        return "T", 0.90
    if toutes & _CIRC_VIRAGE:
        return "T", 0.80
    if toutes & _CIRC_SECONDAIRE:
        return "T", 0.82
    if toutes & _CIRC_LIGNE and not (toutes & _CIRC_INTERSECTION_FORTE):
        return "ligne-droite", 0.88
    return "ligne-droite", 0.55


# ---------------------------------------------------------------------------
# Circonstances FTUSA → affinage du type d'intersection
# ---------------------------------------------------------------------------

# Circonstances qui impliquent OBLIGATOIREMENT une intersection
_CIRC_INTERSECTION_FORTE = {
    4,   # sortait d'un parking / lieu privé / chemin de terre
    5,   # s'engageait dans un parking / lieu privé / chemin de terre
    12,  # virait à droite
    13,  # virait à gauche
    16,  # venait de droite (dans un carrefour)
    17,  # n'avait pas observé le signal de priorité
}

# Circonstances qui impliquent un carrefour avec règle de priorité
_CIRC_CARREFOUR = {16, 17}

# Circonstances de virage simple (T ou carrefour)
_CIRC_VIRAGE = {12, 13}

# Circonstances de sortie/entrée d'une voie secondaire (T)
_CIRC_SECONDAIRE = {4, 5}

# Circonstances de ligne droite pure
_CIRC_LIGNE = {1, 2, 3, 6, 7, 8, 9, 10, 11, 14, 15}


def _affiner_avec_circonstances(
    type_cv: str,
    conf_cv: float,
    circ_a: Sequence[int],
    circ_b: Sequence[int],
) -> Tuple[str, float]:
    """
    Les circonstances priment sur le CV dès qu'elles sont explicites.
    Hiérarchie de décision :
      1. Carrefour avec priorité (circ 16/17) → carrefour
      2. Virage + sortie secondaire            → T
      3. Virage seul                           → T (ou carrefour si CV dit carrefour)
      4. Sortie secondaire seule               → T
      5. Ligne droite pure                     → ligne-droite
      6. Aucune info exploitable               → résultat CV
    """
    toutes = set(circ_a) | set(circ_b)
    if not toutes:
        return type_cv, conf_cv

    # ── Règle 1 : carrefour avec priorité ──
    if toutes & _CIRC_CARREFOUR:
        if type_cv in ("carrefour", "T"):
            return type_cv, min(0.95, conf_cv + 0.15)
        return "carrefour", 0.88

    # ── Règle 2 : virage + sortie secondaire → T certain ──
    if (toutes & _CIRC_VIRAGE) and (toutes & _CIRC_SECONDAIRE):
        return "T", 0.90

    # ── Règle 3 : virage seul ──
    if toutes & _CIRC_VIRAGE:
        if type_cv == "carrefour":
            return "carrefour", min(0.90, conf_cv + 0.10)
        return "T", 0.80

    # ── Règle 4 : sortie rue secondaire seule → T ──
    if toutes & _CIRC_SECONDAIRE:
        return "T", 0.82

    # ── Règle 5 : ligne droite pure ──
    if toutes & _CIRC_LIGNE and not (toutes & _CIRC_INTERSECTION_FORTE):
        # Les circonstances disent ligne droite → elles priment toujours sur le CV
        return "ligne-droite", min(0.92, conf_cv + 0.10) if type_cv == "ligne-droite" else "ligne-droite", 0.85

    # ── Règle 6 : circonstances mixtes, on fait confiance au CV ──
    return type_cv, conf_cv


# ---------------------------------------------------------------------------
# Positions des véhicules selon le scénario
# ---------------------------------------------------------------------------

def _positions_vehicules(
    type_intersection: str,
    circ_a: Sequence[int],
    circ_b: Sequence[int],
) -> List[Dict[str, Any]]:
    ca, cb = set(circ_a), set(circ_b)

    if type_intersection == "ligne-droite":
        # Face-à-face (sens inverse)
        if 15 in ca or 15 in cb:
            return [
                {"id": "A", "x": 0.25, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.75, "y": 0.50, "angle": 180.0},
            ]
        # Dépassement
        if 11 in ca:
            return [
                {"id": "A", "x": 0.55, "y": 0.40, "angle": 12.0},
                {"id": "B", "x": 0.38, "y": 0.54, "angle": 0.0},
            ]
        if 11 in cb:
            return [
                {"id": "A", "x": 0.38, "y": 0.54, "angle": 0.0},
                {"id": "B", "x": 0.55, "y": 0.40, "angle": 12.0},
            ]
        # Changement de file
        if 10 in ca:
            return [
                {"id": "A", "x": 0.55, "y": 0.40, "angle": 8.0},
                {"id": "B", "x": 0.36, "y": 0.55, "angle": 0.0},
            ]
        if 10 in cb:
            return [
                {"id": "A", "x": 0.36, "y": 0.55, "angle": 0.0},
                {"id": "B", "x": 0.55, "y": 0.40, "angle": 8.0},
            ]
        # Marche arrière
        if 14 in ca:
            return [
                {"id": "A", "x": 0.40, "y": 0.50, "angle": 180.0},
                {"id": "B", "x": 0.65, "y": 0.50, "angle": 0.0},
            ]
        if 14 in cb:
            return [
                {"id": "A", "x": 0.65, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.40, "y": 0.50, "angle": 180.0},
            ]
        # Heurte arrière
        if 8 in ca:
            return [
                {"id": "A", "x": 0.60, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.34, "y": 0.50, "angle": 0.0},
            ]
        if 8 in cb:
            return [
                {"id": "A", "x": 0.34, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.60, "y": 0.50, "angle": 0.0},
            ]
        # Stationnement A
        if ca & {1, 2, 3} and not (cb & {1, 2, 3}):
            return [
                {"id": "A", "x": 0.60, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.30, "y": 0.50, "angle": 0.0},
            ]
        if cb & {1, 2, 3} and not (ca & {1, 2, 3}):
            return [
                {"id": "A", "x": 0.30, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.60, "y": 0.50, "angle": 0.0},
            ]
        # Sortie parking / lieu privé
        if 4 in ca or 5 in ca:
            return [
                {"id": "A", "x": 0.50, "y": 0.65, "angle": 270.0},
                {"id": "B", "x": 0.30, "y": 0.50, "angle": 0.0},
            ]
        if 4 in cb or 5 in cb:
            return [
                {"id": "A", "x": 0.30, "y": 0.50, "angle": 0.0},
                {"id": "B", "x": 0.50, "y": 0.65, "angle": 270.0},
            ]
        # Défaut ligne droite : même sens côte à côte
        return [
            {"id": "A", "x": 0.32, "y": 0.50, "angle": 0.0},
            {"id": "B", "x": 0.68, "y": 0.50, "angle": 0.0},
        ]

    if type_intersection == "T":
        # B sort d'une rue secondaire (circ 4 ou 5 de B) → B vient d'en haut
        if cb & {4, 5}:
            return [
                {"id": "A", "x": 0.28, "y": 0.62, "angle": 0.0},
                {"id": "B", "x": 0.52, "y": 0.30, "angle": 90.0},
            ]
        # A sort d'une rue secondaire
        if ca & {4, 5}:
            return [
                {"id": "A", "x": 0.52, "y": 0.30, "angle": 90.0},
                {"id": "B", "x": 0.28, "y": 0.62, "angle": 0.0},
            ]
        if 13 in cb:  # B vire à gauche
            return [
                {"id": "A", "x": 0.28, "y": 0.65, "angle": 0.0},
                {"id": "B", "x": 0.52, "y": 0.28, "angle": 135.0},
            ]
        if 13 in ca:
            return [
                {"id": "A", "x": 0.52, "y": 0.28, "angle": 135.0},
                {"id": "B", "x": 0.28, "y": 0.65, "angle": 0.0},
            ]
        if 12 in cb:  # B vire à droite
            return [
                {"id": "A", "x": 0.28, "y": 0.65, "angle": 0.0},
                {"id": "B", "x": 0.52, "y": 0.30, "angle": 45.0},
            ]
        if 12 in ca:
            return [
                {"id": "A", "x": 0.52, "y": 0.30, "angle": 45.0},
                {"id": "B", "x": 0.28, "y": 0.65, "angle": 0.0},
            ]
        return [
            {"id": "A", "x": 0.30, "y": 0.65, "angle": 0.0},
            {"id": "B", "x": 0.52, "y": 0.30, "angle": 90.0},
        ]

    if type_intersection == "carrefour":
        if 16 in ca:
            return [
                {"id": "A", "x": 0.25, "y": 0.55, "angle": 0.0},
                {"id": "B", "x": 0.55, "y": 0.75, "angle": 270.0},
            ]
        if 16 in cb:
            return [
                {"id": "A", "x": 0.55, "y": 0.75, "angle": 270.0},
                {"id": "B", "x": 0.25, "y": 0.55, "angle": 0.0},
            ]
        if 17 in ca:
            return [
                {"id": "A", "x": 0.25, "y": 0.55, "angle": 0.0},
                {"id": "B", "x": 0.55, "y": 0.75, "angle": 270.0},
            ]
        if 17 in cb:
            return [
                {"id": "A", "x": 0.55, "y": 0.75, "angle": 270.0},
                {"id": "B", "x": 0.25, "y": 0.55, "angle": 0.0},
            ]
        if 13 in ca:
            return [
                {"id": "A", "x": 0.25, "y": 0.55, "angle": 45.0},
                {"id": "B", "x": 0.55, "y": 0.28, "angle": 270.0},
            ]
        if 13 in cb:
            return [
                {"id": "A", "x": 0.55, "y": 0.28, "angle": 270.0},
                {"id": "B", "x": 0.25, "y": 0.55, "angle": 45.0},
            ]
        return [
            {"id": "A", "x": 0.25, "y": 0.55, "angle": 0.0},
            {"id": "B", "x": 0.55, "y": 0.28, "angle": 270.0},
        ]

    # Rond-point (rare, uniquement si détecté explicitement)
    return [
        {"id": "A", "x": 0.25, "y": 0.55, "angle": 20.0},
        {"id": "B", "x": 0.65, "y": 0.38, "angle": 200.0},
    ]


# ---------------------------------------------------------------------------
# Détection STOP
# ---------------------------------------------------------------------------

def _stop_depuis_circonstances(
    circ_a: Sequence[int],
    circ_b: Sequence[int],
    type_intersection: str,
) -> Tuple[bool, Optional[Dict[str, float]]]:
    if 17 not in (set(circ_a) | set(circ_b)):
        return False, None
    if type_intersection in ("carrefour", "T"):
        return True, {"x": 0.70, "y": 0.20}
    return True, {"x": 0.74, "y": 0.20}


# ---------------------------------------------------------------------------
# Extraction de noms de rues (OCR)
# ---------------------------------------------------------------------------

def _extraire_rues(detections: Sequence[DetectionTexte], w: int, h: int) -> List[Dict[str, str]]:
    rues: List[Dict[str, str]] = []
    vus: set = set()
    for d in detections:
        texte = d.texte.strip()
        upper = texte.upper()
        if upper in {"A", "B", "STOP"}:
            continue
        net = "".join(c for c in upper if c.isalnum() or c in {" ", "-", "'"})
        if len(net.strip()) < 3 or not any(c.isalpha() for c in net):
            continue
        cx, cy = _bbox_center(d.bbox)
        if cy > h * 0.85 and cx > w * 0.55:
            continue
        cle = " ".join(texte.split()).lower()
        if cle in vus:
            continue
        vus.add(cle)
        rues.append({
            "nom": " ".join(texte.split()),
            "orientation": _orientation_depuis_angle(_bbox_angle_deg(d.bbox)),
        })
    return rues[:4]


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def extraire_image_croquis(image_ou_pdf_bytes: bytes) -> str:
    image = _normaliser_bytes_vers_image(image_ou_pdf_bytes)
    zone = _recadrer_zone_croquis(image)
    _, buf = cv2.imencode(".png", zone)
    return base64.b64encode(buf).decode("utf-8")


def extraire_croquis_depuis_image(
    image: np.ndarray,
    numero_sinistre: str,
    circonstances_a: Optional[Sequence[int]] = None,
    circonstances_b: Optional[Sequence[int]] = None,
) -> dict:
    """
    Pipeline de décision hiérarchique :
    
    1. Circonstances FTUSA — source de vérité principale (déterministes)
       Si les circonstances donnent un signal fort → on fait confiance à 100%
    
    2. CV topologie sur la zone centrale du dessin (pas les bordures)
       Utilisé seulement si les circonstances sont ambiguës ou absentes
       La zone analysée exclut 15% des bords pour éviter les bordures colorées
    
    3. Positions A/B : déduites du type d'intersection + circonstances
    """
    ca = list(circonstances_a or [])
    cb = list(circonstances_b or [])

    # 1. Recadrer la case 13 et encoder
    zone = _recadrer_zone_croquis(image)
    _, buf = cv2.imencode(".png", zone)
    image_base64 = base64.b64encode(buf).decode("utf-8")
    zh, zw = zone.shape[:2]

    # 2. Circonstances en priorité absolue
    type_circ, conf_circ = _type_depuis_circonstances(ca, cb)
    circ_forte = conf_circ >= 0.80  # signal suffisamment fort

    if circ_forte:
        # Les circonstances sont claires → on n'a pas besoin du CV
        type_final, confiance = type_circ, conf_circ
        print(f"[CROQUIS] Circonstances fortes: {type_final}({confiance:.2f}) circ_A={ca} circ_B={cb}")
    else:
        # 3. CV sur la zone CENTRALE du dessin
        # Exclure 20% à gauche (zone jaune), 25% à droite (zone verte),
        # 10% haut et bas pour éviter les bordures colorées du constat
        marge_gauche = int(0.20 * zw)
        marge_droite = int(0.25 * zw)
        marge_y = int(0.10 * zh)
        zone_interieure = zone[marge_y:zh - marge_y, marge_gauche:zw - marge_droite]
        zi_h, zi_w = zone_interieure.shape[:2]

        try:
            zone_bin = _supprimer_grille_pointillee(zone_interieure)
            segments = _extraire_segments_route(zone_bin, zi_w, zi_h)
            type_cv, conf_cv = _analyser_topologie(segments, zi_w, zi_h)
        except Exception as e:
            print(f"[CROQUIS] CV echoue: {e}")
            type_cv, conf_cv = "ligne-droite", 0.40

        # Combiner CV + circonstances
        type_final, confiance = _affiner_avec_circonstances(type_cv, conf_cv, ca, cb)
        print(
            f"[CROQUIS] CV={type_cv}({conf_cv:.2f}) circ={type_circ}({conf_circ:.2f}) "
            f"-> final={type_final}({confiance:.2f}) circ_A={ca} circ_B={cb}"
        )

    # 4. Positions des véhicules
    vehicules = _positions_vehicules(type_final, ca, cb)

    # 5. Panneau STOP
    panneau_stop, stop_position = _stop_depuis_circonstances(ca, cb, type_final)

    return {
        "numeroSinistre": numero_sinistre,
        "typeIntersection": type_final,
        "rues": [],
        "panneauStop": panneau_stop,
        "panneauStopPosition": stop_position,
        "vehicules": vehicules,
        "confiance": confiance,
        "imageBase64": image_base64,
    }


def extraire_croquis_rapide(
    image_ou_pdf_bytes: bytes,
    numero_sinistre: str,
    circonstances_a: Optional[Sequence[int]] = None,
    circonstances_b: Optional[Sequence[int]] = None,
) -> dict:
    """Depuis des bytes PDF/image — appelle extraire_croquis_depuis_image."""
    image = _normaliser_bytes_vers_image(image_ou_pdf_bytes)
    return extraire_croquis_depuis_image(image, numero_sinistre, circonstances_a, circonstances_b)


def extraire_croquis(image_ou_pdf_bytes: bytes, numero_sinistre: str) -> dict:
    """Appelé par GET /api/constats/{id}/croquis (sans circonstances)."""
    image = _normaliser_bytes_vers_image(image_ou_pdf_bytes)
    zone = _recadrer_zone_croquis(image)
    _, buf = cv2.imencode(".png", zone)
    image_base64 = base64.b64encode(buf).decode("utf-8")

    h, w = zone.shape[:2]
    zone_bin = _supprimer_grille_pointillee(zone)
    segments = _extraire_segments_route(zone_bin, w, h)
    type_cv, confiance = _analyser_topologie(segments, w, h)

    # Sans circonstances : OCR pour positions A/B
    try:
        detections = _ocr(zone)
        rues = _extraire_rues(detections, w, h)
    except Exception:
        detections, rues = [], []

    vehicules = _positions_vehicules(type_cv, [], [])

    resultat = {
        "numeroSinistre": numero_sinistre,
        "typeIntersection": type_cv,
        "rues": rues,
        "panneauStop": False,
        "panneauStopPosition": None,
        "vehicules": vehicules,
        "confiance": confiance,
        "imageBase64": image_base64,
    }
    print(f"[CROQUIS_OCR] {resultat}")
    return resultat
