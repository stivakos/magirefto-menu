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

CATEGORIES = [   # (site label, slug, [xlsx tab names] — a section may pull from >1 tab)
    ("Μενού Ημέρας",      "menu-hmeras", ["Μαγειρευτά", "Της ώρας"]),
    ("Συνοδευτικά",       "synodeytika", ["Συνοδευτικά"]),
    ("Σαλάτες",           "salates",     ["Σαλάτες"]),
    ("Γλυκά",             "glyka",       ["Γλυκά"]),
    ("Αναψυκτικά / Ποτά", "anapsyktika", ["Αναψυκτικά - Ποτά"]),
]
NOTES = {"synodeytika": "…και σε μερίδα για μεγαλύτερη απόλαυση!"}
HIDE_PRICE = {"synodeytika"}          # συνοδευτικά: χωρίς τιμή στο site
MENU_TXT = os.path.join(HERE, "..", "menu-today.txt")

def _norm(s):                          # lower, strip accents & spaces/slashes
    s = "".join(c for c in unicodedata.normalize("NFD", str(s))
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s/]+", "", s).lower()

MENU_DATE = ""
selection = {}
# menu-today.txt keeps one line per xlsx tab (numbering isn't shared between tabs,
# even when several tabs are displayed together under one section on the site).
# Single-tab categories also accept the site label as a key (e.g. "Αναψυκτικά / Ποτά"
# in menu-today.txt vs. the xlsx tab "Αναψυκτικά - Ποτά") for backward compatibility.
_tab_by_norm = {}
for _label, _slug, _tabs in CATEGORIES:
    for _tab in _tabs:
        _tab_by_norm[_norm(_tab)] = _tab
    if len(_tabs) == 1:
        _tab_by_norm[_norm(_label)] = _tabs[0]
for raw in open(MENU_TXT, encoding="utf-8"):
    line = raw.strip()
    if not line or line.startswith("#") or ":" not in line:
        continue
    key, val = line.split(":", 1)
    kn = _norm(key)
    if kn in ("ημερομηνια", "date"):
        MENU_DATE = val.strip()
    elif kn in _tab_by_norm:
        selection[_tab_by_norm[kn]] = [int(n) for n in re.findall(r"\d+", val)]

_wb = openpyxl.load_workbook(DAILY_SOURCE, data_only=True)
def _tab_rows(tab):
    ws = _wb[tab]; d = {}
    for r in range(2, ws.max_row + 1):
        aa, name, price = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value
        if aa is None or not name:
            continue
        try:
            d[int(aa)] = (str(name).strip(), float(price) if price not in (None, "") else None)
        except (TypeError, ValueError):
            continue
    return d

MENU = []
for label, slug, tabs in CATEGORIES:
    items = []
    for tab in tabs:
        rows = _tab_rows(tab)
        for n in selection.get(tab, []):
            if n in rows:
                name, price = rows[n]
                items.append({"name": name, "price": None if slug in HIDE_PRICE else price})
    cat = {"slug": slug, "label": label, "items": items}
    if slug in NOTES:
        cat["note"] = NOTES[slug]
    MENU.append(cat)

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
    return (f'      <li class="item" data-name="{esc(it["name"])}" data-price="{pnum}">'
            f'{line}</li>')

