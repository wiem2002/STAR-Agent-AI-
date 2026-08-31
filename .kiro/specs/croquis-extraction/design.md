# Document de Conception — Extraction de la Case 13 (Croquis de l'Accident)

## Vue d'ensemble

La case 13 du constat amiable FTUSA est un grand rectangle à quadrillage dense occupant la zone centrale-basse du formulaire. La fonction actuelle `_recadrer_zone_croquis()` échoue à l'isoler précisément parce que sa stratégie de détection (contours + filtrage par surface et ratio) est trop permissive.

La nouvelle stratégie repose sur deux observations structurelles :
1. La position de la case 13 est **fixe et connue** dans le document standardisé.
2. La case 13 se distingue de tous les autres champs par la **densité de son quadrillage** (fréquence spatiale élevée des transitions clair/foncé).

Le pipeline complet est :

```
Constat (PDF/image)
      ↓
  Prétraitement (normalisation contraste)
      ↓
  Région d'intérêt initiale (bande 50–85 % de la hauteur)
      ↓
  Détection par densité de grille + filtrage géométrique
      ↓ (fallback si échec)
  Coordonnées relatives fixes
      ↓
  Recadrage précis de la Case_13
      ↓
  Suppression du fond quadrillé (morphologie)
      ↓
  Zone_Croquis (np.ndarray, niveaux de gris)
      ↓
  Encodage PNG → base64
      ↓
  Frontend Angular (croquisImageSrc)
```

---

## Architecture

### Composants

```
ftusa-backend/
  croquis_extraction.py        ← module principal modifié
    _normaliser_contraste()    ← nouveau : égalisation CLAHE
    _detecter_boite_croquis()  ← réécrit : détection par densité de grille
    _recadrer_zone_croquis()   ← réécrit : recadrage précis
    _supprimer_grille_quadrillee() ← réécrit (était _supprimer_grille_pointillee)
    extraire_image_croquis()   ← inchangé (signature)
    extraire_croquis_depuis_image() ← inchangé (signature)
    extraire_croquis_rapide()  ← inchangé (signature)
    extraire_croquis()         ← inchangé (signature)

star-ftusa-agent/
  src/app/features/dashboard/components/analyse-ia-cours/
    analyse-ia-cours.component.ts  ← croquisImageSrc getter (aucun changement requis)
    analyse-ia-cours.component.html ← aucun changement requis
```

---

## Composants et Interfaces

### `_normaliser_contraste(image: np.ndarray) -> np.ndarray`

Applique CLAHE (Contrast Limited Adaptive Histogram Equalization) sur l'image en niveaux de gris pour normaliser la luminosité.

```python
def _normaliser_contraste(image: np.ndarray) -> np.ndarray:
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gris)
```

### `_detecter_boite_croquis(image: np.ndarray) -> Optional[Tuple[int,int,int,int]]`

**Stratégie de détection révisée :**

1. Restreindre la recherche à la bande verticale [50 %, 85 %] de l'image (zone où se trouve toujours la case 13).
2. Appliquer CLAHE pour normaliser le contraste.
3. Calculer un **score de densité de grille** sur une grille de fenêtres glissantes : la case 13 aura la variance locale la plus élevée et un ratio de transitions clair/foncé caractéristique.
4. Identifier le rectangle candidat par seuillage de Canny + `findContours`, en filtrant par :
   - Surface minimale : 8 % de la surface totale de l'image.
   - Rapport largeur/hauteur : entre 1.8 et 3.5.
   - Position horizontale du centre : entre 20 % et 80 % de la largeur.
5. Parmi les candidats, scorer chacun par `score = densité_grille × (1 - |ratio - 2.5| / 2.0)` et retourner le meilleur.

### `_recadrer_zone_croquis(image: np.ndarray) -> np.ndarray`

1. Appelle `_detecter_boite_croquis(image)`.
2. Si `None`, utilise le repli fixe : `(x1=0.15·w, y1=0.52·h, x2=0.85·w, y2=0.83·h)`.
3. Applique un léger rognage des marges (2 % horizontal, 3 % vertical haut, 1 % bas) pour exclure les bordures de case.
4. Retourne le sous-tableau numpy recadré.

### `_supprimer_grille_quadrillee(image: np.ndarray) -> np.ndarray`

Remplace `_supprimer_grille_pointillee`. Stratégie :

1. Convertir en niveaux de gris si nécessaire.
2. Seuillage adaptatif (`ADAPTIVE_THRESH_GAUSSIAN_C`) pour binariser.
3. `MORPH_OPEN` avec un noyau elliptique 2×2 pour supprimer les petits éléments (points de grille ≤ 4 px).
4. `MORPH_CLOSE` avec un noyau 3×3 pour reconnecter les traits manuscrits fragmentés.
5. Retourner l'image binaire (fond blanc = 255, traits = 0).

---

## Modèles de Données

### Entrée de `_recadrer_zone_croquis`

| Paramètre | Type | Description |
|-----------|------|-------------|
| `image` | `np.ndarray` (H×W×3, BGR) | Image du constat, déjà convertie depuis PDF si nécessaire |

### Sortie de `_recadrer_zone_croquis`

| Champ | Type | Description |
|-------|------|-------------|
| retour | `np.ndarray` (h×w×3 ou h×w) | Sous-image de la Case_13 |

### Réponse JSON de l'API (champ `imageBase64`)

