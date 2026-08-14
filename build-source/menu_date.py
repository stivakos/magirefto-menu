# -*- coding: utf-8 -*-
"""Ανάγνωση της ημερομηνίας του menu-today.txt («Τετάρτη 12/8/26»).

Ζει σε δικό του αρχείο επειδή το χρειάζονται **και** το build.py **και** το
check.py — αν αποκλίνουν, ο έλεγχος θα έκρινε άλλη ημερομηνία από αυτή που
θα έμπαινε στη σελίδα.

Ο ιδιοκτήτης γράφει ελεύθερα («Τετάρτη 12/8/26», «12/8/2026», «Δευτέρα
1-9-26»). Κρατάμε μόνο μέρα/μήνα/έτος· η μέρα της εβδομάδας είναι για τον
πελάτη και **επαληθεύεται** χωριστά, γιατί ένα «Τρίτη» πάνω σε Τετάρτη το
βλέπουν όλοι.
"""
import datetime
import re
import unicodedata

# Δευτέρα = 0, όπως το datetime.weekday()
GREEK_DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη",
              "Παρασκευή", "Σάββατο", "Κυριακή"]

_DMY = re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})")
# «Τετάρτη 12/8» — χωρίς έτος. Συμβαίνει· μην αφήσεις τον έλεγχο να σβήσει.
_DM = re.compile(r"(?<!\d)(\d{1,2})\s*[/\-.]\s*(\d{1,2})(?!\s*[/\-.]\s*\d)(?!\d)")


def _fold(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s))
                if unicodedata.category(c) != "Mn")
    return s.lower().strip()


def parse(text, today=None):
    """«Τετάρτη 12/8/26» -> datetime.date(2026, 8, 12). None αν δεν διαβάζεται."""
    s = str(text or "")
    m = _DMY.search(s)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if y < 100:                 # «26» -> 2026
            y += 2000
        try:
            return datetime.date(y, mo, d)
        except ValueError:          # π.χ. 31/2
            return None

    m = _DM.search(s)
    if not m:
        return None
    d, mo = (int(x) for x in m.groups())
    today = today or datetime.date.today()
    # Χωρίς έτος, διάλεξε το κοντινότερο — αλλιώς κάθε «3/1» γραμμένο στις 31/12
    # θα φαινόταν περσινό.
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            cand = datetime.date(y, mo, d)
        except ValueError:
            continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best


def date_iso(text):
    """Μορφή που καταλαβαίνει η JavaScript. Κενό αν δεν διαβάζεται."""
    d = parse(text)
    return d.isoformat() if d else ""


def weekday_written(text):
    """Η μέρα εβδομάδας όπως τη ΓΡΑΨΕ ο ιδιοκτήτης, ή None αν δεν έγραψε."""
    t = _fold(text)
    for name in GREEK_DAYS:
        if _fold(name) in t:
            return name
    return None


def weekday_mismatch(text):
    """(γραμμένη, σωστή) αν δεν ταιριάζουν· αλλιώς None.

    Πιάνει το κλασικό «άλλαξα τον αριθμό, ξέχασα τη μέρα».
    """
    d = parse(text)
    written = weekday_written(text)
    if not d or not written:
        return None
    actual = GREEK_DAYS[d.weekday()]
    return None if _fold(written) == _fold(actual) else (written, actual)
