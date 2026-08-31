#!/usr/bin/env python3
"""Το προσχέδιο μενού: κουβέντα σε σχόλια issue μέχρι το «στείλε».

    python3 menu_draft.py --state state.json --body body.txt [--photo p.jpg]

Κάθε σχόλιο είναι ένας ΓΥΡΟΣ. Ο γύρος προσθέτει πιάτα στο προσχέδιο, ή είναι
εντολή («στείλε», «βγάλε …», «ακύρωση»). Τίποτα δεν δημοσιεύεται πριν το
«στείλε» — ούτε φωτογραφία, ούτε τέλεια λίστα με την πρώτη.

Ο ΚΑΝΟΝΑΣ ΠΟΥ ΤΟ ΚΑΝΕΙ ΝΑ ΔΟΥΛΕΥΕΙ ΧΩΡΙΣ ΣΥΝΤΑΞΗ ΔΙΟΡΘΩΣΗΣ: το προσχέδιο
κρατά ό,τι λύθηκε ΠΟΤΕ· τα εκκρεμή είναι πάντα μόνο του ΤΕΛΕΥΤΑΙΟΥ γύρου. Έτσι
ένα «Σολομός φρέσκο» που δεν αναγνωρίστηκε δεν σε κυνηγά για πάντα: γράφεις το
σωστό όνομα και ο πίνακας εκκρεμοτήτων αδειάζει μόνος του. Δεν χρειάζεται να
πεις τι αντικαθιστά τι, ούτε να ξαναγράψεις όλη τη λίστα.

Η ΚΑΤΑΣΤΑΣΗ ΔΕΝ ΜΠΑΙΝΕΙ ΣΕ ΑΡΧΕΙΟ ΤΟΥ REPO. Ζει σε ένα σχόλιο που η ροή
επεξεργάζεται, με κρυφό δείκτη HTML από κάτω. Δύο λόγοι: το git δεν γεμίζει με
commit ανά διόρθωση, και — το σοβαρό — η φωτογραφία διαβάζεται ΜΙΑ φορά. Αν
ξαναχτίζαμε το προσχέδιο διαβάζοντας όλο το ιστορικό, κάθε σχόλιο θα ξανακαλούσε
το μοντέλο πάνω στην ίδια εικόνα.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

import build
import dish_names
import read_board

MARK = "MENU-STATE"          # ο κρυφός δείκτης μέσα στο σχόλιο-προσχέδιο
HERE = os.path.dirname(os.path.abspath(__file__))
TAB = read_board.TAB


# ── εντολές ─────────────────────────────────────────────────────────────────
# Ο έλεγχος γίνεται σε ΟΛΟΚΛΗΡΟ το σχόλιο: ένα «στείλε» μέσα σε πρόταση δεν
# δημοσιεύει κατά λάθος.
SEND = {"στειλε", "στειλτο", "ok", "οκ", "δημοσιευσε"}
# Δημοσίευση ΠΑΡΑ τις εκκρεμότητες — πρέπει να ζητηθεί ρητά. Σκέτο «στείλε»
# με εκκρεμή πιάτα τα πετούσε σιωπηλά: ο ιδιοκτήτης έβλεπε «Ανέβηκε» και το
# μενού είχε λιγότερα πιάτα απ' όσα ζήτησε, χωρίς λέξη. Ακριβώς το είδος
# σιωπής που αλλού σε αυτό το repo σταματά τη ροή.
SEND_ANYWAY = {"στειλε ετσι", "στειλε χωρις αυτα", "στειλε ετσι κι αλλιως",
               "στειλε τα υπολοιπα"}
CANCEL = {"ακυρωση", "ακυρο", "ξεκινα ξανα", "καθαρισε"}
DROP = re.compile(r"^(?:βγαλε|αφαιρεσε)\s+(.+)$")
# «βάλε Χ» κάνει ό,τι και μια σκέτη λίστα. Υπάρχει για συμμετρία με το
# «βγάλε»: χωρίς αυτό, το «βάλε» περνούσε ως μέρος του ονόματος και το
# πιάτο εκκρεμούσε («βάλε μουσακάς» δεν βρέθηκε), που είναι το χειρότερο
# είδος αποτυχίας — μοιάζει με λάθος του ιδιοκτήτη ενώ είναι της ροής.
ADD = re.compile(r"^(?:βαλε|προσθεσε)\s+(.+)$")


def fold(s):
    """Πεζά, χωρίς τόνους, ΜΕ τα κενά — σε αντίθεση με το dish_names.norm().

    Το norm() σβήνει τα κενά («βγάλε Παστίτσιο» -> «βγαλεπαστιτσιο»), που είναι
    σωστό για ονόματα πιάτων και καταστροφικό για εντολές με όρισμα: καμία
    «βγάλε Χ» δεν θα ταίριαζε ποτέ, και θα περνούσε σιωπηλά ως όνομα πιάτου.
    """
    s = "".join(c for c in unicodedata.normalize("NFD", str(s))
                if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def command(body):
    """(είδος, όρισμα) ή (None, None) αν το σχόλιο είναι λίστα πιάτων."""
    f = fold(body)
    if f in SEND_ANYWAY:          # πριν το SEND: δεν επικαλύπτονται, αλλά η
        return "send", "force"    # σειρά κάνει την πρόθεση προφανή
    if f in SEND:
        return "send", None
    if f in CANCEL:
        return "cancel", None
    # Το όρισμα από το ΑΡΧΙΚΟ κείμενο: με τόνους, όπως το έγραψε, ώστε να
    # βγαίνει αναγνωρίσιμο στα μηνύματα.
    if DROP.match(f):
        return "drop", body.strip().split(None, 1)[1]
    if ADD.match(f):
        return "add", body.strip().split(None, 1)[1]
    return None, None


# ── κατάσταση ───────────────────────────────────────────────────────────────
def blank():
    return {"nums": [], "pending": [], "date_line": None, "source": None}


def verify():
    """Τρέχει το check.py πάνω στο γραμμένο menu-today.txt. None = εντάξει.

    Χωρίς αυτό, το «στείλε» έκανε commit και ανακοίνωνε «Ανέβηκε», και ΜΕΤΑ το
    «Build menu» έτρεχε τον έλεγχο. Αν ο έλεγχος έσκαγε εκεί, η δημοσίευση
    σταματούσε — αλλά το issue είχε ήδη κλείσει λέγοντας ότι ανέβηκε, και το
    site έμενε στο χθεσινό μενού χωρίς να το πάρει κανείς είδηση. Ο έλεγχος
    κοιτά ΟΛΟ το menu-today.txt, όχι μόνο τη γραμμή που γράψαμε: μια χαλασμένη
    γραμμή «Σαλάτες» μπλοκάρει το ίδιο.
    """
    r = subprocess.run([sys.executable, "check.py"], cwd=HERE,
                       capture_output=True, text=True)
    if r.returncode == 0:
        return None
    out = ((r.stdout or "") + (r.stderr or "")).splitlines()
    # Το check.py τυπώνει ολόκληρη αναφορά· στο issue θέλουμε ΜΟΝΟ τα σφάλματα.
    # Χωρίς αυτό το απόσπασμα ήταν οι τελευταίες γραμμές, δηλαδή σαλάτες και
    # γλυκά — και ο ιδιοκτήτης δεν μάθαινε ποτέ τι έφταιξε.
    bad = [l.strip() for l in out if l.lstrip().startswith(("✗", "!!"))]
    return "\n".join(bad or out[-20:]).strip()


def prune(state, rows):
    """Βγάζει Α/Α που δεν υπάρχουν πια στο xlsx. Γυρίζει όσα έφυγαν.

    Χωρίς αυτό το render() σκάει με KeyError, και το προσχέδιο ΚΟΛΛΑΕΙ ΓΙΑ
    ΠΑΝΤΑ: η κατάσταση ξαναδιαβάζεται από το ίδιο σχόλιο σε κάθε γύρο, οπότε
    κάθε επόμενο σχόλιο ξανασκάει στο ίδιο σημείο. Δεν είναι υποθετικό — το #36
    διαγράφηκε από το xlsx ενώ υπήρχαν ανοιχτά issues που το κρατούσαν.
    """
    gone = [a for a in state["nums"] if a not in rows]
    if gone:
        state["nums"] = [a for a in state["nums"] if a in rows]
    return gone


def load(path):
    if path and os.path.isfile(path):
        try:
            return {**blank(), **json.load(open(path, encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            pass          # χαλασμένη κατάσταση => ξεκινάμε καθαρά, όχι σκάσιμο
    return blank()


# ── ο γύρος ─────────────────────────────────────────────────────────────────
def apply_round(state, names, rows, alias):
    """Προσθέτει τα πιάτα του γύρου. Τα εκκρεμή ΑΝΤΙΚΑΘΙΣΤΑΝΤΑΙ, δεν σωρεύονται."""
    pending = []
    for name in names:
        aa, err = read_board.resolve_one(name, rows, alias, numeric=True)
        if err:
            pending.append({"name": name, "why": err})
        elif aa not in state["nums"]:
            state["nums"].append(aa)     # η σειρά γραψίματος = η σειρά στη σελίδα
    state["pending"] = pending
    return state


def drop(state, token, rows, alias):
    """«βγάλε Χ» — χωρίς αυτό, πιάτο που μπήκε κατά λάθος αλλά αναγνωρίστηκε
    κανονικά δεν έβγαινε με τίποτα, παρά μόνο κλείνοντας το issue."""
    aa, err = read_board.resolve_one(token, rows, alias, numeric=True)
    if err:
        return f"Δεν κατάλαβα ποιο πιάτο να βγάλω: {err}"
    if aa not in state["nums"]:
        return f"Το «{rows[aa][0]}» δεν είναι στο προσχέδιο."
    state["nums"].remove(aa)
    return None


# ── τι βλέπει ο ιδιοκτήτης ──────────────────────────────────────────────────
def render(state, rows, note=None):
    out = []
    if note:
        out += [note, ""]
    when = state.get("date_line") or "—"
    out.append(f"**Προσχέδιο — {when}**")
    out.append("")
    if state["nums"]:
        out.append(f"Στο μενού ({len(state['nums'])}):")
        out += [f"{i}. {rows[a][0]} (#{a})" for i, a in enumerate(state["nums"], 1)]
    else:
        out.append("Το προσχέδιο είναι άδειο.")
    out.append("")
    if state["pending"]:
        out.append(f"**Εκκρεμούν ({len(state['pending'])})** — δεν θα μπουν έτσι:")
        out += [f"- «{p['name']}» — {p['why']}" for p in state["pending"]]
        out.append("")
        out.append("Γράψε το σωστό όνομα σε σχόλιο και το εκκρεμές φεύγει μόνο του.")
    else:
        out.append("Τίποτα δεν εκκρεμεί.")
    out.append("")
    out.append("Εντολές: **στείλε** για δημοσίευση · **βάλε <πιάτο>** · "
               "**βγάλε <πιάτο>** · **ακύρωση**")
    out.append("")
    keep = {k: state[k] for k in ("nums", "pending", "date_line", "source")
            if k in state}
    out.append(f"<!-- {MARK} {json.dumps(keep, ensure_ascii=False)} -->")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state")                    # json της προηγούμενης κατάστασης
    ap.add_argument("--body", required=True)      # το κείμενο του γύρου
    ap.add_argument("--photo")                    # αν ο γύρος έφερε φωτογραφία
    ap.add_argument("--draft-out", default="draft.md")   # το σχόλιο-προσχέδιο
    ap.add_argument("--reply-out", default="reply.md")   # η ανακοίνωση, μόνο στο «στείλε»
    ap.add_argument("--state-out", default="state.json")
    a = ap.parse_args()

    rows = build._tab_rows(TAB)
    alias = read_board.aliases()
    state = load(a.state)
    body = open(a.body, encoding="utf-8").read() if os.path.isfile(a.body) else ""

    # ΠΡΙΝ από οτιδήποτε άλλο: παλιό προσχέδιο μπορεί να δείχνει σε πιάτο που
    # ο ιδιοκτήτης έσβησε στο μεταξύ.
    gone = prune(state, rows)

    kind, arg = command(body)
    note = None
    published = False

    if kind == "cancel":
        state = blank()
        note = "Το προσχέδιο άδειασε. Στείλε ξανά τα πιάτα."
    elif kind == "drop":
        note = drop(state, arg, rows, alias) or None
        if note is None:
            note = "Βγήκε."
    elif kind == "send":
        if not state["nums"]:
            note = "Δεν υπάρχει τίποτα να σταλεί — το προσχέδιο είναι άδειο."
        elif state["pending"] and arg != "force":
            note = (f"**Δεν το έστειλα.** Εκκρεμούν {len(state['pending'])} πιάτα "
                    "και θα έλειπαν από το μενού χωρίς να το πάρεις είδηση.\n\n"
                    "Γράψε τα σωστά ονόματα (ή τους αριθμούς τους), ή "
                    "**«στείλε έτσι»** για να δημοσιευτεί χωρίς αυτά.")
        else:
            names = [rows[n][0] for n in state["nums"]]
            with open(build.MENU_TXT, encoding="utf-8") as f:
                before = f.read()
            read_board.write_menu(names, state["date_line"])
            bad = verify()
            if bad:
                # Επαναφορά χωρίς git: το αρχείο δεν πρέπει να μείνει
                # χαλασμένο, γιατί το επόμενο βήμα κάνει «git add».
                with open(build.MENU_TXT, "w", encoding="utf-8") as f:
                    f.write(before)
                note = ("**Δεν δημοσιεύτηκε** — ο έλεγχος βρήκε πρόβλημα στο "
                        "menu-today.txt:\n\n```\n"
                        + "\n".join(bad.splitlines()[-20:]) + "\n```")
            else:
                published = True
    else:
        # Λίστα πιάτων. Η φωτογραφία διαβάζεται ΜΟΝΟ όταν έρχεται, ποτέ ξανά.
        # Η φωτογραφία προηγείται του «βάλε»: ένα «βάλε αυτά» με συνημμένη
        # φωτό έπαιρνε τον δρόμο του κειμένου και διάβαζε ως όνομα πιάτου το
        # ίδιο το markdown της εικόνας. Η φωτό αγνοούνταν, και ο ιδιοκτήτης
        # έβλεπε εκκρεμότητα με ακαταλαβίστικο όνομα.
        if kind == "add" and not a.photo:
            # Ίδιος δρόμος με τη σκέτη λίστα — δέχεται και κόμματα («βάλε
            # μουσακάς, γεμιστά»).
            read, date_line = read_board.read_text(arg)
            names = [n for n, _ in read]
            source = "text"
        elif a.photo:
            read = read_board.read_photo(a.photo)
            names = [n for n, _ in read]
            date_line = read_board.today_line()      # ο πίνακας δείχνει τη σήμερα
            source = "photo"
        else:
            read, date_line = read_board.read_text(body)
            names = [n for n, _ in read]
            source = "text"                          # το κείμενο είναι για αύριο
        if not names:
            note = ("Δεν βρήκα πιάτα σε αυτό το σχόλιο. Γράψε ονόματα χωρισμένα "
                    "με κόμμα, ή «στείλε» για να δημοσιευτεί το προσχέδιο.")
        else:
            # Η ημερομηνία κλειδώνει στον ΠΡΩΤΟ γύρο: μια διόρθωση με κείμενο δεν
            # έχει δουλειά να μετακινήσει στο αύριο ένα μενού που ξεκίνησε από φωτό.
            if not state.get("date_line"):
                state["date_line"] = date_line
                state["source"] = source
            apply_round(state, names, rows, alias)

    # Το σχόλιο-προσχέδιο γράφεται ΠΑΝΤΑ, ακόμη και μετά τη δημοσίευση: κρατά την
    # κατάσταση ζωντανή, ώστε ένα σχόλιο σε κλειστό issue («βγάλε Χ», «στείλε»)
    # να συνεχίζει από εκεί που έμεινε αντί να ξεκινά από το μηδέν.
    if published:
        note = "Δημοσιεύτηκε. Μπορείς ακόμη να διορθώσεις και να ξαναστείλεις."
    if gone:
        warn = ("⚠ Έβγαλα από το προσχέδιο "
                + ", ".join(f"#{a}" for a in gone)
                + " — δεν υπάρχει πια στο DAILY_MENU.xlsx.")
        note = f"{warn}\n\n{note}" if note else warn

    open(a.draft_out, "w", encoding="utf-8").write(render(state, rows, note))
    if published:
        open(a.reply_out, "w", encoding="utf-8").write(
            f"Ανέβηκε — **{state['date_line']}**, {len(state['nums'])} πιάτα:\n\n"
            + "\n".join(f"- {rows[n][0]} (#{n})" for n in state["nums"])
            + "\n\nΣε ένα λεπτό είναι στο site.")
    json.dump(state, open(a.state_out, "w", encoding="utf-8"), ensure_ascii=False)

    print("published" if published else "draft")
    return 0


if __name__ == "__main__":
    sys.exit(main())
