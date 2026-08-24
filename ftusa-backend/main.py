"""
API FastAPI -- point d'entrée HTTP appelé par l'application Angular.

Lancement local :
    pip install fastapi uvicorn python-multipart
    uvicorn main:app --reload --port 8000

Endpoint principal :
    POST /api/constats/analyser   (multipart/form-data, champ "fichier" = le PDF)
"""
import json
import os
import traceback
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Literal

import cv2

import analyse_constat as ac
import croquis_extraction as cx

app = FastAPI(title="API Agent FTUSA")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORRECTIONS_FILE = os.path.join(BASE_DIR, "corrections_croquis.jsonl")
_executor = ThreadPoolExecutor(max_workers=2)


def _sauvegarder_pdf_cache(numero_sinistre: str, pdf_bytes: bytes) -> None:
    ac.sauvegarder_pdf_cache(numero_sinistre, pdf_bytes)


def _charger_pdf_cache(numero_sinistre: str) -> bytes:
    pdf_bytes = ac.charger_pdf_cache(numero_sinistre)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Aucun PDF en cache pour ce numéro de sinistre.")
    return pdf_bytes

# --- CORS : autorise l'appli Angular (adapte le port si besoin) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # URL de dev Angular ; ajoute l'URL de prod aussi
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Chargement des modèles UNE SEULE FOIS au démarrage du serveur ---
# (charger un modèle YOLO à chaque requête serait beaucoup trop lent)
_model_checkbox = None
_moteur = None


@app.on_event("startup")
def charger_ressources():
    global _model_checkbox, _moteur
    _model_checkbox = ac.charger_modele_checkbox()
    _moteur = ac.charger_moteur()
    print("Modèle checkbox + barème FTUSA chargés.")


class CroquisVehicule(BaseModel):
    id: Literal["A", "B"]
    x: float
    y: float
    angle: float


class CroquisRue(BaseModel):
    nom: str
    orientation: Literal["horizontale", "verticale"]


class PositionCroquis(BaseModel):
    x: float
    y: float


class ResultatCroquis(BaseModel):
    numeroSinistre: str
    typeIntersection: Literal["carrefour", "T", "ligne-droite", "rond-point"]
    rues: List[CroquisRue]
    panneauStop: bool
    panneauStopPosition: Optional[PositionCroquis]
    vehicules: List[CroquisVehicule]
    confiance: float
    imageBase64: Optional[str] = None


class ResultatAnalyse(BaseModel):
    circonstancesA: List[int]
    circonstancesB: List[int]
    casId: str
    titre: str
    responsabiliteA: Optional[int]
    responsabiliteB: Optional[int]
    niveauConfiance: int
    aValider: bool
    justification: str
    idAnalyse: str
    modeleIA: str
    dateAnalyse: str
    dureeAnalyse: str
    sourcesUtilisees: List[str]
    reglesAppliquees: int
    scoreSimilariteCas: float
    nombreCasSimilaires: int
    croquisImageBase64: Optional[str] = None
    croquis: Optional[ResultatCroquis] = None


class CorrectionCroquis(BaseModel):
    numeroSinistre: str
    vehiculeId: Literal["A", "B"]
    xCorrige: float
    yCorrige: float
    angleCorrige: float


@app.post("/api/constats/analyser", response_model=ResultatAnalyse)
async def analyser_constat(
    fichier: UploadFile = File(...),
    page: int = 0,
    colGauche: str = "A",
    numeroSinistre: Optional[str] = None,
):
    if fichier.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF.")

    pdf_bytes = await fichier.read()

    ac.nettoyer_cache_expire()

    if numeroSinistre:
        _sauvegarder_pdf_cache(numeroSinistre, pdf_bytes)
    else:
        print("[AVERTISSEMENT] numeroSinistre absent sur /api/constats/analyser : cache non indexé")

    try:
        resultat = ac.analyser_constat(
            _model_checkbox, _moteur, pdf_bytes, num_page=page, col_gauche=colGauche, numero_sinistre=numeroSinistre
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse : {e}")

    image_path = resultat.pop("_imagePath", None)
    try:
        if image_path:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Impossible de relire l'image d'analyse : {image_path}")
            croquis = cx.extraire_croquis_depuis_image(
                image,
                numeroSinistre or resultat.get("idAnalyse", "TMP"),
                circonstances_a=resultat.get("circonstancesA"),
                circonstances_b=resultat.get("circonstancesB"),
            )
        else:
            croquis = cx.extraire_croquis_rapide(
                pdf_bytes,
                numeroSinistre or resultat.get("idAnalyse", "TMP"),
                circonstances_a=resultat.get("circonstancesA"),
                circonstances_b=resultat.get("circonstancesB"),
            )
        resultat["croquis"] = croquis
        resultat["croquisImageBase64"] = croquis.get("imageBase64")
    except Exception as e:
        print(f"[AVERTISSEMENT] Extraction croquis rapide échouée : {e}")
        resultat["croquis"] = None
        resultat["croquisImageBase64"] = None

    return resultat


@app.get("/api/constats/{numero_sinistre}/croquis", response_model=ResultatCroquis)
async def lire_croquis(numero_sinistre: str):
    try:
        pdf_bytes = _charger_pdf_cache(numero_sinistre)
        loop = asyncio.get_event_loop()
        resultat = await loop.run_in_executor(
            _executor, cx.extraire_croquis, pdf_bytes, numero_sinistre
        )
        return resultat
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'extraction du croquis : {e}")


@app.post("/api/constats/{numero_sinistre}/croquis/correction")
def corriger_croquis(numero_sinistre: str, correction: CorrectionCroquis):
    try:
        pdf_bytes = _charger_pdf_cache(numero_sinistre)
        croquis = cx.extraire_croquis(pdf_bytes, numero_sinistre)

        vehicule_original = next(
            (vehicule for vehicule in croquis["vehicules"] if vehicule["id"] == correction.vehiculeId),
            {"id": correction.vehiculeId, "x": 0.5, "y": 0.5, "angle": 0.0},
        )

        enregistrement = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "numeroSinistre": correction.numeroSinistre,
            "vehiculeId": correction.vehiculeId,
            "positionOriginale": vehicule_original,
            "positionCorrigee": {
                "x": correction.xCorrige,
                "y": correction.yCorrige,
                "angle": correction.angleCorrige,
            },
            "croquisExtrait": {
                "typeIntersection": croquis["typeIntersection"],
                "rues": croquis["rues"],
                "panneauStop": croquis["panneauStop"],
                "panneauStopPosition": croquis["panneauStopPosition"],
                "vehicules": croquis["vehicules"],
                "confiance": croquis["confiance"],
            },
        }

        with open(CORRECTIONS_FILE, "a", encoding="utf-8") as fichier_corrections:
            fichier_corrections.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement de la correction : {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}
