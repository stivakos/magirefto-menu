#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Merci Μαγειρευτό online menu (index.html).

Single source of truth = MENU below. Categories are fixed; dishes edited on
request. Prices come from Μαγειρευτό_Μενού.xlsx (owner's rule). Price = number
or None (side dishes shown without price).
"""
import re, html, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "index.html")
# DAILY_MENU.xlsx (owner-maintained source of common dishes) lives in the repo root.
DAILY_SOURCE = os.path.join(HERE, "..", "DAILY_MENU.xlsx")

# GFS Didot fonts are vendored in the repo so the build runs anywhere (cloud/CI, no Mac).
FONT_FACES = open(os.path.join(HERE, "fonts.css"), encoding="utf-8").read()

VIBER_NUMBER = "+306987992887"  # Viber μαγαζιού (για tel: link)
VIBER_DISPLAY = "+30 698 799 2887"

# ---------------------------------------------------------------------------
# Daily menu = parsed from menu-today.txt (owner edits it, even from the phone
# via GitHub) + dishes/prices looked up in DAILY_MENU.xlsx by Α/Α.
#   ΗΜΕΡΟΜΗΝΙΑ: Δευτέρα 20/7/26
#   Μαγειρευτά: 1 8 16 17
#   Της ώρας: 2 3 9
# ---------------------------------------------------------------------------
import unicodedata, openpyxl

CATEGORIES = [   # (site label, slug, xlsx tab name)
    ("Μενού Ημέρας",      "menu-hmeras", "Μενού Ημέρας"),
    ("Συνοδευτικά",       "synodeytika", "Συνοδευτικά"),
    ("Σαλάτες",           "salates",     "Σαλάτες"),
    ("Γλυκά",             "glyka",       "Γλυκά"),
    ("Αναψυκτικά / Ποτά", "anapsyktika", "Αναψυκτικά - Ποτά"),
]
NOTES = {"synodeytika": "…και σε μερίδα για μεγαλύτερη απόλαυση!"}
HIDE_PRICE = {"synodeytika"}          # συνοδευτικά: χωρίς τιμή στο site
MENU_TXT = os.path.join(HERE, "..", "menu-today.txt")

# ---------------------------------------------------------------------------
# «Το μαγαζί μας»: γκαλερί στο τέλος της σελίδας. Οι εικόνες είναι ΑΡΧΕΙΑ στο
# assets/gallery/ (η μόνη εξαίρεση στο «όλα inline») και φορτώνουν lazy — inline
# base64 θα πρόσθετε ~1 MB στο index.html που ο πελάτης κατεβάζει με 4G.
# Παράγονται από το prep-photos.sh. Το τρίτο πεδίο είναι το object-position:
# αλλάζει ποιο κομμάτι κρατάει το τετράγωνο πλακίδιο.
# ---------------------------------------------------------------------------
GALLERY_DIR = "assets/gallery"
GALLERY = [   # (αρχείο, alt, object-position)
    ("01-vitrina.jpg",   "Η βιτρίνα του Merci Μαγειρευτό με τα πιάτα της ημέρας", "center top"),
    ("02-gemista.jpg",   "Γεμιστά πιπεριές και ντομάτες σε μερίδες",              "center"),
    ("03-pastitsio.jpg", "Παστίτσιο και μουσακάς φρεσκογρατιναρισμένα",           "center"),
    ("04-giouvetsi.jpg", "Γιουβέτσι στο ταψί και σούπες, μέσα στη βιτρίνα",       "center"),
    ("05-keftedes.jpg",  "Κεφτέδες σε κόκκινη σάλτσα",                            "center"),
    ("06-vitrina-2.jpg", "Η ζεστή βιτρίνα του μαγαζιού από πλάγια",               "center"),
]
ABOUT_TITLE = "Το μαγαζί μας"
ABOUT_CHIP = "Το μαγαζί"      # κοντύτερο: με 6 chips το rail δεν χωράει το πλήρες
ABOUT_TEXT = ("Μαγειρεύουμε κάθε πρωί σπιτικό φαγητό στην Καρδίτσης 22 — λαδερά, "
              "γιαχνί, ψητά — και το σερβίρουμε ζεστό από τη βιτρίνα, όσο κρατήσει. "
              "Ό,τι βλέπεις στο μενού μαγειρεύτηκε σήμερα.")

import dish_names                      # αναγνώριση πιάτου από το όνομά του
_norm = dish_names.norm                # ίδια συνάρτηση — μία πηγή, χωρίς απόκλιση

MENU_DATE = ""
CLOSED = ""        # γραμμή «ΚΛΕΙΣΤΑ: <πότε ανοίγουμε>» -> κλειστό μαγαζί.
                   # Όσο έχει τιμή, το site δείχνει ανακοίνωση αντί για μενού
                   # και δεν δέχεται παραγγελίες. Σβήσε τη γραμμή για να ανοίξει.
# Οι γραμμές κρατιούνται ΑΚΑΤΕΡΓΑΣΤΕΣ: μπορεί να είναι αριθμοί ή ονόματα, και
# τα ονόματα λύνονται πιο κάτω, όταν έχει φορτωθεί το xlsx.
selection_raw = {}
_slug_by_norm = {_norm(lbl): slug for lbl, slug, _ in CATEGORIES}
for raw in open(MENU_TXT, encoding="utf-8"):
    line = raw.strip()
    if not line or line.startswith("#") or ":" not in line:
        continue
    key, val = line.split(":", 1)
    kn = _norm(key)
    if kn in ("ημερομηνια", "date"):
        MENU_DATE = val.strip()
    elif kn in ("κλειστα", "closed"):
        CLOSED = val.strip()
    elif kn in _slug_by_norm:
        selection_raw[_slug_by_norm[kn]] = val

_wb = openpyxl.load_workbook(DAILY_SOURCE, data_only=True)
SIDE_YES = {"ν", "ναι", "n", "y", "yes", "x", "χ", "✓", "1"}


def _wants_side(v):
    """Στήλη E «Με συνοδευτικό;» — δέχεται Ν / ναι / Χ / ✓ και ό,τι μοιάζει.

    Αν η στήλη δεν υπάρχει καθόλου (παλιό xlsx), όλα βγαίνουν False και η
    λειτουργία μένει αδρανής — το site δουλεύει ακριβώς όπως πριν.
    """
    return str(v or "").strip().lower() in SIDE_YES


def _tab_rows(tab):
    ws = _wb[tab]; d = {}
    for r in range(2, ws.max_row + 1):
        aa, name, price = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value
        side = ws.cell(r, 5).value if ws.max_column >= 5 else None
        if aa is None or not name:
            continue
        try:
            d[int(aa)] = (str(name).strip(),
                          float(price) if price not in (None, "") else None,
                          _wants_side(side))
        except (TypeError, ValueError):
            continue
    return d

# --- ΠΙΑΤΑ.md: ευρετήριο «ποιος αριθμός είναι ποιο πιάτο» -------------------
# Ταξινομημένο κατά ΣΥΧΝΟΤΗΤΑ, όχι κατά Α/Α: τα πιάτα που βάζεις σχεδόν κάθε
# μέρα πρώτα, η ουρά αλφαβητικά στο τέλος. Η σήμανση είναι η στήλη D του
# DAILY_MENU.xlsx:  Κ = κάθε μέρα, Σ = συχνά, κενό = σπάνια.
INDEX_MD = os.path.join(HERE, "..", "ΠΙΑΤΑ.md")
TIERS = [("Κ", "Κάθε μέρα"), ("Σ", "Συχνά"), ("", "Σπάνια — αλφαβητικά")]


def _tab_index(tab):
    """(Α/Α, όνομα, τιμή, σήμανση) για κάθε γραμμή ενός tab."""
    ws = _wb[tab]
    out = []
    for r in range(2, ws.max_row + 1):
        aa, name, price = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value
        tier = ws.cell(r, 4).value
        if aa is None or not name:
            continue
        try:
            n = int(aa)
        except (TypeError, ValueError):
            continue
        try:
            p = float(price) if price not in (None, "") else None
        except (TypeError, ValueError):
            p = None
        t = str(tier).strip().upper() if tier else ""
        out.append((n, str(name).strip(), p, t if t in ("Κ", "Σ") else ""))
    return out


def _md_line(n, name, price):
    p = f"{price:.2f}".replace(".", ",") + " €" if price is not None else "—"
    return f"| **{n}** | {name} | {p} |"


def write_index():
    L = ["# Πιάτα & αριθμοί", "",
         "Ο αριθμός κάθε πιάτου, για να τον γράφεις στο `menu-today.txt`.",
         "**Παράγεται αυτόματα — μην το επεξεργάζεσαι.** Αλλαγές γίνονται στο",
         "`DAILY_MENU.xlsx` (στήλη «Συχνό;»: `Κ` = κάθε μέρα, `Σ` = συχνά).", ""]
    for label, slug, tab in CATEGORIES:
        rows = _tab_index(tab)
        if not rows:
            continue
        L += [f"## {label}", ""]
        if slug in HIDE_PRICE:
            L += ["_Εμφανίζονται στο site χωρίς τιμή._", ""]
        has_tiers = any(r[3] for r in rows)
        for code, title in TIERS:
            part = [r for r in rows if r[3] == code]
            if not part:
                continue
            # η μεγάλη ουρά αλφαβητικά (ψάχνεις με το όνομα)· παντού αλλού
            # με τη σειρά των Α/Α (σύντομες λίστες, τις σκανάρεις με το μάτι)
            part.sort(key=(lambda r: r[1].lower()) if has_tiers and not code
                      else (lambda r: r[0]))
            if has_tiers:
                L += [f"### {title}", ""]
            L += ["| # | Πιάτο | Τιμή |", "|--:|---|--:|"]
            L += [_md_line(n, name, p) for n, name, p, _ in part]
            L += [""]
            first = False
    L += ["---", "",
          f"_{sum(len(_tab_index(t)) for _, _, t in CATEGORIES)} πιάτα συνολικά._"]
    with open(INDEX_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return INDEX_MD


MENU = []
_name_errors = []
for label, slug, tab in CATEGORIES:
    rows = _tab_rows(tab)
    nums, errs = dish_names.parse_selection(selection_raw.get(slug, ""), rows)
    _name_errors += [f"[{label}] {e}" for e in errs]
    items = []
    for n in nums:
        if n in rows:
            name, price, side = rows[n]
            items.append({"name": name,
                          "price": None if slug in HIDE_PRICE else price,
                          "side": side})
    cat = {"slug": slug, "label": label, "items": items}
    if slug in NOTES:
        cat["note"] = NOTES[slug]
    MENU.append(cat)

# Άγνωστο ή διφορούμενο όνομα σταματά το build. Το να παραλειφθεί σιωπηλά ένα
# πιάτο είναι χειρότερο από το να μη δημοσιευτεί το μενού: το site θα έδειχνε
# λάθος κατάλογο και κανείς δεν θα το έπαιρνε είδηση.
if _name_errors:
    raise SystemExit("!! " + "\n!! ".join(_name_errors))

# Τα συνοδευτικά της ημέρας — αυτά προσφέρονται στα πιάτα που τα δέχονται.
# Αν σήμερα δεν έχει επιλεγεί κανένα, η επιλογή δεν εμφανίζεται πουθενά.
SIDES = [it["name"] for c in MENU if c["slug"] == "synodeytika" for it in c["items"]]

def esc(s): return html.escape(str(s), quote=True)
def fmt_price(v):
    return None if v is None else f"{float(v):.2f}".replace(".", ",") + " €"

# time slots 12:00–16:00 every 15' for the order dropdown
_slots, _h, _m = [], 12, 0
while _h < 16 or (_h == 16 and _m == 0):
    _slots.append(f"{_h:02d}:{_m:02d}")
    _m += 15
    if _m == 60: _m, _h = 0, _h + 1
TIME_OPTIONS = '<option value="">Διάλεξε ώρα…</option>' + "".join(
    f'<option value="{s}">{s}</option>' for s in _slots)

def item_html(it):
    portion = f' <span class="portion">{esc(it["portion"])}</span>' if it.get("portion") else ""
    p = fmt_price(it.get("price"))
    price_span = f'<span class="price">{esc(p)}</span>' if p else ""
    dots = '<span class="dots"></span>' if p else '<span class="dots"></span>'
    qty = ('<div class="qty" data-qty="0">'
           '<button class="q-minus" type="button" aria-label="Αφαίρεση" tabindex="-1">−</button>'
           '<span class="q-n">0</span>'
           '<button class="q-plus" type="button" aria-label="Προσθήκη">＋</button></div>')
    pnum = "" if it.get("price") is None else f'{float(it["price"]):.2f}'
    line = (f'<div class="item-line"><span class="gr">{esc(it["name"])}{portion}</span>'
            f'{dots}{price_span}{qty}</div>')
    if it.get("desc"):
        line += f'\n        <p class="desc" lang="el">{esc(it["desc"])}</p>'
    # Πιάτο που συνοδεύεται χωρίς χρέωση: το JS γεμίζει εδώ ΕΝΑ select ανά μερίδα,
    # ώστε δύο μπιφτέκια να μπορούν να πάρουν διαφορετικό συνοδευτικό.
    side_attr = ' data-side="1"' if (it.get("side") and SIDES) else ""
    if side_attr:
        line += '\n        <div class="sides" hidden></div>'
    return (f'      <li class="item" data-name="{esc(it["name"])}" '
            f'data-price="{pnum}"{side_attr}>{line}</li>')

nav = "\n".join(f'    <a class="chip" href="#{c["slug"]}">{esc(c["label"])}</a>' for c in MENU)
nav += f'\n    <a class="chip" href="#magazi">{esc(ABOUT_CHIP)}</a>'

secs = []
for c in MENU:
    if c["items"]:
        body = '<ul class="items">\n' + "\n".join(item_html(it) for it in c["items"]) + '\n    </ul>'
    else:
        body = '<p class="empty-note">— σύντομα —</p>'
    if c.get("note"):
        body += f'\n    <p class="sec-note" lang="el">{esc(c["note"])}</p>'
    secs.append(f'''  <section id="{c["slug"]}" aria-labelledby="h-{c["slug"]}">
    <div class="sec-head">
      <h2 id="h-{c["slug"]}" lang="el">{esc(c["label"])}</h2>
    </div>
    {body}
  </section>''')
sections_html = "\n\n".join(secs)

# --- κλειστό μαγαζί: ανακοίνωση αντί για μενού, χωρίς παραγγελίες ----------
if CLOSED:
    nav = ""
    sections_html = f'''  <section class="closed" aria-labelledby="h-closed">
    <p class="closed-eyebrow" lang="el">Κλειστά για διακοπές</p>
    <h2 id="h-closed" class="closed-title" lang="el">Ανοίγουμε {esc(CLOSED)}</h2>
    <p class="closed-sub" lang="el">Ξεκουραζόμαστε για λίγο και επιστρέφουμε
      με το ίδιο σπιτικό φαγητό. Σας ευχαριστούμε!</p>
    <p class="closed-call">Για πληροφορίες:
      <a href="tel:{VIBER_NUMBER}">{VIBER_DISPLAY}</a></p>
  </section>'''

# κομμάτια που μπαίνουν μόνο όταν το μαγαζί είναι ανοιχτό
date_html = "" if CLOSED else f'<p class="menu-date" lang="el">{esc(MENU_DATE)}</p>'
rail_html = "" if CLOSED else f'''<nav class="rail" aria-label="Κατηγορίες μενού">
  <div class="rail-inner">
{nav}
  </div>
</nav>'''
orderbar_html = "" if CLOSED else f'''<div class="order-bar" id="orderBar" role="region" aria-label="Η παραγγελία σου">
  <div class="order-opts">
    <div class="seg" role="group" aria-label="Τρόπος παραλαβής">
      <button type="button" class="seg-btn active" data-type="delivery">🛵 Delivery</button>
      <button type="button" class="seg-btn" data-type="pickup">🏠 Παραλαβή</button>
    </div>
    <label class="time-field">Ώρα<select id="orderTime">{TIME_OPTIONS}</select></label>
  </div>
  <div class="order-inner">
    <button class="order-clear" id="orderClear" type="button">Καθαρισμός</button>
    <div class="order-sum"><div class="order-list" id="orderItems"></div><b id="orderTotal">0,00 €</b><small id="orderCount">0 είδη</small></div>
  </div>
  <div class="order-actions">
    <a class="order-btn sms" id="orderSms" href="#" role="button">💬 SMS</a>
    <a class="order-btn viber" id="orderViber" href="#" role="button">📲 Viber</a>
  </div>
  <a class="order-call" href="tel:{VIBER_NUMBER}">ή κάλεσέ μας: <b>{VIBER_DISPLAY}</b></a>
</div>'''

# «Το μαγαζί μας» — μπαίνει και στις δύο καταστάσεις (ανοιχτά/κλειστά): όσο είμαστε
# κλειστοί είναι το μόνο που έχει να δει ο πελάτης που σκανάρει το QR.
gallery_html = "\n".join(
    f'      <img src="{GALLERY_DIR}/{esc(f)}" alt="{esc(alt)}" loading="lazy" '
    f'decoding="async" style="object-position:{esc(pos)}">'
    for f, alt, pos in GALLERY)
about_html = f'''  <section id="magazi" aria-labelledby="h-magazi">
    <div class="sec-head">
      <h2 id="h-magazi" lang="el">{esc(ABOUT_TITLE)}</h2>
    </div>
    <p class="about-text" lang="el">{esc(ABOUT_TEXT)}</p>
    <div class="gallery">
{gallery_html}
    </div>
  </section>'''

page_title = (f"Merci Μαγειρευτό · Κλειστά — ανοίγουμε {CLOSED}" if CLOSED
              else "Merci Μαγειρευτό · Μενού — Λάρισα")
page_desc = (f"Το Merci Μαγειρευτό είναι κλειστό για διακοπές. Ανοίγουμε {CLOSED}."
             if CLOSED else
             "Μενού — Merci Μαγειρευτό, σπιτικό φαγητό, Λάρισα. Take away & delivery.")

CSS = """
  :root{
    --paper:#2B487A; --raised:#33528A; --ink:#F3ECDF; --muted:#C6CFDF; --faint:#93A2BE;
    --sea:#E0885A; --sand:#E4CE94; --sand-deep:#D3B978; --leader:#4C67A0;
    --hairline:#3D5A90; --chip-bg:#264270; --mist-2:#233C67; --pot:#E0885A;
    --display:"GFS Didot","Palatino Linotype",Palatino,Georgia,serif;
    --body:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  }
  *{box-sizing:border-box;} html{-webkit-text-size-adjust:100%;}
  @media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth;}}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:1rem;line-height:1.55;}

  /* ---- faint large logo watermark ---- */
  .wm{position:fixed;inset:0;z-index:0;pointer-events:none;background:url("assets/merci-logo.png") no-repeat center 43%;background-size:min(82vw,600px);opacity:.16;}
  .cove,main,footer{position:relative;z-index:1;}

  .cove{overflow:hidden;background:linear-gradient(160deg,#345699,var(--paper));text-align:center;padding:3.25rem 1.25rem 2.2rem;border-bottom:1px solid var(--hairline);}
  .pot{position:absolute;top:1.6rem;left:6%;width:clamp(78px,17vw,128px);height:auto;}
  .pan{position:absolute;top:2.2rem;right:6%;width:clamp(74px,16vw,120px);height:auto;}
  .steam{fill:none;stroke:#EAD9BE;stroke-width:4;stroke-linecap:round;opacity:.0;transform-origin:center;}
  @media (prefers-reduced-motion:no-preference){
    .steam{animation:steam 3.4s ease-in-out infinite;}
    .steam.s2{animation-delay:.7s;} .steam.s3{animation-delay:1.4s;}
  }
  @media (prefers-reduced-motion:reduce){ .steam{opacity:.5;} }
  @keyframes steam{0%{opacity:0;transform:translateY(6px) scaleY(.85);}
    35%{opacity:.75;} 70%{opacity:.35;} 100%{opacity:0;transform:translateY(-6px) scaleY(1.1);}}

  .brand{position:relative;font-family:var(--display);font-weight:400;font-size:clamp(2.6rem,10vw,4.2rem);line-height:1.05;letter-spacing:.01em;margin:0;text-wrap:balance;}
  .brand .merci{display:block;font-size:.4em;letter-spacing:.5em;text-indent:.5em;text-transform:uppercase;color:var(--sea);margin:0 0 .3rem;}
  .brand-sub{position:relative;margin:.9rem 0 0;font-size:.74rem;font-weight:600;letter-spacing:.3em;text-indent:.3em;text-transform:uppercase;color:var(--sand);}
  .menu-date{position:relative;display:inline-block;margin:.8rem 0 0;padding:.32rem 1.15rem;background:var(--sand);color:#22324F;font-weight:800;font-size:clamp(1.5rem,6vw,2.15rem);letter-spacing:.01em;border-radius:999px;box-shadow:0 6px 18px rgba(0,0,0,.28);}

  .rail{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--paper) 90%,transparent);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--hairline);}
  .rail-inner{display:flex;gap:.5rem;overflow-x:auto;padding:.7rem 1.1rem;max-width:48rem;margin:0 auto;scrollbar-width:none;justify-content:flex-start;}
  .rail-inner::-webkit-scrollbar{display:none;}
  .chip{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:.4rem .9rem;border-radius:18px;border:1px solid var(--hairline);background:var(--chip-bg);color:var(--muted);font-size:.94rem;font-weight:600;line-height:1.2;text-align:center;text-decoration:none;white-space:nowrap;cursor:pointer;transition:background-color .2s,color .2s,border-color .2s;}
  .chip:hover{border-color:var(--sea);color:var(--ink);}
  .chip.is-active{background:var(--sea);border-color:var(--sea);color:#10203A;}
  .chip:focus-visible,a:focus-visible{outline:2px solid var(--sand);outline-offset:2px;}

  main{max-width:44rem;margin:0 auto;padding:.75rem 1.25rem 2rem;}
  section{scroll-margin-top:4.6rem;padding-top:2.6rem;}
  .sec-head{display:flex;align-items:baseline;gap:.75rem;border-bottom:2px solid var(--sand-deep);padding-bottom:.55rem;}
  .sec-head h2{font-family:var(--display);font-weight:400;font-size:clamp(1.8rem,6vw,2.3rem);margin:0;letter-spacing:.01em;color:var(--ink);}
  .items{list-style:none;margin:0;padding:0;}
  .item{padding:.72rem 0;border-bottom:1px solid var(--hairline);}
  .item:last-child{border-bottom:none;}
  .item-line{display:flex;align-items:baseline;gap:.55rem;}
  .gr{font-weight:600;}
  .portion{font-weight:400;font-size:.8rem;color:var(--faint);}
  .dots{flex:1 1 1.5rem;min-width:1.5rem;border-bottom:2px dotted var(--leader);transform:translateY(-.28em);}
  .price{font-variant-numeric:tabular-nums;font-weight:650;white-space:nowrap;color:var(--sand);}
  .desc{margin:.3rem 0 0;font-size:.86rem;color:var(--muted);max-width:34rem;}
  .sec-note{margin:1rem 0 0;font-family:var(--display);font-size:1.05rem;font-style:italic;color:var(--sea);text-align:center;}
  .empty-note{margin:1.4rem 0 .4rem;color:var(--faint);font-style:italic;text-align:center;}
  .closed{text-align:center;padding:2.6rem 1.1rem 3rem;}
  .closed-eyebrow{margin:0;color:var(--sea);font-size:.92rem;font-weight:700;letter-spacing:.22em;text-transform:uppercase;}
  .closed-title{font-family:var(--display);font-weight:400;font-size:clamp(2rem,8vw,3rem);line-height:1.15;margin:.7rem auto 0;max-width:16ch;color:var(--ink);}
  .closed-title::after{content:"";display:block;width:72px;height:3px;margin:1.1rem auto 0;border-radius:2px;background:var(--sand);}
  .closed-sub{max-width:34ch;margin:1.2rem auto 0;color:var(--muted);font-size:1.05rem;}
  .closed-call{margin:1.8rem 0 0;font-size:1.05rem;color:var(--muted);}
  .closed-call a{color:var(--sand);font-weight:700;text-decoration:none;white-space:nowrap;}
  .closed-call a:hover{text-decoration:underline;}

  /* ---- quantity stepper ---- */
  .qty{flex:0 0 auto;display:inline-flex;align-items:center;gap:.1rem;margin-left:.6rem;}
  .qty button{width:30px;height:30px;border-radius:50%;border:1px solid var(--sea);background:transparent;color:var(--sea);font-size:1.15rem;line-height:1;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;padding:0;transition:background-color .15s,color .15s;}
  .qty .q-plus{background:var(--sea);color:#10203A;border-color:var(--sea);}
  .qty button:active{transform:scale(.92);}
  .qty .q-minus,.qty .q-n{display:none;}
  .qty .q-n{min-width:1.4ch;text-align:center;font-weight:700;font-variant-numeric:tabular-nums;color:var(--ink);}
  .qty[data-qty]:not([data-qty="0"]) .q-minus,
  .qty[data-qty]:not([data-qty="0"]) .q-n{display:inline-flex;align-items:center;justify-content:center;}
  .item.in-cart{background:color-mix(in srgb,var(--sea) 8%,transparent);}

  /* ---- order bar ---- */
  .order-bar{position:fixed;left:0;right:0;bottom:0;z-index:20;transform:translateY(120%);transition:transform .28s ease;background:color-mix(in srgb,var(--mist-2) 96%,transparent);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-top:1px solid var(--hairline);padding:.7rem 1rem calc(.7rem + env(safe-area-inset-bottom));}
  .order-bar.show{transform:translateY(0);}
  .order-opts{max-width:44rem;margin:0 auto .55rem;display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;}
  .seg{display:inline-flex;border:1px solid var(--hairline);border-radius:12px;overflow:hidden;background:var(--chip-bg);}
  .seg-btn{border:none;background:transparent;color:var(--muted);font-weight:600;font-size:.88rem;padding:.5rem .8rem;cursor:pointer;transition:background-color .15s,color .15s;}
  .seg-btn.active{background:var(--sea);color:#10203A;}
  .time-field{display:inline-flex;align-items:center;gap:.4rem;color:var(--muted);font-size:.88rem;font-weight:600;}
  .time-field select{background:var(--chip-bg);border:1px solid var(--hairline);border-radius:10px;color:var(--ink);padding:.5rem .6rem;font-size:.95rem;font-weight:700;font-family:inherit;cursor:pointer;-webkit-appearance:menulist;appearance:menulist;}
  .time-field select:required:invalid{color:var(--faint);font-weight:600;}
  .order-inner{max-width:44rem;margin:0 auto;display:flex;align-items:center;gap:.8rem;}
  .order-sum{flex:1 1 auto;min-width:0;line-height:1.25;}
  .order-sum b{display:block;font-size:1.05rem;color:var(--ink);font-variant-numeric:tabular-nums;}
  .order-sum small{color:var(--muted);font-size:.8rem;}
  .order-list{font-size:.72rem;line-height:1.3;color:var(--muted);margin-bottom:.2rem;max-height:26vh;overflow-y:auto;}
  .order-list div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .order-list .ol-side{color:var(--sand);}
  .order-actions{max-width:44rem;margin:.55rem auto 0;display:flex;gap:.6rem;}
  .order-btn{flex:1 1 auto;display:inline-flex;align-items:center;justify-content:center;gap:.5rem;border:none;border-radius:14px;padding:.8rem 1rem;font-size:1rem;font-weight:700;cursor:pointer;text-decoration:none;white-space:nowrap;}
  .order-btn.sms{flex:1 1 auto;background:#2FB457;color:#08351a;}
  .order-btn.viber{flex:1 1 auto;background:#7360F2;color:#fff;}
  .order-btn:active{transform:scale(.97);}
  .order-clear{flex:0 0 auto;background:transparent;border:none;color:var(--faint);font-size:.8rem;cursor:pointer;text-decoration:underline;}
  main{padding-bottom:6rem;}
  .order-call{display:block;text-align:center;margin:.45rem auto 0;font-size:.8rem;color:var(--muted);text-decoration:none;}
  .order-call b{color:var(--sand);}

  /* ---- toast ---- */
  .toast{position:fixed;left:50%;bottom:6.5rem;transform:translate(-50%,1.2rem);z-index:30;max-width:calc(100% - 2rem);width:24rem;background:#17293F;color:var(--ink);border:1px solid var(--sea);border-radius:14px;padding:.8rem 1rem;font-size:.9rem;line-height:1.4;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.35);opacity:0;pointer-events:none;transition:opacity .25s ease,transform .25s ease;}
  .toast.show{opacity:1;transform:translate(-50%,0);}

  /* ---- συνοδευτικό χωρίς χρέωση ---- */
  .sides{display:flex;flex-direction:column;gap:.4rem;margin:.55rem 0 .2rem 0;padding-left:.1rem;}
  .side-row{display:flex;align-items:center;gap:.5rem;font-size:.82rem;color:var(--muted);}
  .side-row span{flex:0 0 auto;min-width:5.5rem;}
  .side-row select{flex:1 1 auto;min-width:0;background:var(--chip-bg);border:1px solid var(--hairline);border-radius:10px;color:var(--ink);padding:.4rem .5rem;font-size:.88rem;font-family:inherit;cursor:pointer;-webkit-appearance:menulist;appearance:menulist;}
  .side-row select:invalid,.side-row select:not([value]){color:var(--faint);}

  /* ---- «Το μαγαζί μας» ---- */
  /* Κεντραρισμένα, σε αντίθεση με τις κατηγορίες φαγητού: είναι κείμενο, όχι
     λίστα με τιμές — και στα κλειστά κάθεται κάτω από την κεντραρισμένη ανακοίνωση. */
  #magazi .sec-head{justify-content:center;}
  .about-text{max-width:44ch;margin:1.1rem auto 0;color:var(--muted);text-align:center;}
  .gallery{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem;margin-top:1.5rem;}
  @media (min-width:34rem){ .gallery{grid-template-columns:repeat(3,1fr);} }
  .gallery img{display:block;width:100%;aspect-ratio:1;object-fit:cover;border-radius:12px;border:1px solid var(--hairline);background:var(--raised);}

  footer{border-top:1px solid var(--hairline);background:var(--mist-2);text-align:center;padding:2.2rem 1.5rem 2.6rem;}
  .foot-brand{font-family:var(--display);font-size:1.4rem;margin:0 0 .2rem;}
  .foot-place{font-size:.72rem;font-weight:700;letter-spacing:.26em;text-indent:.26em;text-transform:uppercase;color:var(--sea);margin:0 0 1.2rem;}
  .foot-addr{font-size:.9rem;margin:.1rem 0 .1rem;}
  .foot-addr a{color:var(--ink);text-decoration:none;border-bottom:1px dotted var(--faint);}
  .foot-hours{font-size:.9rem;color:var(--ink);margin:.5rem 0 .5rem;}
  .foot-contact{font-size:1rem;font-weight:700;margin:0 0 1rem;}
  .foot-contact a{color:var(--sand);text-decoration:none;}
  .legal{max-width:34rem;margin:0 auto;font-size:.76rem;line-height:1.6;color:var(--muted);}
  .legal p{margin:.35rem 0;}
"""

POT_SVG = '''<svg class="pot" viewBox="0 0 130 130" aria-hidden="true">
    <path class="steam s1" d="M50 44 C44 36 56 32 50 24 C44 16 56 12 52 6"/>
    <path class="steam s2" d="M67 44 C61 36 73 32 67 24 C61 16 73 12 69 6"/>
    <path class="steam s3" d="M84 44 C78 36 90 32 84 24 C78 16 90 12 86 6"/>
    <rect x="30" y="60" width="70" height="46" rx="9" fill="#C9975B"/>
    <rect x="30" y="60" width="70" height="14" rx="7" fill="#E0A96D"/>
    <rect x="22" y="52" width="86" height="12" rx="6" fill="#E0885A"/>
    <rect x="58" y="45" width="14" height="9" rx="4" fill="#E0885A"/>
    <rect x="14" y="72" width="12" height="20" rx="6" fill="#B07C3F"/>
    <rect x="104" y="72" width="12" height="20" rx="6" fill="#B07C3F"/>
  </svg>'''

PAN_SVG = '''<svg class="pan" viewBox="0 0 140 120" aria-hidden="true">
    <path class="steam s1" d="M52 40 C46 32 58 28 52 20 C46 12 58 8 54 2"/>
    <path class="steam s2" d="M70 40 C64 32 76 28 70 20 C64 12 76 8 72 2"/>
    <ellipse cx="60" cy="78" rx="46" ry="30" fill="#B07C3F"/>
    <ellipse cx="60" cy="73" rx="46" ry="30" fill="#C9975B"/>
    <ellipse cx="60" cy="71" rx="37" ry="22" fill="#2C2013"/>
    <ellipse cx="52" cy="65" rx="9" ry="5" fill="#E0885A" opacity=".7"/>
    <rect x="100" y="66" width="40" height="11" rx="5.5" fill="#7A5326" transform="rotate(-16 100 66)"/>
  </svg>'''

ORDER_JS = r'''
(function () {
  var DATE = __DATE_JSON__;
  var NUMBER = __NUMBER_JSON__;
  var SIDES = __SIDES_JSON__;
  var items = Array.prototype.slice.call(document.querySelectorAll(".item"));
  var bar = document.getElementById("orderBar");
  var elTotal = document.getElementById("orderTotal");
  var elCount = document.getElementById("orderCount");
  var elList = document.getElementById("orderItems");
  var clearBtn = document.getElementById("orderClear");
  var toast = document.getElementById("toast");
  if (!bar) return;

  function money(n) { return n.toFixed(2).replace(".", ",") + " €"; }

  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () { toast.classList.remove("show"); }, 6000);
  }

  function copyText(t) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(t);
    return new Promise(function (res, rej) {
      try {
        var ta = document.createElement("textarea");
        ta.value = t; ta.setAttribute("readonly", "");
        ta.style.position = "absolute"; ta.style.left = "-9999px";
        document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta); res();
      } catch (e) { rej(e); }
    });
  }

  var segBtns = Array.prototype.slice.call(document.querySelectorAll(".seg-btn"));
  var timeEl = document.getElementById("orderTime");
  var orderType = "delivery";
  segBtns.forEach(function (b) {
    b.addEventListener("click", function () {
      segBtns.forEach(function (x) { x.classList.remove("active"); });
      b.classList.add("active");
      orderType = b.getAttribute("data-type");
    });
  });

  function qOf(li) { return parseInt(li.querySelector(".qty").getAttribute("data-qty"), 10) || 0; }

  // --- συνοδευτικά χωρίς χρέωση -------------------------------------------
  // Ένα select ανά μερίδα: 2× μπιφτέκι μπορεί να πάρει πατάτες και ρύζι.
  function syncSides(li) {
    var box = li.querySelector(".sides");
    if (!box) return;
    var q = qOf(li), have = box.children.length;
    for (var i = have; i < q; i++) {
      var row = document.createElement("label");
      row.className = "side-row";
      var txt = document.createElement("span");
      txt.textContent = q > 1 ? "Μερίδα " + (i + 1) : "Συνοδευτικό";
      var sel = document.createElement("select");
      sel.innerHTML = '<option value="">Διάλεξε συνοδευτικό…</option>' +
        SIDES.map(function (s) {
          return '<option value="' + s + '">' + s + "</option>";
        }).join("") + '<option value="—">Χωρίς συνοδευτικό</option>';
      sel.addEventListener("change", refresh);
      row.appendChild(txt); row.appendChild(sel);
      box.appendChild(row);
    }
    while (box.children.length > q) box.removeChild(box.lastChild);
    // οι ετικέτες αλλάζουν όταν αλλάζει η ποσότητα (1 μερίδα -> «Συνοδευτικό»)
    Array.prototype.forEach.call(box.children, function (row, i) {
      row.firstChild.textContent = q > 1 ? "Μερίδα " + (i + 1) : "Συνοδευτικό";
    });
    box.hidden = q === 0;
  }

  function sidesOf(li) {
    var box = li.querySelector(".sides");
    if (!box) return [];
    return Array.prototype.map.call(box.querySelectorAll("select"), function (s) {
      return s.value;
    });
  }

  function refresh() {
    var count = 0, total = 0;
    if (elList) elList.innerHTML = "";
    items.forEach(function (li) {
      var q = qOf(li);
      syncSides(li);
      if (q > 0) {
        count += q;
        var pr = parseFloat(li.getAttribute("data-price"));
        if (!isNaN(pr)) total += pr * q;
        li.classList.add("in-cart");
        if (elList) {
          var d = document.createElement("div");
          d.textContent = q + "× " + li.getAttribute("data-name");
          // το συνοδευτικό φαίνεται και στη μπάρα, δίπλα στο πιάτο
          var chosen = sidesOf(li).filter(function (x) { return x && x !== "—"; });
          if (chosen.length) {
            var sp = document.createElement("span");
            sp.className = "ol-side";
            sp.textContent = " · " + chosen.join(", ");
            d.appendChild(sp);
          }
          elList.appendChild(d);
        }
      } else { li.classList.remove("in-cart"); }
    });
    elTotal.textContent = money(total);
    elCount.textContent = count + (count === 1 ? " είδος" : " είδη");
    bar.classList.toggle("show", count > 0);
  }

  items.forEach(function (li) {
    var qty = li.querySelector(".qty"), nEl = li.querySelector(".q-n");
    function set(q) { q = Math.max(0, q); qty.setAttribute("data-qty", q); nEl.textContent = q; refresh(); }
    li.querySelector(".q-plus").addEventListener("click", function () { set(qOf(li) + 1); });
    li.querySelector(".q-minus").addEventListener("click", function () { set(qOf(li) - 1); });
  });

  clearBtn.addEventListener("click", function () {
    items.forEach(function (li) { li.querySelector(".qty").setAttribute("data-qty", 0); li.querySelector(".q-n").textContent = "0"; });
    refresh();
  });

  function buildText() {
    var lines = ["🍽️ Νέα παραγγελία — Merci Μαγειρευτό", DATE, ""];
    var total = 0;
    items.forEach(function (li) {
      var q = qOf(li);
      if (q <= 0) return;
      var name = li.getAttribute("data-name");
      var praw = li.getAttribute("data-price");
      if (praw !== "") { var pr = parseFloat(praw); total += pr * q; lines.push("• " + q + "× " + name + " — " + money(pr * q)); }
      else { lines.push("• " + q + "× " + name); }
      sidesOf(li).forEach(function (s) {
        if (s && s !== "—") lines.push("    ↳ με " + s);
      });
    });
    lines.push("");
    lines.push("Σύνολο: " + money(total));
    lines.push("");
    lines.push("Τρόπος: " + (orderType === "delivery" ? "🛵 Delivery" : "🏠 Παραλαβή"));
    lines.push("Ώρα: " + timeEl.value);
    lines.push("");
    lines.push(orderType === "delivery"
      ? "(Συμπλήρωσε όνομα & διεύθυνση παράδοσης)"
      : "(Συμπλήρωσε το όνομά σου)");
    return lines.join("\n");
  }

  function validTime() {
    var t = timeEl.value;
    if (!t) { showToast("Διάλεξε ώρα (12:00–16:00)."); timeEl.focus(); return false; }
    var mins = parseInt(t.slice(0, 2), 10) * 60 + parseInt(t.slice(3, 5), 10);
    if (mins < 720 || mins > 960) { showToast("Η ώρα πρέπει να είναι μεταξύ 12:00 και 16:00."); timeEl.focus(); return false; }
    return true;
  }

  function validSides() {
    for (var i = 0; i < items.length; i++) {
      var li = items[i];
      if (qOf(li) <= 0) continue;
      var sel = Array.prototype.filter.call(
        li.querySelectorAll(".sides select"), function (s) { return !s.value; });
      if (sel.length) {
        showToast("Διάλεξε συνοδευτικό για: " + li.getAttribute("data-name"));
        sel[0].focus();
        return false;
      }
    }
    return true;
  }

  var smsBtn = document.getElementById("orderSms");
  smsBtn.addEventListener("click", function (e) {
    e.preventDefault();
    if (!validTime() || !validSides()) return;
    var txt = buildText();
    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    var sep = isIOS ? "&" : "?";
    window.location.href = "sms:" + NUMBER + sep + "body=" + encodeURIComponent(txt);
  });

  // Viber: το «viber://chat?number=» ΔΕΝ δέχεται έτοιμο κείμενο — μόνο το
  // «forward» δέχεται, αλλά εκεί ο πελάτης πρέπει να βρει μόνος του τον
  // παραλήπτη. Οπότε: αντιγράφουμε την παραγγελία και ανοίγουμε τη σωστή
  // συνομιλία· ο πελάτης κάνει μία επικόλληση.
  var viberBtn = document.getElementById("orderViber");
  if (viberBtn) {
    viberBtn.addEventListener("click", function (e) {
      e.preventDefault();
      if (!validTime() || !validSides()) return;
      var txt = buildText();
      function go() {
        showToast("Η παραγγελία αντιγράφηκε. Άνοιξε το Viber και κάνε "
                  + "επικόλληση (κράτα πατημένο στο πεδίο μηνύματος).");
        window.location.href = "viber://chat?number=" + encodeURIComponent(NUMBER);
      }
      copyText(txt).then(go, function () {
        // χωρίς πρόχειρο (παλιό browser): τουλάχιστον άνοιξε τη συνομιλία
        showToast("Άνοιξε το Viber και γράψε την παραγγελία σου.");
        window.location.href = "viber://chat?number=" + encodeURIComponent(NUMBER);
      });
    });
  }

  refresh();
})();
'''.replace("__DATE_JSON__", json.dumps(MENU_DATE, ensure_ascii=False)) \
   .replace("__NUMBER_JSON__", json.dumps(VIBER_NUMBER, ensure_ascii=False)) \
   .replace("__SIDES_JSON__", json.dumps(SIDES, ensure_ascii=False))

order_script = "" if CLOSED else f"<script>\n{ORDER_JS}\n</script>"

HTML = f'''<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)}</title>
<meta name="description" content="{esc(page_desc)}">
</head>
<body>
<style>
{FONT_FACES}
{CSS}
</style>

<div class="wm" aria-hidden="true"></div>

<header class="cove">
  {POT_SVG}
  {PAN_SVG}
  <h1 class="brand" lang="el"><span class="merci">Merci</span>Μαγειρευτό</h1>
  <p class="brand-sub">Σπιτικό φαγητό</p>
  {date_html}
</header>

{rail_html}

<main>
{sections_html}

{about_html}
</main>

{orderbar_html}

<div class="toast" id="toast" role="status" aria-live="polite"></div>

<footer>
  <p class="foot-brand" lang="el">Merci Μαγειρευτό</p>
  <p class="foot-place">Take away &amp; Delivery</p>
  <p class="foot-addr"><a href="https://www.google.com/maps/search/?api=1&amp;query=%CE%9A%CE%B1%CF%81%CE%B4%CE%AF%CF%84%CF%83%CE%B7%CF%82+22+%CE%9B%CE%AC%CF%81%CE%B9%CF%83%CE%B1" target="_blank" rel="noopener">📍 Καρδίτσης 22, 41335 Λάρισα</a></p>
  <p class="foot-hours" lang="el">Δευτέρα – Σάββατο, 12:00 – 16:00</p>
  <p class="foot-contact"><a href="tel:2414010332">☎ 2414010332</a> &nbsp;·&nbsp; <a href="tel:+306987992887">📱 698 799 2887</a></p>
  <div class="legal">
    <p lang="el">Οι τιμές περιλαμβάνουν όλους τους νόμιμους φόρους. Ο καταναλωτής δεν έχει την υποχρέωση να πληρώσει εάν δε λάβει το νόμιμο παραστατικό στοιχείο (απόδειξη-τιμολόγιο).</p>
  </div>
</footer>

<script>
  (function () {{
    var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
    var byId = {{}};
    chips.forEach(function (chip) {{ byId[chip.getAttribute("href").slice(1)] = chip; }});
    var current = null;
    function activate(id) {{
      if (current === id) return;
      current = id;
      chips.forEach(function (chip) {{ chip.classList.remove("is-active"); }});
      var chip = byId[id];
      if (chip) {{ chip.classList.add("is-active"); chip.scrollIntoView({{ block: "nearest", inline: "center", behavior: "smooth" }}); }}
    }}
    if ("IntersectionObserver" in window) {{
      var visible = {{}};
      var observer = new IntersectionObserver(function (entries) {{
        entries.forEach(function (entry) {{ visible[entry.target.id] = entry.isIntersecting; }});
        var secs = document.querySelectorAll("main section");
        for (var i = 0; i < secs.length; i++) {{ if (visible[secs[i].id]) {{ activate(secs[i].id); break; }} }}
      }}, {{ rootMargin: "-20% 0px -60% 0px" }});
      document.querySelectorAll("main section").forEach(function (sec) {{ observer.observe(sec); }});
    }}
  }})();
</script>

{order_script}
</body>
</html>
'''

# Τα γραψίματα μπαίνουν πίσω από main-guard ώστε το social.py να κάνει
# «import build» και να πάρει MENU / MENU_DATE / CLOSED χωρίς να ξαναγράψει
# αρχεία — μία πηγή αλήθειας για τα δεδομένα της ημέρας, χωρίς αντιγραφή.
if __name__ == "__main__":
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(HTML)
    print(f"Wrote {OUT}  ({len(MENU)} categories, "
          f"{sum(len(c['items']) for c in MENU)} dishes)")

    write_index()
    print(f"Wrote {INDEX_MD}")

# NOTE: DAILY_MENU.xlsx is the OWNER-maintained SOURCE of common dishes (per-category
# tabs: Α/Α | Ονομασία | Τιμή). The daily selection ("μαγειρευτά 1 2 4 …") is read FROM
# it to populate MENU above. This build no longer writes/overwrites it (would wipe edits).
