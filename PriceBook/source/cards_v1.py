#!/usr/bin/env python3
"""
cards_v1.py - builds data/conflicts.json (conflict sheet v1) and the evidence
crops in source/crops/ from the 300 dpi page images (source/pages/, extracted
with `pdfimages -png`). One-time import script, kept for audit.

Card kinds:  conflict | verify | question | gap
Line fields: key, label, target (price id or ""), proposed (str or null),
             rule, allow_remove (bool)
Option cards: options = [label, ...], proposed_option = index or null
"""
import csv, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGES = os.path.join(HERE, "pages")
CROPS = os.path.join(HERE, "crops")
os.makedirs(CROPS, exist_ok=True)

_cache = {}
def page(name, rot=0):
    k = (name, rot)
    if k not in _cache:
        im = Image.open(os.path.join(PAGES, name + ".png")).convert("RGB")
        if rot:
            im = im.rotate(rot, expand=True)
        _cache[k] = im
    return _cache[k]

def crop(fname, pg, box, rot=0, post_rot=0, maxw=1800):
    fname = os.path.splitext(fname)[0] + ".jpg"
    out = os.path.join(CROPS, fname)
    im = page(pg, rot).crop(box)
    if post_rot:
        im = im.rotate(post_rot, expand=True)
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(out, "JPEG", quality=82, optimize=True)
    return fname

PENS = "s147-005"
def pen_row(fname, col, seq, rows=1):
    y0 = 140 + 60 * (seq - 1) - 14
    x0, x1 = (0, 1340) if col == "L" else (1250, 2550)
    return crop(fname, PENS, (x0, y0, x1, y0 + 60 * rows + 28))

