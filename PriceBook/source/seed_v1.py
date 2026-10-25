#!/usr/bin/env python3
"""
seed_v1.py - one-time import of the 2026-09-30 price-sheet scans into data/*.csv

Kept for audit: it records exactly how every row in the initial price book was
derived from scan_147.pdf / scan_149.pdf and the transcriptions in
source/transcriptions/. Do NOT re-run it on a live price book (it overwrites
data/prices.csv); use pricebook.py for all changes after import.

Source key used in the `source` column:
  S147-pNN  = scan_147.pdf page NN      S149 = scan_149.pdf (older pen sheet)
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
TODAY = "2026-09-30"

FIELDS = ["id", "family", "category", "item", "variant", "brand", "sku", "size",
          "stock", "color", "sides", "qty_min", "qty_max", "unit", "price",
          "price_max", "min_charge", "cost", "fulfillment", "equipment",
          "turnaround", "status", "cards", "source", "mark", "updated",
          "notes", "keywords"]

ROWS = []
def P(id, **kw):
    r = {f: "" for f in FIELDS}
    r["id"] = id
    r["updated"] = TODAY
    r["status"] = "active"
    r["fulfillment"] = "in-house"
    for k, v in kw.items():
        if k not in r:
            raise KeyError(k)
        r[k] = "" if v is None else str(v)
    if r["price"]:
        r["price"] = f"{float(r['price']):.2f}"
    if r["price_max"]:
        r["price_max"] = f"{float(r['price_max']):.2f}"
    if r["min_charge"]:
        r["min_charge"] = f"{float(r['min_charge']):.2f}"
    if r["cost"]:
        r["cost"] = f"{float(r['cost']):.2f}"
    assert not any(x["id"] == id for x in ROWS), f"duplicate id {id}"
    ROWS.append(r)
    return r

# ---------------------------------------------------------------- COPIES B/W
KW_BW = "black and white copies, b&w, bw, xerox, photocopy, copy"
for size, tiers in [
    ("8.5x11", [("1", "20", ".10", ".20"), ("21", "99", None, ".13"), ("100", "", None, ".11")]),
    ("8.5x14", [("1", "20", ".13", ".26"), ("21", "99", ".09", ".17"), ("100", "", ".08", ".13")]),
    ("11x17",  [("1", "20", ".20", ".40"), ("21", "99", ".14", ".29"), ("100", "", ".12", ".22")]),
]:
    for qmin, qmax, simplex, duplex in tiers:
        tag = f"{qmin}-{qmax}" if qmax else f"{qmin}up"
        if simplex is None:
            P(f"bw-{size}-simplex-{tag}", family=f"bw-{size}-simplex", category="Copies - B/W",
              item="B/W copy", variant="single-sided", size=size, color="B/W", sides="1",
              qty_min=qmin, qty_max=qmax, unit="each", status="unpriced", cards="C06",
              source="S147-p03", mark="printed (struck)", keywords=KW_BW,
              notes="Printed " + (".07" if qmin == "21" else ".06/.08 (struck digit unclear)") +
                    " is struck; blue replacement scribbled out. No readable price.")
        else:
            P(f"bw-{size}-simplex-{tag}", family=f"bw-{size}-simplex", category="Copies - B/W",
              item="B/W copy", variant="single-sided", size=size, color="B/W", sides="1",
              qty_min=qmin, qty_max=qmax, unit="each", price=simplex, source="S147-p03",
              mark="printed", keywords=KW_BW)
        P(f"bw-{size}-duplex-{tag}", family=f"bw-{size}-duplex", category="Copies - B/W",
          item="B/W copy", variant="duplex (price per sheet, both sides)", size=size, 
          color="B/W", sides="2", qty_min=qmin, qty_max=qmax, unit="each", price=duplex,
          source="S147-p03", mark="printed", keywords=KW_BW + ", double-sided, 2-sided")

# -------------------------------------------------------------- COPIES COLOR
KW_CO = "color copies, colour, xerox, photocopy, copy, Versant"
for size, lo, hi in [("8.5x11", ".69", ".49"), ("8.5x14", ".89", ".69"), ("11x17", "1.38", ".98")]:
    P(f"color-{size}-1-25", family=f"color-{size}", category="Copies - Color", item="Color copy",
      size=size, color="Color", qty_min=1, qty_max=25, unit="each",
      price=lo, source="S147-p03", mark="printed", equipment="Versant 180 (inferred)", keywords=KW_CO)
    P(f"color-{size}-26up", family=f"color-{size}", category="Copies - Color", item="Color copy",
      size=size, color="Color", qty_min=26, unit="each",
      price=hi, source="S147-p03", mark="printed", equipment="Versant 180 (inferred)", keywords=KW_CO)

# --------------------------------------------------------- LARGE FORMAT B/W
KW_LFB = ("large format, wide format, blueprint, blueprints, plans, plan set, engineering, architectural, "
          "construction drawings, bond, PlotWave, oversize copy")
EQ_LFB = "PlotWave 300 (inferred)"
P("lf-bw-18x24-walkin", family="lf-bw-18x24", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="walk-in (no account)", size="18x24", color="B/W", unit="each", price="2.00",
  source="S147-p03; S147-p01", mark="printed", equipment=EQ_LFB, keywords=KW_LFB,
  notes="Both sheets agree ($2.00).")
P("lf-bw-18x24-account", family="lf-bw-18x24", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="account customer", size="18x24", color="B/W", unit="each", price="1.50",
  source="S147-p03", mark="printed", equipment=EQ_LFB, keywords=KW_LFB)
P("lf-bw-24x36-walkin", family="lf-bw-24x36", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="walk-in (no account)", size="24x36", color="B/W", unit="each", status="unpriced",
  cards="C01", source="S147-p03; S147-p01", mark="printed (struck)", equipment=EQ_LFB, keywords=KW_LFB,
  notes="p03: $2.50 struck in blue, no replacement. p01 (older LF sheet): $2.50, pen-labelled B/W.")
P("lf-bw-24x36-account", family="lf-bw-24x36", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="account customer", size="24x36", color="B/W", unit="each", price="2.00",
  source="S147-p03", mark="printed", equipment=EQ_LFB, keywords=KW_LFB)
P("lf-bw-30x42-walkin", family="lf-bw-30x42", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="walk-in (no account)", size="30x42", color="B/W", unit="each", price="3.50",
  status="pending", cards="C02", source="S147-p03", mark="pencil", equipment=EQ_LFB, keywords=KW_LFB,
  notes="p03: $3.25 struck, pencil 3.50. p01 (older): $3.25.")
P("lf-bw-30x42-account", family="lf-bw-30x42", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="account customer", size="30x42", color="B/W", unit="each", price="3.00",
  source="S147-p03", mark="printed", equipment=EQ_LFB, keywords=KW_LFB,
  notes="Line through $3.00 is the table grid line, not a strike.")
P("lf-bw-36x48-walkin", family="lf-bw-36x48", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="walk-in (no account)", size="36x48", color="B/W", unit="each", price="5.00",
  source="S147-p03", mark="printed", equipment=EQ_LFB, keywords=KW_LFB)
P("lf-bw-36x48-account", family="lf-bw-36x48", category="Large Format - B/W", item="Large format B/W copy/print",
  variant="account customer", size="36x48", color="B/W", unit="each", price="4.50",
  source="S147-p03", mark="printed", equipment=EQ_LFB, keywords=KW_LFB)
P("lf-bw-other-sqft", category="Large Format - B/W", item="Large format B/W, other sizes",
  variant="non-standard size", color="B/W", unit="sq ft", price="1.25", status="pending",
  cards="C03", source="S147-p03", mark="printed", equipment=EQ_LFB, keywords=KW_LFB + ", custom size",
  notes="p03 says per sq ft; p01 (older) says per linear foot.")
P("lf-bw-other-linft", category="Large Format - B/W", item="Large format B/W, other sizes",
  variant="non-standard size (older sheet rule)", color="B/W", unit="linear ft", price="1.25",
  status="superseded", cards="C03", source="S147-p01", mark="printed", equipment=EQ_LFB, keywords=KW_LFB,
  notes="Older LF sheet. Loses to p03 per-sq-ft rule unless C03 says otherwise.")

# ------------------------------------------------------------ VELLUM
P("vellum-18x24", category="Large Format - Vellum", item="Copy onto vellum", size="18x24", stock="vellum",
  color="B/W", unit="each", price="3.00", source="S147-p01; S147-p03", mark="printed", equipment=EQ_LFB,
  keywords="vellum, translucent, plans, architectural", notes="Both sheets agree.")
P("vellum-24x36", category="Large Format - Vellum", item="Copy onto vellum", size="24x36", stock="vellum",
  color="B/W", unit="each", price="6.00", source="S147-p01; S147-p03", mark="printed", equipment=EQ_LFB,
  keywords="vellum, translucent, plans, architectural", notes="Both sheets agree.")
for sz in ("30x42", "36x48"):
    P(f"vellum-{sz}", category="Large Format - Vellum", item="Copy onto vellum", size=sz, stock="vellum",
      color="B/W", unit="each", status="unpriced", cards="C26", source="(gap)", keywords="vellum, plans",
      notes="No price on any sheet.")

# ------------------------------------------------------- LARGE FORMAT COLOR
KW_LFC = "large format color, poster, color plot, wide format, signage print, rendering"
EQ_LFC = "Canon large-format (inferred)"
P("lf-color-18x24", family="lf-color-std", category="Large Format - Color", item="Large format color print",
  variant="standard size", size="18x24", stock="bond", color="Color", unit="each", price="7.95", status="pending",
  cards="C05", source="S147-p01", mark="pen (purple)", equipment=EQ_LFC, keywords=KW_LFC,
  notes="First digit overwritten; 2 of 3 reads say 7.95 (alt 9.95). Stray pen tick above '24'.")
for sz, pr in (("24x36", "12.95"), ("30x42", "15.95"), ("36x48", "19.95")):
    P(f"lf-color-{sz}", family="lf-color-std", category="Large Format - Color", item="Large format color print",
      variant="standard size", size=sz, stock="bond", color="Color", unit="each", price=pr, status="pending",
      cards="C04", source="S147-p01", mark="pen", equipment=EQ_LFC, keywords=KW_LFC,
      notes="Handwritten on older LF sheet. p03 prices LF color by the sq ft instead.")
P("lf-color-bond-sqft", category="Large Format - Color", item="Large format color print, other sizes",
  variant="bond, non-standard size", stock="bond", color="Color", unit="sq ft", price="3.00", status="pending",
  cards="C04", source="S147-p03", mark="printed", equipment=EQ_LFC, keywords=KW_LFC + ", custom size")
P("lf-color-photo-sqft", category="Large Format - Color", item="Large format color print on photo paper",
  variant="photo paper, non-standard size", stock="photo paper", color="Color", unit="sq ft", price="6.00",
  status="pending", cards="C10", source="S147-p03", mark="printed", equipment="Canon PRO-4100S (inferred)",
  keywords=KW_LFC + ", photo, enlargement, custom size")

# ------------------------------------------------------------ SCANNING
KW_SC = "scan, scanning, digitize, pdf, scan to file, scan to email"
P("scan-lf-bw-first", family="scan-lf-bw", category="Scanning", item="Scan to file, large format",
  variant="first page", color="B/W", unit="page", price="10.00", source="S147-p03", mark="printed",
  keywords=KW_SC + ", plans, large format")
P("scan-lf-bw-add", family="scan-lf-bw", category="Scanning", item="Scan to file, large format",
  variant="each following page", color="B/W", unit="page", price="1.00", source="S147-p03", mark="printed",
  keywords=KW_SC + ", plans, large format")
P("scan-lf-color-first", family="scan-lf-color", category="Scanning", item="Scan to file, large format color",
  variant="first page", color="Color", unit="page", price="10.00", source="S147-p03; S147-p01",
  mark="printed (pasted strip)", keywords=KW_SC + ", color scan, large format",
  notes="Same strip pasted on both sheets.")
P("scan-lf-color-add", family="scan-lf-color", category="Scanning", item="Scan to file, large format color",
  variant="each page after first", color="Color", unit="page", price="5.00", source="S147-p03; S147-p01",
  mark="printed (pasted strip)", keywords=KW_SC + ", color scan, large format")
P("scan-lf-extra-save", category="Scanning", item="Scan to file, large format", variant="multiple saves (each extra)",
  unit="each", price="3.00", status="pending", cards="C17", source="S147-p03", mark="printed", keywords=KW_SC)
P("scan-doc-first", family="scan-doc", category="Scanning", item="Scan to file, 8.5x11-11x17 (document feedable)",
  variant="first page (includes 1 CD)", size="8.5x11-11x17", unit="page", price="5.00", source="S147-p03",
  mark="printed", equipment="Versant 180 (pen note on sheet)", keywords=KW_SC + ", document feeder, ADF")
P("scan-doc-add", family="scan-doc", category="Scanning", item="Scan to file, 8.5x11-11x17 (document feedable)",
  variant="each following page", size="8.5x11-11x17", unit="page", price="0.25", source="S147-p03",
  mark="printed", equipment="Versant 180 (pen note on sheet)", keywords=KW_SC + ", document feeder, ADF")
P("scan-doc-extra-save", category="Scanning", item="Scan to file, 8.5x11-11x17", variant="multiple saves (each extra CD)",
  unit="each", price="3.00", status="pending", cards="C17", source="S147-p03", mark="printed", keywords=KW_SC + ", CD")
P("scan-photo-base", family="scan-photo", category="Scanning", item="Scan photographs / non-feedable originals",
  variant="setup", unit="job", price="10.00", source="S147-p03", mark="printed",
  keywords=KW_SC + ", photo scan, photographs, flatbed", notes="Plus $35/hour until job is completed.")
P("scan-photo-hourly", family="scan-photo", category="Scanning", item="Scan photographs / non-feedable originals",
  variant="labor until complete", unit="hour", price="35.00", source="S147-p03", mark="printed",
  keywords=KW_SC + ", photo scan, photographs, flatbed")

# ------------------------------------------------- COMPUTER & FILE SERVICES
KW_FS = "print from file, email, flash drive, usb, camera card, thumb drive, file printing"
P("file-print-no-changes", category="Computer & File Services", item="Print from electronic file",
  variant="1-99 copies, no changes to file", unit="job", price="2.50", price_max="10.00", source="S147-p03",
  mark="printed", keywords=KW_FS, notes="$2.50-$10.00 labor, PLUS copy charge.")
P("file-print-changes-base", family="file-print-changes", category="Computer & File Services",
  item="Print from electronic file", variant="1-99 copies, with changes to file", unit="job", price="2.50",
  source="S147-p03", mark="printed", keywords=KW_FS + ", edits, design changes",
  notes="$2.50 & $15 min / $75 per hour, PLUS copy charge.")
P("file-print-changes-hourly", family="file-print-changes", category="Computer & File Services",
  item="Print from electronic file", variant="file changes, labor", unit="hour", price="75.00", min_charge="15.00",
  source="S147-p03", mark="printed", keywords=KW_FS + ", edits, design changes")
P("enlarge-reduce", category="Computer & File Services", item="Enlarge / reduce", unit="each", price="1.00",
  source="S147-p03", mark="printed", keywords="enlarge, reduce, resize, scale", notes="Plus copy charge.")
P("self-serve-computer", category="Computer & File Services", item="Self-serve computer", unit="minute",
  price="0.30", source="S147-p03", mark="printed", keywords="computer rental, public computer")
P("self-serve-copies", category="Computer & File Services", item="Self-serve computer copies",
  color="B/W", unit="each", price="0.10", source="S147-p03", mark="printed", keywords="computer printout")
P("media-cd-copy", category="Computer & File Services", item="Copy CD", unit="each", price="5.00",
  source="S147-p03", mark="printed", keywords="CD, disc, duplicate")
P("media-dvd-copy", category="Computer & File Services", item="Copy DVD", unit="each", price="20.00",
  source="S147-p03", mark="printed", keywords="DVD, disc, duplicate")

# ------------------------------------------------------------ PHOTO PRINTS
KW_PH = "photo, photograph, picture, enlargement, print, glossy, luster, matte"
EQ_PH = "Canon PRO-4100S (inferred)"
new_photo = [("4x6", "1.99"), ("5x7", "2.99"), ("8x10", "5.99"), ("11x14", "12.99"), ("12x18", "14.99"),
             ("16x20", "16.99"), ("16x24", "18.99"), ("18x24", "19.99"), ("20x30", "25.00"),
             ("24x30", "30.00"), ("24x36", "36.00")]
old_diff = {"12x18": "12.99", "18x24": "18.99", "24x36": "36.99"}
for sz, pr in new_photo:
    conflict = sz in old_diff
    P(f"photo-{sz}", family="photo", category="Photo Prints", item="Photo print", size=sz, stock="photo paper",
      color="Color", unit="each", price=pr, status="pending" if conflict else "active",
      cards="C08" if conflict else "", source="S147-p09; S147-p14", mark="printed", equipment=EQ_PH,
      keywords=KW_PH, notes=f"Older photo sheet: ${old_diff[sz]}." if conflict else "")
    if conflict:
        P(f"photo-{sz}-oldsheet", category="Photo Prints", item="Photo print (older sheet price)", size=sz,
          stock="photo paper", color="Color", unit="each", price=old_diff[sz], status="superseded", cards="C08",
          source="S147-p10", mark="printed", equipment=EQ_PH, keywords=KW_PH)
for sz, pr in (("8.5x11", "5.99"), ("10x14", "11.99"), ("11x17", "11.99"), ("36x48", "72.99")):
    P(f"photo-{sz}", family="photo", category="Photo Prints", item="Photo print", size=sz, stock="photo paper",
      color="Color", unit="each", price=pr, status="pending", cards="C09", source="S147-p10", mark="printed",
      equipment=EQ_PH, keywords=KW_PH, notes="Only on the older photo sheet (upside-down scan).")
P("photo-touchup", category="Photo Prints", item="Photo touch-up / color correction", unit="photo", price="10.00",
  source="S147-p09; S147-p14", mark="printed", keywords="retouch, color correction, fix photo, lighting",
  notes="Older sheet lists resize / crop-stretch / lighting-resolution correction as 'additional charges' (unpriced).")
P("photo-cropping", category="Photo Prints", item="Photo cropping", unit="photo", price="5.00",
  source="S147-p14", mark="pen (purple)", keywords="crop, cropping, photo")

# ------------------------------------------------------------ LABELS
KW_LB = "labels, address labels, return address, Avery 5160, mailing labels, stickers"
new_lab = {"120": ("17.56", "20.60", 4), "250": ("25.76", "32.59", 9), "500": ("37.23", "49.37", 16),
           "1000": ("54.99", "80.80", 34)}
old_lab = {"120": ("15.96", "18.72"), "250": ("23.41", "29.62"), "500": ("33.84", "44.88"), "1000": ("49.99", "73.45")}
for q, (bk, co, sh) in new_lab.items():
    for ink, pr, opr in (("Black ink", bk, old_lab[q][0]), ("Color ink", co, old_lab[q][1])):
        tag = "black" if ink.startswith("Black") else "color"
        P(f"labels-5160-{tag}-{q}", family=f"labels-5160-{tag}", category="Labels", item="Printed labels, Avery 5160",
          variant=f"{q} labels ({sh} sheets), includes type/set-up", size="1x2.625", stock="Avery 5160 white",
          color=ink, qty_min=q, qty_max=q, unit="lot", price=pr, status="pending", cards="C07",
          source="S147-p11", mark="printed", turnaround="same or next day", keywords=KW_LB,
          notes=f"Older label sheet: ${opr}. Prices do not include sales tax.")
        P(f"labels-5160-{tag}-{q}-oldsheet", category="Labels", item="Printed labels, Avery 5160 (older sheet price)",
          variant=f"{q} labels ({sh} sheets)", color=ink, qty_min=q, qty_max=q, unit="lot", price=opr,
          status="superseded", cards="C07", source="S147-p02", mark="printed", keywords=KW_LB)
P("labels-clear-stock", category="Labels", item="Label add-on: clear label stock", unit="sheet", price="1.50",
  status="pending", cards="C07", source="S147-p11", mark="printed", keywords=KW_LB + ", clear, transparent",
  notes="Older label sheet: $1.00/sheet.")
P("labels-clear-stock-oldsheet", category="Labels", item="Label add-on: clear label stock (older sheet price)",
  unit="sheet", price="1.00", status="superseded", cards="C07", source="S147-p02", mark="printed", keywords=KW_LB)
P("labels-logo", category="Labels", item="Label add-on: add a logo", unit="job", price="5.00",
  source="S147-p11; S147-p02", mark="printed", keywords=KW_LB + ", logo", notes="Both sheets agree.")
P("labels-other-template", category="Labels", item="Label add-on: any other Avery template", unit="job",
  price="10.00", source="S147-p11; S147-p02", mark="printed", keywords=KW_LB + ", other Avery sizes",
  notes="Both sheets agree.")
P("labels-artwork", category="Labels", item="Label add-on: misc. artwork", unit="job", price_max="",
  source="S147-p11; S147-p02", mark="printed", keywords=KW_LB + ", artwork, design",
  notes="Estimate (no fixed price).")

# ------------------------------------------------------------ BUSINESS CARDS
KW_BC = "business cards, cards, calling cards"
for q, pr in (("100", "49.99"), ("250", "59.99"), ("500", "89.99"), ("1000", "99.99")):
    P(f"bc-4over-{q}", family="bc-4over", category="Business Cards", item="Business cards, outsourced (4over)",
      variant="1 or 2 sides; 14pt or 16pt gloss/matte cover or 14pt uncoated", size="2x3.5",
      stock="14pt/16pt cover", color="Color", qty_min=q, qty_max=q, unit="lot", price=pr, fulfillment="4over",
      turnaround="approx. 1 week", source="S147-p07 (= p13)", mark="printed", keywords=KW_BC + ", 4over, premium, thick",
      notes="Artwork/layout extra. Art 1-up with crop marks and bleeds. Other sizes: special quote.")
for q, s1, s2 in (("100", "34.40", "47.30"), ("200", "46.30", "58.10"), ("250", "52.25", "67.00"), ("500", "82.00", "99.00")):
    P(f"bc-inhouse-1s-{q}", family="bc-inhouse-1s", category="Business Cards", item="Business cards, in-house",
      variant="1-sided, 80# cover, 10-up", size="2x3.5", stock="80# cover (any in stock)", sides="1",
      qty_min=q, qty_max=q, unit="lot", price=s1, turnaround="same day or 1 day", source="S147-p07 (= p13)",
      mark="printed", equipment="Versant 180 (inferred)", keywords=KW_BC + ", in house, same day")
    P(f"bc-inhouse-2s-{q}", family="bc-inhouse-2s", category="Business Cards", item="Business cards, in-house",
      variant="2-sided, 80# cover, 10-up (2-sided not recommended)", size="2x3.5", stock="80# cover (any in stock)",
      sides="2", qty_min=q, qty_max=q, unit="lot", price=s2, turnaround="same day or 1 day",
      source="S147-p07 (= p13)", mark="printed", equipment="Versant 180 (inferred)", keywords=KW_BC + ", in house, same day")
P("bc-inhouse-bleed-cutting", category="Business Cards", item="Business cards, in-house: bleed surcharge",
  variant="bleeds = 8-up, yields 20% fewer cards", unit="job", price="5.00", source="S147-p07 (= p13)",
  mark="printed", keywords=KW_BC + ", bleed, full bleed, cutting",
  notes="With bleeds the layout is 8-up instead of 10-up: 20% less quantity, plus $5.00 cutting.")

# ------------------------------------------- TRADE SHEET (NCR / ENVELOPES / INKS)
MULT = 2.5
from decimal import Decimal, ROUND_HALF_UP
def trade(id, listed, **kw):
    kw.setdefault("status", "pending")
    kw.setdefault("cards", "C11")
    kw.setdefault("fulfillment", "trade (outside printer)")
    kw.setdefault("source", "S147-p12")
    kw.setdefault("mark", "printed; 'Multiply x2.5' in pen")
    note = kw.pop("notes", "")
    P(id, price=(Decimal(listed) * Decimal("2.5")).quantize(Decimal("0.01"), ROUND_HALF_UP), cost=listed,
      notes=(f"Trade sheet lists ${float(listed):.2f}; price = x2.5 per handwritten note. " + note).strip(), **kw)
ncr = {
 "8.5x11": {"2-part": ["39.60", "52.80", "85.80", "151.80", "117.48"], "3-part": ["51.48", "72.60", "125.40", "225.24", "183.48"],
            "4-part": ["63.36", "93.72", "163.68", "302.28", "249.48"], "2nd side": ["34.00", "41.29", "66.76", "126.76", "186.29"]},
 "8.5x14": {"2-part": ["42.24", "56.76", "87.12", "167.64", "133.32"], "3-part": ["55.44", "79.20", "137.28", "253.38", "208.56"],
            "4-part": ["69.96", "101.64", "183.62", "343.20", "286.44"], "2nd side": ["34.00", "41.29", "66.76", "126.76", "186.29"]},
}
QTYS = ["125", "250", "500", "1000", "addl-1000"]
for sz, cols in ncr.items():
    for part, vals in cols.items():
        pslug = part.replace(" ", "")
        for q, v in zip(QTYS, vals):
            qm = "" if q == "addl-1000" else q
            extra = {}
            if q == "addl-1000":
                extra = dict(cards="C11 C12", notes="Row labelled '2ND 1000' on sheet.")
            trade(f"ncr-{sz}-{pslug}-{q}", v, family=f"ncr-{sz}-{pslug}", category="NCR Forms",
                  item="NCR (carbonless) forms", variant=(f"{part} sets" if part != "2nd side" else "printing on 2nd side (add-on)")
                  + (" - each additional 1,000 ('2ND 1000')" if q == "addl-1000" else ""),
                  size=sz, stock="NCR carbonless", qty_min=qm or "1000", qty_max=qm, unit="lot",
                  keywords="NCR, carbonless, invoice, receipt book, work order, multi-part, forms", **extra)
env = {"wove": ("Wove #6-3/4, #9, #10 regular", ["38.50", "49.61", "70.18", "52.03"]),
       "laid": ("Cotton / laid parchment #10, A-2, A-6", ["49.50", "67.10", "106.70", "90.75"]),
       "linen": ("Linen - Beckett, Classic, Strathmore", ["55.00", "74.80", "125.40", "106.48"]),
       "white-catalog": ("White 9x12, 10x13 catalog / booklet", ["77.00", "98.95", "143.99", "123.42"])}
for slug, (desc, vals) in env.items():
    for q, v in zip(["250", "500", "1000", "addl-1000"], vals):
        qm = "" if q == "addl-1000" else q
        extra = dict(cards="C11 C12", notes="Row labelled '2ND 1000' on sheet.") if q == "addl-1000" else {}
        trade(f"env-{slug}-{q}", v, family=f"env-{slug}", category="Envelopes", item="Printed envelopes",
              variant=desc + (" - each additional 1,000 ('2ND 1000')" if q == "addl-1000" else ""),
              stock=desc, qty_min=qm or "1000", qty_max=qm, unit="lot",
              keywords="envelopes, printed envelopes, #10, return address, catalog envelope", **extra)
for q, a, b, c in (("250", "27.00", "59.99", "74.99"), ("500", "29.99", "66.99", "80.99"),
                   ("1000", "49.99", "84.99", "94.99"), ("addl-1000", "89.99", "140.00", "150.00")):
    qm = "" if q == "addl-1000" else q
    for slug, desc, v in (("1s-1ink", "1 side, black or blue ink", a), ("2s-black-1std", "2 sided, black + 1 std ink", b),
                          ("2color", "2 color, 2 std inks", c)):
        trade(f"bc-trade-{slug}-{q}", v, family=f"bc-trade-{slug}", category="Business Cards",
              item="Business cards, trade sheet (offset)", variant=desc + (" - '2ND 1000' row" if q == "addl-1000" else ""),
              size="2x3.5", qty_min=qm or "1000", qty_max=qm, unit="lot", status="superseded",
              cards="C11 C12" if q == "addl-1000" else "C11",
              keywords=KW_BC + ", offset, raised, thermography")
for slug, desc, v, unit in (("standard", "Standard ink charge", "15.00", "job"), ("pms", "PMS ink charge", "40.00", "job"),
                            ("metallic", "Metallic ink charge", "50.00", "job"),
                            ("close-reg", "Close registration charge", "20.00", "per 1000")):
    trade(f"ink-{slug}", v, category="Special Inks", item=desc, variant="add-on (trade sheet)", unit=unit,
          keywords="special ink, PMS, spot color, metallic, registration, offset")
P("ink-hairline-reg", category="Special Inks", item="Hairline registration charge", variant="add-on (trade sheet)",
  unit="job", status="retired", fulfillment="trade (outside printer)", source="S147-p12", mark="printed",
  notes="Sheet says N/A (not offered).")

# ------------------------------------------------------------ BINDERY
KW_BI = "bindery, finishing"
def B(id, item, price, unit, **kw):
    kw.setdefault("source", "S147-p04"); kw.setdefault("mark", "printed")
    kw["keywords"] = (KW_BI + ", " + kw.get("keywords", "")).strip(", ")
    P(id, category=kw.pop("category", "Bindery & Finishing"), item=item, price=price, unit=unit, **kw)
B("cutting", "Cutting", "1.00", "cut", keywords="cut, trim, guillotine")
B("padding-base", "Padding", "5.00", "job", family="padding", min_charge="10.00", variant="base",
  keywords="pads, notepads, padding compound", notes="$5.00 base plus $0.50 per pad; $10.00 minimum.")
B("padding-per-pad", "Padding", "0.50", "pad", family="padding", variant="per pad", keywords="pads, notepads")
B("numbering-per-1000", "Numbering", "50.00", "per 1000", family="numbering", variant="numbering machine (per 1,000)",
  status="pending", cards="C15", keywords="numbering, sequential numbers, tickets, raffle")
B("numbering-per-page", "Numbering", "0.03", "page", family="numbering", variant="copy cost plus $0.03 per page",
  status="pending", cards="C15", keywords="numbering, sequential numbers, variable data, tickets, raffle",
  notes="Plus copy cost.")
B("folding-per-1000", "Folding", "25.00", "per 1000", min_charge="15.00", keywords="fold, tri-fold, bi-fold, letter fold")
B("scoring-per-1000", "Scoring", "50.00", "per 1000", family="scoring", min_charge="35.00", status="pending",
  cards="C14", keywords="score, crease")
B("scoring-per-500", "Scoring", "30.00", "per 500", family="scoring", min_charge="35.00", status="pending",
  cards="C14", keywords="score, crease", notes="Minimum ($35) is higher than the 500 price ($30).")
B("perfing-per-1000", "Perfing", "50.00", "per 1000", family="perfing", min_charge="20.00", keywords="perforate, perf, tear-off")
B("perfing-per-500", "Perfing", "30.00", "per 500", family="perfing", min_charge="20.00", keywords="perforate, perf, tear-off")
B("drilling", "Drilling", "1.00", "hole", variant="per hole, up to 2 in. thick", keywords="drill, hole punch, 3-hole")
B("sorting-manual", "Sorting (manual)", "0.05", "page", keywords="collate, collating, sort")
B("stapling-manual", "Stapling (manual)", "0.05", "staple", keywords="staple, stapling")
B("comb-half-inch", "Spiral binding (Ibico comb)", "1.50", "book", family="comb", variant="1/2 in. book",
  keywords="comb binding, plastic comb, GBC, ibico, bind, spiral", notes="Plus $0.69 per cover. 1 standard book with covers = $2.88.")
B("comb-one-inch", "Spiral binding (Ibico comb)", "2.00", "book", family="comb", variant="1 in. book",
  keywords="comb binding, plastic comb, ibico, bind")
B("comb-add-half-inch", "Spiral binding (Ibico comb)", "0.50", "each", family="comb",
  variant="each additional 1/2 in.", keywords="comb binding, ibico, bind")
B("comb-cover", "Spiral binding (Ibico comb)", "0.69", "cover", family="comb", variant="cover (each)",
  keywords="comb binding, clear cover, vinyl cover, back cover")
B("coil-half-inch", "Coil binding", "3.50", "book", family="coil", variant="1/2 in. book",
  keywords="coil, spiral, plastic coil, bind", notes="Plus $0.69 per cover. 1 standard book with covers = $4.88.")
B("coil-add-half-inch", "Coil binding", "0.50", "each", family="coil", variant="each additional 1/2 in.",
  keywords="coil, spiral, bind")
B("coil-cover", "Coil binding", "0.69", "cover", family="coil", variant="cover (each)", keywords="coil, cover")
B("shrink-wrap", "Shrink wrapping", "1.00", "per 500", variant="per 500 sheets", keywords="shrink wrap, package")
B("booklet-making", "Booklet making (by machine)", "0.50", "book", keywords="booklet, saddle stitch, fold and staple")
B("corner-round-per-1000", "Corner rounding (4 sides)", "20.00", "per 1000", family="corner-round", min_charge="5.00",
  keywords="round corners, corner rounder")
B("corner-round-per-500", "Corner rounding (4 sides)", "15.00", "per 500", family="corner-round", min_charge="5.00",
  keywords="round corners, corner rounder")
B("mounting", "Mounting", "10.00", "piece", variant="per piece, board not included", keywords="mount, foam board, gatorboard")
for sz, pr, mark, note in (("card", "1.50", "printed", "'.75' struck; 1.50 printed beside it."),
                           ("8.5x11", "2.00", "pencil", "1.50 struck; pencil 2.00."),
                           ("8.5x14", "3.00", "pencil", "2.50 struck; pencil 3.00."),
                           ("11x17", "4.00", "pen", "3.00 struck; pencil value scribbled out; pen 4.00.")):
    B(f"laminate-{sz}", "Laminating", pr, "each", category="Laminating", family="laminate", size="" if sz == "card" else sz,
      variant="card size" if sz == "card" else "", mark=mark, status="pending", cards="C13",
      keywords="laminate, lamination, laminating, pouch", notes=note)
B("laminate-24in-sqft", "Laminating, 24 in. wide", "2.95", "sq ft", category="Laminating", family="laminate",
  variant="24 in. roll", keywords="laminate, lamination, roll laminate, poster")
B("labor-hourly", "Labor", "35.00", "hour", category="Labor & Design", keywords="labor, shop time, hourly")
B("graphic-services", "Graphic services / design", "75.00", "hour", category="Labor & Design",
  keywords="design, layout, artwork, typesetting, graphic design", notes="Get an estimate.")

# ------------------------------------------------------------ SIGNAGE (4over)
KW_SG = "signs, signage, 4over, outdoor"
for id, item, variant, pr, extra in (
    ("banner-13oz", "Vinyl banner", "13 oz scrim vinyl (waterproof, durable)", "4.00", "banner, vinyl banner"),
    ("banner-8oz-mesh", "Vinyl banner", "8 oz mesh vinyl (economical, light)", "4.00", "banner, mesh banner, fence banner"),
    ("foam-core", "Foam core print", "", "11.50", "foam board, foamcore, mounted print"),
    ("coroplast-4mm", "Coroplast sign", "4 mm (waterproof, lightweight, traditional yard sign)", "8.00",
     "yard sign, coroplast, corrugated plastic, lawn sign"),
    ("coroplast-10mm", "Coroplast sign", "10 mm (heavy duty, weather resistant)", "8.00",
     "yard sign, coroplast, corrugated plastic, heavy duty"),
    ("aluminum-sandwich", "Aluminum sandwich board (ACM)", "two aluminum sheets, polyethylene core, 1/8 in. (3 mm)", "24.00",
     "aluminum sign, ACM, dibond, metal sign"),
    ("car-magnet", "Car magnet", "", "20.00", "magnet, vehicle magnet, car sign")):
    P(id, category="Signs & Banners (4over)", item=item, variant=variant, unit="sq ft", price=pr, fulfillment="4over",
      turnaround="approx. 1 week", status="pending", cards="C16", source="S147-p08", mark="printed",
      keywords=KW_SG + ", " + extra, notes="Artwork/layout extra." + (" Same price as 4 mm." if id == "coroplast-10mm" else ""))

# ------------------------------------------------------------ PENS & MARKERS
BRANDS = [("bic", "BIC"), ("client", "Pentel"), ("energel", "Pentel"), ("energize", "Pentel"), ("ergotwist", "Pentel"),
          ("expo", "Expo"), ("flexgrip", "Paper Mate"), ("frixion", "Pilot"), ("gelly", "Sakura"), ("hi-liter", "Avery"),
          ("icy pentel", "Pentel"), ("itoya", "Itoya"), ("jetstream", "Uni-ball"), ("liquid expo", "Expo"),
          ("liquid expresso", "Paper Mate"), ("marks-a-lot", "Avery"), ("marvy", "Marvy Uchida"), ("meanstreak", "Sharpie"),
          ("papermate", "Paper Mate"), ("pentel", "Pentel"), ("pilot", "Pilot"), ("precise", "Pilot"), ("sakura", "Sakura"),
          ("sanford", "Sanford"), ("sharpie", "Sharpie"), ("super sharpie", "Sharpie"), ("uni power", "Uni-ball"),
          ("uniball", "Uni-ball"), ("vis", "Expo"), ("zarasa", "Zebra"), ("zebra", "Zebra")]
def brand_of(item):
    s = item.lower()
    best = ""
    for k, b in BRANDS:
        if s.startswith(k) and len(k) > len(best):
            best, bb = k, b
    return bb if best else ""
def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower().replace("à", "a"))).strip("-")
def num(v):
    v = v.strip().replace(",", ".")
    if re.fullmatch(r"\d{3}", v):           # '349' -> 3.49
        v = v[0] + "." + v[1:]
    if re.fullmatch(r"\d{2}", v):           # '95' -> .95
        v = "." + v
    return f"{float(v):.2f}"

pens = json.load(open(os.path.join(HERE, "transcriptions", "pens_A.json")))
VERIFY = {  # (col,seq): note   -> card C18
    ("L", 35): "Red over black 'Elite: 2.33'. Read as 1.99 (alt 1.89 / 1.39). 'Elite' suggests the item is now Profile Elite.",
    ("R", 26): "Red read as 3.69 (alt 2.69).",
    ("R", 32): "Red read as 4.39 (alt 4.59).",
    ("R", 10): "No red update. Printed price blacked out; black marker 2.89 in the next cell.",
}
RETIRE = {("L", 5), ("L", 10), ("L", 41), ("R", 11)}  # card C20
NO_UPDATE = []
KW_PEN = "pens, markers, highlighters, pencils, retail, office supply, writing"
for r in pens["rows"]:
    key = (r["col"], r["seq"])
    item, sku = r["item"].strip(), r["sku"].strip()
    if item.startswith("Sanford Uniball Gel Impact"):
        item = "Sanford Uniball Gel Impact (silver)"
    base = "pen-" + slug(item + ("-" + sku if sku else ""))
    hws = [h for h in r["handwritten"] if not h["struck"]]
    red = [h for h in hws if h["ink"] == "red" and h["applies_to"] in ("each", "unclear")]
    other = [h for h in hws if h["ink"] != "red" and h["applies_to"] in ("each", "unclear")
             and re.fullmatch(r"[\d.,]+", h["value"].strip())]
    printed = "" if r["each_struck"] else r["printed_each"].strip()
    status, cards, notes, mark = "active", "", [], "printed"
    if red:
        price, mark = num(red[-1]["value"]), "red pen"
    elif other:
        price, mark = num(other[-1]["value"]), other[-1]["ink"] + " pen"
    elif printed:
        price = num(printed)
    else:
        price = ""
    if key == ("L", 31):
        r["printed_each"] = "1.35"   # verifier + transcriber B: 1.35 (A read 1.33); struck either way
    if r["printed_each"].strip() and (red or other):
        notes.append(f"Printed {r['printed_each'].strip()}" + (" (struck)" if r["each_struck"] else "") + ".")
    if key in VERIFY:
        status, cards = "pending", "C18"; notes.append(VERIFY[key])
    if key in RETIRE:
        status, cards = "pending", "C20"
        notes.append(f"Struck on the current sheet with no new price (printed {r['printed_each'].strip()}).")
    if not red and not other and key not in RETIRE and key not in VERIFY:
        status, cards = "pending", "C21"; notes.append("No red-pen update on the current sheet.")
        NO_UPDATE.append(item + (f" {sku}" if sku else ""))
    if key == ("L", 35):
        notes.append("Black note 'Elite: 2.33' also on the row.")
    P(base, family=base, category="Pens & Markers", item=item, brand=brand_of(item), sku=sku, unit="each",
      price=price, fulfillment="retail stock", status=status if price or key in RETIRE else "unpriced",
      cards=cards, source=f"S147-p06 row {r['col']}{r['seq']}", mark=mark, keywords=KW_PEN,
      notes=" ".join(notes))
    box = r["printed_box"].strip()
    box_hw = [h for h in hws if h["applies_to"] == "box"]
    if r["row_struck"] or (r["box_struck"] and not box_hw):
        box = ""   # struck with the row (e.g. Bic Widebody): no box price
    if box or box_hw:
        bprice = num(box_hw[-1]["value"]) if box_hw else num(box)
        P(base + "-box", family=base, category="Pens & Markers", item=item, variant="box / dozen (2nd column)",
          brand=brand_of(item), sku=sku, unit="box", price=bprice, fulfillment="retail stock",
          status="pending", cards="C22" + (" C20" if key in RETIRE else ""), source=f"S147-p06 row {r['col']}{r['seq']}",
          mark="black pen" if box_hw else "printed", keywords=KW_PEN + ", box, dozen",
          notes=("Printed " + box + " struck. " if box_hw else "") +
                "Second price column; never updated when single prices went up.")
# loose handwritten notes -> new items (card C19)
for id, item, pr, note in (
    ("pen-bic-velocity", "Bic Velocity (pen)", "1.75", "Note 'Bic Velocity' above the table with red 1.75; model not given."),
    ("pen-pentel-energel-margin", "Pentel Energel (model not given)", "3.49",
     "Sideways margin note 'Pentel/Energel 3.49'. The Energel Liquid Ink BL57A row is 3.75 in red."),
    ("pen-pentel-twist-erase-express", "Pentel Twist-Erase Express", "2.09",
     "Pencil note under the table; also 'Pentel Twist Erase ... 2.09' at the top edge. Replaces struck QE107A?"),
    ("pen-pentel-twist-erase-gt", "Pentel Twist-Erase GT", "2.66", "Pencil note under the table ('266', decimal not visible)."),
    ("pen-pilot-g-tec", "Pilot G-Tec pen", "2.64", "Note under right table: 'Pilot G Tec Pen 2.64 ea'.")):
    P(id, family=id, category="Pens & Markers", item=item, brand=brand_of(item) or item.split()[0], unit="each",
      price=pr, fulfillment="retail stock", status="pending", cards="C19", source="S147-p06 (handwritten note)",
      mark="handwritten", keywords=KW_PEN, notes=note)

# ------------------------------------------------------------ WRITE
os.makedirs(DATA, exist_ok=True)
with open(os.path.join(DATA, "prices.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(ROWS)
json.dump(NO_UPDATE, open(os.path.join(HERE, "transcriptions", "pens_no_update.json"), "w"), indent=1)
print(f"wrote {len(ROWS)} price rows; {len(NO_UPDATE)} pens without red update")
