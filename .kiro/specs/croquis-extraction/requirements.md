# Document de Spécifications — Extraction de la Case 13 (Croquis de l'Accident)

## Introduction

Le constat amiable FTUSA est un formulaire standardisé dont la **case 13** contient le « Croquis de l'accident » : un grand rectangle à quadrillage dense où les parties dessinent à la main la configuration routière et les trajectoires des véhicules.

La fonction `_recadrer_zone_croquis()` dans `ftusa-backend/croquis_extraction.py` est censée isoler uniquement cette case, mais le recadrage actuel est trop large et capture la quasi-totalité de la page. L'objectif de cette feature est de corriger ce recadrage et d'améliorer le traitement post-extraction pour mettre en évidence les dessins manuscrits.

La solution doit fonctionner exclusivement avec OpenCV (vision par ordinateur classique), sans modèle ML additionnel, et doit s'exécuter en moins de 2 secondes.

---

## Glossaire

- **Extracteur** : le module Python `croquis_extraction.py` et ses fonctions d'extraction de la case 13.
- **Case_13** : la zone rectangulaire quadrillée du formulaire FTUSA portant le numéro 13 et le libellé « Croquis de l'accident ».
- **Zone_Croquis** : l'image recadrée résultant de l'extraction de la Case_13.
- **Grille_Fond** : le quadrillage dense de petits carrés imprimé sur le fond de la Case_13.
- **Dessin_Main** : les traits tracés à la main par les assurés (véhicules, routes, flèches) par-dessus la Grille_Fond.
- **Constat** : le document PDF ou image (scan) du constat amiable FTUSA fourni en entrée.
- **Frontend** : l'application Angular 18 `star-ftusa-agent/` qui affiche la Zone_Croquis.
- **API** : le backend FastAPI `ftusa-backend/` qui traite le Constat et retourne la Zone_Croquis encodée en base64.

---

## Exigences

### Exigence 1 : Localisation précise de la Case_13

**User Story :** En tant que gestionnaire de sinistres, je veux que le système localise avec précision la Case_13 du Constat, afin d'obtenir uniquement la grille quadrillée sans les champs adjacents.

#### Critères d'acceptation

1. WHEN un Constat valide est fourni à l'Extracteur, THE Extracteur SHALL identifier la région de la Case_13 avec une marge d'erreur inférieure à 5 % de la hauteur et de la largeur de la Case_13.
2. THE Extracteur SHALL utiliser la position structurelle connue de la Case_13 (zone centrale-basse du document, entre 50 % et 85 % de la hauteur et 15 % et 85 % de la largeur) comme hypothèse initiale de recherche.
3. WHEN la détection par analyse de contours échoue, THE Extracteur SHALL utiliser les coordonnées relatives fixes `(x1=0.15·w, y1=0.52·h, x2=0.85·w, y2=0.83·h)` comme recadrage de repli.
4. THE Extracteur SHALL détecter la Case_13 en s'appuyant sur la densité de la Grille_Fond (nombre de transitions alternées clair/foncé dans la région candidate).
5. WHEN plusieurs régions candidates sont détectées, THE Extracteur SHALL sélectionner celle dont le rapport largeur/hauteur est le plus proche de 2,5 et dont la densité de quadrillage est la plus élevée.

---

### Exigence 2 : Robustesse de la détection sur scans de qualité variable

**User Story :** En tant que gestionnaire de sinistres, je veux que le système fonctionne sur des scans de qualité hétérogène, afin que les Constats numérisés dans des conditions variées soient traités correctement.

#### Critères d'acceptation

1. WHEN le Constat présente une luminosité réduite ou une sur-exposition, THE Extracteur SHALL normaliser le contraste de l'image avant la détection.
2. WHEN le Constat est légèrement incliné (rotation inférieure à 5 degrés), THE Extracteur SHALL tout de même extraire la Case_13 avec une précision conforme à l'Exigence 1.1.
3. WHEN la résolution du Constat est comprise entre 72 DPI et 300 DPI, THE Extracteur SHALL produire une Zone_Croquis exploitable (hauteur minimale de 100 pixels, largeur minimale de 200 pixels).
4. IF la résolution du Constat est inférieure à 72 DPI ou si l'image est illisible, THEN THE Extracteur SHALL retourner une erreur descriptive plutôt qu'une Zone_Croquis incorrecte.