prices = {r["id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "prices.csv"), encoding="utf-8"))}
def L(key, label, target="", proposed=None, rule="", allow_remove=False):
    if target:
        assert target in prices, target
    return dict(key=key, label=label, target=target, proposed=proposed, rule=rule, allow_remove=allow_remove)

# shared crops
crop("p03_lf_tables.png", "s147-002", (0, 2480, 2250, 2900))
crop("p01_lf_block.png", "s147-000", (2700, 1150, 5000, 2750))
crop("p01_2436.png", "s147-000", (2700, 1180, 5000, 1560))
crop("p01_3042.png", "s147-000", (2700, 1720, 5000, 2010))
crop("p01_1824.png", "s147-000", (2700, 2060, 5000, 2400))
crop("p01_3648_linft.png", "s147-000", (2700, 2540, 5000, 3250))
crop("p03_bw_8511.png", "s147-002", (700, 1760, 2250, 2140))
crop("p02_labels_old.png", "s147-001", (200, 700, 2200, 2250))
crop("p11_labels_new.png", "s147-010", (100, 1250, 2300, 2900))
crop("p09_photo_new.png", "s147-008", (150, 1150, 2100, 2650))
crop("p10_photo_old.png", "s147-009", (300, 1100, 2450, 2800), rot=180)
crop("p12_trade_all.png", "s147-011", (250, 450, 3300, 2350), rot=90, maxw=2400)
crop("p12_trade_top.png", "s147-011", (250, 450, 3300, 1450), rot=90, maxw=2400)
crop("p04_lam.png", "s147-003", (550, 2100, 2000, 2450))
crop("p04_num_fold_score_perf.png", "s147-003", (550, 540, 2150, 1200))
crop("p08_signs.png", "s147-007", (0, 1150, 2400, 2700))
crop("p03_scan.png", "s147-002", (0, 780, 2250, 1400))
crop("p15_reno.png", "s147-014", (230, 830, 1050, 940))
crop("p15_essendant_reno.png", "s147-014", (1170, 1600, 2074, 1975))   # stops above the Carton Source login line
crop("p15_spr.png", "s147-014", (1170, 2185, 2074, 2450))
crop("p17_inland.png", "s147-016", (1170, 1110, 2160, 1800))
crop("pens_top.png", PENS, (0, 0, 2550, 230))
crop("pens_bottom.png", PENS, (0, 3060, 2550, 3300))
crop("pens_margin.png", PENS, (0, 1150, 210, 2500), post_rot=-90)
pen_row("pen_profile.png", "L", 35)
pen_row("pen_twin.png", "R", 26)
pen_row("pen_deluxe.png", "R", 32)
pen_row("pen_sakura.png", "R", 10)
pen_row("pen_struck_widebody.png", "L", 5)
pen_row("pen_struck_ergotwist.png", "L", 10)
pen_row("pen_struck_twisterase.png", "L", 41)
pen_row("pen_struck_calligraphy.png", "R", 11)
pen_row("pen_box_sample.png", "L", 1, rows=4)

no_update = json.load(open(os.path.join(HERE, "transcriptions", "pens_no_update.json")))
nu_lines = []
for pid, r in prices.items():
    if r["category"] == "Pens & Markers" and r["unit"] == "each" and "C21" in r["cards"].split():
        nu_lines.append(f"{r['item']} {r['sku']}".strip() + f"  ${r['price']}")

cards = [
 dict(id="C01", section="Large Format", kind="conflict", title="B/W 24x36, walk-in price",
      context=["Copy-services sheet (p3): no-account $2.50 is struck in blue, nothing written in. Account price $2.00.",
               "Older Large Format sheet (p1): 24x36 $2.50, with 'B/W' written in pen."],
      crops=[("p03_lf_tables.png", "Copy-services sheet p3, large format tables"), ("p01_2436.png", "Older LF sheet p1")],
      lines=[L("a", "24x36 B/W, walk-in (no account)", "lf-bw-24x36-walkin", None, "R4: struck, nothing written in")]),
 dict(id="C02", section="Large Format", kind="conflict", title="B/W 30x42, walk-in price",
      context=["p3: $3.25 struck, '350' in pencil beside it.", "Older LF sheet p1: $3.25."],
      crops=[("p03_lf_tables.png", "p3"), ("p01_3042.png", "p1")],
      lines=[L("a", "30x42 B/W, walk-in (no account)", "lf-bw-30x42-walkin", "3.50", "R1: pencil beats print")]),
 dict(id="C03", section="Large Format", kind="conflict", title="B/W large format, other sizes: per sq ft or per linear ft?",
      context=["p3 (newer): '$1.25 per sq ft otherwise on B/W large format'.",
               "p1 (older LF sheet): 'Otherwise ... charged at $1.25 per linear foot'.",
               "At 36 in. wide, 1 linear ft = 3 sq ft, so the per-sq-ft rule costs 3x as much."],
      crops=[("p03_lf_tables.png", "p3"), ("p01_3648_linft.png", "p1")],
      options=["$1.25 per sq ft (p3)", "$1.25 per linear foot (p1)", "Other: ____________________"], proposed_option=0,
      rule="R3: newer sheet wins", targets=["lf-bw-other-sqft", "lf-bw-other-linft"]),
 dict(id="C04", section="Large Format", kind="conflict", title="Color large format: flat prices vs. per sq ft",
      context=["p1 has flat color prices handwritten in pen: 24x36 $12.95, 30x42 $15.95, 36x48 $19.95 (18x24 see C05).",
               "p3 prices color by area: bond $3/sq ft, photo $6/sq ft. At $3/sq ft: 24x36 = $18.00, 30x42 = $26.25, 36x48 = $36.00.",
               "Proposal: pen prices for the standard sizes; $3/sq ft bond only for non-standard sizes."],
      crops=[("p01_lf_block.png", "p1 with pen color prices"), ("p03_lf_tables.png", "p3")],
      lines=[L("a", "24x36 color (bond)", "lf-color-24x36", "12.95", "R1: pen beats print"),
             L("b", "30x42 color (bond)", "lf-color-30x42", "15.95", "R1"),
             L("c", "36x48 color (bond)", "lf-color-36x48", "19.95", "R1"),
             L("d", "Other sizes, color bond, per sq ft", "lf-color-bond-sqft", "3.00", "only rule for other sizes")]),
 dict(id="C05", section="Large Format", kind="verify", title="Color 18x24: first digit overwritten",
      context=["Purple pen '_.95 Color' over the 18x24 line; the first digit is written over another digit.",
               "Two of three independent reads say 7.95 (the other allows 9.95). Stray pen tick above the '24' in '18 x 24'."],
      crops=[("p01_1824.png", "p1, 18x24 line")],
      options=["$7.95", "$9.95", "Other: $________"], proposed_option=0, rule="R5",
      targets=["lf-color-18x24"]),
 dict(id="C06", section="Copies", kind="conflict", title="B/W 8.5x11 single-sided, 21-99 and 100+",
      context=["Printed .07 (21-99) and .06 or .08 (100+) are struck; the blue replacements are scribbled out.",
               "Duplex (.13 / .11) is unchanged. For reference 8.5x14 single is .09 / .08."],
      crops=[("p03_bw_8511.png", "p3, B/W copies")],
      lines=[L("a", "8.5x11 B/W single, 21-99", "bw-8.5x11-simplex-21-99", None, "R4"),
             L("b", "8.5x11 B/W single, 100 & up", "bw-8.5x11-simplex-100up", None, "R4")]),
 dict(id="C07", section="Labels", kind="conflict", title="Avery 5160 labels: two sheets disagree on every price",
      context=["Newer 'Personal Label Printing' sheet (p11), black / color: 120 $17.56 / $20.60, 250 $25.76 / $32.59, "
               "500 $37.23 / $49.37, 1000 $54.99 / $80.80, clear stock $1.50/sheet.",
               "Older sheet (p2): 120 $15.96 / $18.72, 250 $23.41 / $29.62, 500 $33.84 / $44.88, 1000 $49.99 / $73.45, clear $1.00.",
               "Logo +$5 and other-template +$10 agree on both."],
      crops=[("p11_labels_new.png", "Newer sheet p11"), ("p02_labels_old.png", "Older sheet p2")],
      options=["Newer sheet (p11) prices", "Older sheet (p2) prices", "Other (write on the sheet)"], proposed_option=0,
      rule="R3: newer sheet wins"),
 dict(id="C08", section="Photo Prints", kind="conflict", title="Photo prints: 3 sizes priced differently",
      context=["Newer 'Photo Print Pricing' sheet (p9/p14) vs. older upside-down 'PHOTO PRINTS' sheet (p10)."],
      crops=[("p09_photo_new.png", "Newer p9"), ("p10_photo_old.png", "Older p10")],
      lines=[L("a", "12x18  (older sheet $12.99)", "photo-12x18", "14.99", "R3"),
             L("b", "18x24  (older sheet $18.99)", "photo-18x24", "19.99", "R3"),
             L("c", "24x36  (older sheet $36.99)", "photo-24x36", "36.00", "R3")]),
 dict(id="C09", section="Photo Prints", kind="question", title="Sizes only on the older photo sheet: keep or drop?",
      context=["The newer sheet dropped these sizes. Note 11x17 ($11.99) is cheaper than 11x14 ($12.99) on the newer sheet."],
      crops=[("p10_photo_old.png", "Older p10")],
      lines=[L("a", "8.5x11 photo", "photo-8.5x11", "5.99", "keep at older price", True),
             L("b", "10x14 photo", "photo-10x14", "11.99", "keep", True),
             L("c", "11x17 photo", "photo-11x17", "11.99", "keep", True),
             L("d", "36x48 photo", "photo-36x48", "72.99", "keep", True)]),
 dict(id="C10", section="Photo Prints", kind="question", title="Photo paper on large format: list or $6/sq ft?",
      context=["p3: large format color on photo paper $6/sq ft. The photo list prices the same sizes separately.",
               "$6/sq ft gives 18x24 = $18.00 (list $19.99), 24x36 = $36.00 (list $36.00), 36x48 = $72.00 (older list $72.99)."],
      crops=[("p03_lf_tables.png", "p3")],
      options=["Photo list for listed sizes; $6/sq ft only for custom sizes", "$6/sq ft for everything 11x17 and up",
               "Other: ____________________"], proposed_option=0, rule="more specific price wins",
      targets=["lf-color-photo-sqft"]),
 dict(id="C11", section="Trade Sheet", kind="question", title="Blue trade sheet (NCR, envelopes, bus cards, inks): still live?",
      context=["Handwritten 'Multiply x 2.5' / 'Times 2.5'. Read as trade cost; retail = listed x 2.5.",
               "Example: 250 8.5x11 2-part NCR listed $52.80 -> $132.00. Special inks: PMS $40 -> $100.",
               "Its business-card block (250 1-side $27.00 -> $67.50) clashes with the business-card sheet (in-house $52.25, 4over $59.99).",
               "Proposal: NCR, envelopes and special inks live at x2.5; its business-card block retired."],
      crops=[("p12_trade_all.png", "Blue trade sheet p12")],
      options=["Live at x2.5 (NCR, envelopes, inks); retire its business-card block", "Live, but multiplier is x______",
               "Archive the whole sheet (quote these jobs individually)", "Other: ____________________"], proposed_option=0,
      rule="handwritten note"),
 dict(id="C12", section="Trade Sheet", kind="question", title="What does the '2ND 1000' row mean?",
      context=["Read as 'each additional 1,000'. Fits NCR 2-part (1000 $151.80, 2nd 1000 $117.48) and envelopes.",
               "Does not fit NCR 2nd side (1000 $126.76, 2nd 1000 $186.29) or trade bus cards (1000 $49.99, 2nd 1000 $89.99)."],
      crops=[("p12_trade_top.png", "p12, top half")],
      options=["Each additional 1,000 (as read)", "Price for 2,000 total", "Other: ____________________"], proposed_option=0,
      rule="best reading"),
 dict(id="C13", section="Bindery", kind="verify", title="Laminating: confirm the pencil / pen prices",
      context=["Card: .75 struck, 1.50 beside it. 8.5x11: 1.50 struck, pencil 2.00. 8.5x14: 2.50 struck, pencil 3.00.",
               "11x17: 3.00 struck, a pencil value scribbled out, then 4.00 in pen."],
      crops=[("p04_lam.png", "p4, laminating")],
      lines=[L("a", "Laminate card size", "laminate-card", "1.50", "R2"),
             L("b", "Laminate 8.5x11", "laminate-8.5x11", "2.00", "R1"),
             L("c", "Laminate 8.5x14", "laminate-8.5x14", "3.00", "R1"),
             L("d", "Laminate 11x17", "laminate-11x17", "4.00", "R2")]),
 dict(id="C14", section="Bindery", kind="question", title="Scoring minimum is higher than the 500 price",
      context=["Scoring: $50/1,000, $30/500, $35 minimum. Perfing on the same sheet: $50/1,000, $30/500, $20 minimum."],
      crops=[("p04_num_fold_score_perf.png", "p4")],
      options=["Keep as printed ($35 minimum, so up to 500 = $35)", "Scoring minimum is $______"], proposed_option=0,
      rule="as printed", targets=["scoring-per-1000", "scoring-per-500"]),
 dict(id="C15", section="Bindery", kind="question", title="Numbering: two prices on one line",
      context=["'50.00 per 1,000; copy cost plus .03 per page'."],
      crops=[("p04_num_fold_score_perf.png", "p4")],
      options=["Two methods: numbering machine $50/1,000, or numbers printed on the press = copy cost + $0.03/page",
               "One method: ____________________"], proposed_option=0, rule="best reading",
      targets=["numbering-per-1000", "numbering-per-page"]),
 dict(id="C16", section="Signs & Banners", kind="question", title="4over signage prices current? 10 mm coroplast = 4 mm?",
      context=["All sq-ft prices from the 4-Over sheet. 4 mm and 10 mm coroplast are both $8.00/sq ft (likely a typo).",
               "Mark does the 4over ordering, so he can confirm."],
      crops=[("p08_signs.png", "p8")],
      options=["All current as printed", "Ask Mark to re-check against 4over", "10 mm coroplast = $______ /sq ft"],
      proposed_option=0, rule="as printed",
      targets=["banner-13oz", "banner-8oz-mesh", "foam-core", "coroplast-4mm", "coroplast-10mm", "aluminum-sandwich", "car-magnet"]),
 dict(id="C17", section="Scanning", kind="question", title="Scan delivery: 'includes 1 CD', '$3.00 each CD'",
      context=["Document scans include 1 CD; multiple saves $3.00 each (CD). Large-format multiple saves $3.00 each."],
      crops=[("p03_scan.png", "p3, scan to electronic file")],
      options=["Any delivery copy (CD, USB, email): first included, $3.00 each extra", "CD only; email / USB no charge",
               "Other: ____________________"], proposed_option=0, rule="best reading",
      targets=["scan-lf-extra-save", "scan-doc-extra-save"]),
 dict(id="C18", section="Pens & Markers", kind="verify", title="Pen prices that are hard to read",
      context=["Current (red-pen) sheet. Two independent reads agreed on these, but the handwriting is ambiguous."],
      crops=[("pen_profile.png", "Papermate Profile 89465"), ("pen_twin.png", "Sharpie Super Twin Tip"),
             ("pen_deluxe.png", "Uniball Deluxe"), ("pen_sakura.png", "Sakura Micron")],
      lines=[L("a", "Papermate Profile 89465 (black note 'Elite: 2.33'; red 1.99, or 1.89 / 1.39?)",
               "pen-papermate-profile-89465", "1.99", "R5"),
             L("b", "Sharpie Super Twin Tip 36201 (3.69 or 2.69?)", "pen-sharpie-super-twin-tip-36201", "3.69", "R5"),
             L("c", "Uniball Deluxe 60052 (4.39 or 4.59?)", "pen-uniball-deluxe-60052", "4.39", "R5"),
             L("d", "Sakura Micron (no red; black marker 2.89 over blacked-out price)", "pen-sakura-micron-xsdk005-49", "2.89", "R1")]),
 dict(id="C19", section="Pens & Markers", kind="question", title="Handwritten pen notes: add as new items?",
      context=["Notes written around the table, not in a row. 'Pentel Twist Erase ... 2.09' is also at the clipped top edge."],
      crops=[("pens_top.png", "Top of sheet"), ("pens_margin.png", "Left margin (rotated)"), ("pens_bottom.png", "Bottom of sheet")],
      lines=[L("a", "Bic Velocity (pen)", "pen-bic-velocity", "1.75", "handwritten", True),
             L("b", "Pentel Energel, model? ____ (row BL57A is $3.75)", "pen-pentel-energel-margin", "3.49", "handwritten", True),
             L("c", "Pentel Twist-Erase Express", "pen-pentel-twist-erase-express", "2.09", "handwritten", True),
             L("d", "Pentel Twist-Erase GT", "pen-pentel-twist-erase-gt", "2.66", "handwritten", True),
             L("e", "Pilot G-Tec pen", "pen-pilot-g-tec", "2.64", "handwritten", True)]),
 dict(id="C20", section="Pens & Markers", kind="question", title="Struck-out pens: discontinue?",
      context=["Struck on the current sheet with no new price."],
      crops=[("pen_struck_widebody.png", "Bic Widebody"), ("pen_struck_ergotwist.png", "Ergotwist"),
             ("pen_struck_twisterase.png", "Pentel Twist Erase QE107A"), ("pen_struck_calligraphy.png", "Sanford Calligraphy")],
      lines=[L("a", "Bic Widebody SCWB11-BK (was $1.35)", "pen-bic-widebody-scwb11-bk", "retire", "R4"),
             L("b", "Ergotwist BK99A-A (was $6.45)", "pen-ergotwist-bk99a-a", "retire", "R4"),
             L("c", "Pentel Twist Erase QE107A (was $0.95)", "pen-pentel-twist-erase-qe107a", "retire", "R4"),
             L("d", "Sanford Calligraphy (was $1.49)", "pen-sanford-calligraphy", "retire", "R4")]),
 dict(id="C21", section="Pens & Markers", kind="question", title=f"{len(nu_lines)} pens got no red-pen update",
      context=["Unchanged, or just not checked yet? Circle any that need re-pricing."],
      list_items=sorted(nu_lines), crops=[],
      options=["All unchanged: keep printed prices", "Re-check the circled ones", "Re-check all of them"], proposed_option=0,
      rule="as printed"),
 dict(id="C22", section="Pens & Markers", kind="question", title="Second price column (box / dozen) was never updated",
      context=[f"{sum(1 for r in prices.values() if r['unit'] == 'box')} items have a second price. Single prices went up 20-100% in red; the second column did not change.",
               "Example: Bic 4 Color single $2.89 -> $3.74, second column still $30.12."],
      crops=[("pen_box_sample.png", "Rows 1-4")],
      options=["Drop the second-column prices; sell by the each", "Keep them as printed", "I'll re-price them"],
      proposed_option=0, rule="stale", extra_question="Column 2 is:   [ ] box   [ ] dozen   [ ] other: ________"),
 dict(id="C23", section="Phone List", kind="question", title="7-digit phone numbers",
      context=["Most numbers on the phone list have no area code (e.g. Mark 831-xxxx, Horizon 858-2300)."],
      crops=[], options=["All 7-digit numbers are 775", "Some aren't (mark them on the phone list)"], proposed_option=0,
      rule="local numbers"),
 dict(id="C24", section="Phone List", kind="question", title="Reno store and Reno accounts",
      context=["Phone list has Rainbow Reno 770-2276 / fax 770-2273, Essendant Reno acct (335 Edison Way Suite 8), SPR Reno acct."],
      crops=[("p15_reno.png", "p15"), ("p15_essendant_reno.png", "p15, Essendant"), ("p15_spr.png", "p15, SPR")],
      options=["Reno still active: keep all", "Reno closed: drop Reno phone/fax and Reno accounts"], proposed_option=0,
      rule="as printed"),
 dict(id="C25", section="Phone List", kind="question", title="Inland Business Systems sticker (M11387)",
      context=["Service/supplies sticker: Sacramento 916-928-0804, toll free 888-249-3551, inlandbusiness.us, M11387.",
               "Inland / Lucas / Sierra is a Xerox dealer, so this is probably the Versant 180."],
      crops=[("p17_inland.png", "p17")],
      options=["Versant 180 service; M11387 = machine / customer #", "Other machine: ____________________"],
      proposed_option=0, rule="best reading"),
 dict(id="C26", section="Missing", kind="gap", title="No price on any sheet: fill in or leave blank",
      context=["Leave a line blank to keep it unpriced."],
      crops=[],
      lines=[L("a", "Color copies, duplex (proposal: 2x the single-sided price)", "", "2x single", "gap"),
             L("b", "Vellum 30x42", "vellum-30x42", None, "gap"),
             L("c", "Vellum 36x48", "vellum-36x48", None, "gap"),
             L("d", "Sales tax rate for quotes (%)", "", None, "gap")]),
]
for c in cards:
    c.setdefault("lines", [])
    c.setdefault("options", [])
    c.setdefault("proposed_option", None)
    c.setdefault("targets", [])
    c.setdefault("list_items", [])
    c.setdefault("extra_question", "")
    c["crops"] = [dict(file=os.path.splitext(f)[0] + ".jpg", caption=cap) for f, cap in c["crops"]]
    c["status"] = "open"
    c["answer"] = None
    c["sheet_version"] = 1
    for f in c["crops"]:
        assert os.path.exists(os.path.join(CROPS, f["file"])), f

# POST_V1: layout tweaks applied after first render (crop heights, drop duplicate crops)
H = {"p12_trade_all.jpg": 3.1, "p12_trade_top.jpg": 1.55, "p10_photo_old.jpg": 1.35, "p09_photo_new.jpg": 1.35,
     "p04_num_fold_score_perf.jpg": 1.15, "p11_labels_new.jpg": 1.45, "p02_labels_old.jpg": 1.45, "p17_inland.jpg": 1.1,
     "p15_essendant_reno.jpg": 0.75, "p15_spr.jpg": 0.55, "p08_signs.jpg": 1.5, "p03_scan.jpg": 0.9, "p01_lf_block.jpg": 1.55,
     "pen_box_sample.jpg": 0.75, "p03_lf_tables.jpg": 1.0, "pens_top.jpg": 0.5, "pens_bottom.jpg": 0.5}
for c in cards:
    for cr in c["crops"]:
        if cr["file"] in H:
            cr["h"] = H[cr["file"]]
    if c["id"] == "C15": c["crops"] = []; c["context"].append("Same bindery page as C14.")
    if c["id"] == "C09": c["crops"] = []; c["context"].append("See the older-sheet crop on C08.")
    if c["id"] == "C10": c["crops"] = []; c["context"].append("See the p3 large-format crop on C01.")
    if c["id"] == "C22": c["on_accept"] = "retire"

doc = dict(version=1, created="2026-09-30",
           rules={"R1": "Handwriting beats print on the same sheet.",
                  "R2": "In a chain of strike-throughs, the last value written wins.",
                  "R3": "Newer sheet beats older (logo-header sheets over the older typed sheets; the red-pen pen list is current).",
                  "R4": "Struck with nothing written in, or unreadable: no proposal, you decide.",
                  "R5": "Two independent transcriptions agree, but the handwriting is ambiguous: please confirm."},
           cards=cards)
json.dump(doc, open(os.path.join(ROOT, "data", "conflicts.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(cards), "cards;", len(os.listdir(CROPS)), "crops")
