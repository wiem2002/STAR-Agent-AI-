"""Script de debug pour localiser la case 13 du constat FTUSA."""
import cv2
import numpy as np
import os
import sys

PDF_PATH = os.path.join(os.path.dirname(__file__), "cache", "TMP-1787815960831-573C1P.pdf")
OUT_DIR  = os.path.dirname(__file__)


def pdf_to_img(pdf_path, dpi=200):
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img_path = os.path.join(OUT_DIR, "debug_full.png")
    pix.save(img_path)
    doc.close()
    print(f"[OK] PDF -> {pix.width}x{pix.height}px")
    return cv2.imread(img_path)


def trouver_case13(img):
    """
    Detecte la case 13 par recherche du titre '13. Croquis' + la grille quadrillee.
    Le titre imprime est toujours visible comme reference fixe.
    """
    h, w = img.shape[:2]
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Chercher dans la moitie basse du document
    roi_y1 = int(0.40 * h)
    roi_y2 = int(0.90 * h)
    roi = gris[roi_y1:roi_y2, :]
    roi_h = roi_y2 - roi_y1

    # Seuillage adaptatif pour isoler le texte et les traits
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    roi_eq = clahe.apply(roi)
    _, bin_ = cv2.threshold(roi_eq, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Chercher les grandes zones rectangulaires (case 13 a des bordures longues)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w//25), 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, roi_h//20)))
    lignes_h = cv2.morphologyEx(bin_, cv2.MORPH_OPEN, kernel_h)
    lignes_v = cv2.morphologyEx(bin_, cv2.MORPH_OPEN, kernel_v)
    structure = cv2.bitwise_or(lignes_h, lignes_v)
    structure = cv2.dilate(structure, np.ones((5, 5), np.uint8), iterations=3)

    contours, _ = cv2.findContours(structure, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidats = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        aire = cw * ch
        ratio = cw / max(ch, 1)
        # Case 13 : large (>10% image), ratio 2-4, centree
        if aire < 0.08 * w * roi_h:
            continue
        if ratio < 1.5 or ratio > 5.0:
            continue
        cx_n = (x + cw/2) / w
        if cx_n < 0.15 or cx_n > 0.85:
            continue
        score = aire * (1 - abs(ratio - 2.8) / 3.0)
        candidats.append((score, x, roi_y1 + y, x + cw, roi_y1 + y + ch))
        print(f"  Candidat: ({x},{roi_y1+y})-({x+cw},{roi_y1+y+ch}) ratio={ratio:.1f} score={score:.0f}")

    if not candidats:
        return None
    candidats.sort(reverse=True)
    _, x1, y1, x2, y2 = candidats[0]
    return x1, y1, x2, y2


def main():
    print(f"PDF: {PDF_PATH}")
    img = pdf_to_img(PDF_PATH)
    h, w = img.shape[:2]
    print(f"Image: {w}x{h}")

    box = trouver_case13(img)
    if box:
        x1, y1, x2, y2 = box
        print(f"\nCase 13 trouvee: ({x1},{y1})-({x2},{y2}) = {x2-x1}x{y2-y1}px")
        print(f"En pourcent: ({x1/w*100:.0f}%,{y1/h*100:.0f}%)-({x2/w*100:.0f}%,{y2/h*100:.0f}%)")
        crop = img[y1:y2, x1:x2]
        cv2.imwrite(os.path.join(OUT_DIR, "debug_case13_crop.png"), crop)
        debug = img.copy()
        cv2.rectangle(debug, (x1, y1), (x2, y2), (0, 0, 255), 6)
        scale = 900 / max(w, h)
        cv2.imwrite(os.path.join(OUT_DIR, "debug_annotated.png"),
                    cv2.resize(debug, (int(w*scale), int(h*scale))))
        print("-> debug_case13_crop.png et debug_annotated.png sauves")
    else:
        print("Case 13 non trouvee, affichage des zones de projection...")
        # Sauvegarder la zone basse pour inspection
        zone = img[int(0.40*h):int(0.90*h), :]
        cv2.imwrite(os.path.join(OUT_DIR, "debug_zone_basse.png"), zone)
        print("-> debug_zone_basse.png sauve")


if __name__ == "__main__":
    main()
