# -*- coding: utf-8 -*-
"""Αναγνώριση πιάτου από το όνομά του, όπως το λέει ο ιδιοκτήτης.

Ο ιδιοκτήτης δίνει το μενού περιγραφικά — «μπιφτέκι, φιλέτο κοτόπουλο,
μουσακάς» — όχι με αριθμούς. Το `menu-today.txt` δέχεται και τα δύο:

    Μενού Ημέρας: μπιφτέκι, μουσακάς, γεμιστά
    Μενού Ημέρας: 38 17 8            (ο παλιός τρόπος δουλεύει ακριβώς ίδια)

**Ποτέ δεν μαντεύει.** «Φιλέτο κοτόπουλο» ταιριάζει και στο #40 (σχάρας) και
στο #54 (a la creme): εκεί σταματά και ζητά διευκρίνιση. Ένα λάθος πιάτο στο
site είναι ακριβώς η σιωπηλή αστοχία που όλο το check.py προσπαθεί να αποτρέψει.

Ο κώδικας ζει εδώ και όχι μέσα στο build.py επειδή τον χρειάζονται **και** το
build.py **και** το check.py — αν αποκλίνουν, ο έλεγχος θα εγκρίνει κάτι
διαφορετικό από αυτό που θα χτιστεί.
"""
import re
import unicodedata

# Ήχοι που στα ελληνικά γράφονται με πολλούς τρόπους: «Ρεβίθια»/«Ρεβύθια».
_SOUND = [("ει", "ι"), ("οι", "ι"), ("υι", "ι"), ("αι", "ε"),
          ("ου", "u"), ("η", "ι"), ("υ", "ι"), ("ω", "ο"), ("ς", "σ")]

_SPLIT = r"[\s/,&()\-–—]+"
MIN_WORD = 3          # λέξεις κάτω από 3 γράμματα («με», «a», «la») δεν μετράνε


def norm(s):
    """Πεζά, χωρίς τόνους, χωρίς κενά/καθέτους."""
    s = "".join(c for c in unicodedata.normalize("NFD", str(s))
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s/]+", "", s).lower()


def sound(s):
    """Ισοπεδώνει την ορθογραφία ώστε «Ρεβίθια» == «Ρεβύθια»."""
    s = norm(s)
    for a, b in _SOUND:
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)          # διπλά σύμφωνα -> ένα


def stems(s):
    """Ρίζες ανά λέξη: «Γλώσσες τηγανητές» -> {γλοσ, τιγανιτ}.
    Πιάνει ενικό/πληθυντικό και γένος, που το Levenshtein τα χάνει."""
    out = set()
    for w in re.split(_SPLIT, str(s)):
        w = sound(w)
        if len(w) < MIN_WORD:
            continue
        w = re.sub(r"σ$", "", w)                # πρώτα το τελικό ς/σ …
        w = re.sub(r"[αειου]{1,2}$", "", w)     # … και μετά η κατάληξη
        if len(w) >= MIN_WORD:
            out.add(w)
    return out


def words(s):
    return [w for w in (sound(x) for x in re.split(_SPLIT, str(s)))
            if len(w) >= MIN_WORD]


def _covers(query_word, name_words):
    return any(nw.startswith(query_word) or query_word.startswith(nw)
               for nw in name_words)


def resolve(token, rows):
    """token: ό,τι έγραψε ο χρήστης. rows: {Α/Α: (όνομα, …)}.

    Επιστρέφει (Α/Α, None) σε επιτυχία, ή (None, μήνυμα λάθους) αλλιώς.
    """
    token = str(token).strip()
    if not token:
        return None, "κενό όνομα πιάτου."

    def name_of(n):
        return rows[n][0]

    # 1. ακριβώς το ίδιο όνομα — κερδίζει πάντα.
    #    Αλλιώς το «Γεμιστά» δεν θα ξεχώριζε ποτέ από το «Γεμιστά με κιμά».
    hit = [n for n in rows if norm(name_of(n)) == norm(token)]
    if len(hit) == 1:
        return hit[0], None

    # 2. ίδιο αν αγνοήσουμε ορθογραφία/τόνους («ρεβιθια» -> «Ρεβύθια»)
    key = " ".join(words(token))
    hit = [n for n in rows if " ".join(words(name_of(n))) == key]
    if len(hit) == 1:
        return hit[0], None

    # 3. όλες οι λέξεις του token υπάρχουν στο όνομα («μπιφτέκι» -> #38)
    qw = words(token)
    if qw:
        hit = [n for n in rows
               if all(_covers(q, words(name_of(n))) for q in qw)]
        if len(hit) == 1:
            return hit[0], None
        if len(hit) > 1:
            opts = ", ".join(f"«{name_of(n)}» ({n})" for n in sorted(hit))
            return None, (f"«{token}» ταιριάζει σε {len(hit)} πιάτα: {opts}. "
                          f"Γράψε πιο συγκεκριμένα ή βάλε τον αριθμό.")

    # 4. τίποτα — πρότεινε ό,τι μοιάζει, για να μη ψάχνει στα τυφλά
    st = stems(token)
    near = [n for n in rows if st and st & stems(name_of(n))]
    extra = ""
    if near:
        extra = ("  Μήπως: "
                 + ", ".join(f"«{name_of(n)}» ({n})" for n in sorted(near)[:4])
                 + ";")
    return None, (f"«{token}» δεν βρέθηκε στο DAILY_MENU.xlsx.{extra}")


def parse_selection(value, rows):
    """Μια γραμμή του menu-today.txt -> ([Α/Α], [μηνύματα λάθους]).

    Δέχεται αριθμούς χωρισμένους με κενά (παλιός τρόπος), ονόματα χωρισμένα με
    κόμμα, ή μείγμα: «38, μουσακάς, 8».
    """
    nums, errs = [], []
    for part in re.split(r"[,·;]+", str(value)):
        part = part.strip()
        if not part:
            continue
        if re.fullmatch(r"[\d\s]+", part):        # καθαροί αριθμοί
            nums += [int(x) for x in re.findall(r"\d+", part)]
            continue
        n, msg = resolve(part, rows)
        if msg:
            errs.append(msg)
        else:
            nums.append(n)
    return nums, errs
