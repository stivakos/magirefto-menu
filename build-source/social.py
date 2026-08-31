#!/usr/bin/env python3
"""Φτιάχνει την εικόνα του μαυροπίνακα για τα social (Facebook / Instagram).

    python3 social.py            ->  ../social/menu.jpg   (1080×1350, 4:5)

Τα δεδομένα της ημέρας έρχονται με «import build»: το build.py κρατά τα
γραψίματά του πίσω από main-guard, οπότε εδώ παίρνουμε MENU / MENU_DATE /
CLOSED χωρίς να ξαναγραφτεί το index.html και χωρίς αντιγραφή κώδικα. Αν
αλλάξει το menu-today.txt, αλλάζει και η εικόνα — αυτόματα, από την ίδια πηγή.

Η σελίδα στήνεται σε HTML και φωτογραφίζεται με headless Chrome, ώστε να
χρησιμοποιεί το ίδιο fonts.css (GFS Didot) με το site. Το Pillow δεν θα
μπορούσε: οι ενσωματωμένες γραμματοσειρές είναι woff2.

Δεν κρατάμε αρχείο ανά ημέρα — ένα αρχείο που ξαναγράφεται. Μια εικόνα 200 KB
κάθε μέρα θα φούσκωνε το repo κατά ~70 MB τον χρόνο.
"""
import datetime
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

import build   # noqa: E402  — πηγή δεδομένων· δεν γράφει αρχεία στο import

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SLATE = os.path.join(ROOT, "assets", "social", "slate.jpg")
OUT = os.path.join(ROOT, "social", "menu.jpg")
# Ταυτότητα της εικόνας — ανεβαίνει δίπλα της στο social-preview branch.
SIDECAR = os.path.join(ROOT, "social", "menu.json")
FONTS = open(os.path.join(HERE, "fonts.css"), encoding="utf-8").read()

W, H = 1080, 1350          # Instagram feed 4:5 — δουλεύει και σε Facebook

MAIN_SLUG = "menu-hmeras"          # τα μαγειρευτά: μία στήλη, είναι μεγάλα ονόματα
TWO_COL = ("salates", "glyka")     # κοντά ονόματα -> δύο στήλες, μισές γραμμές
# Ό,τι δεν αναφέρεται εδώ (Συνοδευτικά, Αναψυκτικά) μπαίνει στη μία γραμμή
# «και ακόμη:». Τα Συνοδευτικά ούτως ή άλλως δεν έχουν τιμές.

SITE = "stivakos.github.io/magirefto-menu"   # ό,τι κωδικοποιεί και το τυπωμένο QR

LIST_H = 828               # px για τη λίστα: 1350 μείον κεφαλίδα και υποσέλιδο
LINE = 1.72                # ύψος γραμμής + κενό, ως πολλαπλάσιο του font-size
MIN_PT, MAX_PT = 26, 46    # κάτω από 26px δεν διαβάζεται σε κινητό μέσα στο feed
FLOOR_PT = 15              # απόλυτο κατώτατο: καλύτερα δυσανάγνωστο παρά κομμένο

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if c and (os.path.isfile(c) or shutil.which(c)):
            return c
    raise SystemExit(
        "ΣΦΑΛΜΑ: δεν βρέθηκε Chrome/Chromium. Όρισε τη μεταβλητή CHROME.")


def esc(s):
    return html.escape(str(s), quote=True)


def fmt_price(v):
    return "" if v is None else f"{float(v):.2f}".replace(".", ",") + " €"


def scale_for(lines):
    """Μέγεθος γραμματοσειράς & κενού από τις γραμμές που πρέπει να χωρέσουν.

    Το `lines` δεν είναι πλήθος πιάτων: οι δίστηλες ομάδες μετράνε μισές
    γραμμές και κάθε επικεφαλίδα ομάδας πιάνει ~1,5. Το body έχει
    overflow:hidden, άρα υπερχείλιση θα έκοβε σιωπηλά πιάτα — γι' αυτό ο
    υπολογισμός γίνεται εδώ και όχι «με το μάτι».
    """
    per = LIST_H / max(lines, 1)
    size = max(MIN_PT, min(MAX_PT, per / LINE))
    return round(size), round(size * 0.42)