nav = "\n".join(f'    <a class="chip" href="#{c["slug"]}">{esc(c["label"])}</a>' for c in MENU)

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
  .wm{position:fixed;inset:0;z-index:0;pointer-events:none;background:url("assets/merci-logo.png") no-repeat center 43%;background-size:min(82vw,600px);opacity:.11;}
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
  .rail-inner{display:flex;gap:.5rem;overflow-x:auto;padding:.7rem 1.1rem;max-width:46rem;margin:0 auto;scrollbar-width:none;justify-content:flex-start;}
  .rail-inner::-webkit-scrollbar{display:none;}
  .chip{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:.4rem 1.1rem;border-radius:18px;border:1px solid var(--hairline);background:var(--chip-bg);color:var(--muted);font-size:.94rem;font-weight:600;line-height:1.2;text-align:center;text-decoration:none;white-space:nowrap;cursor:pointer;transition:background-color .2s,color .2s,border-color .2s;}
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
  .order-actions{max-width:44rem;margin:.55rem auto 0;display:flex;gap:.6rem;}
  .order-btn{flex:1 1 auto;display:inline-flex;align-items:center;justify-content:center;gap:.5rem;border:none;border-radius:14px;padding:.8rem 1rem;font-size:1rem;font-weight:700;cursor:pointer;text-decoration:none;white-space:nowrap;}
  .order-btn.sms{flex:1 1 auto;background:#2FB457;color:#08351a;}
  .order-btn:active{transform:scale(.97);}
  .order-clear{flex:0 0 auto;background:transparent;border:none;color:var(--faint);font-size:.8rem;cursor:pointer;text-decoration:underline;}
  main{padding-bottom:6rem;}
  .order-call{display:block;text-align:center;margin:.45rem auto 0;font-size:.8rem;color:var(--muted);text-decoration:none;}
  .order-call b{color:var(--sand);}

  /* ---- toast ---- */
  .toast{position:fixed;left:50%;bottom:6.5rem;transform:translate(-50%,1.2rem);z-index:30;max-width:calc(100% - 2rem);width:24rem;background:#17293F;color:var(--ink);border:1px solid var(--sea);border-radius:14px;padding:.8rem 1rem;font-size:.9rem;line-height:1.4;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.35);opacity:0;pointer-events:none;transition:opacity .25s ease,transform .25s ease;}
  .toast.show{opacity:1;transform:translate(-50%,0);}

  footer{border-top:1px solid var(--hairline);background:var(--mist-2);text-align:center;padding:2.2rem 1.5rem 2.6rem;}
  .foot-brand{font-family:var(--display);font-size:1.4rem;margin:0 0 .2rem;}
  .foot-place{font-size:.72rem;font-weight:700;letter-spacing:.26em;text-indent:.26em;text-transform:uppercase;color:var(--sea);margin:0 0 1.2rem;}
  .foot-hours{font-size:.9rem;color:var(--ink);margin:0 0 1rem;}
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
  var items = Array.prototype.slice.call(document.querySelectorAll(".item"));
  var bar = document.getElementById("orderBar");
  var elTotal = document.getElementById("orderTotal");
  var elCount = document.getElementById("orderCount");
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

  function refresh() {
    var count = 0, total = 0;
    items.forEach(function (li) {
      var q = qOf(li);
      if (q > 0) {
        count += q;
        var pr = parseFloat(li.getAttribute("data-price"));
        if (!isNaN(pr)) total += pr * q;
        li.classList.add("in-cart");
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

  var smsBtn = document.getElementById("orderSms");
  smsBtn.addEventListener("click", function (e) {
    e.preventDefault();
    if (!validTime()) return;
    var txt = buildText();
    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    var sep = isIOS ? "&" : "?";
    window.location.href = "sms:" + NUMBER + sep + "body=" + encodeURIComponent(txt);
  });

  refresh();
})();
'''.replace("__DATE_JSON__", json.dumps(MENU_DATE, ensure_ascii=False)) \
   .replace("__NUMBER_JSON__", json.dumps(VIBER_NUMBER, ensure_ascii=False))

HTML = f'''<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Merci Μαγειρευτό · Μενού — Λάρισα</title>
<meta name="description" content="Μενού — Merci Μαγειρευτό, σπιτικό φαγητό, Λάρισα. Take away & delivery.">
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
  <p class="menu-date" lang="el">{esc(MENU_DATE)}</p>
</header>

<nav class="rail" aria-label="Κατηγορίες μενού">
  <div class="rail-inner">
{nav}
  </div>
</nav>

<main>
{sections_html}
</main>

<div class="order-bar" id="orderBar" role="region" aria-label="Η παραγγελία σου">
  <div class="order-opts">
    <div class="seg" role="group" aria-label="Τρόπος παραλαβής">
      <button type="button" class="seg-btn active" data-type="delivery">🛵 Delivery</button>
      <button type="button" class="seg-btn" data-type="pickup">🏠 Παραλαβή</button>
    </div>
    <label class="time-field">Ώρα<select id="orderTime">{TIME_OPTIONS}</select></label>
  </div>
  <div class="order-inner">
    <button class="order-clear" id="orderClear" type="button">Καθαρισμός</button>
    <div class="order-sum"><b id="orderTotal">0,00 €</b><small id="orderCount">0 είδη</small></div>
  </div>
  <div class="order-actions">
    <a class="order-btn sms" id="orderSms" href="#" role="button">💬 Παραγγελία με SMS</a>
  </div>
  <a class="order-call" href="tel:{VIBER_NUMBER}">ή κάλεσέ μας: <b>{VIBER_DISPLAY}</b></a>
</div>

<div class="toast" id="toast" role="status" aria-live="polite"></div>

<footer>
  <p class="foot-brand" lang="el">Merci Μαγειρευτό</p>
  <p class="foot-place">Λάρισα · Take away &amp; Delivery</p>
  <p class="foot-hours" lang="el">Δευτέρα – Σάββατο, 12:00 – 16:00</p>
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

<script>
{ORDER_JS}
</script>
</body>
</html>
'''

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Wrote {OUT}  ({len(MENU)} categories, {sum(len(c['items']) for c in MENU)} dishes)")

# NOTE: DAILY_MENU.xlsx is the OWNER-maintained SOURCE of common dishes (per-category
# tabs: Α/Α | Ονομασία | Τιμή). The daily selection ("μαγειρευτά 1 2 4 …") is read FROM
# it to populate MENU above. This build no longer writes/overwrites it (would wipe edits).
