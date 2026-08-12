#!/usr/bin/env python3
"""Δημοσίευση της εικόνας του μενού σε Facebook Page & Instagram.

    python3 publish.py            # στεγνή δοκιμή αν λείπουν τα secrets
    python3 publish.py --force    # αγνοεί το «ΔΗΜΟΣΙΕΥΣΗ: όχι» (για δοκιμές)

Καλείται από το .github/workflows/publish-social.yml όταν αλλάξει το post.txt.
Ελέγχει ΤΡΙΑ πράγματα πριν στείλει — καθένα τους αντιστοιχεί σε λάθος που θα
έφτανε σε πελάτες και δεν ξεγίνεται:

  1. ΔΗΜΟΣΙΕΥΣΗ: ναι            — ρητή έγκριση, όχι σιωπηλή δημοσίευση.
  2. η ημερομηνία του post.txt ταιριάζει με του menu-today.txt
                                — αλλιώς εγκρίνεις εικόνα άλλης μέρας.
  3. δεν έχει ήδη δημοσιευτεί   — αλλιώς δεύτερο commit = δεύτερο post.

Τα tokens έρχονται από GitHub Secrets. Αν λείπουν, τυπώνει τι ΘΑ έστελνε και
βγαίνει με 0: η ροή δοκιμάζεται ολόκληρη χωρίς λογαριασμούς.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
POST_TXT = os.path.join(ROOT, "post.txt")
MENU_TXT = os.path.join(ROOT, "menu-today.txt")

# Η εικόνα ζει σε orphan branch, όχι στο main: το git κρατά κάθε έκδοση και θα
# φούσκωνε ~75 MB/χρόνο. Με force-push το branch έχει πάντα ΕΝΑ commit.
IMAGE_URL = ("https://raw.githubusercontent.com/stivakos/magirefto-menu/"
             "social-preview/menu.jpg")

# Η έκδοση του Graph API λήγει (~2 χρόνια). Όταν σπάσει, εδώ αλλάζει.
GRAPH = "https://graph.facebook.com/v21.0"

YES = {"ναι", "nai", "yes", "ok"}


def read_field(path, key):
    """Διαβάζει «ΚΛΕΙΔΙ: τιμή» αγνοώντας σχόλια — ίδια λογική με το build.py."""
    if not os.path.isfile(path):
        return ""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            if k.strip().upper().startswith(key):
                return v.strip()
    return ""


def read_caption(path):
    out, grab = [], False
    for line in open(path, encoding="utf-8"):
        if line.strip().startswith("#"):
            continue
        if line.strip().upper().startswith("ΛΕΖΑΝΤΑ"):
            grab = True
            continue
        if grab:
            out.append(line.rstrip())
    return "\n".join(out).strip()


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"!! Το API απάντησε {e.code}: {detail}")


def to_facebook(caption, token, page_id):
    r = post(f"{GRAPH}/{page_id}/photos",
             {"url": IMAGE_URL, "caption": caption, "access_token": token})
    return f"Facebook: post {r.get('post_id') or r.get('id')}"


def to_instagram(caption, token, ig_id):
    # Δύο βήματα: πρώτα «container» με το URL, μετά δημοσίευση. Γι' αυτό η
    # εικόνα ΠΡΕΠΕΙ να είναι σε δημόσιο URL — το Instagram την κατεβάζει μόνο του.
    c = post(f"{GRAPH}/{ig_id}/media",
             {"image_url": IMAGE_URL, "caption": caption, "access_token": token})
    r = post(f"{GRAPH}/{ig_id}/media_publish",
             {"creation_id": c["id"], "access_token": token})
    return f"Instagram: post {r.get('id')}"


def reset():
    """Μηδενίζει την έγκριση και σταμπάρει τη νέα ημερομηνία.

    Τρέχει μετά από κάθε αλλαγή του μενού. Η ΛΕΖΑΝΤΑ μένει ανέπαφη — αν έγραψες
    κάτι καλό, δεν χρειάζεται να το ξαναγράψεις κάθε μέρα.
    """
    menu_date = read_field(MENU_TXT, "ΗΜΕΡΟΜΗΝΙΑ")
    txt = open(POST_TXT, encoding="utf-8").read()
    txt = re.sub(r"(?m)^ΔΗΜΟΣΙΕΥΣΗ:.*$", "ΔΗΜΟΣΙΕΥΣΗ: όχι", txt, count=1)
    txt = re.sub(r"(?m)^ΗΜΕΡΟΜΗΝΙΑ:.*$", f"ΗΜΕΡΟΜΗΝΙΑ: {menu_date}", txt, count=1)
    open(POST_TXT, "w", encoding="utf-8").write(txt)
    print(f"post.txt: έγκριση σε «όχι», ημερομηνία «{menu_date}».")
    return 0


def main():
    if "--reset" in sys.argv:
        return reset()
    force = "--force" in sys.argv

    approved = read_field(POST_TXT, "ΔΗΜΟΣΙΕΥΣΗ").lower()
    if approved.startswith("έγινε") or approved.startswith("εγινε"):
        print(f"Έχει ήδη δημοσιευτεί ({approved}). Δεν ξαναστέλνω.")
        return 0
    if approved not in YES and not force:
        print(f"ΔΗΜΟΣΙΕΥΣΗ: {approved or '—'} — δεν δημοσιεύω.")
        return 0

    post_date = read_field(POST_TXT, "ΗΜΕΡΟΜΗΝΙΑ")
    menu_date = read_field(MENU_TXT, "ΗΜΕΡΟΜΗΝΙΑ")
    if post_date != menu_date:
        raise SystemExit(
            f"!! Η ημερομηνία του post.txt ({post_date or '—'}) δεν ταιριάζει με "
            f"του menu-today.txt ({menu_date or '—'}).\n"
            f"   Η εικόνα είναι άλλης μέρας — άλλαξε πρώτα το μενού.")

    if read_field(MENU_TXT, "ΚΛΕΙΣΤΑ"):
        print("Το μαγαζί είναι κλειστό — η ανακοίνωση δημοσιεύεται κανονικά.")

    caption = read_caption(POST_TXT)
    if not caption:
        raise SystemExit("!! Κενή ΛΕΖΑΝΤΑ στο post.txt.")

    fb_token = os.environ.get("FB_PAGE_TOKEN", "")
    fb_page = os.environ.get("FB_PAGE_ID", "")
    ig_id = os.environ.get("IG_USER_ID", "")

    if not fb_token:
        print("— ΣΤΕΓΝΗ ΔΟΚΙΜΗ (λείπουν τα secrets) —")
        print(f"  εικόνα:     {IMAGE_URL}")
        print(f"  ημερομηνία: {post_date}")
        print(f"  λεζάντα:\n{caption}")
        return 0

    done = [to_facebook(caption, fb_token, fb_page)] if fb_page else []
    if ig_id:
        done.append(to_instagram(caption, fb_token, ig_id))
    for line in done:
        print("✓ " + line)

    # σφράγισμα ώστε δεύτερο commit στο post.txt να μην ξαναστείλει
    txt = open(POST_TXT, encoding="utf-8").read()
    txt = re.sub(r"(?m)^ΔΗΜΟΣΙΕΥΣΗ:.*$",
                 f"ΔΗΜΟΣΙΕΥΣΗ: έγινε {post_date}", txt, count=1)
    open(POST_TXT, "w", encoding="utf-8").write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
