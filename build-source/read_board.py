#!/usr/bin/env python3
"""Διαβάζει φωτογραφία μαυροπίνακα — ή σκέτο κείμενο — και γράφει το μενού.

    python3 read_board.py ../menu-photo.jpg
    python3 read_board.py --text ../menu-text.txt

Ο ιδιοκτήτης φωτογραφίζει τον πίνακα που έχει ήδη γράψει με το χέρι. Αυτό το
σενάριο τον διαβάζει και ενημερώνει το `menu-today.txt` — τίποτε άλλο.

Με `--text` δεν καλείται μοντέλο καθόλου: το κείμενο το γράφει ο ίδιος, σωστά.
Το μοντέλο υπάρχει επειδή η κιμωλία είναι χειρόγραφη, όχι επειδή χρειάζεται
ερμηνεία — ο resolver παρακάτω είναι ο ίδιος και στις δύο περιπτώσεις. Το
κείμενο αφορά **αύριο**: το γράφεις το βράδυ για την επόμενη μέρα.

ΤΟ ΜΟΝΤΕΛΟ ΚΑΝΕΙ ΜΟΝΟ ΑΝΑΓΝΩΣΗ. Γυρίζει ονόματα πιάτων όπως είναι γραμμένα
στην κιμωλία· ΔΕΝ του ζητείται ποτέ Α/Α και δεν βλέπει τον κατάλογο. Ποιο πιάτο
είναι ποιο το αποφασίζει το `dish_names.py` — ο ίδιος κώδικας που τρέχει στο
build και στον έλεγχο. Έτσι ένα «μπάμιες» σκέτο σταματά τη ροή, όπως ακριβώς
σταματά κι όταν το γράφει ο ιδιοκτήτης με το χέρι, αντί να μαντέψει πιάτο.

Αν του δίναμε τον κατάλογο, θα «κόλλαγε» ό,τι διαβάζει στο πλησιέστερο γνωστό
όνομα — και ένα καινούργιο πιάτο θα εμφανιζόταν σιωπηλά ως κάποιο άλλο.

Χωρίς ANTHROPIC_API_KEY τυπώνει τι θα έκανε και βγαίνει με 0.
"""
import base64
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import build          # ο guard __main__ του build.py το κρατά αβλαβές (βλ. social.py)
import dish_names
import menu_date
from menu_date import GREEK_DAYS

MODEL = os.environ.get("BOARD_MODEL", "claude-opus-5")
TAB = "Μενού Ημέρας"          # ο μαυροπίνακας γράφει ΜΟΝΟ μαγειρευτά
ALIASES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "board-aliases.txt")
ATHENS = ZoneInfo("Europe/Athens")

PROMPT = """Αυτή είναι φωτογραφία του μαυροπίνακα ενός μαγαζιού με μαγειρευτό
φαγητό. Κατέγραψε ΑΚΡΙΒΩΣ τα πιάτα που είναι γραμμένα, με τη σειρά που
εμφανίζονται.

Κανόνες:
- Γράψε το όνομα όπως ακριβώς είναι στην κιμωλία. Μη διορθώσεις ορθογραφία, μη
  συμπληρώσεις λέξεις που δεν βλέπεις, μη μεταφράσεις.
- Μην παραλείψεις πιάτο και μην προσθέσεις πιάτο που δεν βλέπεις.
- Αγνόησε την επικεφαλίδα («Merci Menu», «Merci μενού») και το «Καλή σας όρεξη».
- Η τιμή είναι ο αριθμός δίπλα στο πιάτο (π.χ. «7,00» -> 7.00). Αν δεν
  διαβάζεται ή δεν υπάρχει, βάλε null.
- Αν μια γραμμή ενώνει δύο πιάτα με κάθετο (π.χ. «Μπακαλιάρος/Γλώσσα»), γράψ'
  την όπως είναι, σε μία εγγραφή.
- Αν κάτι δεν διαβάζεται καθόλου, γράψε το όσο το διαβάζεις· μη μαντέψεις.
- Είναι ΧΕΙΡΟΓΡΑΦΗ ελληνική κιμωλία. Γράμματα μπερδεύονται εύκολα: σ/β/ς,
  υ/ν, θ/σ, ρ/ο. Πριν γράψεις μια λέξη, έλεγξε ότι είναι ΥΠΑΡΚΤΗ ελληνική
  λέξη. Αν σου βγαίνει ανύπαρκτη λέξη («Κοτόβουπα»), ξανακοίταξε το γράμμα
  που δεν ταιριάζει — σχεδόν πάντα είναι λάθος ανάγνωσης, όχι λάθος του
  πίνακα. Διορθώνεις ΜΟΝΟ γράμματα που παρανόησες· δεν αλλάζεις πιάτο, δεν
  προσθέτεις λέξεις που δεν βλέπεις."""

