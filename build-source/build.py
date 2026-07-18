#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Merci Μαγειρευτό online menu (self-contained index.html) from the xlsx."""
import re, html, os, openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ONIRO = "/Users/stavros/oniropetra-menu/index.html"
XLSX = os.path.join(HERE, "menu-data.xlsx")
OUT = os.path.join(HERE, "..", "index.html")

# --- fonts: reuse the embedded GFS Didot @font-face blocks from oniropetra ---
oniro = open(ONIRO, encoding="utf-8").read()
FONT_FACES = "\n".join(re.findall(r'@font-face\s*\{.*?\}', oniro, re.S))

CAT_META = {
    "ΜΑΓΕΙΡΕΥΤΑ ΗΜΕΡΑΣ": ("mageirefta", "Ημέρας", "Home-style"),
    "ΚΟΤΟΠΟΥΛΟ": ("kotopoulo", "Κοτόπουλο", "Chicken"),
    "ΧΟΙΡΙΝΟ": ("xoirino", "Χοιρινό", "Pork"),
    "ΜΟΣΧΑΡΙ": ("moschari", "Μοσχάρι", "Beef"),
    "ΑΡΝΙ - ΚΑΤΣΙΚΙ": ("arni", "Αρνί & Κατσίκι", "Lamb & Goat"),
    "ΣΟΥΒΛΑ - ΨΗΤΑ": ("souvla", "Σούβλα & Ψητά", "Grill"),
    "ΘΑΛΑΣΣΙΝΑ - ΨΑΡΙΑ": ("thalassina", "Θαλασσινά & Ψάρια", "Seafood & Fish"),
    "ΜΑΚΑΡΟΝΙΕΣ - ΖΥΜΑΡΙΚΑ": ("makaronies", "Ζυμαρικά", "Pasta"),
    "ΝΗΣΤΙΣΙΜΑ": ("nistisima", "Νηστίσιμα", "Fasting / Vegan"),
    "ΣΑΛΑΤΕΣ": ("salates", "Σαλάτες", "Salads"),
    "ΟΡΕΚΤΙΚΑ": ("orektika", "Ορεκτικά", "Appetizers"),
    "ΣΥΝΟΔΕΥΤΙΚΑ": ("synodeytika", "Συνοδευτικά", "Sides"),
    "ΓΛΥΚΑ": ("glyka", "Γλυκά", "Desserts"),
    "ΑΝΑΨΥΚΤΙΚΑ": ("anapsyktika", "Αναψυκτικά", "Soft Drinks"),
    "ΜΠΥΡΕΣ": ("mpyres", "Μπύρες", "Beers"),
    "ΚΡΑΣΙΑ": ("krasia", "Κρασιά", "Wines"),
    "ΚΟΥΒΕΡ - ΨΩΜΙ": ("kouver", "Κουβέρ & Ψωμί", "Bread"),
}

def esc(s): return html.escape(str(s), quote=True)

def fmt_price(p):
    if p is None: return None
    try: v = float(p)
    except (TypeError, ValueError): return None
    return f"{v:.2f}".replace(".", ",") + " €"

SIZE_RE = re.compile(r'(\d+\s?(gr|kg|ml|Lt)\b|\d+\s?Τεμάχ|Τεμάχιο|\d+-\d+\s?(gr|ml))', re.I)
SKIP_DESC = {"Μερίδα", "Ατομική", "Νηστίσιμο", ""}

def split_desc(d):
    """return (description_or_None, portion_or_None)"""
    if not d: return (None, None)
    d = " ".join(str(d).split())
    if d in SKIP_DESC: return (None, None)
    if SIZE_RE.search(d) and len(d) <= 14:
        return (None, d)                      # short size/qty -> portion qualifier
    if d.endswith("...") or d.endswith("…"):
        return (None, None)                    # truncated -> drop
    return (d, None)

# --- read catalog ---
wb = openpyxl.load_workbook(XLSX, data_only=True)
ws = wb["Πλήρες Μενού"]
sections, cur = [], None
for row in ws.iter_rows(values_only=True):
    a = row[0]; name = row[1]; desc = row[2] if len(row) > 2 else None
    price = row[3] if len(row) > 3 else None
    if a and str(a).startswith("▶"):
        key = str(a).replace("▶", "").strip()
        meta = CAT_META.get(key)
        if meta:
            cur = {"key": key, "slug": meta[0], "gr": meta[1], "en": meta[2], "items": []}
            sections.append(cur)
        else:
            cur = None
        continue
    if cur is None or not name or not str(name).strip():
        continue
    nm = str(name).strip()
    if nm.startswith(("🍽", "#", "Σύνολο")):
        continue
    d, portion = split_desc(desc)
    cur["items"].append({"name": nm, "desc": d, "portion": portion, "price": fmt_price(price)})

