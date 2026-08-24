"""
Script de debug pour tester l'extraction du croquis sur un PDF ou image.

Usage :
    python debug_croquis.py test_constat.pdf
    python debug_croquis.py test_constat.pdf --circ-a 12 13 --circ-b 9
"""

import sys
import argparse
import cv2
import numpy as np
import croquis_extraction as cx


def main():
    parser = argparse.ArgumentParser(description="Debug extraction croquis FTUSA")
    parser.add_argument("fichier", help="Chemin vers le PDF ou image")
    parser.add_argument("--circ-a", nargs="*", type=int, default=[], metavar="N",
                        help="Circonstances cochées pour A (ex: 12 13)")
    parser.add_argument("--circ-b", nargs="*", type=int, default=[], metavar="N",
                        help="Circonstances cochées pour B (ex: 9 10)")
    parser.add_argument("--save", default="debug_croquis_result.png",
                        help="Fichier de sortie pour visualiser (défaut: debug_croquis_result.png)")
    args = parser.parse_args()

    with open(args.fichier, "rb") as f:
        data = f.read()

    print(f"Fichier : {args.fichier}")
    print(f"Circ A  : {args.circ_a}")
    print(f"Circ B  : {args.circ_b}")
    print()

    # 1. Extraire l'image de la case 13
    image = cx._normaliser_bytes_vers_image(data)
    zone = cx._recadrer_zone_croquis(image)

    # 2. Analyse CV
    h, w = zone.shape[:2]
    zone_bin = cx._supprimer_grille_pointillee(zone)
    segments = cx._extraire_segments_route(zone_bin, w, h)
    type_cv, conf_cv = cx._analyser_topologie(segments, w, h)
    print(f"[CV]  type={type_cv}  confiance={conf_cv:.2f}  segments={len(segments)}")

    # 3. Affinage avec circonstances
    type_final, conf_final = cx._affiner_avec_circonstances(
        type_cv, conf_cv, args.circ_a, args.circ_b
    )
    print(f"[FIN] type={type_final}  confiance={conf_final:.2f}")

    # 4. Visualisation : dessine les segments détectés sur la case 13
    vis = zone.copy()
    for x1, y1, x2, y2 in segments:
        cv2.line(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

    # Ajoute le label
    cv2.putText(vis, f"{type_final} ({conf_final:.0%})", (8, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # Côte à côte : original | binaire | segments
    zone_bin_color = cv2.cvtColor(zone_bin, cv2.COLOR_GRAY2BGR)
    combined = np.hstack([
        cv2.resize(zone,          (w, h)),
        cv2.resize(zone_bin_color, (w, h)),
        cv2.resize(vis,            (w, h)),
    ])
    cv2.imwrite(args.save, combined)
    print(f"\nVisualisation sauvée → {args.save}")
    print("  Colonne 1 : image originale de la case 13")
    print("  Colonne 2 : après suppression grille (binaire)")
    print("  Colonne 3 : segments routiers détectés (vert) + résultat")


if __name__ == "__main__":
    main()
