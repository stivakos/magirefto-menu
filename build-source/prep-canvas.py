#!/usr/bin/env python3
"""Ετοιμάζει τον καμβά του μαυροπίνακα για τις εικόνες των social.

Τρέχει ΤΟΠΙΚΑ και ΧΕΙΡΟΚΙΝΗΤΑ (θέλει Pillow και τη φωτογραφία του άδειου
μαυροπίνακα, που είναι εκτός git). Το παραγόμενο assets/social/slate.jpg
γίνεται commit — το social.py διαβάζει μόνο αυτό.

Η πρωτότυπη φωτογραφία είναι πολύ φωτεινή (μέση φωτεινότητα ~119): η λευκή
κιμωλία πάνω της δεν ξεχωρίζει. Εδώ σκουραίνει και παίρνει βινιέτα, ώστε το
κείμενο να διαβάζεται και στη μέση και στις γωνίες.
"""
import os

from PIL import Image, ImageEnhance, ImageStat, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Documents/ΜΑΓΕΙΡΕΥΤΟ/Μαγειρευτό Μαυροπίνακας ΚΕΝΟ.jpg")
OUT = os.path.join(HERE, "..", "assets", "social", "slate.jpg")

# Η καθαρή σχιστόλιθος μέσα στην κορνίζα, ήδη σε λόγο 4:5 (Instagram feed).
# Έξω από αυτό το παράθυρο μπαίνουν κορνίζα, παράθυρο και πάτωμα.
CROP = (420, 620, 2520, 3245)
SIZE = (1080, 1350)
DARKEN = 0.46          # στοχεύουμε μέση φωτεινότητα ~55
VIGNETTE = 0.55        # πόσο σκουραίνουν οι γωνίες


def main():
    if not os.path.isfile(SRC):
        raise SystemExit(f"ΣΦΑΛΜΑ: δεν βρέθηκε η φωτογραφία: {SRC}")

    im = Image.open(SRC).crop(CROP).resize(SIZE, Image.LANCZOS).convert("RGB")
    im = ImageEnhance.Brightness(im).enhance(DARKEN)
    im = ImageEnhance.Contrast(im).enhance(1.12)

    # βινιέτα: μαύρη μάσκα με φωτεινό οβάλ στο κέντρο, πολύ θολωμένη
    w, h = SIZE
    mask = Image.new("L", SIZE, 0)
    ImageDraw.Draw(mask).ellipse(
        (-w * 0.15, -h * 0.10, w * 1.15, h * 1.10), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w * 0.18))
    dark = ImageEnhance.Brightness(im).enhance(1 - VIGNETTE)
    im = Image.composite(im, dark, mask)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT, quality=86, optimize=True)

    mean = ImageStat.Stat(im.convert("L")).mean[0]
    print(f"{os.path.relpath(OUT, os.path.join(HERE, '..'))}  "
          f"{im.size[0]}×{im.size[1]}  {os.path.getsize(OUT) // 1024} KB  "
          f"μέση φωτεινότητα {mean:.0f}")


if __name__ == "__main__":
    main()