SCHEMA = {
    "type": "object",
    "properties": {
        "dishes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": ["number", "null"]},
                },
                "required": ["name", "price"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["dishes"],
    "additionalProperties": False,
}


def read_photo(path):
    """Στέλνει την εικόνα στο μοντέλο και γυρίζει [(όνομα, τιμή), ...]."""
    import anthropic

    media = mimetypes.guess_type(path)[0] or "image/jpeg"
    if media not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        raise SystemExit(f"!! Μη υποστηριζόμενος τύπος εικόνας: {media}")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("ascii")

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media, "data": data}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return [(d["name"].strip(), d["price"]) for d in json.loads(text)["dishes"]]


_BULLET = re.compile(r"^\s*(?:[-–—*•]|\d+[.)])\s+")


def read_text(body):
    """Πιάτα από σκέτο κείμενο. Γυρίζει ([(όνομα, None), ...], γραμμή ημερομηνίας).

    Χωρίζει ΜΟΝΟ σε γραμμές και κόμματα — ποτέ σε κάθετο: «Μπακαλιάρος/Γλώσσα»
    είναι ένα πιάτο, όπως ακριβώς και στον πίνακα.

    Τιμή δεν διαβάζεται. Στη φωτογραφία χρησίμευε μόνο για την προειδοποίηση
    «ο πίνακας γράφει άλλη τιμή από το DAILY_MENU.xlsx»· οι τιμές του site
    βγαίνουν ούτως ή άλλως από το xlsx, ποτέ από εδώ.

    Η ημερομηνία είναι **αύριο**, γιατί αυτό είναι το νόημα του κειμένου: το
    στέλνεις σήμερα για την επόμενη μέρα. Μπορείς να τη δηλώσεις ρητά σε πρώτη
    γραμμή («Τρίτη 1/9»), οπότε κερδίζει αυτή — έτσι γράφεις και για σήμερα.
    """
    lines = [l.strip() for l in body.replace("\r\n", "\n").split("\n")]
    lines = [l for l in lines if l and not l.startswith("#")]

    # Πρώτη γραμμή ΧΩΡΙΣ κόμμα που διαβάζεται ως ημερομηνία = δήλωση ημέρας. Το
    # κόμμα είναι ο διαχωριστής των πιάτων, άρα γραμμή με κόμμα είναι λίστα — και
    # χωρίς αυτόν τον όρο ένα «1/2 κοτόπουλο» μέσα στη λίστα θα την κατάπινε όλη.
    day = None
    if lines and "," not in lines[0]:
        day = menu_date.parse(lines[0])
        if day is not None:
            lines.pop(0)
    if day is None:
        day = datetime.now(ATHENS).date() + timedelta(days=1)

    dishes = []
    for line in lines:
        for part in _BULLET.sub("", line).split(","):
            part = part.strip()
            if part:
                dishes.append((part, None))
    return dishes, day_line(day)


def aliases():
    """Το λεξικό συντομογραφιών του μαγαζιού: {κανονικοποιημένο κείμενο: Α/Α}.

    Ο πίνακας γράφει «Φιλέτο κοτόπουλο», που στη βάση είναι δύο πιάτα (#40 και
    #54). Καμία αυτόματη λογική δεν μπορεί να το λύσει — και δεν πρέπει να το
    μαντέψει. Το λύνει ο ιδιοκτήτης, μία φορά, γραπτώς.
    """
    out = {}
    if not os.path.isfile(ALIASES):
        return out
    for i, line in enumerate(open(ALIASES, encoding="utf-8"), 1):
        line = line.split("#")[0].strip()
        if not line:
            continue
        if "=" not in line:
            raise SystemExit(f"!! board-aliases.txt γραμμή {i}: λείπει το «=».")
        text, num = line.rsplit("=", 1)
        if not num.strip().isdigit():
            raise SystemExit(f"!! board-aliases.txt γραμμή {i}: "
                             f"το «{num.strip()}» δεν είναι αριθμός πιάτου.")
        out[dish_names.sound(dish_names.norm(text))] = int(num)
    return out


def resolve(read, rows):
    """Ονόματα -> Α/Α, με το dish_names. Γυρίζει (νούμερα, σφάλματα, τιμές)."""
    alias = aliases()
    nums, errors, prices = [], [], []
    for name, price in read:
        aa = alias.get(dish_names.sound(dish_names.norm(name)))
        err = None
        if aa is None:
            aa, err = dish_names.resolve(name, rows, where="στο DAILY_MENU.xlsx")
        elif aa not in rows:
            err = f"το board-aliases.txt δείχνει στο #{aa}, που δεν υπάρχει."
        if err:
            errors.append(f"«{name}»: {err}")
            continue
        if aa in nums:                       # ο πίνακας γράφει κάτι δύο φορές
            continue
        nums.append(aa)
        prices.append((aa, rows[aa][0], rows[aa][1], price))
    return nums, errors, prices


