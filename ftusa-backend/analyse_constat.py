"""
Service d'analyse de constat FTUSA -- regroupe toute la logique du notebook
(extraction des circonstances cochées + décision de responsabilité) dans un
module Python réutilisable par une API.

Ce module ne dépend d'aucun notebook/Jupyter -- il est prévu pour tourner
comme un service backend classique.
"""
import os
import sys
import tempfile
import cv2
import fitz  # PyMuPDF
import numpy as np
from sklearn.cluster import KMeans

# --- Compatibilité anciens checkpoints YOLO (cf. notebook, section 3) ---
import ultralytics.utils as _u
if not hasattr(_u, "yaml_load"):
    try:
        from ultralytics.utils.yaml import yaml_load as _yaml_load
    except ImportError:
        import yaml
        def _yaml_load(file, append_filename=False):
            with open(file, errors="ignore", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if append_filename:
                data["yaml_file"] = str(file)
            return data
    _u.yaml_load = _yaml_load

from ultralytics import YOLO
from huggingface_hub import HfApi, hf_hub_download

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("moteur_ftusa", None)
from moteur_ftusa import MoteurFTUSA


# ============================================================
# 1. Libellés des 17 circonstances (notebook, section 6)
# ============================================================
CIRCUMSTANCE_LABELS = {
    1: "en stationnement", 2: "quittait un stationnement",
    3: "prenait un stationnement",
    4: "sortait d'un parking, d'un lieu privé, d'un chemin de terre",
    5: "s'engageait dans un parking, un lieu privé, un chemin de terre",
    6: "arrêt de circulation", 7: "frottement sans changement de file",
    8: "heurtait à l'arrière, en roulant dans le même sens et sur une même file",
    9: "roulait dans le même sens et sur une file différente",
    10: "changeait de file", 11: "doublait", 12: "virait à droite",
    13: "virait à gauche", 14: "reculait",
    15: "empiétait sur la partie de chaussée réservée à la circulation en sens inverse",
    16: "venait de droite (dans un carrefour)",
    17: "n'avait pas observé le signal de priorité",
}

# --- Grille calibrée (notebook, section 7) -- à ajuster si le template diffère ---
TOP_FRAC = 368 / 1451
ROW_HEIGHT_FRAC = 35.57 / 1451
N_ROWS = 17
MAX_ROW_DIST = 0.018

# --- Mapping circonstance -> fait (notebook, section 13) ---
CIRCONSTANCE_TO_FAIT = {
    1:  {"stationnement": "regulier"},
    2:  {"action": "quitte_stationnement"},
    3:  {"action": "manoeuvre_pour_stationner"},
    4:  {"action": "sort_aire_stationnement_ou_chemin_terre"},
    5:  {"action": "s_engage_aire_stationnement_ou_chemin_terre"},
    6:  {"stationnement": "regulier"},
    7:  {"change_file": False},
    8:  {"sens": "meme_sens", "file": "meme_file", "action": "heurte_arriere"},
    9:  {"sens": "meme_sens", "file": "file_differente"},
    10: {"change_file": True},
    11: {"action": "double_empiete_axe_median"},
    12: {"action": "couloir_de_marche_ou_bifurque"},
    13: {"action": "bifurque_a_gauche"},
    14: {"action": "marche_arriere_ou_demi_tour"},
    15: {"sens": "sens_inverse", "action": "empiete_axe_median"},
    16: {"prioritaire_droite": True},
    17: {"action": "ne_respecte_pas_signalisation"},
}


# ============================================================
# 2. Chargement du modèle (au démarrage du serveur, une seule fois)
# ============================================================
def charger_modele_checkbox():
    api = HfApi()
    repo_id = "linhdo/checkbox-detector"
    files = api.list_repo_files(repo_id=repo_id, repo_type="space")
    pt_files = [f for f in files if f.endswith(".pt")]
    assert pt_files, "Aucun .pt trouvé dans linhdo/checkbox-detector"
    detect_weights = [f for f in pt_files if "classif" not in f.lower()]
    weights_filename = detect_weights[0] if detect_weights else pt_files[0]
    weights_path = hf_hub_download(repo_id=repo_id, repo_type="space", filename=weights_filename)
    return YOLO(weights_path)


def charger_moteur(bareme_path=None):
    if bareme_path is None:
        bareme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bareme_ftusa.json")
    return MoteurFTUSA(bareme_path)


# ============================================================
# 3. PDF -> image (notebook, section 4)
# ============================================================
def pdf_vers_image(pdf_bytes, num_page=0, dpi=300, sortie=None):
    # Use the OS temp directory to be cross-platform (Windows/Linux)
    if sortie is None:
        td = tempfile.gettempdir()
        sortie = os.path.join(td, f"constat_page_{num_page}.png")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[num_page]
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(sortie)
    doc.close()
    return sortie


# ============================================================
# 4. Extraction des circonstances (notebook, section 7)
# ============================================================
def pretraiter_image(image_path, sortie=None):
    if sortie is None:
        td = tempfile.gettempdir()
        sortie = os.path.join(td, "constat_pretraite.jpg")
    img_color = cv2.imread(image_path)
    if img_color is None:
        raise ValueError(f"Impossible de lire l'image prétraitee: {image_path}")
    gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)
    gray_eq_3ch = cv2.cvtColor(gray_eq, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(sortie, gray_eq_3ch)
    return sortie


def detecter_cases(model, image_path, conf=0.15, imgsz=1280):
    image_pretraitee = pretraiter_image(image_path)
    results = model.predict(image_pretraitee, conf=conf, iou=0.45,
                             agnostic_nms=True, imgsz=imgsz, verbose=False)
    img = cv2.imread(image_pretraitee)
    h, w = img.shape[:2]

    detections = []
    for r in results:
        for box in r.boxes:
            cls_name = model.names[int(box.cls)]
            confv = float(box.conf)
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
            detections.append({"cls": cls_name, "conf": confv,
                                "box": (x1, y1, x2, y2), "cx": cx, "cy": cy})
    return detections


def assigner_lignes_par_grille(points_colonne):
    lignes = {}
    for p in points_colonne:
        ligne_est = round((p["cy"] - TOP_FRAC) / ROW_HEIGHT_FRAC) + 1
        ligne_est = min(max(ligne_est, 1), N_ROWS)
        cy_attendu = TOP_FRAC + (ligne_est - 1) * ROW_HEIGHT_FRAC
        if abs(p["cy"] - cy_attendu) > MAX_ROW_DIST:
            continue
        if ligne_est not in lignes or p["conf"] > lignes[ligne_est]["conf"]:
            lignes[ligne_est] = p
    return lignes


def extraire_circonstances_cochees(model, image_path, conf=0.15, imgsz=1280, col_gauche="A"):
    detections = detecter_cases(model, image_path, conf=conf, imgsz=imgsz)
    if not detections:
        return {"A": [], "B": []}

    # Si on a moins de 2 detections, KMeans(n_clusters=2) échoue. Gérer
    # explicitement les cas 1 detection (attribuer à la colonne de gauche)
    # et 0 detections (déjà géré ci-dessus).
    col_droite = "B" if col_gauche == "A" else "A"
    cx_all = np.array([d["cx"] for d in detections])
    detections_annotees = []
    if len(cx_all) < 2:
        # Tous les repères sont considérés dans la colonne demandée
        for d in detections:
            detections_annotees.append({**d, "colonne": col_gauche})
    else:
        km_col = KMeans(n_clusters=2, n_init=10, random_state=0).fit(cx_all.reshape(-1, 1))
        centers = km_col.cluster_centers_.flatten()
        cluster_gauche = int(np.argmin(centers))
        for d, label in zip(detections, km_col.labels_):
            col = col_gauche if label == cluster_gauche else col_droite
            detections_annotees.append({**d, "colonne": col})

    lignes_A = assigner_lignes_par_grille([d for d in detections_annotees if d["colonne"] == "A"])
    lignes_B = assigner_lignes_par_grille([d for d in detections_annotees if d["colonne"] == "B"])

    def est_coche(cls_name):
        c = cls_name.lower()
        return "check" in c and "un" not in c

    resultat = {"A": [], "B": []}
    for col, lignes in [("A", lignes_A), ("B", lignes_B)]:
        for numero_ligne, d in lignes.items():
            if est_coche(d["cls"]):
                resultat[col].append(numero_ligne)
    resultat["A"].sort()
    resultat["B"].sort()
    return resultat


# ============================================================
# 5. Décision orientée (notebook, section 13)
# ============================================================
def _construire_faits(circonstances_A, circonstances_B, role_A):
    """role_A : 'X' ou 'Y' -- rôle attribué au véhicule A pour cette tentative.
    Le véhicule B reçoit automatiquement le rôle complémentaire."""
    role_B = "Y" if role_A == "X" else "X"
    faits = {"vehicule_X_action": [], "vehicule_Y_action": []}

    def appliquer(numeros, role):
        for n in numeros:
            for cle, valeur in CIRCONSTANCE_TO_FAIT.get(n, {}).items():
                if cle == "action":
                    faits[f"vehicule_{role}_action"].append(valeur)
                elif cle == "stationnement":
                    faits[f"vehicule_{role}_stationnement"] = valeur
                elif cle == "change_file":
                    faits[f"vehicule_{role}_change_file"] = valeur
                elif cle == "prioritaire_droite":
                    faits[f"vehicule_{role}_prioritaire_droite"] = valeur
                elif cle in ("sens", "file"):
                    faits[cle] = valeur  # clé globale au dossier

    appliquer(circonstances_A, role_A)
    appliquer(circonstances_B, role_B)
    return faits


def determiner_cas_oriente(moteur, circonstances_A, circonstances_B):
    """Essaie les deux orientations (A=X ou A=Y) et retient la meilleure.
    Retourne (resultat_matching, responsabiliteA, responsabiliteB) avec les
    pourcentages déjà remappés sur les véhicules physiques A/B."""
    faits_A_est_X = _construire_faits(circonstances_A, circonstances_B, "X")
    faits_A_est_Y = _construire_faits(circonstances_A, circonstances_B, "Y")

    resultat_A_est_X = moteur.determiner_cas(faits_A_est_X)
    resultat_A_est_Y = moteur.determiner_cas(faits_A_est_Y)

    candidats = [(resultat_A_est_X, "X"), (resultat_A_est_Y, "Y")]
    candidats.sort(key=lambda c: (c[0].confiance, not c[0].a_valider), reverse=True)
    meilleur, role_A = candidats[0]

    if role_A == "X":
        resp_A = meilleur.responsabilite.get("X")
        resp_B = meilleur.responsabilite.get("Y")
    else:
        resp_A = meilleur.responsabilite.get("Y")
        resp_B = meilleur.responsabilite.get("X")

    if (resultat_A_est_X.confiance == resultat_A_est_Y.confiance
            and resultat_A_est_X.cas_id != resultat_A_est_Y.cas_id):
        meilleur.a_valider = True

    return meilleur, resp_A, resp_B


def generer_justification(resultat, circonstances_A, circonstances_B):
    libelles_A = [CIRCUMSTANCE_LABELS[n] for n in circonstances_A if n in CIRCUMSTANCE_LABELS]
    libelles_B = [CIRCUMSTANCE_LABELS[n] for n in circonstances_B if n in CIRCUMSTANCE_LABELS]

    phrase = f"Cas FTUSA n°{resultat.cas_id} : {resultat.titre}. "
    if libelles_A:
        phrase += f"Véhicule A : {', '.join(libelles_A)}. "
    if libelles_B:
        phrase += f"Véhicule B : {', '.join(libelles_B)}. "
    if resultat.notes:
        phrase += " ".join(resultat.notes)
    return phrase.strip()


# ============================================================
# 6. Pipeline complet (ce que l'API va appeler)
# ============================================================
def analyser_constat(model_checkbox, moteur, pdf_bytes, num_page=0, col_gauche="A"):
    image_path = pdf_vers_image(pdf_bytes, num_page=num_page)
    circonstances = extraire_circonstances_cochees(model_checkbox, image_path, col_gauche=col_gauche)
    resultat, resp_A, resp_B = determiner_cas_oriente(moteur, circonstances["A"], circonstances["B"])
    justification = generer_justification(resultat, circonstances["A"], circonstances["B"])

    return {
        "circonstancesA": circonstances["A"],
        "circonstancesB": circonstances["B"],
        "casId": resultat.cas_id,
        "titre": resultat.titre,
        "responsabiliteA": round(resp_A * 100) if resp_A is not None else None,
        "responsabiliteB": round(resp_B * 100) if resp_B is not None else None,
        "niveauConfiance": round(resultat.confiance * 100),
        "aValider": resultat.a_valider,
        "justification": justification,
    }
