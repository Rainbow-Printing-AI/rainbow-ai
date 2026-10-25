#!/usr/bin/env python3
"""
pricebook.py - Rainbow Printing & Office Supply price book.

Master data lives in data/ as plain CSV/JSON (edit-able in Excel, easy to diff):
  data/prices.csv      one row per price point
  data/contacts.csv    phone list (no logins; those live only in private/)
  data/conflicts.json  open questions / conflict sheet cards
  data/changelog.csv   every change ever made (append-only)
  data/settings.json   shop-wide settings (sales tax rate, sheet version)

Commands (run with -h for options):
  find TERMS...           search prices (size, qty, color, sides, synonyms understood)
  get ID                  one price row in full, with its history
  set ID PRICE            change a price (logs to changelog)
  edit ID FIELD=VALUE...  change other fields (logs to changelog)
  edit-contact ID F=V...  change a phone-list entry (status=retired to drop it)
  add                     add a new price row
  retire ID               discontinue a price row (kept for history)
  history [ID]            show the change log
  quote ITEM QTY [+ ITEM QTY ...]   price a job, itemized
  contacts [TERMS...]     search the phone list
  conflicts [ID]          list open questions, or show one card
  resolve CARD ANSWERS... record answers from the marked-up conflict sheet
  close CARD              mark a card done after manual follow-up
  validate                check the data for problems
  build                   regenerate book PDF, xlsx, HTML, project mirror
  conflicts-pdf           regenerate the printable conflict sheet (open cards only)

Status values: active | pending (proposed, awaiting the conflict sheet) |
               unpriced | superseded (lost to another source) | retired
"""
import argparse, csv, datetime as dt, json, math, os, re, shutil, sys, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.join(ROOT, "build")

PRICE_FIELDS = ["id", "family", "category", "item", "variant", "brand", "sku", "size", "stock", "color",
                "sides", "qty_min", "qty_max", "unit", "price", "price_max", "min_charge", "cost",
                "fulfillment", "equipment", "turnaround", "status", "cards", "source", "mark",
                "updated", "notes", "keywords"]
CONTACT_FIELDS = ["id", "name", "organization", "role", "kind", "value", "visibility", "notes", "source",
                  "status", "cards", "updated"]
LOG_FIELDS = ["when", "who", "action", "table", "id", "field", "old", "new", "source", "note"]
STATUSES = {"active", "pending", "unpriced", "superseded", "retired"}
LIVE = {"active", "pending", "unpriced"}
UNITS = {"each", "side", "page", "sheet", "photo", "book", "cover", "pad", "staple", "cut", "hole", "minute", "hour",
         "piece", "job", "box", "lot", "sq ft", "linear ft", "per 1000", "per 500"}
CATEGORY_ORDER = ["Copies - B/W", "Copies - Color", "Large Format - B/W", "Large Format - Color",
                  "Large Format - Vellum", "Scanning", "Computer & File Services", "Photo Prints", "Labels",
                  "Business Cards", "NCR Forms", "Envelopes", "Special Inks", "Bindery & Finishing",
                  "Laminating", "Signs & Banners (4over)", "Labor & Design", "Pens & Markers"]

# ------------------------------------------------------------------ utilities
def today():
    return dt.date.today().isoformat()

def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")

def secret_fragments():
    """Known login/password/tax-ID fragments, one per line, kept only in private/ (never in git)."""
    p = os.path.join(ROOT, "private", "secret_check.txt")
    if not os.path.exists(p):
        return []
    return [ln.strip() for ln in open(p, encoding="utf-8") if ln.strip() and not ln.startswith("#")]