def page_html():
    slate_url = "file://" + os.path.abspath(SLATE)
    date_line = build.MENU_DATE

    if build.CLOSED:
        body = f'''
    <div class="closed-wrap">
      <div class="closed-eyebrow">Κλειστά για διακοπές</div>
      <div class="closed-title">Ανοίγουμε<br>{esc(build.CLOSED)}</div>
      <div class="closed-sub">Σας ευχαριστούμε — τα λέμε από κοντά!</div>
    </div>'''
        foot = (f'☎ {esc(build.VIBER_DISPLAY)}'
                f'<div class="site">{SITE}</div>')
    else:
        # Ό,τι τελείωσε δεν μπαίνει στην εικόνα: αν κάποιος την ανοίξει το
        # μεσημέρι, πρέπει να δείχνει τι ΥΠΑΡΧΕΙ ακόμη.
        avail = {c["slug"]: list(c["items"]) for c in build.MENU}
        shown = [dict(c, items=avail[c["slug"]]) for c in build.MENU
                 if avail[c["slug"]] and (c["slug"] == MAIN_SLUG or c["slug"] in TWO_COL)]

        lines = 0.0
        for c in shown:
            n = len(c["items"])
            lines += (n + 1) // 2 if c["slug"] in TWO_COL else n
            if c["slug"] != MAIN_SLUG:
                lines += 1.5          # η επικεφαλίδα της ομάδας
        size, gap = scale_for(lines)
        # Η σελίδα μικραίνει μόνη της μέχρι να χωρέσει (ως FLOOR_PT), οπότε εδώ
        # δεν προειδοποιούμε για κόψιμο — μόνο ότι η εικόνα βγαίνει πυκνή.
        if lines > LIST_H / (MIN_PT * LINE):
            print(f"ℹ  {lines:.0f} γραμμές — πυκνή εικόνα. Θα χωρέσουν όλα, αλλά "
                  f"με μικρά γράμματα· σκέψου δεύτερη εικόνα για σαλάτες/γλυκά.",
                  file=sys.stderr)

        groups = []
        for c in shown:
            two = c["slug"] in TWO_COL
            rows = "\n".join(
                f'        <li><span class="n">{esc(it["name"])}</span>'
                f'<span class="dots"></span>'
                f'<span class="p">{fmt_price(it.get("price"))}</span></li>'
                for it in c["items"])
            head = ("" if c["slug"] == MAIN_SLUG else
                    f'      <div class="group-head">{esc(c["label"])}</div>\n')
            groups.append(
                f'{head}      <ul class="items{" two" if two else ""}">\n'
                f'{rows}\n      </ul>')

        shown_slugs = {c["slug"] for c in shown}
        extra = [c["label"] for c in build.MENU
                 if avail[c["slug"]] and c["slug"] not in shown_slugs]
        extra_line = (f'<div class="extra">και ακόμη: {esc(" · ".join(extra))}</div>'
                      if extra else "")
        body = f'''
    <div class="date">{esc(date_line)}</div>
    <div class="board" style="font-size:{size}px;--gap:{gap}px">
      <div class="board-inner">
{chr(10).join(groups)}
      </div>
    </div>
    {extra_line}'''
        foot = ("Take away &amp; Delivery &nbsp;·&nbsp; ☎ 2414010332"
                f'<div class="site">{SITE}</div>')

    return f'''<!doctype html>
<html lang="el"><head><meta charset="utf-8"><style>
{FONTS}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{width:{W}px;height:{H}px;overflow:hidden;
       background:#1b1b1b url("{slate_url}") center/cover no-repeat;
       font-family:"GFS Didot",Georgia,serif;color:#F4F1E8;
       display:flex;flex-direction:column;align-items:center;
       padding:64px 70px 56px;text-align:center;
       /* η κιμωλία δεν είναι ποτέ κοφτή: ελαφρύ θόλωμα σε όλο το κείμενο */
       text-shadow:0 0 2px rgba(255,255,255,.45),0 1px 3px rgba(0,0,0,.55);}}
  .eyebrow{{font-family:Georgia,serif;font-size:26px;letter-spacing:.42em;
           text-indent:.42em;color:#E9C892;}}
  .brand{{font-size:86px;line-height:1.05;margin-top:6px;}}
  .rule{{width:190px;height:3px;margin:26px 0 0;border-radius:2px;
        background:#E9C892;opacity:.85;box-shadow:0 0 6px rgba(233,200,146,.5);}}
  .date{{font-size:38px;margin:24px 0 34px;color:#FFF;}}
  /* Το .board-inner δεν είναι διακοσμητικό: σε κεντραρισμένο flex η υπερχείλιση
     βγαίνει και από πάνω και το scrollHeight δεν τη δείχνει. Το εσωτερικό block
     έχει το πραγματικό ύψος του περιεχομένου, οπότε μετριέται σωστά. */
  /* min-height:0 απαραίτητο: τα flex items έχουν min-height:auto και δεν
     συρρικνώνονται κάτω από το περιεχόμενό τους — το clientHeight μεγάλωνε
     μαζί με τη λίστα και η μέτρηση υπερχείλισης έβγαινε πάντα ψευδής. */
  .board{{width:100%;flex:1 1 auto;min-height:0;overflow:hidden;
         display:flex;flex-direction:column;justify-content:center;}}
  .board-inner{{width:100%;}}
  .items{{list-style:none;width:100%;display:flex;flex-direction:column;
         gap:var(--gap);}}
  .items.two{{display:grid;grid-template-columns:1fr 1fr;
             column-gap:calc(var(--gap) + 34px);}}
  .items li{{display:flex;align-items:baseline;text-align:left;}}
  .group-head{{font-family:Georgia,serif;font-size:.76em;letter-spacing:.2em;
              text-indent:.2em;color:#E9C892;
              margin:calc(var(--gap) + 26px) 0 calc(var(--gap) + 4px);}}
  .n{{white-space:nowrap;}}
  .dots{{flex:1 1 auto;margin:0 .5em;border-bottom:2px dotted rgba(244,241,232,.45);
        transform:translateY(-.25em);}}
  .p{{white-space:nowrap;font-family:Georgia,serif;font-size:.82em;color:#E9C892;}}
  .extra{{font-family:Georgia,serif;font-size:23px;color:#D8D2C4;margin-top:26px;}}
  .foot{{font-family:Georgia,serif;font-size:24px;letter-spacing:.06em;
        color:#E9C892;margin-top:auto;padding-top:26px;}}
  .site{{font-family:Georgia,serif;font-size:21px;letter-spacing:.02em;
        color:#D8D2C4;margin-top:9px;}}
  .closed-wrap{{flex:1 1 auto;display:flex;flex-direction:column;
               justify-content:center;}}
  .closed-eyebrow{{font-family:Georgia,serif;font-size:27px;letter-spacing:.24em;
                  color:#E9C892;}}
  .closed-title{{font-size:82px;line-height:1.15;margin-top:30px;}}
  .closed-sub{{font-family:Georgia,serif;font-size:28px;color:#D8D2C4;margin-top:34px;}}
</style></head><body>
  <div class="eyebrow">MERCI</div>
  <div class="brand">Μαγειρευτό</div>
  <div class="rule"></div>
{body}
  <div class="foot">{foot}</div>
<script>
  // Το scale_for() της Python είναι εκτίμηση. Εδώ η σελίδα μετράει τον εαυτό
  // της και μικραίνει μέχρι να χωρέσει όντως — αλλιώς το overflow:hidden θα
  // έκοβε σιωπηλά τα τελευταία πιάτα, όπως έγινε με 18+13+11.
  (function () {{
    var b = document.querySelector(".board");
    var inner = document.querySelector(".board-inner");
    if (!b || !inner) return;
    var size = parseFloat(getComputedStyle(b).fontSize);
    while (inner.offsetHeight > b.clientHeight && size > {FLOOR_PT}) {{
      size -= 1;
      b.style.fontSize = size + "px";
      b.style.setProperty("--gap", Math.round(size * 0.42) + "px");
    }}
    // Αν ούτε στο κατώτατο μέγεθος χωράει, τουλάχιστον να μη χάνονται τα
    // ΠΡΩΤΑ πιάτα: το κεντράρισμα κόβει και από πάνω, το flex-start μόνο κάτω.
    if (inner.offsetHeight > b.clientHeight) b.style.justifyContent = "flex-start";
  }})();
</script>
</body></html>'''


