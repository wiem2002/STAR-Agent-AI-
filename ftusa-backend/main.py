"""
API FastAPI -- point d'entrée HTTP appelé par l'application Angular.

Lancement local :
    pip install fastapi uvicorn python-multipart
    uvicorn main:app --reload --port 8000

Endpoint principal :
    POST /api/constats/analyser   (multipart/form-data, champ "fichier" = le PDF)
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

import analyse_constat as ac

app = FastAPI(title="API Agent FTUSA")

# --- CORS : autorise l'appli Angular (adapte le port si besoin) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # URL de dev Angular ; ajoute l'URL de prod aussi
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


@app.post("/api/constats/analyser", response_model=ResultatAnalyse)
async def analyser_constat(fichier: UploadFile = File(...), page: int = 0, colGauche: str = "A"):
    if fichier.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF.")

    pdf_bytes = await fichier.read()

    try:
        resultat = ac.analyser_constat(
            _model_checkbox, _moteur, pdf_bytes, num_page=page, col_gauche=colGauche
        )
    except Exception as e:
        # Log full traceback to stdout for easier debugging in dev
        import traceback
        tb = traceback.format_exc()
        print("Erreur lors de l'analyse :", tb)
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse : {e}")

    return resultat


@app.get("/api/health")
def health():
    return {"status": "ok"}