def read_csv(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def write_csv(name, rows, fields):
    path = os.path.join(DATA, name)
    fd, tmp = tempfile.mkstemp(dir=DATA, suffix=".tmp")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    os.replace(tmp, path)

def load_prices():
    return read_csv("prices.csv")

def save_prices(rows):
    write_csv("prices.csv", rows, PRICE_FIELDS)

def load_contacts():
    return read_csv("contacts.csv")

def save_contacts(rows):
    write_csv("contacts.csv", rows, CONTACT_FIELDS)

def load_cards():
    p = os.path.join(DATA, "conflicts.json")
    if not os.path.exists(p):
        return {"version": 0, "rules": {}, "cards": []}
    return json.load(open(p, encoding="utf-8"))

def save_cards(doc):
    p = os.path.join(DATA, "conflicts.json")
    fd, tmp = tempfile.mkstemp(dir=DATA, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    os.replace(tmp, p)

def load_settings():
    p = os.path.join(DATA, "settings.json")
    s = {"sales_tax_rate": None, "shop": "Rainbow Printing & Office Supply"}
    if os.path.exists(p):
        s.update(json.load(open(p, encoding="utf-8")))
    return s

def log(action, table, id, field="", old="", new="", who="", source="", note=""):
    path = os.path.join(DATA, "changelog.csv")
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow(dict(when=now(), who=who or os.environ.get("PRICEBOOK_USER", "Claude"), action=action,
                        table=table, id=id, field=field, old=old, new=new, source=source, note=note))

def money(v):
    if v in ("", None):
        return ""
    return f"${float(v):,.2f}"

def fmt_price(r):
    if not r.get("price"):
        return "no price" if r.get("status") != "retired" else "-"
    p = money(r["price"])
    if r.get("price_max"):
        p += "-" + money(r["price_max"])
    return p

def unit_label(r):
    u = r.get("unit", "")
    return {"each": "ea", "side": "/side", "lot": "lot", "sq ft": "/sq ft", "linear ft": "/lin ft", "per 1000": "/1,000",
            "per 500": "/500", "hour": "/hr", "minute": "/min"}.get(u, "/" + u if u else "")

def qty_label(r):
    a, b = r.get("qty_min", ""), r.get("qty_max", "")
    if not a and not b:
        return ""
    if r.get("unit") == "lot":
        if "addl-1000" in r.get("id", ""):
            return "each add'l 1,000"
        return f"{int(a):,}" if a else ""
    if a and b:
        return f"{a}-{b}" if a != b else a
    if a:
        return f"{a}+"
    return f"up to {b}"

def flag(r):
    s = r.get("status", "")
    if s == "pending":
        return "PENDING " + r.get("cards", "")
    if s == "unpriced":
        return "NO PRICE " + r.get("cards", "")
    if s in ("superseded", "retired"):
        return s.upper()
    return ""

# ------------------------------------------------------------------ sizes
FRACT = {"½": ".5", "¼": ".25", "¾": ".75"}
NAMED_SIZES = {"letter": "8.5x11", "legal": "8.5x14", "tabloid": "11x17", "ledger": "11x17",
               "arch c": "18x24", "arch d": "24x36", "arch e": "36x48", "ansi d": "22x34", "ansi e": "34x44",
               "business card": "2x3.5", "postcard": "4x6"}

def norm_num(s):
    s = s.strip().replace('"', "").replace("in", "").strip()
    for k, v in FRACT.items():
        s = s.replace(k, v)
    m = re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", s) or re.fullmatch(r"(\d+)-(\d+)/(\d+)", s)
    if m:
        return float(m.group(1)) + float(m.group(2)) / float(m.group(3))
    return float(s)

def norm_size(s):
    """'36 x 24', '24"x36"', '8 1/2 x 11', 'letter' -> '24x36' / '8.5x11' (short side first). None if not a size."""
    if not s:
        return None
    t = s.lower().strip()
    if t in NAMED_SIZES:
        return NAMED_SIZES[t]
    for k, v in FRACT.items():
        t = t.replace(k, v)
    m = re.fullmatch(r'\s*([\d.]+(?:[ -]\d+/\d+)?)\s*"?\s*(?:in)?\s*[x×by]+\s*([\d.]+(?:[ -]\d+/\d+)?)\s*"?\s*(?:in)?\s*', t)
    if not m:
        return None
    try:
        a, b = sorted((norm_num(m.group(1)), norm_num(m.group(2))))
    except ValueError:
        return None
    f = lambda x: (f"{x:.2f}".rstrip("0").rstrip("."))
    return f"{f(a)}x{f(b)}"

def size_dims(s):
    n = norm_size(s)
    if not n:
        return None
    a, b = n.split("x")
    return float(a), float(b)

# ------------------------------------------------------------------ search
SYN = {"bw": "b/w", "b&w": "b/w", "blackandwhite": "b/w", "black-and-white": "b/w", "mono": "b/w",
       "colour": "color", "colored": "color", "double-sided": "duplex", "2-sided": "duplex", "two-sided": "duplex",
       "double": "duplex", "front-and-back": "duplex", "single-sided": "single", "1-sided": "single",
       "one-sided": "single", "simplex": "single", "laminate": "laminat", "lamination": "laminat",
       "laminating": "laminat", "laminated": "laminat", "blueprints": "blueprint", "posters": "poster",
       "banners": "banner", "labels": "label", "envelopes": "envelope", "copies": "copy", "prints": "print",
       "photos": "photo", "pens": "pen", "markers": "marker", "cards": "card", "scans": "scan",
       "carbonless": "ncr", "walkin": "walk-in", "acct": "account"}
STOP = {"price", "prices", "for", "of", "a", "an", "the", "how", "much", "is", "what", "whats", "what's", "cost",
        "costs", "do", "we", "charge", "on", "in", "per", "at", "and", "to", "our"}

def haystack(r):
    parts = [r.get(k, "") for k in ("id", "category", "item", "variant", "brand", "sku", "stock", "color",
                                     "fulfillment", "equipment", "keywords", "notes", "unit")]
    if r.get("sides") == "2":
        parts.append("duplex double-sided")
    if r.get("sides") == "1":
        parts.append("single")
    if r.get("color", "").lower() in ("b/w", "black ink"):
        parts.append("b/w black")
    return " ".join(parts).lower()

def parse_query(terms):
    """split free text into size / qty / text tokens."""
    q = " ".join(terms)
    sizes, qtys, words = [], [], []
    for pat in (r'\d+(?:\.\d+)?(?:\s+\d/\d)?\s*"?\s*(?:in)?\s*[x×]\s*\d+(?:\.\d+)?(?:\s+\d/\d)?\s*"?',):
        for m in re.finditer(pat, q.lower()):
            n = norm_size(m.group(0))
            if n:
                sizes.append(n)
        q = re.sub(pat, " ", q.lower())
    low = q.lower()
    for name, sz in NAMED_SIZES.items():
        if re.search(r"\b" + re.escape(name) + r"\b", low):
            sizes.append(sz)
            low = re.sub(r"\b" + re.escape(name) + r"\b", " ", low)
    low = low.replace("black and white", "b/w").replace("black & white", "b/w")
    for tok in re.split(r"[\s,]+", low):
        tok = tok.strip("?.!:;()")
        if not tok or tok in STOP:
            continue
        if re.fullmatch(r"\d{1,4}", tok):
            qtys.append(int(tok))
            continue
        words.append(SYN.get(tok, tok))
    return sizes, qtys, words

def match_row(r, sizes, qtys, words):
    if sizes:
        rs = norm_size(r.get("size", "")) or ""
        if rs not in sizes:
            return False
    if qtys and (r.get("qty_min") or r.get("qty_max")):
        lo = int(r["qty_min"]) if r.get("qty_min") else 0
        hi = int(r["qty_max"]) if r.get("qty_max") else 10 ** 9
        if r.get("unit") == "lot" and "addl" not in r.get("id", ""):
            if not any(q == lo for q in qtys):
                return False
        elif not any(lo <= q <= hi for q in qtys):
            return False
    hs = haystack(r)
    for w in words:
        stem = w.rstrip("s") if len(w) > 3 else w
        if stem not in hs:
            return False
    return True

def search(rows, terms, include_all=False, category=None):
    sizes, qtys, words = parse_query(terms)
    out = []
    for r in rows:
        if not include_all and r.get("status") not in LIVE:
            continue
        if category and category.lower() not in r.get("category", "").lower():
            continue
        if match_row(r, sizes, qtys, words):
            out.append(r)
    return out, (sizes, qtys, words)

def print_rows(rows, show_id=True):
    if not rows:
        print("  (nothing found)")
        return
    for r in rows:
        desc = r["item"]
        extra = ", ".join(x for x in (r.get("variant"), r.get("size"), r.get("color") if r.get("color") not in
                                      (r.get("item"),) else "") if x)
        q = qty_label(r)
        ul = unit_label(r) if r.get("price") else ""
        line = f"  {fmt_price(r):>12} {ul:<7} {desc}"
        if extra:
            line += f" | {extra}"
        if q:
            line += f" | qty {q}"
        f = flag(r)
        if f:
            line += f"   [{f.strip()}]"
        if show_id:
            line += f"   <{r['id']}>"
        print(line)

# ------------------------------------------------------------------ quoting
def family_rows(rows, fam):
    return [r for r in rows if r.get("family") == fam and r.get("status") in LIVE]

def pick_tier(rows, r, qty):
    fam = r.get("family")
    if not fam:
        return r
    cands = [x for x in family_rows(rows, fam) if x.get("unit") == r.get("unit")]
    for c in cands:
        lo = int(c["qty_min"]) if c.get("qty_min") else 0
        hi = int(c["qty_max"]) if c.get("qty_max") else 10 ** 9
        if c.get("unit") != "lot" and lo <= qty <= hi and (c.get("qty_min") or c.get("qty_max")):
            return c
    return r

def quote_line(rows, key, qty, w=None, h=None, length=None):
    byid = {r["id"]: r for r in rows}
    r = byid.get(key)
    if r is None:
        fam = family_rows(rows, key)
        if not fam:
            raise SystemExit(f"quote: no price id or family '{key}'. Try: pricebook.py find ...")
        r = fam[0]
    if r.get("status") not in LIVE:
        raise SystemExit(f"quote: {r['id']} is {r.get('status')} - not quoted. "
                         f"See why: pricebook.py get {r['id']}   Current prices: pricebook.py find ...")
    r = pick_tier(rows, r, qty)
    warn = []
    if r.get("status") == "pending":
        warn.append(f"price is PENDING (conflict card {r.get('cards')})")
    if r.get("status") == "unpriced" or not r.get("price"):
        return r, None, [f"NO PRICE on file for {r['id']} ({r.get('cards', '')})"], ""
    p = float(r["price"])
    u = r.get("unit")
    how = ""
    if u == "sq ft":
        if not (w and h):
            dims = size_dims(r.get("size", ""))
            if not dims:
                raise SystemExit(f"quote: {r['id']} is priced per sq ft - give --w and --h in inches")
            w, h = dims
        sqft = w * h / 144.0
        total = sqft * p * qty
        how = f"{qty} x {w:g}x{h:g} in ({sqft:.2f} sq ft) x {money(p)}/sq ft"
    elif u == "linear ft":
        L = length or h
        if not L:
            raise SystemExit(f"quote: {r['id']} is priced per linear ft - give --length in inches")
        total = (L / 12.0) * p * qty
        how = f"{qty} x {L:g} in ({L / 12:.2f} ft) x {money(p)}/lin ft"
    elif u == "lot":
        fam = family_rows(rows, r.get("family")) if r.get("family") else [r]
        lots = sorted([x for x in fam if x.get("qty_max")], key=lambda x: int(x["qty_min"]))
        addl = [x for x in fam if "addl" in x["id"]]
        exact = [x for x in lots if int(x["qty_min"]) == qty]
        if exact:
            r = exact[0]
            total, how = float(r["price"]), f"{qty:,} = lot price"
        elif addl and lots and qty > int(lots[-1]["qty_min"]):
            base = lots[-1]
            extra = math.ceil((qty - int(base["qty_min"])) / 1000)
            total = float(base["price"]) + extra * float(addl[0]["price"])
            how = f"{int(base['qty_min']):,} lot {money(base['price'])} + {extra} x add'l 1,000 {money(addl[0]['price'])}"
            if addl[0].get("status") == "pending":
                warn.append(f"add'l-1,000 price is PENDING ({addl[0].get('cards')})")
        else:
            up = [x for x in lots if int(x["qty_min"]) >= qty]
            if not up:
                raise SystemExit(f"quote: no lot for {qty} in {r.get('family')}; lots: " +
                                 ", ".join(x["qty_min"] for x in lots))
            r = up[0]
            total = float(r["price"])
            how = f"next lot up is {int(r['qty_min']):,} = {money(r['price'])} (no {qty:,} lot)"
            warn.append(f"quoted the {int(r['qty_min']):,} lot")
        if r.get("status") == "pending" and not any("PENDING" in x for x in warn):
            warn.append(f"price is PENDING ({r.get('cards')})")
    elif u in ("per 1000", "per 500"):
        fam = family_rows(rows, r.get("family")) if r.get("family") else [r]
        r500 = [x for x in fam if x.get("unit") == "per 500"]
        r1000 = [x for x in fam if x.get("unit") == "per 1000"]
        if qty <= 500 and r500:
            r = r500[0]
            total, how = float(r["price"]), f"up to 500 = {money(r['price'])}"
        else:
            r = r1000[0] if r1000 else r
            per = 1000 if r["unit"] == "per 1000" else 500
            total = qty / per * float(r["price"])
            how = f"{qty:,} x {money(r['price'])}/{per:,}"
    else:
        total = p * qty
        how = f"{qty:,} x {money(p)}" + (f" ({qty_label(r)} tier)" if qty_label(r) else "")
    mc = r.get("min_charge")
    if mc and total < float(mc):
        how += f" -> minimum {money(mc)}"
        total = float(mc)
    return r, round(total + 1e-9, 2), warn, how

# ------------------------------------------------------------------ cards
def card_by_id(doc, cid):
    for c in doc["cards"]:
        if c["id"].upper() == cid.upper():
            return c
    raise SystemExit(f"no card {cid}")

def strip_card(rows, cid, table, who, source, activate=True, retire=False):
    """remove card id from rows; pending rows with no remaining cards become active (or retired)."""
    n = 0
    for r in rows:
        cards = r.get("cards", "").split()
        if cid not in cards:
            continue
        cards.remove(cid)
        old_status = r["status"]
        r["cards"] = " ".join(cards)
        if retire and old_status in LIVE:
            r["status"] = "retired"
        elif activate and old_status == "pending" and not cards:
            r["status"] = "active" if r.get("price", "x") != "" or table == "contacts" else "unpriced"
        if r["status"] != old_status:
            log("status", table, r["id"], "status", old_status, r["status"], who, source, f"card {cid}")
        r["updated"] = today()
        n += 1
    return n

def apply_price(r, value, who, source, note, table="prices"):
    old = r.get("price", "")
    r["price"] = f"{float(value):.2f}"
    log("set", table, r["id"], "price", old, r["price"], who, source, note)
    if r.get("status") != "active":
        log("status", table, r["id"], "status", r.get("status", ""), "active", who, source, note)
    r["status"] = "active"
    r["updated"] = today()

# ------------------------------------------------------------------ commands
def cmd_find(a):
    rows = load_prices()
    res, (sizes, qtys, words) = search(rows, a.terms, a.all, a.category)
    if not res and words:
        # relax: any word
        res = [r for r in rows if (a.all or r.get("status") in LIVE) and
               any((w.rstrip("s") if len(w) > 3 else w) in haystack(r) for w in words) and
               (not sizes or (norm_size(r.get("size", "")) or "") in sizes)]
        if res:
            print("  (no exact match; showing partial matches)")
    if a.json:
        print(json.dumps(res, indent=1))
        return
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    res.sort(key=lambda r: (order.get(r["category"], 99), r.get("family", ""), r["item"],
                            int(r["qty_min"]) if r.get("qty_min", "").isdigit() else 0))
    cur = None
    for r in res[: a.limit]:
        if r["category"] != cur:
            cur = r["category"]
            print(f"\n{cur}")
        print_rows([r], show_id=not a.no_id)
    if len(res) > a.limit:
        print(f"\n  ... {len(res) - a.limit} more (use --limit)")

def cmd_get(a):
    rows = load_prices()
    byid = {r["id"]: r for r in rows}
    if a.id not in byid:
        res, _ = search(rows, [a.id], include_all=True)
        raise SystemExit(f"no id '{a.id}'." + (" Did you mean: " + ", ".join(r["id"] for r in res[:8]) if res else ""))
    r = byid[a.id]
    if a.json:
        print(json.dumps(r, indent=1)); return
    for k in PRICE_FIELDS:
        if r.get(k):
            print(f"  {k:12} {r[k]}")
    hist = [h for h in read_csv("changelog.csv") if h["id"] == a.id]
    if hist:
        print("  history:")
        for h in hist:
            print(f"    {h['when']}  {h['action']:7} {h['field']}: {h['old']} -> {h['new']}  ({h['who']}; {h['source']}) {h['note']}")

def cmd_set(a):
    rows = load_prices()
    byid = {r["id"]: r for r in rows}
    if a.id not in byid:
        raise SystemExit(f"no id '{a.id}' (use find)")
    r = byid[a.id]
    try:
        float(a.price)
    except ValueError:
        raise SystemExit("price must be a number, e.g. 3.50")
    had_cards = r.get("cards", "")
    old_price = r.get("price", "")
    apply_price(r, a.price, a.by, a.source, a.note)
    if had_cards and not a.keep_cards:
        r["cards"] = ""
        doc = load_cards()
        for cid in had_cards.split():
            for c in doc["cards"]:
                if c["id"] == cid and c["status"] == "open":
                    for ln in c.get("lines", []):
                        if ln.get("target") == a.id:
                            ln["answer"] = f"{float(a.price):.2f}"
                    c.setdefault("notes", []).append(f"{today()}: {a.id} set to {a.price} directly ({a.source or 'chat'})")
        save_cards(doc)
    save_prices(rows)
    print(f"{a.id}: {money(old_price) or 'no price'} -> {money(r['price'])} (logged)")
    print_rows([r])

def cmd_edit(a):
    rows = load_prices()
    byid = {r["id"]: r for r in rows}
    if a.id not in byid:
        raise SystemExit(f"no id '{a.id}'")
    r = byid[a.id]
    for kv in a.pairs:
        if "=" not in kv:
            raise SystemExit(f"expected FIELD=VALUE, got {kv}")
        k, v = kv.split("=", 1)
        if k not in PRICE_FIELDS or k == "id":
            raise SystemExit(f"unknown/locked field {k}")
        if k == "status" and v not in STATUSES:
            raise SystemExit(f"status must be one of {sorted(STATUSES)}")
        log("edit", "prices", a.id, k, r.get(k, ""), v, a.by, a.source, a.note)
        r[k] = v
    r["updated"] = today()
    save_prices(rows)
    print_rows([r])

def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9.]+", "-", s.lower())).strip("-")

def cmd_add(a):
    rows = load_prices()
    rid = a.id or slugify("-".join(x for x in (a.item, a.variant, a.size, a.qty_min) if x))
    if any(r["id"] == rid for r in rows):
        raise SystemExit(f"id {rid} exists")
    if a.unit not in UNITS:
        raise SystemExit(f"unit must be one of {sorted(UNITS)}")
    r = {k: "" for k in PRICE_FIELDS}
    r.update(id=rid, family=a.family or "", category=a.category, item=a.item, variant=a.variant or "",
             size=norm_size(a.size) or a.size or "", color=a.color or "", sides=a.sides or "",
             qty_min=a.qty_min or "", qty_max=a.qty_max or "", unit=a.unit,
             price=f"{float(a.price):.2f}" if a.price else "", min_charge=a.min_charge or "",
             fulfillment=a.fulfillment, stock=a.stock or "", sku=a.sku or "", brand=a.brand or "",
             status="active" if a.price else "unpriced", source=a.source or f"added {today()}",
             mark="verbal/chat", updated=today(), notes=a.note or "", keywords=a.keywords or "")
    rows.append(r)
    log("add", "prices", rid, "price", "", r["price"], a.by, a.source, a.note)
    save_prices(rows)
    print_rows([r])

def cmd_retire(a):
    rows = load_prices()
    byid = {r["id"]: r for r in rows}
    if a.id not in byid:
        raise SystemExit(f"no id '{a.id}'")
    r = byid[a.id]
    log("retire", "prices", a.id, "status", r["status"], "retired", a.by, a.source, a.note)
    r["status"] = "retired"
    r["updated"] = today()
    save_prices(rows)
    print_rows([r])

def cmd_history(a):
    hist = read_csv("changelog.csv")
    if a.id:
        hist = [h for h in hist if h["id"] == a.id or h["id"].startswith(a.id)]
    for h in hist[-a.limit:]:
        print(f"{h['when']}  {h['who']:8} {h['action']:7} {h['table']:8} {h['id']:40} {h['field']}: "
              f"{h['old']} -> {h['new']}  {h['source']} {h['note']}")

def cmd_quote(a):
    rows = load_prices()
    parts, cur = [], []
    for t in a.items:
        if t == "+":
            parts.append(cur); cur = []
        else:
            cur.append(t)
    if cur:
        parts.append(cur)
    grand, all_warn = 0.0, []
    print(f"Quote {today()}")
    for p in parts:
        key = p[0]
        qty = int(p[1]) if len(p) > 1 else 1
        r, total, warn, how = quote_line(rows, key, qty, a.w, a.h, a.length)
        label = r["item"] + (f" - {r['variant']}" if r.get("variant") else "") + (f" {r['size']}" if r.get("size") else "")
        if total is None:
            print(f"  {'???':>10}  {label}")
        else:
            grand += total
            print(f"  {money(total):>10}  {label}   [{how}]")
        for w in warn:
            print(f"              ! {w}")
        all_warn += warn
    print(f"  {'-' * 10}")
    print(f"  {money(grand):>10}  subtotal")
    rate = a.tax if a.tax is not None else load_settings().get("sales_tax_rate")
    if rate:
        tax = round(grand * float(rate) / 100, 2)
        print(f"  {money(tax):>10}  sales tax {rate}%")
        print(f"  {money(grand + tax):>10}  total")
    else:
        print("              (sales tax not included - rate not set)")

def cmd_contacts(a):
    rows = load_contacts()
    words = [w.lower() for w in a.terms]
    for r in rows:
        if not a.all and r.get("status") == "retired":
            continue
        if not a.all and r.get("visibility") == "internal" and a.public:
            continue
        hs = " ".join(r.values()).lower()
        if all(w in hs for w in words):
            flagtxt = f"  [PENDING {r['cards']}]" if r.get("status") == "pending" else ""
            who = r["name"] + (f" ({r['organization']})" if r["organization"] and r["organization"] not in r["name"] else "")
            print(f"  {who:45} {r['kind']:8} {r['value']}{flagtxt}" + (f"  - {r['notes']}  <{r['id']}>" if a.verbose else ""))

def cmd_edit_contact(a):
    rows = load_contacts()
    byid = {r["id"]: r for r in rows}
    if a.id not in byid:
        raise SystemExit(f"no contact '{a.id}' (use: contacts WORDS -v)")
    r = byid[a.id]
    for kv in a.pairs:
        k, v = kv.split("=", 1)
        if k not in CONTACT_FIELDS or k == "id":
            raise SystemExit(f"unknown/locked field {k}")
        if k == "status" and v not in ("active", "pending", "retired"):
            raise SystemExit("contact status must be active, pending or retired")
        log("edit", "contacts", a.id, k, r.get(k, ""), v, a.by, a.source, a.note)
        r[k] = v
    r["updated"] = today()
    save_contacts(rows)
    print(f"  {r['id']}: {r['name']} {r['kind']} {r['value']} [{r['status']}]")

def cmd_conflicts(a):
    doc = load_cards()
    if a.id:
        c = card_by_id(doc, a.id)
        print(json.dumps(c, indent=1, ensure_ascii=False)); return
    for c in doc["cards"]:
        if a.all or c["status"] == "open":
            print(f"  {c['id']}  {c['status']:8} {c['section']:16} {c['title']}")

def cmd_resolve(a):
    """pricebook.py resolve C02 a=ok            (accept the proposal on line a)
       pricebook.py resolve C06 a=0.08 b=0.07  (write-in prices)
       pricebook.py resolve C09 d=remove       (retire that line's item)
       pricebook.py resolve C07 opt=1          (option cards: 1 = first option, as printed)
       pricebook.py resolve C11 opt=2 text="x3" (non-proposed option: recorded; follow up by hand, then `close`)"""
    doc = load_cards()
    c = card_by_id(doc, a.card)
    rows = load_prices()
    contacts = load_contacts()
    byid = {r["id"]: r for r in rows}
    src = a.source or f"conflict sheet v{c.get('sheet_version', 1)}"
    answers = dict(kv.split("=", 1) for kv in a.answers)
    c["answer"] = answers
    c["answered"] = today()
    manual = []
    for ln in c.get("lines", []):
        v = answers.get(ln["key"], answers.get("all"))
        if v is None:
            continue
        ln["answer"] = v
        t = byid.get(ln.get("target", ""))
        if v in ("ok", "OK", "yes"):
            if t is None:
                manual.append(f"line {ln['key']} ({ln['label']}): OK '{ln.get('proposed')}' - no price row, apply by hand")
            elif ln.get("proposed") == "retire":
                log("retire", "prices", t["id"], "status", t["status"], "retired", a.by, src, c["id"])
                t["status"] = "retired"
            elif ln.get("proposed") in (None, ""):
                manual.append(f"line {ln['key']}: OK but there was no proposal")
            else:
                try:
                    apply_price(t, ln["proposed"], a.by, src, c["id"])
                except ValueError:
                    manual.append(f"line {ln['key']}: proposal '{ln['proposed']}' is not a number - apply by hand")
        elif v in ("remove", "retire", "drop"):
            if t is not None:
                log("retire", "prices", t["id"], "status", t["status"], "retired", a.by, src, c["id"])
                t["status"] = "retired"
        elif v in ("blank", "skip", ""):
            pass
        else:
            try:
                val = float(v.replace("$", ""))
            except ValueError:
                manual.append(f"line {ln['key']}: answer '{v}' recorded - apply by hand")
                continue
            if t is None:
                manual.append(f"line {ln['key']} ({ln['label']}): {v} - no price row, apply by hand")
            else:
                apply_price(t, val, a.by, src, c["id"])
        if t is not None:
            cards = t.get("cards", "").split()
            if c["id"] in cards:
                cards.remove(c["id"]); t["cards"] = " ".join(cards)
            t["updated"] = today()
    if c.get("options"):
        opt = answers.get("opt")
        if opt is None:
            raise SystemExit("option card: give opt=N (1 = first option as printed)")
        idx = int(opt) - 1
        c["answer_option"] = idx
        if c.get("proposed_option") is not None and idx == c["proposed_option"]:
            retire = c.get("on_accept") == "retire"
            n = strip_card(rows, c["id"], "prices", a.by, src, retire=retire)
            n += strip_card(contacts, c["id"], "contacts", a.by, src)
            print(f"  proposal accepted: {n} rows updated")
        else:
            manual.append(f"option {opt} ('{c['options'][idx]}') is not the proposal - apply by hand, then: pricebook.py close {c['id']}")
    unanswered = [ln["key"] for ln in c.get("lines", []) if "answer" not in ln]
    if manual:
        c["manual"] = c.get("manual", []) + manual
    if unanswered:
        c["status"] = "open"          # partly answered; unanswered lines roll to the next sheet
    elif manual:
        c["status"] = "answered"      # needs hand follow-up, then `close`
    else:
        strip_card(rows, c["id"], "prices", a.by, src)
        strip_card(contacts, c["id"], "contacts", a.by, src)
        c["status"] = "resolved"
    log("resolve", "cards", c["id"], "answer", "", json.dumps(answers), a.by, src, "; ".join(manual))
    save_prices(rows); save_contacts(contacts); save_cards(doc)
    print(f"{c['id']}: {c['status']}")
    for m in manual:
        print("  TODO:", m)

def cmd_close(a):
    doc = load_cards()
    c = card_by_id(doc, a.card)
    rows, contacts = load_prices(), load_contacts()
    n = strip_card(rows, c["id"], "prices", a.by, a.source or "manual follow-up")
    n += strip_card(contacts, c["id"], "contacts", a.by, a.source or "manual follow-up")
    c["status"] = "resolved"
    log("close", "cards", c["id"], "status", "", "resolved", a.by, a.source, a.note)
    save_prices(rows); save_contacts(contacts); save_cards(doc)
    print(f"{c['id']} closed; {n} rows released")

def validate(verbose=True):
    rows, contacts, doc = load_prices(), load_contacts(), load_cards()
    problems = []
    ids = set()
    for r in rows:
        if r["id"] in ids:
            problems.append(f"duplicate id {r['id']}")
        ids.add(r["id"])
        if r.get("status") not in STATUSES:
            problems.append(f"{r['id']}: bad status '{r.get('status')}'")
        if r.get("unit") not in UNITS:
            problems.append(f"{r['id']}: bad unit '{r.get('unit')}'")
        for k in ("price", "price_max", "min_charge", "cost"):
            if r.get(k):
                try:
                    float(r[k])
                except ValueError:
                    problems.append(f"{r['id']}: {k} not a number '{r[k]}'")
        for k in ("qty_min", "qty_max"):
            if r.get(k) and not r[k].isdigit():
                problems.append(f"{r['id']}: {k} not an integer '{r[k]}'")
        if r.get("status") == "active" and not r.get("price") and "estimate" not in r.get("notes", "").lower():
            problems.append(f"{r['id']}: active but no price")
        if r.get("size") and not norm_size(r["size"]) and "-" not in r["size"]:
            problems.append(f"{r['id']}: size '{r['size']}' not parseable")
    for c in contacts:
        if c.get("status") not in ("active", "pending", "retired"):
            problems.append(f"contact {c['id']}: bad status '{c.get('status')}'")
    card_ids = {c["id"] for c in doc["cards"]}
    for r in rows + contacts:
        for cid in r.get("cards", "").split():
            if cid not in card_ids:
                problems.append(f"{r['id']}: unknown card {cid}")
    for c in doc["cards"]:
        for ln in c.get("lines", []):
            if ln.get("target") and ln["target"] not in ids:
                problems.append(f"{c['id']} line {ln['key']}: unknown target {ln['target']}")
    secret = re.compile("|".join([r"\bpw:", r"\bpassword\b", r"\bpasswd\b"] + [re.escape(s) for s in secret_fragments()]))
    for name in ("prices.csv", "contacts.csv", "conflicts.json", "changelog.csv"):
        p = os.path.join(DATA, name)
        if os.path.exists(p) and secret.search(open(p, encoding="utf-8").read()):
            problems.append(f"{name}: looks like it contains a login/password/tax ID - those belong in private/")
    if verbose:
        n_open = sum(1 for c in doc["cards"] if c["status"] != "resolved")
        print(f"{len(rows)} price rows, {len(contacts)} contacts, {n_open} open cards")
        for p in problems:
            print("  PROBLEM:", p)
        print("RESULT", "PASS" if not problems else "FAIL")
    return problems

def cmd_validate(a):
    sys.exit(1 if validate() else 0)

def cmd_build(a):
    import pb_render
    probs = validate(verbose=False)
    if probs:
        print("validate failed - fix first:"); [print("  ", p) for p in probs]; sys.exit(1)
    os.makedirs(BUILD, exist_ok=True)
    outs = pb_render.build_all(ROOT, draft=a.draft, only=a.only)
    for o in outs:
        print("  wrote", os.path.relpath(o, ROOT))

def cmd_conflicts_pdf(a):
    import pb_render
    os.makedirs(BUILD, exist_ok=True)
    out = pb_render.conflicts_pdf(ROOT, include=a.cards)
    print("  wrote", os.path.relpath(out, ROOT))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="pricebook.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def who(p):
        p.add_argument("--by", default="", help="who made the change (default: $PRICEBOOK_USER or Claude)")
        p.add_argument("--source", default="", help="where the info came from, e.g. 'Andrew in chat 2026-10-02'")
        p.add_argument("--note", default="")
    p = sp.add_parser("find", help="search prices"); p.add_argument("terms", nargs="*")
    p.add_argument("--all", action="store_true", help="include superseded/retired"); p.add_argument("--category")
    p.add_argument("--json", action="store_true"); p.add_argument("--limit", type=int, default=80)
    p.add_argument("--no-id", action="store_true"); p.set_defaults(fn=cmd_find)
    p = sp.add_parser("get"); p.add_argument("id"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_get)
    p = sp.add_parser("set", help="change a price"); p.add_argument("id"); p.add_argument("price")
    p.add_argument("--keep-cards", action="store_true", help="leave the row on its open conflict card"); who(p); p.set_defaults(fn=cmd_set)
    p = sp.add_parser("edit"); p.add_argument("id"); p.add_argument("pairs", nargs="+"); who(p); p.set_defaults(fn=cmd_edit)
    p = sp.add_parser("add"); who(p)
    for k in ("id", "family", "variant", "size", "color", "sides", "qty-min", "qty-max", "price", "min-charge",
              "stock", "sku", "brand", "keywords"):
        p.add_argument("--" + k)
    p.add_argument("--category", required=True); p.add_argument("--item", required=True)
    p.add_argument("--unit", default="each"); p.add_argument("--fulfillment", default="in-house"); p.set_defaults(fn=cmd_add)
    p = sp.add_parser("retire"); p.add_argument("id"); who(p); p.set_defaults(fn=cmd_retire)
    p = sp.add_parser("history"); p.add_argument("id", nargs="?"); p.add_argument("--limit", type=int, default=50); p.set_defaults(fn=cmd_history)
    p = sp.add_parser("quote", help="quote a job: ITEM QTY [+ ITEM QTY ...]"); p.add_argument("items", nargs="+")
    p.add_argument("--w", type=float, help="width in inches (sq ft items)"); p.add_argument("--h", type=float, help="height in inches")
    p.add_argument("--length", type=float, help="length in inches (linear ft items)")
    p.add_argument("--tax", type=float, help="sales tax %% (overrides settings)"); p.set_defaults(fn=cmd_quote)
    p = sp.add_parser("contacts"); p.add_argument("terms", nargs="*"); p.add_argument("--all", action="store_true")
    p.add_argument("--public", action="store_true", help="hide internal numbers"); p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_contacts)
    p = sp.add_parser("edit-contact"); p.add_argument("id"); p.add_argument("pairs", nargs="+"); who(p); p.set_defaults(fn=cmd_edit_contact)
    p = sp.add_parser("conflicts"); p.add_argument("id", nargs="?"); p.add_argument("--all", action="store_true"); p.set_defaults(fn=cmd_conflicts)
    p = sp.add_parser("resolve", help=cmd_resolve.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("card"); p.add_argument("answers", nargs="+"); who(p); p.set_defaults(fn=cmd_resolve)
    p = sp.add_parser("close"); p.add_argument("card"); who(p); p.set_defaults(fn=cmd_close)
    p = sp.add_parser("validate"); p.set_defaults(fn=cmd_validate)
    p = sp.add_parser("build"); p.add_argument("--draft", choices=["auto", "yes", "no"], default="auto")
    p.add_argument("--only", nargs="*", choices=["book", "xlsx", "html", "mirror"]); p.set_defaults(fn=cmd_build)
    p = sp.add_parser("conflicts-pdf"); p.add_argument("cards", nargs="*", help="card ids (default: all open)")
    p.set_defaults(fn=cmd_conflicts_pdf)
    a = ap.parse_args(argv)
    for k in ("qty_min", "qty_max", "min_charge"):
        if hasattr(a, k) and getattr(a, k) is None:
            pass
    a.fn(a)

if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    main()