def day_line(d):
    """«Δευτέρα 31/8/26» — η μορφή που ξαναδιαβάζουν menu_date.py και check.py."""
    return f"{GREEK_DAYS[d.weekday()]} {d.day}/{d.month}/{d:%y}"


def today_line():
    return day_line(datetime.now(ATHENS).date())


def write_menu(names, date_line):
    """Γράφει τη γραμμή «Μενού Ημέρας», την ημερομηνία, και ανοίγει το μαγαζί."""
    path = build.MENU_TXT
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    out, seen_menu, seen_date = [], False, False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("ΚΛΕΙΣΤΑ:"):
            continue                          # στέλνεις μενού => έχεις ανοιχτά
        if stripped.startswith("ΗΜΕΡΟΜΗΝΙΑ:"):
            out.append(f"ΗΜΕΡΟΜΗΝΙΑ: {date_line}")
            seen_date = True
            continue
        if re.match(r"^Μενού Ημέρας\s*:", stripped):
            out.append("Μενού Ημέρας: " + ", ".join(names))
            seen_menu = True
            continue
        out.append(line)

    if not seen_date or not seen_menu:
        raise SystemExit("!! Το menu-today.txt δεν έχει γραμμή "
                         f"{'ΗΜΕΡΟΜΗΝΙΑ' if not seen_date else 'Μενού Ημέρας'} "
                         "— δεν το πειράζω.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    text_mode = "--text" in sys.argv
    src = args[0] if args else os.path.join(
        build.HERE, "..", "menu-text.txt" if text_mode else "menu-photo.jpg")
    if not os.path.isfile(src):
        raise SystemExit(f"!! Δεν βρήκα {'το κείμενο' if text_mode else 'την εικόνα'}: {src}")

    rows = build._tab_rows(TAB)

    if text_mode:
        # Καμία κλήση μοντέλου, άρα ούτε κλειδί — τρέχει και τοπικά όπως είναι.
        with open(src, encoding="utf-8") as f:
            read, date_line = read_text(f.read())
        if not read:
            raise SystemExit("!! Δεν βρήκα κανένα πιάτο στο κείμενο. Γράψε τα "
                             "ονόματα χωρισμένα με κόμμα.")
    else:
        date_line = today_line()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("— ΣΤΕΓΝΗ ΔΟΚΙΜΗ (λείπει το ANTHROPIC_API_KEY) —")
            print(f"  εικόνα:     {src}")
            print(f"  μοντέλο:    {MODEL}")
            print(f"  ημερομηνία: {date_line}")
            print(f"  κατάλογος:  {len(rows)} πιάτα στο tab «{TAB}»")
            return 0
        read = read_photo(src)
        if not read:
            raise SystemExit("!! Δεν διάβασα κανένα πιάτο. Ξαναβγάλε τη φωτογραφία "
                             "πιο κοντά και με τον πίνακα ίσιο στο κάδρο.")

    nums, errors, prices = resolve(read, rows)
    if errors:
        print("Διάβασα από " + ("το κείμενο:" if text_mode else "τον πίνακα:"))
        for name, price in read:
            print(f"  · {name}" + (f" — {price}" if price is not None else ""))
        print()
        raise SystemExit(
            "!! Δεν μπόρεσα να αντιστοιχίσω:\n  ✗ "
            + "\n  ✗ ".join(errors)
            + "\n\nΤο μενού ΔΕΝ άλλαξε — το site μένει όπως ήταν.\n"
            + ("Γράψε το πλήρες όνομα του πιάτου και ξαναστείλ' το."
               if text_mode else
               "Αν ο πίνακας το γράφει έτσι κάθε φορά, πρόσθεσε μια γραμμή στο "
               "board-aliases.txt (π.χ. «φιλέτο κοτόπουλο = 40»)."))

    names = [rows[n][0] for n in nums]
    write_menu(names, date_line)

    print(f"✓ {date_line} — {len(names)} πιάτα:\n")
    for aa, name, base_price, board_price in prices:
        mark = ""
        if board_price is not None and base_price is not None \
                and abs(float(board_price) - float(base_price)) > 0.001:
            mark = f"   ⚠ ο πίνακας γράφει {board_price:.2f} αντί για {base_price:.2f}"
        print(f"  #{aa:<3} {name}{mark}")
    if any(p[3] is not None and p[2] is not None
           and abs(float(p[3]) - float(p[2])) > 0.001 for p in prices):
        print("\nΟι τιμές του site ΔΕΝ άλλαξαν — αυτές ζουν στο DAILY_MENU.xlsx.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