def main():
    if not os.path.isfile(SLATE):
        raise SystemExit(
            f"ΣΦΑΛΜΑ: λείπει ο καμβάς {SLATE} — τρέξε το prep-canvas.py.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    chrome = find_chrome()

    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "social.html")
        png = os.path.join(tmp, "social.png")
        with open(page, "w", encoding="utf-8") as f:
            f.write(page_html())
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             # ΜΗΝ βάλεις --user-data-dir σε φρέσκο φάκελο: ο Chrome μπαίνει σε
             # first-run και κρεμάει επ' αόριστον αντί να τραβήξει screenshot.
             "--force-device-scale-factor=1", f"--window-size={W},{H}",
             # χρόνος για να τρέξει το script που μικραίνει τη λίστα
             "--virtual-time-budget=3000",
             f"--screenshot={png}", "file://" + page],
            check=True, capture_output=True, timeout=120)
        if not os.path.isfile(png):
            raise SystemExit("ΣΦΑΛΜΑ: ο Chrome δεν παρήγαγε εικόνα.")

        # JPEG αντί για PNG: το Instagram το θέλει έτσι, και είναι 5× μικρότερο
        from PIL import Image
        Image.open(png).convert("RGB").save(OUT, quality=88, optimize=True)

    # Ταυτότητα δίπλα στην εικόνα: ανεβαίνει μαζί της στο social-preview και
    # λέει ΠΟΙΑΣ ΜΕΡΑΣ είναι. Χωρίς αυτό, μια έγκριση δημοσίευσης που τρέχει
    # παράλληλα με το build θα έστελνε τη ΧΘΕΣΙΝΗ εικόνα: οι ημερομηνίες σε
    # post.txt/menu-today.txt θα ταίριαζαν, αλλά το branch δεν θα είχε
    # προλάβει να ενημερωθεί. Το publish.py το ελέγχει πριν στείλει.
    with open(SIDECAR, "w", encoding="utf-8") as f:
        json.dump({"date": build.MENU_DATE,
                   "closed": build.CLOSED,
                   "built": datetime.datetime.now(
                       datetime.timezone.utc).isoformat(timespec="seconds")},
                  f, ensure_ascii=False)

    state = "ΚΛΕΙΣΤΑ" if build.CLOSED else build.MENU_DATE
    print(f"{os.path.relpath(OUT, ROOT)}  {W}×{H}  "
          f"{os.path.getsize(OUT) // 1024} KB  ({state})")


if __name__ == "__main__":
    sys.exit(main())
