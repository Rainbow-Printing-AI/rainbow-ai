#!/usr/bin/env python3
"""
mergelabels.py — mail merge: one address per label on Avery die-cut sheets.

Reads an .xlsx (first sheet, or --sheet) or .csv with a header row.  Columns are found by
header name (case/space-insensitive):
  name     : RepName, Name, Contact, Full Name, Attn
  company  : Company, Business, Organization
  address1 : Address1, Address, Street, Address 1
  address2 : Address2, Address 2, Suite, Unit
  city / state / zip : City, State (or ST), Zip (or Zip Code, Postal Code)

Label lines, top to bottom:  Name / Company / Address1 [Address2] / City, ST ZIP
(empty lines dropped).  Text is vector, black, embedded Liberation Sans (Helvetica
metrics) when available, left-aligned --inset in from the die, block vertically centered,
--clear inches of clearance inside the die.  Every label starts at --max-pt; a label that
doesn't fit steps down to --wrap-pt, then wraps its widest line (balanced, preferring
a break after - / ,) and steps down to --min-pt.

Cleanup (reported, never silent): whitespace trimmed/collapsed; full state names -> USPS
2-letter; numeric ZIPs zero-padded to 5; Address2 dropped when it's an email, already
contained in Address1, or just the company name repeated; a bare-number Address2 becomes
"#n"; Address2 joined onto the Address1 line.  Records missing street, city, state or ZIP
are skipped and listed.  --fix "ROW:field=value" overrides a cell (ROW = spreadsheet row
number, field = name|company|address1|address2|city|state|zip; value "" blanks it).

Writes the labels PDF (exactly 8.5x11, no marks, no bleed) and <out stem>_merge.csv —
the exact lines printed, one record per row, in print order, with sheet/position.
Verify with:  verify_print.py OUT --grid PRESET

  mergelabels.py "Mailing List.xlsx" --grid avery5160
  mergelabels.py list.csv --grid avery5160 --sort zip --fix "12:city=Incline Village"
"""
import argparse, csv, os, re, sys

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_print import GRIDS, parse_grid  # noqa: E402

IN = 72.0
HEADERS = {
    "name": ["repname", "name", "contact", "fullname", "contactname", "attn", "attention"],
    "company": ["company", "business", "organization", "organisation", "companyname", "businessname"],
    "address1": ["address1", "address", "street", "streetaddress", "addressline1", "mailingaddress"],
    "address2": ["address2", "addressline2", "suite", "unit", "apt"],
    "city": ["city", "town"],
    "state": ["state", "st", "province"],
    "zip": ["zip", "zipcode", "postalcode", "postcode", "zip5"],
}
STATES = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL",
    "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "calif": "CA", "calif.": "CA", "nev": "NV", "nev.": "NV"}
FIELDS = list(HEADERS)


def font_setup(want):
    if want != "auto":
        return want
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "LiberationSans-Regular.ttf"),
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont("MergeSans", p))
            return "MergeSans"
    print("WARN  no TTF found; using unembedded Helvetica", file=sys.stderr)
    return "Helvetica"


def read_rows(path, sheet):
    if path.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    return rows[0], rows[1:]


