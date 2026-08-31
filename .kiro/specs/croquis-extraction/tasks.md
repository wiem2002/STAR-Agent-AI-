# Plan d'implémentation — Extraction de la Case 13 (Croquis de l'Accident)

## Vue d'ensemble

Réécriture ciblée de `ftusa-backend/croquis_extraction.py` pour corriger le recadrage de la case 13 en utilisant une détection par densité de grille et des coordonnées de repli robustes, suivie d'une amélioration du post-traitement morphologique.

## Tâches

- [x] 1. Implémenter la normalisation de contraste
  - Ajouter la fonction `_normaliser_contraste(image: np.ndarray) -> np.ndarray` dans `croquis_extraction.py`
  - Utiliser CLAHE (`cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))`)
  - Gérer les entrées BGR (3 canaux) et niveaux de gris (1 canal)
  - _Exigences : 2.1_

- [ ] 2. Réécrire `_detecter_boite_croquis()` avec détection par densité de grille
  - [ ] 2.1 Implémenter la détection des régions candidates
    - Restreindre la recherche à la bande verticale [50 %, 85 %] de la hauteur de l'image
    - Appliquer `_normaliser_contraste` avant la détection
    - Utiliser Canny + `findContours` avec filtres : surface ≥ 8 % de l'image, ratio largeur/hauteur entre 1.8 et 3.5, centre horizontal entre 20 % et 80 %
    - _Exigences : 1.1, 1.2, 2.2, 2.3_

  - [ ] 2.2 Implémenter le scoring par densité de grille
    - Pour chaque région candidate, calculer la densité de grille : variance locale normalisée sur un sous-échantillon de la région
    - Scorer chaque candidat : `score = densité_grille × (1 - |ratio - 2.5| / 2.0)`
    - Retourner la boîte englobante du candidat avec le score le plus élevé, ou `None` si aucun candidat
    - _Exigences : 1.4, 1.5_

  - [ ]* 2.3 Écrire le test par propriétés P3 — Scoring du candidat
    - **Property 3 : Scoring du candidat le mieux adapté**
    - **Validates: Requirements 1.5**
    - Générer des listes de candidats avec ratios et densités connus, vérifier que le bon est sélectionné
    - `Feature: croquis-extraction, Property 3: Scoring du candidat le mieux adapté`

- [ ] 3. Réécrire `_recadrer_zone_croquis()` avec repli robuste
  - Appeler `_detecter_boite_croquis(image)`
  - Si `None`, utiliser `(x1=0.15·w, y1=0.52·h, x2=0.85·w, y2=0.83·h)` comme repli
  - Appliquer un rognage des marges : 2 % horizontal, 3 % vertical haut, 1 % bas
  - Appeler `_clip_box` pour garantir des coordonnées dans les limites de l'image
  - _Exigences : 1.1, 1.3, 2.2, 2.3_

  - [ ]* 3.1 Écrire le test par propriétés P1 — Précision de la détection
    - **Property 1 : Précision de la détection sur images de qualité variable**
    - **Validates: Requirements 1.1, 2.1, 2.2, 2.3**
    - Générer des images synthétiques avec un rectangle de grille connu, varier luminosité/rotation/résolution, vérifier IoU ≥ 0.85
    - `Feature: croquis-extraction, Property 1: Précision de la détection sur images de qualité variable`

  - [ ]* 3.2 Écrire le test de cas limite P2 — Repli sur image uniforme
    - **Property 2 : Repli sur coordonnées fixes en cas d'échec**
    - **Validates: Requirements 1.3**
    - Fournir une image uniforme, vérifier que les dimensions de sortie correspondent au repli ±2 px
    - `Feature: croquis-extraction, Property 2: Repli sur image uniforme`

- [ ] 4. Checkpoint — Vérifier que le recadrage est visuellement correct
  - Exécuter `extraire_image_croquis()` sur `test_constat.pdf` et sauvegarder le résultat en PNG pour inspection visuelle
  - S'assurer que tous les tests existants passent, signaler toute question à l'utilisateur

- [ ] 5. Réécrire `_supprimer_grille_quadrillee()` (post-traitement morphologique)
  - Renommer `_supprimer_grille_pointillee` en `_supprimer_grille_quadrillee` dans `croquis_extraction.py`
  - Mettre à jour tous les appels internes à cette fonction
  - Implémenter le pipeline : seuillage adaptatif → `MORPH_OPEN` (noyau elliptique 2×2) → `MORPH_CLOSE` (noyau 3×3)
  - Retourner une image binaire (fond blanc 255, traits 0)
  - _Exigences : 3.1, 3.2, 3.3_

  - [ ]* 5.1 Écrire le test par propriétés P4 — Suppression de la grille de fond
    - **Property 4 : Suppression des éléments de grille de fond**
    - **Validates: Requirements 3.1**
    - Générer une image de points réguliers ≤ 4×4 px, vérifier que ≥ 95 % des pixels sont blancs après traitement
    - `Feature: croquis-extraction, Property 4: Suppression des éléments de grille`

  - [ ]* 5.2 Écrire le test par propriétés P5 — Conservation des traits et format de sortie
    - **Property 5 : Conservation des traits manuscrits et format de sortie**
    - **Validates: Requirements 3.2, 3.3**
    - Générer une image avec des lignes ≥ 3 px sur fond quadrillé, vérifier que les lignes restent foncées et que la sortie est en niveaux de gris
    - `Feature: croquis-extraction, Property 5: Conservation des traits`

- [ ] 6. Vérifier l'encodage base64 et les fonctions publiques de l'API
  - S'assurer que `extraire_image_croquis()`, `extraire_croquis_depuis_image()`, `extraire_croquis_rapide()` et `extraire_croquis()` appellent bien `_recadrer_zone_croquis()` réécrite
  - Vérifier que la réponse JSON contient toujours `imageBase64` non vide
  - _Exigences : 5.1, 5.2, 6.1, 6.4_

  - [ ]* 6.1 Écrire le test par propriétés P6 — Aller-retour base64
    - **Property 6 : Aller-retour de l'encodage base64**
    - **Validates: Requirements 5.1**
    - Pour toute image numpy, vérifier que `base64 → decode → png_decode` produit une image de dimensions identiques avec PSNR ≥ 40 dB
    - `Feature: croquis-extraction, Property 6: Aller-retour base64`

  - [ ]* 6.2 Écrire le test unitaire de non-régression des symboles publics
    - Vérifier que `croquis_extraction` exporte bien tous les symboles publics attendus
    - _Exigences : 6.4_

- [ ] 7. Checkpoint final — Tous les tests doivent passer
  - Exécuter la suite de tests complète
  - S'assurer que l'API retourne une Zone_Croquis correctement recadrée sur `test_constat.pdf`
  - Signaler toute question à l'utilisateur avant de conclure

## Notes

- Les tâches marquées `*` sont optionnelles et peuvent être ignorées pour un MVP rapide
- Chaque tâche référence les exigences pour la traçabilité
- La bibliothèque de tests par propriétés utilisée est `hypothesis`
- Aucun nouveau modèle ML ni nouvelle dépendance externe n'est introduit
