#!/bin/bash
# Ετοιμάζει τις φωτογραφίες της γκαλερί «Το μαγαζί μας».
#
# Τρέχει ΤΟΠΙΚΑ και ΧΕΙΡΟΚΙΝΗΤΑ (θέλει macOS `sips` και τον φάκελο των πρωτότυπων,
# που είναι εκτός git). Τα παραγόμενα assets/gallery/*.jpg γίνονται commit — το CI
# δεν ξανατρέχει αυτό το script.
#
# Για αλλαγή φωτογραφίας: άλλαξε τη σειρά στο PHOTOS, τρέξε το script, μετά
# ενημέρωσε το GALLERY στο build.py (όνομα + περιγραφή alt).

set -euo pipefail

SRC="$HOME/Documents/ΜΑΓΕΙΡΕΥΤΟ/ΦΩΤΟ ΦΑΓΗΤΑ"
OUT="$(cd "$(dirname "$0")/.." && pwd)/assets/gallery"
MAX=800         # μεγάλη πλευρά σε px· τα πλακίδια είναι ~230-350 CSS px, αρκεί και σε retina
QUALITY=60      # ~130-150 KB ανά φωτογραφία

# αρχείο πηγής  →  όνομα προορισμού (η σειρά = η σειρά στη σελίδα)
PHOTOS=(
  "merci φαγητά.png|01-vitrina.jpg"
  "IMG20260525123657.jpg|02-gemista.jpg"
  "IMG20260525123654.jpg|03-pastitsio.jpg"
  "IMG20260525122438.jpg|04-giouvetsi.jpg"
  "IMG20260525122713.jpg|05-keftedes.jpg"
  "IMG20260525122506.jpg|06-vitrina-2.jpg"
)

if [ ! -d "$SRC" ]; then
  echo "ΣΦΑΛΜΑ: δεν βρέθηκε ο φάκελος πρωτότυπων: $SRC" >&2
  exit 1
fi

mkdir -p "$OUT"

for entry in "${PHOTOS[@]}"; do
  src="$SRC/${entry%%|*}"
  dst="$OUT/${entry##*|}"
  if [ ! -f "$src" ]; then
    echo "ΣΦΑΛΜΑ: λείπει η φωτογραφία: $src" >&2
    exit 1
  fi
  sips -s format jpeg -s formatOptions "$QUALITY" -Z "$MAX" "$src" --out "$dst" >/dev/null
  printf '%-20s %6s KB\n' "$(basename "$dst")" "$(( $(stat -f%z "$dst") / 1024 ))"
done

echo "Σύνολο: $(du -sh "$OUT" | cut -f1)  ->  $OUT"