sections = [s for s in sections if s["items"]]

# --- build HTML ---
nav = "\n".join(
    f'    <a class="chip" href="#{s["slug"]}">{esc(s["gr"])}<span class="chip-en">{esc(s["en"])}</span></a>'
    for s in sections)

def item_html(it):
    portion = f' <span class="portion">{esc(it["portion"])}</span>' if it["portion"] else ""
    price = (f'<span class="price">{esc(it["price"])}</span>' if it["price"]
             else '<span class="price price-tba">—</span>')
    line = (f'<div class="item-line"><span class="gr">{esc(it["name"])}{portion}</span>'
            f'<span class="dots"></span>{price}</div>')
    if it["desc"]:
        line += f'\n        <p class="desc" lang="el">{esc(it["desc"])}</p>'
    return f'      <li class="item">{line}</li>'

secs = []
for s in sections:
    items = "\n".join(item_html(it) for it in s["items"])
    secs.append(f'''  <section id="{s["slug"]}" aria-labelledby="h-{s["slug"]}">
    <div class="sec-head">
      <h2 id="h-{s["slug"]}" lang="el">{esc(s["gr"])}</h2>
      <span class="en-label">{esc(s["en"])}</span>
    </div>
    <ul class="items">
{items}
    </ul>
  </section>''')
sections_html = "\n\n".join(secs)

CSS = """
  :root {
    --paper:#FBF6EE; --raised:#FFFDF8; --ink:#3A2A17; --muted:#6E5A44; --faint:#9A836A;
    --sea:#A6542E; --mist:#E4D6BE; --mist-2:#F1E7D5; --sand:#C8A24B; --sand-deep:#9C7A2E;
    --leader:#D8C6A8; --hairline:#E7DCC8; --chip-bg:#F1E7D5; --sun:#E0A96D;
    --display:"GFS Didot","Palatino Linotype",Palatino,Georgia,serif;
    --body:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  }
  @media (prefers-color-scheme: dark){:root{
    --paper:#1C160F; --raised:#241C12; --ink:#F0E6D6; --muted:#C3B199; --faint:#9E8A70;
    --sea:#E0885A; --mist:#3A2E1E; --mist-2:#241C12; --sand:#CBA85C; --sand-deep:#E0C77E;
    --leader:#4A3B28; --hairline:#2E2417; --chip-bg:#26200f; --sun:#C9975B;}}
  :root[data-theme="light"]{
    --paper:#FBF6EE; --raised:#FFFDF8; --ink:#3A2A17; --muted:#6E5A44; --faint:#9A836A;
    --sea:#A6542E; --mist:#E4D6BE; --mist-2:#F1E7D5; --sand:#C8A24B; --sand-deep:#9C7A2E;
    --leader:#D8C6A8; --hairline:#E7DCC8; --chip-bg:#F1E7D5; --sun:#E0A96D;}
  :root[data-theme="dark"]{
    --paper:#1C160F; --raised:#241C12; --ink:#F0E6D6; --muted:#C3B199; --faint:#9E8A70;
    --sea:#E0885A; --mist:#3A2E1E; --mist-2:#241C12; --sand:#CBA85C; --sand-deep:#E0C77E;
    --leader:#4A3B28; --hairline:#2E2417; --chip-bg:#26200f; --sun:#C9975B;}

  *{box-sizing:border-box;} html{-webkit-text-size-adjust:100%;}
  @media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth;}}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-size:1rem;line-height:1.55;}

  .cove{position:relative;overflow:hidden;background:linear-gradient(var(--mist-2),var(--paper));text-align:center;padding:3.25rem 1.25rem 2rem;border-bottom:1px solid var(--hairline);}
  .cove-sun{position:absolute;top:2rem;right:9%;width:clamp(64px,15vw,104px);aspect-ratio:1;border-radius:50%;background:radial-gradient(circle at 38% 35%,var(--sun),#c98a4e);opacity:.85;}
  .brand{position:relative;font-family:var(--display);font-weight:400;font-size:clamp(2.6rem,10vw,4.2rem);line-height:1.05;letter-spacing:.01em;margin:0;text-wrap:balance;}
  .brand .merci{display:block;font-size:.42em;letter-spacing:.5em;text-indent:.5em;text-transform:uppercase;color:var(--sea);margin:0 0 .35rem;}
  .brand-sub{position:relative;margin:.9rem 0 0;font-size:.74rem;font-weight:600;letter-spacing:.3em;text-indent:.3em;text-transform:uppercase;color:var(--muted);}

  .rail{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--paper) 88%,transparent);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--hairline);}
  .rail-inner{display:flex;gap:.5rem;overflow-x:auto;padding:.65rem 1.1rem;max-width:44rem;margin:0 auto;scrollbar-width:none;}
  .rail-inner::-webkit-scrollbar{display:none;}
  .chip{flex:0 0 auto;display:inline-flex;flex-direction:column;align-items:center;justify-content:center;min-height:44px;padding:.4rem 1.05rem;border-radius:18px;border:1px solid var(--hairline);background:var(--chip-bg);color:var(--muted);font-size:.9rem;font-weight:600;line-height:1.2;text-align:center;text-decoration:none;white-space:nowrap;cursor:pointer;transition:background-color .2s,color .2s,border-color .2s;}
  .chip-en{display:block;font-size:.56rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;opacity:.65;margin-top:.1rem;}
  .chip:hover{border-color:var(--sea);color:var(--ink);}
  .chip.is-active{background:var(--ink);border-color:var(--ink);color:var(--paper);}
  .chip:focus-visible,a:focus-visible{outline:2px solid var(--sea);outline-offset:2px;}

  main{max-width:44rem;margin:0 auto;padding:.75rem 1.25rem 2rem;}
  section{scroll-margin-top:4.6rem;padding-top:2.4rem;}
  .sec-head{display:flex;align-items:baseline;gap:.75rem;border-bottom:2px solid var(--ink);padding-bottom:.55rem;}
  .sec-head h2{font-family:var(--display);font-weight:400;font-size:clamp(1.7rem,5.5vw,2.1rem);margin:0;letter-spacing:.01em;}
  .sec-head .en-label{margin-left:auto;font-size:.72rem;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--sand-deep);white-space:nowrap;}
  .items{list-style:none;margin:0;padding:0;}
  .item{padding:.72rem 0;border-bottom:1px solid var(--hairline);}
  .item:last-child{border-bottom:none;}
  .item-line{display:flex;align-items:baseline;gap:.55rem;}
  .gr{font-weight:600;}
  .portion{font-weight:400;font-size:.8rem;color:var(--faint);}
  .dots{flex:1 1 1.5rem;min-width:1.5rem;border-bottom:2px dotted var(--leader);transform:translateY(-.28em);}
  .price{font-variant-numeric:tabular-nums;font-weight:650;white-space:nowrap;}
  .price-tba{color:var(--faint);font-weight:400;}
  .desc{margin:.3rem 0 0;font-size:.86rem;color:var(--muted);max-width:34rem;}

  footer{border-top:1px solid var(--hairline);background:var(--mist-2);text-align:center;padding:2.2rem 1.5rem 2.6rem;}
  .foot-brand{font-family:var(--display);font-size:1.4rem;margin:0 0 .2rem;}
  .foot-place{font-size:.72rem;font-weight:700;letter-spacing:.26em;text-indent:.26em;text-transform:uppercase;color:var(--sea);margin:0 0 1.2rem;}
  .foot-hours{font-size:.9rem;color:var(--ink);margin:0 0 1rem;}
  .legal{max-width:34rem;margin:0 auto;font-size:.76rem;line-height:1.6;color:var(--muted);}
  .legal p{margin:.35rem 0;}
"""