---

### Exigence 3 : Traitement post-extraction — Suppression du fond quadrillé

**User Story :** En tant que gestionnaire de sinistres, je veux que le fond quadrillé soit supprimé de la Zone_Croquis, afin que seuls les traits manuscrits des véhicules et routes soient visibles.

#### Critères d'acceptation

1. WHEN une Zone_Croquis est extraite, THE Extracteur SHALL appliquer un filtre morphologique pour supprimer les éléments de la Grille_Fond dont la taille est inférieure à 4 × 4 pixels.
2. WHEN la suppression du fond est appliquée, THE Extracteur SHALL conserver tous les traits du Dessin_Main dont l'épaisseur est supérieure à 2 pixels.
3. THE Extracteur SHALL produire une image résultante en niveaux de gris avec fond blanc et traits foncés (image binaire ou pseudo-binaire).
4. WHEN les traits du Dessin_Main et la Grille_Fond ont des épaisseurs similaires, THE Extracteur SHALL privilégier la conservation des traits plutôt que la suppression du fond.

---

### Exigence 4 : Performance dans le chemin critique de l'API

**User Story :** En tant que développeur backend, je veux que l'extraction complète s'exécute en moins de 2 secondes, afin de ne pas dégrader les temps de réponse de l'API.

#### Critères d'acceptation

1. WHEN l'Extracteur traite un Constat de résolution standard (150 DPI, format A4), THE Extracteur SHALL terminer l'extraction et le traitement en moins de 2 secondes sur un processeur monocœur standard.
2. THE Extracteur SHALL limiter le pipeline de traitement à des opérations OpenCV classiques (pas d'OCR, pas de réseau de neurones) pour garantir la performance.
3. WHEN le Constat est fourni en format PDF, THE Extracteur SHALL convertir uniquement la première page en image avant de lancer la détection.

---

### Exigence 5 : Encodage et transmission au Frontend

**User Story :** En tant que développeur full-stack, je veux que la Zone_Croquis traitée soit encodée en base64 et transmise au Frontend, afin de l'afficher dans le composant « Croquis détecté ».

#### Critères d'acceptation

1. WHEN la Zone_Croquis est produite, THE Extracteur SHALL l'encoder en base64 au format PNG et la retourner dans le champ `imageBase64` de la réponse JSON.
2. THE API SHALL inclure le champ `imageBase64` dans toutes les réponses des endpoints `/api/constats/{id}/croquis` et de l'analyse complète du Constat.
3. WHEN le Frontend reçoit une réponse contenant `imageBase64`, THE Frontend SHALL construire l'URL de source de l'image sous la forme `data:image/png;base64,{imageBase64}` et l'affecter à `croquisImageSrc`.
4. IF `imageBase64` est absent ou vide dans la réponse, THEN THE Frontend SHALL afficher le composant placeholder `sketchPlaceholder` à la place de l'image.

---

### Exigence 6 : Maintenabilité et remplacement de la fonction existante

**User Story :** En tant que développeur backend, je veux que la nouvelle implémentation remplace proprement `_recadrer_zone_croquis()`, afin de maintenir la cohérence du code existant.

#### Critères d'acceptation

1. THE Extracteur SHALL exposer une fonction `_recadrer_zone_croquis(image: np.ndarray) -> np.ndarray` avec la même signature que la fonction existante.
2. THE Extracteur SHALL exposer une fonction `_supprimer_grille_quadrillee(image: np.ndarray) -> np.ndarray` distincte pour le traitement post-extraction, appelable indépendamment.
3. WHEN `_recadrer_zone_croquis()` est appelée, THE Extracteur SHALL retourner une image numpy (BGR ou niveaux de gris) représentant uniquement la Case_13.
4. THE Extracteur SHALL conserver toutes les autres fonctions publiques de `croquis_extraction.py` sans modification de leur signature ni de leur comportement observable.
