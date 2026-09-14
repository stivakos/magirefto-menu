#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Γράφει το soldout.json — τι τελείωσε σήμερα. Το καλεί το soldout.yml.

Η είσοδος έρχεται από τη σελίδα του tablet (/tablet/), που στέλνει ΟΛΗ τη
λίστα κάθε φορά, όχι «πάτησα το Χ». Έτσι δύο γρήγορα πατήματα δεν πατάνε το
ένα το άλλο: όποιο αίτημα φτάσει τελευταίο έχει την πλήρη εικόνα του tablet.

    python3 soldout.py --date 2026-09-14 --items "menu-hmeras:8,synodeytika:2"

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="date_iso του μενού, όπως το είδε το tablet")
    ap.add_argument("--items", default="", help="slug:aa χωρισμένα με κόμμα· κενό = όλα διαθέσιμα")
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

    items.sort()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"date_iso": a.date, "items": items}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    summary = ", ".join(names[k] for k in items) or "όλα διαθέσιμα"
    print(f"Τελείωσαν: {summary}")
    # πρώτη γραμμή του commit — το workflow τη διαβάζει από εδώ
    msg = os.environ.get("COMMIT_MSG_FILE")
    if msg:
        with open(msg, "w", encoding="utf-8") as f:
            f.write(f"Τελείωσαν ({a.date}): {summary}"[:200] + "\n")


if __name__ == "__main__":
    main()