HTML = f'''<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Merci Μαγειρευτό · Μενού — Λάρισα</title>
<meta name="description" content="Μενού / Τιμοκατάλογος — Merci Μαγειρευτό, μαμαδίστικο φαγητό, Λάρισα. Take away & delivery.">
</head>
<body>
<style>
{FONT_FACES}
{CSS}
</style>

<header class="cove">
  <div class="cove-sun" aria-hidden="true"></div>
  <h1 class="brand" lang="el"><span class="merci">Merci</span>Μαγειρευτό</h1>
  <p class="brand-sub">Μαμαδίστικο φαγητό · Λάρισα</p>
</header>

<nav class="rail" aria-label="Κατηγορίες μενού / Menu categories">
  <div class="rail-inner">
{nav}
  </div>
</nav>

<main>
{sections_html}
</main>

<footer>
  <p class="foot-brand" lang="el">Merci Μαγειρευτό</p>
  <p class="foot-place">Λάρισα · Take away &amp; Delivery</p>
  <p class="foot-hours" lang="el">Δευτέρα – Σάββατο, 12:00 – 15:30</p>
  <div class="legal">
    <p lang="el">Οι αναγραφόμενες τιμές αφορούν παραγγελίες μέσω πλατφορμών delivery.</p>
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
</body>
</html>
'''

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

ni = sum(len(s["items"]) for s in sections)
missing = sum(1 for s in sections for it in s["items"] if not it["price"])
print(f"Wrote {OUT}")
print(f"sections={len(sections)}  items={ni}  without_price={missing}")
