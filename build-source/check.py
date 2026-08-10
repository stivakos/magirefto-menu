# -*- coding: utf-8 -*-
"""
Έλεγχος του DAILY_MENU.xlsx και του menu-today.txt πριν το ανέβασμα.

Πιάνει τις σιωπηλές αστοχίες — αυτές που ΔΕΝ ρίχνουν το build, αλλά κάνουν
ένα πιάτο να εξαφανιστεί από το site χωρίς να το καταλάβεις.

Τρέξε το από τον φάκελο build-source:      python check.py
Έξοδος: 0 = όλα καλά (ή μόνο προειδοποιήσεις), 1 = υπάρχει σφάλμα.
"""

import ast
import os
import re
import sys
import unicodedata

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD_PY = os.path.join(HERE, "build.py")
XLSX = os.path.join(HERE, "..", "DAILY_MENU.xlsx")
MENU_TXT = os.path.join(HERE, "..", "menu-today.txt")


# --- ρυθμίσεις: διαβάζονται από το build.py ώστε να μην ξεφύγουν ποτέ ------
def config_from_build():
    """Παίρνει CATEGORIES / HIDE_PRICE από το build.py χωρίς να το εκτελέσει."""
    tree = ast.parse(open(BUILD_PY, encoding="utf-8").read())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in ("CATEGORIES", "HIDE_PRICE"):
                try:
                    found[t.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    missing = {"CATEGORIES", "HIDE_PRICE"} - set(found)
    if missing:
        sys.exit(f"!! Δεν βρέθηκαν {missing} στο build.py — άλλαξε η δομή του;")
    return found["CATEGORIES"], set(found["HIDE_PRICE"])


CATEGORIES, HIDE_PRICE = config_from_build()

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s))
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s/]+", "", s).lower()


# --- 1. το ίδιο το αρχείο --------------------------------------------------
if not os.path.exists(XLSX):
    sys.exit(f"!! Δεν βρέθηκε το {XLSX}")

wb = openpyxl.load_workbook(XLSX, data_only=True)

tabs_needed = [tab for _, _, tab in CATEGORIES]
for tab in tabs_needed:
    if tab not in wb.sheetnames:
        err(f"ΛΕΙΠΕΙ ΤΟ TAB «{tab}» — το build θα σκάσει. "
            f"Υπάρχοντα tabs: {', '.join(wb.sheetnames)}")

extra = [s for s in wb.sheetnames if s not in tabs_needed]
if extra:
    warn(f"Tabs που αγνοούνται εντελώς από το site: {', '.join(extra)}")

if errors:
    print("\n".join("✗ " + e for e in errors))
    sys.exit(1)


# --- 2. περιεχόμενο κάθε tab ----------------------------------------------
catalog = {}   # slug -> {Α/Α: (όνομα, τιμή)}
summary = []

for label, slug, tab in CATEGORIES:
    ws = wb[tab]
    rows, names_seen = {}, {}
    valid = 0

    for r in range(2, ws.max_row + 1):
        aa = ws.cell(r, 1).value
        name = ws.cell(r, 2).value
        price = ws.cell(r, 3).value

        blank = aa is None and not name and price in (None, "")
        if blank:
            continue

        # Α/Α
        if aa is None:
            if name:
                err(f"[{tab}] γραμμή {r}: το πιάτο «{str(name).strip()}» "
                    f"ΔΕΝ ΕΧΕΙ Α/Α — δεν θα εμφανιστεί ποτέ.")
            continue
        try:
            n = int(aa)
        except (TypeError, ValueError):
            err(f"[{tab}] γραμμή {r}: Α/Α «{aa}» δεν είναι ακέραιος — "
                f"η γραμμή προσπερνιέται σιωπηλά.")
            continue

        # όνομα
        if not name or not str(name).strip():
            err(f"[{tab}] γραμμή {r}: Α/Α {n} χωρίς ονομασία — προσπερνιέται.")
            continue
        name = str(name).strip()

        # τιμή — η κλασική παγίδα: κείμενο «8,50» ρίχνει ΟΛΗ τη γραμμή
        val = None
        if price not in (None, ""):
            if isinstance(price, str):
                if "," in price:
                    err(f"[{tab}] γραμμή {r}: «{name}» — τιμή «{price}» είναι "
                        f"ΚΕΙΜΕΝΟ με κόμμα. Το πιάτο ΘΑ ΕΞΑΦΑΝΙΣΤΕΙ. "
                        f"Γράψε την ως αριθμό ({price.replace(',', '.')}).")
                    continue
                try:
                    val = float(price)
                    warn(f"[{tab}] γραμμή {r}: «{name}» — η τιμή είναι κείμενο "
                         f"«{price}». Δουλεύει, αλλά κάν' την αριθμό.")
                except ValueError:
                    err(f"[{tab}] γραμμή {r}: «{name}» — τιμή «{price}» δεν "
                        f"διαβάζεται ως αριθμός. Το πιάτο θα εξαφανιστεί.")
                    continue
            else:
                try:
                    val = float(price)
                except (TypeError, ValueError):
                    err(f"[{tab}] γραμμή {r}: «{name}» — τιμή «{price}» άκυρη. "
                        f"Το πιάτο θα εξαφανιστεί.")
                    continue
            if val is not None and val <= 0:
                warn(f"[{tab}] γραμμή {r}: «{name}» με τιμή {val}.")
        elif slug not in HIDE_PRICE:
            warn(f"[{tab}] γραμμή {r}: «{name}» χωρίς τιμή — θα εμφανιστεί "
                 f"στο site χωρίς τιμή.")

        # διπλά
        if n in rows:
            err(f"[{tab}] γραμμή {r}: ΔΙΠΛΟ Α/Α {n} («{name}» και "
                f"«{rows[n][0]}»). Το ένα από τα δύο χάνεται.")
        rows[n] = (name, val)

        key = norm(name)
        if key in names_seen:
            warn(f"[{tab}]: ίδια ονομασία σε Α/Α {names_seen[key]} και {n} "
                 f"(«{name}»).")
        else:
            names_seen[key] = n
        valid += 1

    catalog[slug] = rows
    nxt = (max(rows) + 1) if rows else 1
    gaps = [i for i in range(1, max(rows) + 1) if i not in rows] if rows else []
    summary.append((label, valid, nxt, gaps))


