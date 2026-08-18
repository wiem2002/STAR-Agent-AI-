# STAR Assurances — Agent IA Barème FTUSA

Interface Angular 18 (standalone components) répliquant le tableau de bord
"Agent IA – Détermination du barème FTUSA", avec palette verte STAR et
architecture `core/` (models, services) + `shared/` (composants réutilisables)
+ `features/dashboard/` (les 10 panneaux de l'interface).

## Installation

```bash
npm install
npm start
```

L'application démarre sur http://localhost:4200

## Structure du projet

```
src/app/
  core/
    models/        → interfaces TypeScript (Dossier, Circonstance, AnalyseIA...)
    services/       → services avec données mock (DossierService, AnalyseIaService, StatistiqueService)
  shared/
    components/
      sidebar/       → menu latéral desktop
      topbar/         → barre supérieure (titre, notifications, utilisateur)
      panel-card/     → carte numérotée réutilisable pour chaque panneau
      mobile-nav/     → aperçu du menu mobile (panneau 10)
  features/
    dashboard/
      dashboard.component.ts    → grille assemblant les 10 panneaux
      components/
        tableau-de-bord/          → 1. KPIs + répartition + top cas FTUSA
        nouveau-dossier/           → 2. formulaire à onglets
        analyse-ia-cours/          → 3. stepper + aperçus (constat, croquis, photos)
        circonstances-constat/     → 4. cases à cocher véhicule A/B + autres éléments
        resultat-analyse/          → 5. cas proposé, justification, responsabilités
        details-techniques/        → 6. métadonnées de l'analyse
        validation-gestionnaire/   → 7. décision, responsabilités, commentaire
        historique-dossiers/       → 8. tableau des dossiers traités
        statistiques-ftusa/        → 9. répartition des cas + évolution précision
        interface-mobile/          → 10. aperçu du menu mobile
```

## Notes

- Toutes les données affichées sont des données mock renvoyées par les
  services de `core/services/` via des `Observable` (`of(...)`), prêtes à être
  remplacées par de vrais appels HTTP (`HttpClient`) vers votre API.
- Les graphiques (donut, barres, courbe) sont construits en CSS/SVG pur —
  aucune dépendance externe de charting n'est nécessaire.
- La palette est définie en variables CSS dans `src/styles.scss`
  (`--star-green-*`, `--star-amber`, `--star-red`, `--star-slate`).
