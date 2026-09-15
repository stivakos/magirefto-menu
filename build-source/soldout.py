#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Γράφει το soldout.json — τι τελείωσε σήμερα. Το καλεί το soldout.yml.

Η είσοδος έρχεται από τη σελίδα του tablet (/tablet/), που στέλνει ΟΛΗ τη
λίστα κάθε φορά, όχι «πάτησα το Χ». Έτσι δύο γρήγορα πατήματα δεν πατάνε το
ένα το άλλο: όποιο αίτημα φτάσει τελευταίο έχει την πλήρη εικόνα του tablet.

    python3 soldout.py --date 2026-09-14 --items "menu-hmeras:8,synodeytika:2" \
                       --few "menu-hmeras:16=2,glyka:3=1"

--items = τελείωσαν. --few = «τελευταίες μερίδες»: πόσες έμειναν (2 ή 1), μόνο
για τις κατηγορίες του FEW_SLUGS (απόφαση ιδιοκτήτη 15/9/2026 — στα συνοδευτικά
και στα ποτά μόνο «τελείωσε»). Ο πελάτης δεν βλέπει τον αριθμό· τον χρειάζεται
το όριο του καλαθιού.

Κλειδί πιάτου = slug + Α/Α, όπως στο menu.json. Όχι όνομα: το «σνίτσελ» θα
ήθελε ξανά αναγνώριση, με ό,τι ασάφεια φέρνει, για κάτι που το tablet ήδη ξέρει.

ΔΕΝ ξαναχτίζει το site. Η σελίδα διαβάζει το soldout.json όταν ανοίγει, οπότε
ένα «τελείωσε» μέσα στη βάρδια δεν αγγίζει ούτε το index.html ούτε την εικόνα
των social ούτε την έγκριση δημοσίευσης.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MENU_JSON = os.path.join(HERE, "..", "menu.json")
OUT = os.path.join(HERE, "..", "soldout.json")
KEY = re.compile(r"^[a-z][a-z-]{0,30}:\d{1,4}$")
FEW_SLUGS = {"menu-hmeras", "salates", "glyka"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="date_iso του μενού, όπως το είδε το tablet")
    ap.add_argument("--items", default="", help="slug:aa χωρισμένα με κόμμα· κενό = όλα διαθέσιμα")
    ap.add_argument("--few", default="", help="slug:aa=2 ή =1, χωρισμένα με κόμμα")
    a = ap.parse_args()

    menu = json.load(open(MENU_JSON, encoding="utf-8"))
    # Tablet που έμεινε στο χθεσινό μενού δεν γράφει πάνω στο σημερινό. Το
    # tablet το καταλαβαίνει μόνο του: δεν βλέπει ποτέ το «✓ στο site».
    if a.date != menu.get("date_iso"):
        sys.exit(f"!! Το tablet έστειλε για {a.date!r}, το μενού είναι για "
                 f"{menu.get('date_iso')!r}. Δεν γράφτηκε τίποτα.")

    names = {f'{c["slug"]}:{it["aa"]}': it["name"]
             for c in menu.get("categories", []) for it in c["items"]}
    items, skipped = [], []
    for tok in (t.strip() for t in a.items.split(",")):
        if not tok:
            continue
        if KEY.match(tok) and tok in names:
            if tok not in items:
                items.append(tok)
        else:
            skipped.append(tok)
    # Άγνωστο κλειδί (πιάτο που έφυγε από το μενού μέσα στη μέρα) αγνοείται και
    # δεν ρίχνει τα υπόλοιπα: μέσα στη βάρδια μετράει να περάσει ό,τι ισχύει.
    for tok in skipped:
        print(f"-- αγνοήθηκε: {tok[:40]!r} (δεν είναι στο σημερινό μενού)")

    few = {}
    for tok in (t.strip() for t in a.few.split(",")):
        if not tok:
            continue
        key, _, n = tok.partition("=")
        # Ό,τι τελείωσε δεν είναι και «λίγο»: αν έρθουν και τα δύο, κερδίζει το
        # τελείωσε — το ασφαλές για τον πελάτη.
        if (KEY.match(key) and key in names and n in ("1", "2")
                and key.split(":")[0] in FEW_SLUGS and key not in items):
            few[key] = int(n)
        else:
            print(f"-- αγνοήθηκε (λίγες μερίδες): {tok[:40]!r}")

    items.sort()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"date_iso": a.date, "items": items,
                   "few": dict(sorted(few.items()))}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    summary = ", ".join(names[k] for k in items) or "όλα διαθέσιμα"
    if few:
        summary += " · λίγες: " + ", ".join(f"{names[k]} ({n})" for k, n in sorted(few.items()))
    print(f"Τελείωσαν: {summary}")
    # πρώτη γραμμή του commit — το workflow τη διαβάζει από εδώ
    msg = os.environ.get("COMMIT_MSG_FILE")
    if msg:
        with open(msg, "w", encoding="utf-8") as f:
            f.write(f"Τελείωσαν ({a.date}): {summary}"[:200] + "\n")


if __name__ == "__main__":
    main()