# --- 3. η επιλογή της ημέρας ----------------------------------------------
slug_by_norm = {norm(lbl): slug for lbl, slug, _ in CATEGORIES}
label_by_slug = {slug: lbl for lbl, slug, _ in CATEGORIES}
date_found = False
picked = {}

if not os.path.exists(MENU_TXT):
    err(f"Δεν βρέθηκε το {MENU_TXT}")
else:
    for ln, raw in enumerate(open(MENU_TXT, encoding="utf-8"), 1):
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        kn = norm(key)
        if kn in ("ημερομηνια", "date"):
            date_found = bool(val.strip())
            if not date_found:
                err(f"menu-today.txt γραμμή {ln}: κενή ΗΜΕΡΟΜΗΝΙΑ.")
            continue
        if kn not in slug_by_norm:
            err(f"menu-today.txt γραμμή {ln}: άγνωστη κατηγορία «{key.strip()}» "
                f"— αγνοείται. Επιτρεπτές: "
                f"{', '.join(l for l, _, _ in CATEGORIES)}")
            continue

        slug = slug_by_norm[kn]
        nums = [int(x) for x in re.findall(r"\d+", val)]
        picked[slug] = nums
        rows = catalog.get(slug, {})

        seen = set()
        for n in nums:
            if n in seen:
                warn(f"menu-today.txt γραμμή {ln} ({label_by_slug[slug]}): "
                     f"ο αριθμός {n} γραμμένος δύο φορές.")
            seen.add(n)
            if n not in rows:
                err(f"menu-today.txt γραμμή {ln} ({label_by_slug[slug]}): "
                    f"Α/Α {n} ΔΕΝ ΥΠΑΡΧΕΙ στο xlsx — αγνοείται σιωπηλά.")

    if not date_found:
        err("menu-today.txt: λείπει εντελώς η γραμμή ΗΜΕΡΟΜΗΝΙΑ.")

    for _, slug, _ in CATEGORIES:
        if not picked.get(slug):
            warn(f"Η κατηγορία «{label_by_slug[slug]}» δεν έχει επιλογές — "
                 f"δεν θα εμφανιστεί σήμερα.")


# --- 4. αναφορά ------------------------------------------------------------
print("\n── ΒΑΣΗ ΠΙΑΤΩΝ (DAILY_MENU.xlsx) " + "─" * 28)
for label, valid, nxt, gaps in summary:
    g = f"  κενά Α/Α: {', '.join(map(str, gaps))}" if gaps else ""
    print(f"  {label:20s} {valid:3d} πιάτα   επόμενο Α/Α: {nxt}{g}")

if picked:
    print("\n── ΜΕΝΟΥ ΗΜΕΡΑΣ " + "─" * 44)
    for _, slug, _ in CATEGORIES:
        nums = picked.get(slug, [])
        if not nums:
            continue
        rows = catalog.get(slug, {})
        shown = [rows[n][0] for n in nums if n in rows]
        print(f"  {label_by_slug[slug]:20s} {len(shown)}: "
              f"{', '.join(shown) if shown else '—'}")

if warnings:
    print("\n── ΠΡΟΕΙΔΟΠΟΙΗΣΕΙΣ " + "─" * 41)
    for w in warnings:
        print("  ⚠  " + w)

if errors:
    print("\n── ΣΦΑΛΜΑΤΑ " + "─" * 48)
    for e in errors:
        print("  ✗  " + e)
    print(f"\n{len(errors)} σφάλμα(τα). Διόρθωσέ τα πριν το ανέβασμα.\n")
    sys.exit(1)

print(f"\n✓ Όλα εντάξει"
      f"{f' ({len(warnings)} προειδοποιήσεις)' if warnings else ''}.\n")
