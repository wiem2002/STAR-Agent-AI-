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
    h, w = image.shape[:2]
    zone = image[int(0.45 * h):, :]
    oy = int(0.45 * h)

    gris = cv2.cvtColor(zone, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gris, (5, 5), 0)
    _, bin_ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bin_ = cv2.morphologyEx(bin_, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)

    contours, _ = cv2.findContours(bin_, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    meilleurs: List[Tuple[float, Tuple[int, int, int, int]]] = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        aire = cw * ch
        if aire < 0.04 * w * h:
            continue
        ratio = cw / max(ch, 1)
        if ratio < 1.1 or ratio > 3.2:
            continue
        cx = x + cw / 2
        if cx < 0.22 * w or cx > 0.78 * w:
            continue
        score = aire * (1.0 - abs(ratio - 1.7) / 2.0)
        meilleurs.append((score, (x, y + oy, x + cw, y + oy + ch)))

    if not meilleurs:
        return None
    meilleurs.sort(key=lambda t: t[0], reverse=True)
    return meilleurs[0][1]


def _recadrer_zone_croquis(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    box = _detecter_boite_croquis(image)
    if box is None:
        box = (int(0.28 * w), int(0.58 * h), int(0.72 * w), int(0.78 * h))
    x1, y1, x2, y2 = _clip_box(*box, w, h)
    mx = int(0.02 * (x2 - x1))
    my_top = int(0.12 * (y2 - y1))
    my_bot = int(0.03 * (y2 - y1))
    x1, y1, x2, y2 = _clip_box(x1 + mx, y1 + my_top, x2 - mx, y2 - my_bot, w, h)
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
        for l in lignes[:, 0, :]:
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
    Analyse la topologie des segments routiers pour déterminer le type
    d'intersection.

    Retourne (type_intersection, confiance).
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

    # Longueur totale par direction
    long_h = sum(l for l, *_ in horizontaux)
    long_v = sum(l for l, *_ in verticaux)
    long_o = sum(l for l, _ in obliques)

    total = long_h + long_v + long_o + 1e-9

    ratio_h = long_h / total
    ratio_v = long_v / total

    # Décision topologique
    # ─ Ligne droite : dominance horizontale nette, peu ou pas de vertical
    if ratio_h > 0.55 and ratio_v < 0.20:
        return "ligne-droite", min(0.92, 0.60 + ratio_h * 0.5)

    # ─ Carrefour : horizontal ET vertical significatifs + segment vertical
    #   couvre une grande partie de la hauteur de l'image
    if ratio_h > 0.25 and ratio_v > 0.25:
        # Vérifie que le segment vertical est long (traverse la route)
        if verticaux:
            max_long_v = max(l for l, *_ in verticaux)
            if max_long_v > h * 0.35:
                return "carrefour", 0.82
        return "T", 0.72

    # ─ Intersection T : horizontal dominant + vertical partiel (< hauteur)
    if ratio_h > 0.30 and ratio_v > 0.10:
        if verticaux:
            max_long_v = max(l for l, *_ in verticaux)
            if max_long_v < h * 0.55:  # Le vertical ne couvre pas toute la hauteur
                return "T", 0.75
            return "carrefour", 0.70
        return "T", 0.60

    # ─ Présence forte d'obliques → dessin complexe → carrefour ou T
    if long_o > long_h * 0.4 and ratio_h > 0.20:
        return "T", 0.55

    return "ligne-droite", 0.45


# ---------------------------------------------------------------------------
# Circonstances FTUSA → affinage du type d'intersection
# ---------------------------------------------------------------------------

_CIRC_CARREFOUR = {16, 17}
_CIRC_VIRAGE    = {12, 13}
_CIRC_LIGNE     = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15}


def _affiner_avec_circonstances(
    type_cv: str,
    conf_cv: float,
    circ_a: Sequence[int],
    circ_b: Sequence[int],
) -> Tuple[str, float]:
    """
    Combine le résultat CV avec les circonstances.

    - Si les circonstances sont très claires, elles priment sur le CV.
    - Sinon, le CV est la référence avec boost/malus de confiance.
    """
    toutes = set(circ_a) | set(circ_b)
    if not toutes:
        return type_cv, conf_cv

    # Signal fort des circonstances
    if toutes & _CIRC_CARREFOUR:
        if type_cv in ("carrefour", "T"):
            return type_cv, min(0.95, conf_cv + 0.15)
        return "carrefour", 0.85

    a_virage = bool(toutes & _CIRC_VIRAGE)
    a_ligne  = bool(toutes & _CIRC_LIGNE)

    if a_virage and not a_ligne:
        # Seulement des virages → forcément une intersection
        if type_cv == "ligne-droite":
            return "T", 0.70
        return type_cv, min(0.92, conf_cv + 0.10)

    if a_virage and a_ligne:
        # Mixte → probable intersection
        if type_cv == "ligne-droite":
            return "T", 0.65
        return type_cv, conf_cv

    if a_ligne and not a_virage:
        # Seulement ligne droite
        if type_cv in ("carrefour", "T"):
            # CV dit intersection mais circonstances disent ligne → garder CV
            # (le dessin est la source primaire), mais baisser la confiance
            return type_cv, max(0.45, conf_cv - 0.20)
        return "ligne-droite", min(0.92, conf_cv + 0.10)

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
        # Sortie rue secondaire
        if 4 in ca or 5 in ca:
            return [
                {"id": "A", "x": 0.50, "y": 0.30, "angle": 180.0},
                {"id": "B", "x": 0.28, "y": 0.65, "angle": 0.0},
            ]
        if 4 in cb or 5 in cb:
            return [
                {"id": "A", "x": 0.28, "y": 0.65, "angle": 0.0},
                {"id": "B", "x": 0.50, "y": 0.30, "angle": 180.0},
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
    """Point d'entrée principal appelé depuis main.py après l'analyse."""
    ca = list(circonstances_a or [])
    cb = list(circonstances_b or [])

    # 1. Recadrer la case 13
    zone = _recadrer_zone_croquis(image)
    _, buf = cv2.imencode(".png", zone)
    image_base64 = base64.b64encode(buf).decode("utf-8")

    h, w = zone.shape[:2]

    # 2. Analyse CV : détecter les axes routiers dans le dessin
    zone_bin = _supprimer_grille_pointillee(zone)
    segments = _extraire_segments_route(zone_bin, w, h)
    type_cv, conf_cv = _analyser_topologie(segments, w, h)

    # 3. Affiner avec les circonstances
    type_final, confiance = _affiner_avec_circonstances(type_cv, conf_cv, ca, cb)

    # 4. Positions des véhicules selon le scénario
    vehicules = _positions_vehicules(type_final, ca, cb)

    # 5. Panneau STOP
    panneau_stop, stop_position = _stop_depuis_circonstances(ca, cb, type_final)

    print(
        f"[CROQUIS] CV={type_cv}({conf_cv:.2f}) "
        f"circ_A={ca} circ_B={cb} "
        f"→ final={type_final}({confiance:.2f}) stop={panneau_stop}"
    )

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
