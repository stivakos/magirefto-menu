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
import html
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
FONTS = open(os.path.join(HERE, "fonts.css"), encoding="utf-8").read()

W, H = 1080, 1350          # Instagram feed 4:5 — δουλεύει και σε Facebook
MAIN_SLUG = "menu-hmeras"  # τα μαγειρευτά· οι υπόλοιπες κατηγορίες μπαίνουν ως υποσημείωση

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


def scale_for(n):
    """Μέγεθος γραμματοσειράς & κενού ανάλογα με το πλήθος πιάτων.

    Με 6 πιάτα θέλουμε μεγάλα γράμματα, με 16 πρέπει να χωρέσουν όλα. Τα όρια
    βγήκαν από δοκιμή: κάτω από 26px η κιμωλία δεν διαβάζεται στο κινητό.
    """
    if n <= 8:
        return 46, 26
    if n <= 12:
        return 40, 18
    if n <= 16:
        return 33, 12
    return 27, 7


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
        foot = f'☎ {esc(build.VIBER_DISPLAY)}'
    else:
        main = next((c for c in build.MENU if c["slug"] == MAIN_SLUG), None)
        items = main["items"] if main else []
        size, gap = scale_for(len(items))
        rows = "\n".join(
            f'      <li><span class="n">{esc(it["name"])}</span>'
            f'<span class="dots"></span>'
            f'<span class="p">{fmt_price(it.get("price"))}</span></li>'
            for it in items)
        extra = [c["label"] for c in build.MENU
                 if c["slug"] != MAIN_SLUG and c["items"]]
        extra_line = (f'<div class="extra">και ακόμη: {esc(" · ".join(extra))}</div>'
                      if extra else "")
        body = f'''
    <div class="date">{esc(date_line)}</div>
    <ul class="items" style="font-size:{size}px;gap:{gap}px">
{rows}
    </ul>
    {extra_line}'''
        foot = "Take away &amp; Delivery &nbsp;·&nbsp; ☎ 2414010332"

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
  .items{{list-style:none;width:100%;display:flex;flex-direction:column;
         flex:1 1 auto;justify-content:center;}}
  .items li{{display:flex;align-items:baseline;text-align:left;}}
  .n{{white-space:nowrap;}}
  .dots{{flex:1 1 auto;margin:0 .5em;border-bottom:2px dotted rgba(244,241,232,.45);
        transform:translateY(-.25em);}}
  .p{{white-space:nowrap;font-family:Georgia,serif;font-size:.82em;color:#E9C892;}}
  .extra{{font-family:Georgia,serif;font-size:23px;color:#D8D2C4;margin-top:26px;}}
  .foot{{font-family:Georgia,serif;font-size:24px;letter-spacing:.06em;
        color:#E9C892;margin-top:auto;padding-top:26px;}}
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
             f"--screenshot={png}", "file://" + page],
            check=True, capture_output=True, timeout=120)
        if not os.path.isfile(png):
            raise SystemExit("ΣΦΑΛΜΑ: ο Chrome δεν παρήγαγε εικόνα.")

        # JPEG αντί για PNG: το Instagram το θέλει έτσι, και είναι 5× μικρότερο
        from PIL import Image
        Image.open(png).convert("RGB").save(OUT, quality=88, optimize=True)

    state = "ΚΛΕΙΣΤΑ" if build.CLOSED else build.MENU_DATE
    print(f"{os.path.relpath(OUT, ROOT)}  {W}×{H}  "
          f"{os.path.getsize(OUT) // 1024} KB  ({state})")


if __name__ == "__main__":
    sys.exit(main())