```json
{
  "numeroSinistre": "string",
  "typeIntersection": "string",
  "imageBase64": "string (base64 PNG)"
}
```

---

## Propriétés de Correction

*Une propriété est une caractéristique ou un comportement qui doit rester vrai pour toutes les exécutions valides du système — une spécification formelle de ce que le système doit faire. Les propriétés servent de pont entre les spécifications lisibles par l'humain et les garanties d'exactitude vérifiables par machine.*

### Vue d'ensemble des tests orientés propriétés

Les tests par propriétés (Property-Based Testing, PBT) valident la correction logicielle en testant des propriétés universelles sur de nombreuses entrées générées aléatoirement. Chaque propriété est une spécification formelle qui doit tenir pour toutes les entrées valides.

**Bibliothèque retenue :** `hypothesis` (Python), avec `@given` et des stratégies personnalisées pour générer des images synthétiques.

---

### Propriété 1 : Précision de la détection sur images de qualité variable

*Pour tout* Constat synthétique (luminosité entre 0.5× et 1.5× la normale, rotation entre -5° et +5°, résolution entre 72 et 300 DPI) contenant un rectangle de grille positionné dans la bande [50 %, 85 %], la boîte retournée par `_detecter_boite_croquis` doit chevaucher la vérité terrain (IoU ≥ 0.85).

**Validates: Requirements 1.1, 2.1, 2.2, 2.3**

---

### Propriété 2 : Repli sur coordonnées fixes en cas d'échec de détection (cas limite)

*Pour toute* image entièrement uniforme (aucun contour détectable), `_recadrer_zone_croquis` doit retourner une région dont les dimensions correspondent aux coordonnées relatives fixes `(0.15·w, 0.52·h, 0.85·w, 0.83·h)` à ±2 px près.

**Validates: Requirements 1.3**

---

### Propriété 3 : Scoring du candidat le mieux adapté

*Pour tout* ensemble de régions candidates avec des ratios et densités de grille connus, `_detecter_boite_croquis` doit sélectionner la région dont le ratio largeur/hauteur est le plus proche de 2.5 et la densité de grille la plus élevée.

**Validates: Requirements 1.5**

---

### Propriété 4 : Suppression des éléments de grille de fond

*Pour toute* image synthétique composée uniquement de points réguliers ≤ 4 × 4 px (simulant la Grille_Fond), `_supprimer_grille_quadrillee` doit retourner une image dont plus de 95 % des pixels sont blancs (≥ 240/255).

**Validates: Requirements 3.1**

---

### Propriété 5 : Conservation des traits manuscrits et format de sortie

*Pour toute* image synthétique contenant des lignes d'épaisseur ≥ 3 px superposées à une grille de fond, après application de `_supprimer_grille_quadrillee`, les pixels correspondant aux lignes doivent être foncés (≤ 50/255) dans l'image de sortie. De plus, l'image de sortie doit être en niveaux de gris (2D).

**Validates: Requirements 3.2, 3.3**

---

### Propriété 6 : Aller-retour de l'encodage base64

*Pour toute* image numpy valide produite par `_recadrer_zone_croquis`, encoder en PNG puis en base64, puis décoder le base64 et décoder le PNG doit produire une image de dimensions identiques avec des valeurs de pixels proches (PSNR ≥ 40 dB).

**Validates: Requirements 5.1**

---

### Propriété 7 : Présence de `imageBase64` dans toutes les réponses API

*Pour tout* Constat valide soumis aux endpoints `/api/constats/{id}/croquis` et à l'analyse complète, la réponse JSON doit contenir la clé `imageBase64` avec une valeur non vide.

**Validates: Requirements 5.2**

---

## Gestion des Erreurs

| Situation | Comportement attendu |
|-----------|---------------------|
| Image trop petite (< 100 × 50 px) | `ValueError` avec message descriptif |
| PDF vide ou corrompu | `ValueError` propagée depuis `pdf_vers_image` |
| Détection de Case_13 échouée | Repli silencieux sur coordonnées fixes |
| Encodage PNG échoué | `RuntimeError` avec message descriptif |

---

## Stratégie de Test

### Tests unitaires

- Tester `_normaliser_contraste` : vérifier que la plage dynamique de sortie est ≥ 200 sur une image terne.
- Tester `_detecter_boite_croquis` sur une image synthétique avec une grille connue.
- Tester le repli de `_recadrer_zone_croquis` sur une image uniforme.
- Tester `_supprimer_grille_quadrillee` avec une image de points purs.
- Tester la construction de `croquisImageSrc` dans le composant Angular (données mockées).
- Vérifier que les symboles publics de `croquis_extraction.py` n'ont pas changé (test de non-régression).

### Tests orientés propriétés (hypothesis)

Chaque propriété ci-dessus doit être implémentée sous la forme d'un unique test `@given` avec au moins 100 itérations.

Format de tag : `Feature: croquis-extraction, Property {N}: {titre}`

| Test | Propriété | Iterations |
|------|-----------|-----------|
| `test_detection_accuracy_quality_variations` | P1 | 100 |
| `test_fallback_on_featureless_image` | P2 (edge case) | 50 |
| `test_candidate_scoring` | P3 | 100 |
| `test_grid_removal_pure_dots` | P4 | 100 |
| `test_line_preservation_and_output_format` | P5 | 100 |
| `test_base64_roundtrip` | P6 | 100 |
| `test_api_always_includes_image_base64` | P7 | 50 |
