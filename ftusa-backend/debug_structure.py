"""Analyse la structure du constat pour trouver les coordonnees de la case 13."""
import cv2
import numpy as np
import os

PDF_PATH = os.path.join(os.path.dirname(__file__), "cache", "TMP-1787815960831-573C1P.pdf")
OUT_DIR  = os.path.dirname(__file__)


def main():
    import fitz
    doc = fitz.open(PDF_PATH)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(200/72, 200/72))
    img_path = os.path.join(OUT_DIR, "debug_full.png")
    pix.save(img_path)
    doc.close()

    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    print(f"Image: {w}x{h}")

    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gris = clahe.apply(gris)

    # Sauvegarder des tranches verticales pour inspection visuelle
    slices = [
        (0.45, 0.55, "slice_45_55"),
        (0.50, 0.60, "slice_50_60"),
        (0.55, 0.65, "slice_55_65"),
        (0.58, 0.68, "slice_58_68"),
        (0.60, 0.72, "slice_60_72"),
        (0.62, 0.75, "slice_62_75"),
        (0.65, 0.78, "slice_65_78"),
        (0.68, 0.80, "slice_68_80"),
    ]
    for y1p, y2p, name in slices:
        y1, y2 = int(y1p*h), int(y2p*h)
        crop = img[y1:y2, :]
        cv2.imwrite(os.path.join(OUT_DIR, f"debug_{name}.png"), crop)
        print(f"{name}: y={y1}-{y2} ({y1/h*100:.0f}%-{y2/h*100:.0f}%)")

    # Analyse de la projection horizontale (lignes foncees = bordures)
    _, bin_ = cv2.threshold(gris, 100, 255, cv2.THRESH_BINARY_INV)
    proj_h = np.sum(bin_, axis=1) / 255
    print("\nLignes avec beaucoup de pixels fonces (bordures horizontales):")
    for y in range(int(0.45*h), int(0.85*h)):
        if proj_h[y] > w * 0.35:
            print(f"  y={y} ({y/h*100:.1f}%) : {int(proj_h[y])} px ({proj_h[y]/w*100:.0f}%)")


if __name__ == "__main__":
    main()
