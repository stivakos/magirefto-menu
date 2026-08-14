#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Πιάτα που τελείωσαν μέσα στη μέρα.

    python3 soldout.py "μουσακάς"        # τελείωσε
    python3 soldout.py "ξανά μουσακάς"   # επανήλθε
    python3 soldout.py "καθάρισε"        # άδειασε τη λίστα
    python3 soldout.py --reset           # συγχρονισμός με την ημερομηνία του μενού

Η κατάσταση ζει στο `soldout.txt` και **όχι** μέσα στο menu-today.txt: εκεί
γράφει αυτόματα το Shortcut του κινητού, και μια αποτυχημένη αυτόματη εγγραφή
δεν πρέπει ποτέ να μπορεί να χαλάσει το μενού της ημέρας.

Το αρχείο κρατά και την ΗΜΕΡΟΜΗΝΙΑ για την οποία ισχύει. Έτσι η λίστα
**αδειάζει μόνη της** όταν αλλάξει το μενού. Δύο δικλείδες, όχι μία:

  1. το `--reset` τρέχει στο CI πριν το build και καθαρίζει το αρχείο,
  2. το `active()` αγνοεί τη λίστα αν η ημερομηνία δεν ταιριάζει.

Η δεύτερη υπάρχει επειδή ένα ξεχασμένο «τελείωσε» πάνω σε φρέσκο φαγητό είναι
σιωπηλό λάθος: δείχνει σωστό, και χάνει παραγγελίες χωρίς να το μάθει κανείς.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SOLDOUT_TXT = os.path.join(ROOT, "soldout.txt")
MENU_TXT = os.path.join(ROOT, "menu-today.txt")

BACK = ("ξανα", "ξανά", "επανηλθε", "επανήλθε", "+")
CLEAR = ("καθαρισε", "καθάρισε", "καθαρισμος", "καθαρισμός", "τιποτα",
         "τίποτα", "ολα", "όλα", "clear", "reset")


def _field(path, key):
    """«ΚΛΕΙΔΙ: τιμή» αγνοώντας σχόλια — ίδιο μοτίβο με το publish.py."""
    if not os.path.isfile(path):
        return ""
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        k, v = s.split(":", 1)
        if k.strip().upper().startswith(key):
            return v.strip()
    return ""


def read():
    """(ημερομηνία, [ονόματα]) όπως είναι γραμμένα στο soldout.txt."""
    date = _field(SOLDOUT_TXT, "ΗΜΕΡΟΜΗΝΙΑ")
    raw = _field(SOLDOUT_TXT, "ΤΕΛΕΙΩΣΑΝ")
    names = [p.strip() for p in re.split(r"[,·;]+", raw) if p.strip()]
    return date, names


def menu_date():
    return _field(MENU_TXT, "ΗΜΕΡΟΜΗΝΙΑ")


def active():
    """Τα ονόματα που ΙΣΧΥΟΥΝ σήμερα. Κενή λίστα αν η ημερομηνία δεν ταιριάζει."""
    date, names = read()
    return names if date and date == menu_date() else []


def write(date, names):
    """Γράφει τις δύο γραμμές, αφήνοντας άθικτο το σχόλιο-οδηγίες από πάνω."""
    txt = open(SOLDOUT_TXT, encoding="utf-8").read()
    txt = re.sub(r"(?m)^ΗΜΕΡΟΜΗΝΙΑ:.*$", f"ΗΜΕΡΟΜΗΝΙΑ: {date}", txt, count=1)
    txt = re.sub(r"(?m)^ΤΕΛΕΙΩΣΑΝ:.*$", "ΤΕΛΕΙΩΣΑΝ: " + ", ".join(names),
                 txt, count=1)
    open(SOLDOUT_TXT, "w", encoding="utf-8").write(txt)


def _today_items():
    """{δείκτης: (όνομα,)} με ΟΛΑ τα πιάτα της σημερινής σελίδας.

    Η αναγνώριση γίνεται μέσα στο σημερινό μενού, όχι σε ολόκληρο το xlsx.
    Έτσι το «σνίτσελ» — που κανονικά είναι διφορούμενο — λύνεται μόνο του αν
    σήμερα σερβίρεται ένα από τα δύο.
    """
    import build            # εδώ μέσα: το build.py διαβάζει ΑΥΤΟ το αρχείο
    items = [it for c in build.MENU for it in c["items"]]
    return {i: (it["name"],) for i, it in enumerate(items)}


def main(argv):
    arg = " ".join(argv).strip()

    if arg == "--reset":
        date, names = read()
        now = menu_date()
        if date == now:
            print(f"soldout.txt: ίδια ημερομηνία ({now or '—'}), τίποτα να κάνω.")
            return 0
        write(now, [])
        print(f"soldout.txt: νέα ημερομηνία «{now}» — η λίστα άδειασε"
              + (f" (είχε: {', '.join(names)})" if names else "") + ".")
        return 0

    if not arg:
        date, names = read()
        print(f"{date or '—'}: " + (", ".join(names) if names else "κανένα"))
        return 0

    import dish_names
    date, names = read()
    if date != menu_date():          # πρώτη σήμανση της ημέρας
        date, names = menu_date(), []

    low = arg.lower().lstrip("+ ").strip()
    if low in CLEAR:
        write(date, [])
        print("Η λίστα άδειασε.")
        return 0

    undo = arg.lower().startswith(BACK) or arg.startswith("+")
    token = re.sub(r"^\s*(ξανά|ξανα|επανήλθε|επανηλθε|\+)\s*", "", arg,
                   flags=re.I).strip()

    n, msg = dish_names.resolve(token, _today_items(),
                                where="στο σημερινό μενού")
    if msg:
        print("!! " + msg, file=sys.stderr)
        return 1
    name = _today_items()[n][0]

    key = dish_names.norm(name)
    names = [x for x in names if dish_names.norm(x) != key]
    if not undo:
        names.append(name)
    write(date, names)
    print(("Επανήλθε: " if undo else "Τελείωσε: ") + name)
    print("Λίστα: " + (", ".join(names) if names else "κανένα"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