def norm_key(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def map_headers(head):
    keys = [norm_key(h) for h in head]
    m = {}
    for field, names in HEADERS.items():
        for n in names:
            if n in keys and keys.index(n) not in m.values():
                m[field] = keys.index(n); break
    return m


def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def toks(s):
    syn = {"suite": "ste", "unit": "ste", "apt": "ste", "apartment": "ste", "no": "", "number": ""}
    t = [syn.get(x, x) for x in re.findall(r"[a-z0-9]+", s.lower())]
    return [x for x in t if x]


def contained(a2, a1):
    """Address2 tokens appear as a contiguous run in Address1 (or match with the unit word dropped)."""
    b, a = toks(a2), toks(a1)
    for cand in (b, [x for x in b if x != "ste"]):
        n = len(cand)
        if n and any(a[i:i + n] == cand for i in range(len(a) - n + 1)) and (n > 1 or cand == b and len(b) > 1):
            return True
    return False


def build(rec, rowno, notes):
    def note(msg):
        notes.append(f"row {rowno}: {msg}")
    st = rec["state"]
    if st.lower() in STATES:
        note(f"state {st!r} -> {STATES[st.lower()]}"); st = STATES[st.lower()]
    st = st.upper() if len(st) == 2 else st
    z = rec["zip"]
    if re.fullmatch(r"\d{1,4}", z):
        note(f"ZIP {z} zero-padded"); z = z.zfill(5)
    a1, a2 = rec["address1"], rec["address2"]
    if a2:
        if "@" in a2:
            note(f"Address2 is an email ({a2}) — dropped"); a2 = ""
        elif contained(a2, a1):
            note(f"Address2 {a2!r} already in Address1 — dropped"); a2 = ""
        elif re.sub(r"^(attn:?\s*)", "", a2, flags=re.I).lower() in rec["company"].lower() \
                or a2.lower() in rec["company"].lower():
            note(f"Address2 {a2!r} repeats the company — dropped"); a2 = ""
        elif re.fullmatch(r"\d+[A-Za-z]?", a2):
            a2 = "#" + a2
    street = (a1.rstrip(",") + " " + a2).strip() if a2 else a1
    missing = [k for k, v in (("street", street), ("city", rec["city"]), ("state", st), ("ZIP", z)) if not v]
    if missing:
        return None, missing
    if not rec["name"]:
        note("no name — company only")
    lines = [l for l in (rec["name"], rec["company"], street, f"{rec['city']}, {st} {z}") if l]
    return lines, z


def wrap_once(lines, font, pt, w):
    """split the widest line in two: balanced widths, preferring a break after - / , & or before ( ."""
    i = max(range(len(lines)), key=lambda k: stringWidth(lines[k], font, pt))
    words = lines[i].split(" ")
    best = None
    for j in range(1, len(words)):
        head, tail = " ".join(words[:j]), " ".join(words[j:])
        mw = max(stringWidth(head, font, pt), stringWidth(tail, font, pt))
        if mw > w:
            continue
        punct = head.endswith(("-", "/", ",", "&", ";", ":")) or tail.startswith("(")
        score = mw * (0.8 if punct else 1.0)
        if best is None or score < best[0]:
            best = (score, head, tail)
    if best is None:
        return None
    return lines[:i] + [best[1], best[2]] + lines[i + 1:]


def fit(lines, font, w, h, max_pt, min_pt, lead, wrap_pt):
    """step down to wrap_pt unwrapped; then wrap (at most twice) and step max_pt..min_pt;
    last resort: unwrapped down to min_pt."""
    def tries(cur, lo):
        pt = max_pt
        while pt >= lo - 1e-9:
            if max(stringWidth(l, font, pt) for l in cur) <= w and pt * (1 + lead * (len(cur) - 1)) <= h:
                return pt
            pt -= 0.25
        return None
    pt = tries(lines, wrap_pt)
    if pt:
        return lines, pt
    cur = list(lines)
    for _ in range(2):
        cur = wrap_once(cur, font, min_pt, w)
        if cur is None:
            break
        pt = tries(cur, min_pt)
        if pt:
            return cur, pt
    pt = tries(lines, min_pt)
    return (lines, pt) if pt else (None, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help=".xlsx or .csv with a header row")
    ap.add_argument("--grid", default="avery5160", help=f"preset ({', '.join(sorted(GRIDS))}) or cols,rows,w,h,left,top,pitch_x,pitch_y")
    ap.add_argument("--sheet", help="worksheet name (default: first)")
    ap.add_argument("--sort", choices=["source", "zip"], default="source")
    ap.add_argument("--font", default="auto", help="auto = embedded Liberation Sans/Arial; or a reportlab font name")
    ap.add_argument("--max-pt", type=float, default=10)
    ap.add_argument("--min-pt", type=float, default=7)
    ap.add_argument("--wrap-pt", type=float, default=9, help="shrink unwrapped only this far before wrapping a long line")
    ap.add_argument("--leading", type=float, default=1.18)
    ap.add_argument("--clear", type=float, default=0.08, help="clearance inside each die, inches")
    ap.add_argument("--inset", type=float, default=0.15, help="left text inset from the die edge, inches (>= --clear)")
    ap.add_argument("--fix", action="append", default=[], help='"ROW:field=value" cell override')
    ap.add_argument("--out")
    a = ap.parse_args()

    g = parse_grid(a.grid)
    if len(g) > 8 and g[8] == "round":
        sys.exit("round die-cuts aren't supported for address merges")
    cols, rows_, lw, lh, left, top, px, py = g[:8]
    per = cols * rows_
    font = font_setup(a.font)
    head, data = read_rows(a.source, a.sheet)
    hm = map_headers(head)
    for need in ("address1", "city", "state", "zip"):
        if need not in hm:
            sys.exit(f"no {need} column found in header {head}")
    if "name" not in hm and "company" not in hm:
        sys.exit(f"no name or company column found in header {head}")
    print("columns: " + ", ".join(f"{k}={head[v]!r}" for k, v in hm.items()))

    fixes = {}
    for f in a.fix:
        m = re.fullmatch(r"(\d+):(\w+)=(.*)", f, re.S)
        if not m or m.group(2) not in FIELDS:
            sys.exit(f"bad --fix {f!r} (want ROW:field=value, field in {FIELDS})")
        fixes.setdefault(int(m.group(1)), {})[m.group(2)] = m.group(3)

    notes, skipped, recs = [], [], []
    for k, r in enumerate(data):
        rowno = k + 2
        if not any(clean(x) for x in r):
            continue
        rec = {f: clean(r[hm[f]]) if f in hm and hm[f] < len(r) else "" for f in FIELDS}
        for f, v in fixes.get(rowno, {}).items():
            notes.append(f"row {rowno}: --fix {f}: {rec[f]!r} -> {v!r}"); rec[f] = v
        lines, z = build(rec, rowno, notes)
        if lines is None:
            skipped.append(f"row {rowno}: {rec['company'] or rec['name']} — missing {', '.join(z)}"); continue
        recs.append((rowno, z, lines))
    if a.sort == "zip":
        recs.sort(key=lambda t: (t[1], t[0]))

    w = (lw - a.inset - a.clear) * IN
    h = (lh - 2 * a.clear) * IN
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.source)),
        f"{os.path.splitext(os.path.basename(a.source))[0]}_{a.grid if a.grid in GRIDS else 'custom'}_{per}up_letter.pdf")
    c = canvas.Canvas(out, pagesize=(8.5 * IN, 11 * IN))
    c.setTitle(os.path.splitext(os.path.basename(out))[0])
    c.setFillColorRGB(0, 0, 0)
    log, shrunk, wrapped, bad = [], 0, 0, []
    for n, (rowno, z, lines) in enumerate(recs):
        if n and n % per == 0:
            c.showPage(); c.setFillColorRGB(0, 0, 0)
        pos = n % per
        r, col = divmod(pos, cols)
        fl, pt = fit(lines, font, w, h, a.max_pt, a.min_pt, a.leading, a.wrap_pt)
        if fl is None:
            bad.append(f"row {rowno}: {lines}"); continue
        shrunk += pt < a.max_pt; wrapped += len(fl) > len(lines)
        x = (left + col * px + a.inset) * IN
        cy = (11 - (top + r * py + lh / 2)) * IN
        lead = pt * a.leading
        y0 = cy + (len(fl) - 1) * lead / 2 - 0.36 * pt
        c.setFont(font, pt)
        for i, l in enumerate(fl):
            c.drawString(x, y0 - i * lead, l)
        log.append([n // per + 1, pos + 1, rowno, f"{pt:g}"] + fl)
    if bad:
        print("FAIL  these records don't fit even at --min-pt with wrapping:\n  " + "\n  ".join(bad))
        sys.exit(1)
    c.save()
    mcsv = os.path.splitext(out)[0] + "_merge.csv"
    with open(mcsv, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(["sheet", "position", "source_row", "pt", "line1", "line2", "line3", "line4", "line5", "line6"])
        wr.writerows(log)
    sheets = -(-len(recs) // per)
    last = len(recs) - (sheets - 1) * per
    print(f"{a.grid}: {cols}x{rows_} = {per}/sheet, {len(recs)} labels on {sheets} sheets (last sheet {last}), "
          f"order: {a.sort}")
    print(f"font {font} {a.max_pt:g} pt ({shrunk} stepped down, {wrapped} wrapped, min {a.min_pt:g}), "
          f"inset {a.inset} in, clearance {a.clear} in")
    if notes:
        print(f"cleanup ({len(notes)}):\n  " + "\n  ".join(notes))
    if skipped:
        print(f"SKIPPED ({len(skipped)}):\n  " + "\n  ".join(skipped))
    print(f"wrote {out}\nwrote {mcsv}")


if __name__ == "__main__":
    main()
