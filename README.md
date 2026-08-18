# Agent IA FTUSA — Projet intégré (frontend Angular + backend Python)

## 1. Lancer le backend (analyse du constat)

```bash
cd ftusa-backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Le modèle YOLO se charge une seule fois au démarrage (`@app.on_event("startup")`), donc le tout
premier appel après le lancement du serveur peut prendre quelques secondes de plus.

Vérifie que ça tourne : http://localhost:8000/api/health doit répondre `{"status": "ok"}`.

## 2. Lancer le frontend Angular

```bash
cd star-ftusa-agent
npm install
npm start   # équivalent à : ng serve
```

Ouvre http://localhost:4200.

## 3. Tester le flux complet dans l'interface

1. Écran **"Nouveau dossier"** → onglet **"Pièces jointes"** → dépose le constat (PDF) — les photos
   de véhicules sont optionnelles pour l'instant (l'analyse de dommages n'est pas encore branchée).
2. Clique **"Suivant"**, puis onglet **"Lancer l'analyse"** → **"🚀 Lancer l'analyse"**.
3. L'écran **"Analyse IA en cours"** s'affiche : les 5 étapes s'animent visuellement pendant que la
   vraie requête HTTP part vers `http://localhost:8000/api/constats/analyser` en arrière-plan
   (upload du PDF en `multipart/form-data`).
4. Dès que le backend répond, la barre passe à 100% et le panneau **"Résultat de l'analyse IA"**
   s'affiche avec :
   - le cas FTUSA retenu (`casId`, `titre`)
   - les pourcentages **Responsabilité A** / **Responsabilité B**
   - le niveau de confiance
   - la justification en texte
   - les circonstances détectées (affichées comme "chips", ex: `A: circonstance 17`)

## Ce qui a été modifié dans le projet Angular d'origine

| Fichier | Changement |
|---|---|
| `app.config.ts` | Ajout de `provideHttpClient()` |
| `environments/environment.ts` (+ `.prod.ts`) | URL du backend (`apiUrl`) |
| `core/services/dossier-courant.service.ts` | **Nouveau** — transporte le fichier PDF entre "Nouveau dossier" et "Analyse IA en cours" (pas de routing par URL dans ce projet, donc passage par service) |
| `core/services/analyse-ia.service.ts` | Remplace le mock par un vrai appel HTTP (`analyserConstat()`), avec mapping de la réponse API vers le modèle `ResultatAnalyseIA` déjà utilisé par l'interface existante |
| `nouveau-dossier.component.ts/.html/.scss` | Conserve désormais le vrai objet `File` (pas seulement son nom), distingue le PDF (constat) des photos, empêche de continuer sans PDF |
| `analyse-ia-cours.component.ts/.html/.scss` | Ne simule plus une fausse progression : anime les étapes pendant que l'appel réel tourne, gère les erreurs réseau |

## Limitations actuelles (à faire évoluer)

- **Les photos de dommages ne sont pas encore envoyées à l'API** — seul le PDF du constat est
  analysé pour l'instant (extraction circonstances + décision FTUSA). Le pipeline `analyser_dommages`
  du notebook `stage-wiem` existe déjà côté Python mais n'est pas encore branché dans `main.py`
  ni côté Angular.
- Le **croquis affiché** dans "Analyse IA en cours" reste une illustration statique (pas encore le
  vrai croquis détecté par le pipeline `extraire_positions_vehicules` de `stage-wiem`).
- Les **"éléments clés utilisés par l'IA"** affichent actuellement les numéros bruts de circonstances
  (`A: circonstance 17`) plutôt que leurs libellés complets — à améliorer en renvoyant aussi
  `CIRCUMSTANCE_LABELS` depuis l'API, ou en le dupliquant côté Angular.
- Aucune gestion d'authentification / upload sécurisé — à ajouter avant toute mise en production.
