#!/usr/bin/env python3
"""
verify_print.py — measure a finished PDF before it goes to the press.

Two modes:

1. Imposition check (default).  Reads the /RainbowLayout record that impose.py
   stores in the PDF, renders every page, and checks the actual ink against it:
     * page box is exactly the intended sheet size
     * all 8 crop marks per piece are present and start at the bleed edge
     * no ink outside the bleed boxes except the marks (nothing in gutters/margins)
     * bleed ring actually carries ink (warns if it is white)
     * no light hairline on the trim where mirrored bleed meets the art (600 dpi, no antialias)
     * duplex: every back slot that has content sits behind a front slot with content
   For PDFs without a layout record, pass --trim/--bleed/--mark/--sheet/--cols/--rows
   to describe what you expect.
   Booklets (booklet.py): planned blank pages must be empty, duplex backing ignores them,
   and with --source ORIGINAL.pdf (or the original sitting next to the output) the rendered
   sheets are folded and nested in software and every reading page is compared with the
   original: right page, right place, upright.

2. Die-cut label check (--grid PRESET or --grid "cols,rows,w,h,left,top,pitch_x,pitch_y[,round]"
   in inches).  Renders the PDF and checks every mark of ink lands inside a label
   with --clearance to spare, and that the page box is exactly the sheet size.
   Round presets (avery22877 etc.) measure against the circle, not its bounding box.
   --flood IN is for print-to-the-edge art whose background deliberately runs IN
   past the die: ink may reach die+IN, the clearance check is replaced by a check
   that the band across each die edge is solid ink (no white slivers on drift).
   --alignment writes an outline-only test page for the preset to print on plain
   paper and hold against the label stock.

Both modes also run the crush check (crushcheck.py): any chromatic vector color or flat
image color too dark for the Versant to show a hue (L* < l_crush in press.json) FAILS the
file — impose.py / labels.py lift those automatically, so a FAIL here means the file
bypassed them.  --allow-crush downgrades it to a warning.

Exit status 0 = PASS, 1 = FAIL.  Warnings do not fail.

  python3 verify_print.py "Harper_8up_letter.pdf"
  python3 verify_print.py "Deck_8.5x5.5_booklet24pp_letter_duplex.pdf" --source Deck.pdf
  python3 verify_print.py badges.pdf --grid avery8395
  python3 verify_print.py --grid avery5160 --alignment
  python3 verify_print.py stickers.pdf --grid avery22877 --flood 0.1
"""
import argparse, json, os, subprocess, sys, tempfile
# Mac: find pdftoppm in ~/.rainbow (setup-mac.sh); harmless elsewhere
os.environ["PATH"] = os.path.expanduser("~/.rainbow/env/bin") + os.pathsep + os.environ.get("PATH", "")

import numpy as np
import bleedscan
import pikepdf
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # our own pdftoppm renders; banners at SEAM_DPI exceed PIL's bomb limit (2026-10-28)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crushcheck  # noqa: E402

IN = 72.0
DPI = 144
INK = 200      # gray level below this counts as ink (0..255)

# Die-cut presets: cols, rows, label_w, label_h, left_margin, top_margin, pitch_x, pitch_y (inches, letter sheet)
# From Avery's published geometry; confirm with --alignment on plain paper before running stock.
GRIDS = {
    "avery8395": (2, 4, 3.375, 2.3333, 0.6875, 0.55, 3.75, 2.5233),   # name badges (also 5395, 25395, 42395, 45395, 48395, 85395, 88395)
    "avery5160": (3, 10, 2.625, 1.0, 0.1875, 0.5, 2.75, 1.0),          # address labels (also 8160, 5260, 8460)
    "avery5161": (2, 10, 4.0, 1.0, 0.15625, 0.5, 4.1875, 1.0),
    "avery5162": (2, 7, 4.0, 1.3333, 0.15625, 0.8333, 4.1875, 1.3333),
    "avery5163": (2, 5, 4.0, 2.0, 0.15625, 0.5, 4.1875, 2.0),          # shipping labels (also 8163, 5263, 8463)
    "avery5164": (2, 3, 4.0, 3.3333, 0.15625, 0.5, 4.1875, 3.3333),
    "avery5167": (4, 20, 1.75, 0.5, 0.28125, 0.5, 2.0625, 0.5),        # return address (also 8167)
    "avery5371": (2, 5, 3.5, 2.0, 0.75, 0.5, 3.5, 2.0),                # business cards, no gap (also 8371, 8471, 5911)
}
# Round: 9th field "round" -> circle of diameter w inscribed in the w x h cell.
GRIDS["avery22807"] = (3, 4, 2.0, 2.0, 0.625, 0.625, 2.625, 2.5833, "round")  # 2" round print-to-the-edge, 12/sheet
for _k in ("avery22877", "avery22817"):
    GRIDS[_k] = GRIDS["avery22807"]
GRIDS["avery5395"] = GRIDS["avery8395"]
GRIDS["avery8163"] = GRIDS["avery5163"]
GRIDS["avery8160"] = GRIDS["avery5160"]


def render(path, dpi=DPI):
    """Render all pages to grayscale numpy arrays (0=black)."""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", path, os.path.join(td, "p")],
                       check=True, capture_output=True)
        files = sorted(f for f in os.listdir(td) if f.endswith(".png"))
        return [np.asarray(Image.open(os.path.join(td, f)).convert("L")) for f in files]


def px(v_pt, dpi=DPI):
    return v_pt / IN * dpi


def check_crush(pdf, rep, allow=False):
    """Fail (or warn with allow=True) on colors that will crush to black on the Versant."""
    try:
        cr = crushcheck.check_pdf(pdf)
    except Exception as e:
        rep.warn(f"crush check could not run: {e}")
        return
    lines, n_vec, n_img = crushcheck.summarise(cr, verbose=False)
    lifted = []
    if "/RainbowLayout" in pdf.docinfo:
        try:
            lifted = json.loads(str(pdf.docinfo["/RainbowLayout"])).get("crush_lifted", [])
        except Exception:
            pass
    p = cr["press"]
    if n_vec or n_img:
        msg = (f"{n_vec + n_img} color(s) will print as black on the Versant (chromatic below L*{p['l_crush']:g}): "
               + "; ".join(l[6:] for l in lines if l.startswith("CRUSH")))
        (rep.warn if allow else rep.fail)(msg + ("" if allow else " — rerun impose.py/labels.py without --no-crush-fix, or crushcheck.py --fix"))
    else:
        rep.ok(f"crush check: no chromatic color below L*{p['l_crush']:g}")
        if lifted:
            rep.warn(f"crush guard changed {len(lifted)} color(s) in this file — TELL ANDREW: " + "; ".join(lifted))
    if cr["shadings"]:
        rep.warn(f"{cr['shadings']} gradient(s) not evaluated by the crush check — eyeball dark gradient ends")


class Report:
    def __init__(self):
        self.fails, self.warns, self.lines = [], [], []

    def ok(self, msg):    self.lines.append(f"  OK    {msg}")
    def warn(self, msg):  self.lines.append(f"  WARN  {msg}"); self.warns.append(msg)
    def fail(self, msg):  self.lines.append(f"  FAIL  {msg}"); self.fails.append(msg)

    def finish(self):
        for l in self.lines:
            print(l)
        print(f"RESULT  {'PASS' if not self.fails else 'FAIL'}"
              f"  ({len(self.fails)} fail, {len(self.warns)} warn)")
        return 0 if not self.fails else 1


# --------------------------------------------------------------------------- imposition mode
def check_pagebox(pdf, sheet_in, rep):
    sw, sh = sheet_in[0] * IN, sheet_in[1] * IN
    bad = []
    for i, p in enumerate(pdf.pages):
        x0, y0, x1, y1 = (float(v) for v in p.mediabox)
        w, h = abs(x1 - x0), abs(y1 - y0)
        if abs(w - sw) > 0.5 or abs(h - sh) > 0.5:
            bad.append(f"p{i+1} {w/IN:.3f}x{h/IN:.3f}")
    if bad:
        rep.fail(f"page box: expected {sheet_in[0]:g}x{sheet_in[1]:g} in, got {', '.join(bad)} — the RIP will scale this")
    else:
        rep.ok(f"page box {sheet_in[0]:g}x{sheet_in[1]:g} in on all {len(pdf.pages)} page(s)")


def mark_segments(tx0, ty0, tw, th, bleed, mark):
    tx1, ty1 = tx0 + tw, ty0 + th
    segs = []
    for x in (tx0, tx1):
        segs.append(((x, ty1 + bleed), (x, ty1 + bleed + mark)))
        segs.append(((x, ty0 - bleed), (x, ty0 - bleed - mark)))
    for y in (ty0, ty1):
        segs.append(((tx0 - bleed, y), (tx0 - bleed - mark, y)))
        segs.append(((tx1 + bleed, y), (tx1 + bleed + mark, y)))
    return segs


def to_px(x_pt, y_pt, H):
    """PDF points (origin bottom-left) -> raster pixel (row, col)."""
    return H - px(y_pt), px(x_pt)


def check_sheet(img, pieces, bleed_pt, mark_pt, rep, tag):
    H, W = img.shape
    allowed = np.zeros_like(img, dtype=bool)
    mark_missing, mark_total = [], 0
    b = px(bleed_pt)
    for k, piece in enumerate(pieces):
        tx0, ty0, tw, th = piece["trim"]
        # bleed box -> allowed
        r1, c0 = to_px(tx0 - bleed_pt, ty0 - bleed_pt, H)
        r0, c1 = to_px(tx0 + tw + bleed_pt, ty0 + th + bleed_pt, H)
        r0, r1, c0, c1 = int(r0) - 1, int(np.ceil(r1)) + 1, int(c0) - 1, int(np.ceil(c1)) + 1
        allowed[max(r0, 0):min(r1, H), max(c0, 0):min(c1, W)] = True
        if piece.get("label") is None:
            continue
        # bleed ring ink coverage
        rt1, ct0 = to_px(tx0, ty0, H); rt0, ct1 = to_px(tx0 + tw, ty0 + th, H)
        ring = np.ones_like(img, dtype=bool)
        ring[int(rt0) + 2:int(rt1) - 2, int(ct0) + 2:int(ct1) - 2] = False
        ring &= allowed
        ring[:max(r0, 0)] = False; ring[min(r1, H):] = False
        ring[:, :max(c0, 0)] = False; ring[:, min(c1, W):] = False
        ring_px = img[ring]
        cover = (ring_px < 250).mean() if ring_px.size else 0
        if mark_pt > 0:
            for (ax, ay), (bx, by) in mark_segments(tx0, ty0, tw, th, bleed_pt, mark_pt):
                mark_total += 1
                mx, my = (ax + bx) / 2, (ay + by) / 2
                r, c = to_px(mx, my, H)
                r, c = int(round(r)), int(round(c))
                win = img[max(r - 2, 0):r + 3, max(c - 2, 0):c + 3]
                if win.size == 0 or win.min() > INK:
                    mark_missing.append(f"piece {k+1} ({mx/IN:.2f},{my/IN:.2f})")
                # allow mark ink (dilated 2px) in the outside-ink test
                ra, ca = to_px(ax, ay, H); rb, cb = to_px(bx, by, H)
                rlo, rhi = sorted((int(ra), int(rb))); clo, chi = sorted((int(ca), int(cb)))
                allowed[max(rlo - 2, 0):rhi + 3, max(clo - 2, 0):chi + 3] = True
        if bleed_pt > 0 and cover < 0.05:
            rep.warn(f"{tag} piece {k+1}: bleed ring is {cover*100:.0f}% inked — fine only if the art has a white background")
    stray = int(((img < INK) & ~allowed).sum())
    if mark_pt > 0:
        if mark_missing:
            rep.fail(f"{tag}: {len(mark_missing)}/{mark_total} crop marks missing/misplaced: {'; '.join(mark_missing[:4])}")
        else:
            rep.ok(f"{tag}: all {mark_total} crop marks present at bleed edge")
    if stray > 10:
        rep.fail(f"{tag}: {stray} px of ink outside the bleed boxes/marks (gutters or margins)")
    else:
        rep.ok(f"{tag}: no ink outside bleed boxes and marks")
    # per-slot content flags for duplex comparison
    flags = []
    for piece in pieces:
        tx0, ty0, tw, th = piece["trim"]
        rt1, ct0 = to_px(tx0, ty0, H); rt0, ct1 = to_px(tx0 + tw, ty0 + th, H)
        flags.append(bool((img[int(rt0):int(rt1), int(ct0):int(ct1)] < 250).mean() > 0.002))
    return flags


SEAM_DPI = 600     # trim/bleed join check: rendered without antialiasing
SEAM_DELTA = 25    # a trim line this much lighter than the art both sides of it is a hairline
SEAM_FRAC = 0.25   # ...along this fraction of an edge -> FAIL


def check_seams(path, layout, rep):
    """Mirrored bleed is a raster strip butted against the vector art. A strip that is
    a pixel short (or carries a blank raster column) leaves a light hairline exactly on the
    trim; a cut that drifts a hair outward then shows it on the finished piece. Render
    without antialiasing at SEAM_DPI and compare the trim line with the art just inside and
    just outside it, along every trim edge of every piece."""
    bleed_pt = layout["bleed_in"] * IN
    if bleed_pt <= 0:
        return
    bad = []
    with tempfile.TemporaryDirectory() as td:
        for i, sheet in enumerate(layout["sheets"]):
            out = os.path.join(td, f"s{i}")
            subprocess.run(["pdftoppm", "-r", str(SEAM_DPI), "-gray", "-aa", "no", "-aaVector", "no",
                            "-f", str(i + 1), "-l", str(i + 1), "-singlefile", "-png", path, out],
                           check=True, capture_output=True)
            img = np.asarray(Image.open(out + ".png").convert("L")).astype(np.int16)
            H, W = img.shape
            d = SEAM_DPI / IN
            for k, pc in enumerate(sheet["pieces"]):
                if pc.get("label") is None or pc.get("blank"):
                    continue
                tx0, ty0, tw, th = pc["trim"]
                c0, c1 = tx0 * d, (tx0 + tw) * d
                r0, r1 = H - (ty0 + th) * d, H - ty0 * d
                m = 12  # stay clear of the corners
                # (name, axis, line position, inward sign, span)
                edges = [("left", 1, c0, +1, (r0 + m, r1 - m)), ("right", 1, c1, -1, (r0 + m, r1 - m)),
                         ("top", 0, r0, +1, (c0 + m, c1 - m)), ("bottom", 0, r1, -1, (c0 + m, c1 - m))]
                for name, axis, pos, inward, (a, b) in edges:
                    a, b = int(a), int(b)
                    if b - a < 20:
                        continue
                    def band(lo, hi):
                        lo, hi = int(round(pos + lo)), int(round(pos + hi))
                        lo, hi = min(lo, hi), max(lo, hi)
                        if lo < 0 or (hi >= (W if axis == 1 else H)):
                            return None
                        sl = img[a:b, lo:hi + 1] if axis == 1 else img[lo:hi + 1, a:b].T
                        return sl.max(axis=1)
                    seam_b = band(-2, 2)
                    ins = band(inward * 5, inward * 9)
                    outs = band(-inward * 5, -inward * 9)
                    if seam_b is None or ins is None or outs is None:
                        continue
                    hit = (seam_b - np.maximum(ins, outs)) > SEAM_DELTA
                    if hit.mean() > SEAM_FRAC:
                        bad.append(f"p{i+1} piece {k+1} {name} edge ({hit.mean()*100:.0f}%)")
    if bad:
        rep.fail(f"light hairline on the trim where the mirrored bleed meets the art: {'; '.join(bad[:6])}"
                 f"{' …' if len(bad) > 6 else ''}")
    else:
        rep.ok("trim/bleed joins: no light hairline on any trim edge")


ART_DPI = 300   # bleed-artifact check render
CONT_OFF_PX = 2          # continuity check: compare the lines this far outside / inside the trim
CONT_DIFF = 60           # max channel difference (0-255) that still counts as the same art
CONT_MAX_SHARE = 0.03    # share of an edge allowed to differ (antialiased features crossing it)


def check_bleed_artifacts(path, layout, rep):
    """Generated bleed (mirrored or edge-extended by impose.py) must not show a hard edge running
    parallel to the trim — that is a box/QR/rule from just inside the trim copied into the bleed,
    which shows on the finished piece if the cut drifts outward. Pieces whose source carried its
    own bleed are skipped (customer bleed may legitimately hold a frame or rule)."""
    bleed_pt = layout["bleed_in"] * IN
    if bleed_pt <= 0 or not any(pc.get("bleed_fill") for sh in layout["sheets"] for pc in sh["pieces"]):
        return
    bad, breaks = [], []
    d = ART_DPI / IN
    with tempfile.TemporaryDirectory() as td:
        for i, sheet in enumerate(layout["sheets"]):
            gen = [pc for pc in sheet["pieces"] if pc.get("bleed_fill")]
            if not gen:
                continue
            out = os.path.join(td, f"s{i}")
            subprocess.run(["pdftoppm", "-r", str(ART_DPI), "-f", str(i + 1), "-l", str(i + 1),
                            "-singlefile", "-png", path, out], check=True, capture_output=True)
            img = np.asarray(Image.open(out + ".png").convert("RGB"))
            H, W = img.shape[:2]
            for k, pc in enumerate(sheet["pieces"]):
                if not pc.get("bleed_fill"):
                    continue
                tx0, ty0, tw, th = pc["trim"]
                c0, c1 = tx0 * d, (tx0 + tw) * d
                r0, r1 = H - (ty0 + th) * d, H - ty0 * d
                b = bleed_pt * d
                ra, rb = int(np.ceil(r0)) + 3, int(r1) - 3          # along vertical edges, clear of corners
                ca, cb = int(np.ceil(c0)) + 3, int(c1) - 3
                # bands strictly inside the bleed, rows along the edge, col 0 at the trim
                bands = {
                    "left": img[ra:rb, int(np.ceil(c0 - b)) + 1:int(c0)][:, ::-1],
                    "right": img[ra:rb, int(np.ceil(c1)) + 1:int(c1 + b)],
                    "top": np.swapaxes(img[int(np.ceil(r0 - b)) + 1:int(r0), ca:cb][::-1], 0, 1),
                    "bottom": np.swapaxes(img[int(np.ceil(r1)) + 1:int(r1 + b), ca:cb], 0, 1),
                }
                for side, band in bands.items():
                    run, col = bleedscan.hard_edge(band, ART_DPI)
                    if run >= bleedscan.MIN_RUN_IN:
                        bad.append(f"p{i+1} piece {k+1} {side} ({run:.2f} in, {col/ART_DPI:.3f} in out from trim)")
                # continuity: generated bleed (mirror or edge-extend) must carry on the art at the
                # trim — the line just outside matches the line just inside. A strip placed on the
                # wrong side or turned 180 (impose.py rot 90 + rotated cells, 2026-10-29) fails here.
                o = CONT_OFF_PX
                lines = {
                    "left": (img[ra:rb, int(c0) - o - 1], img[ra:rb, int(np.ceil(c0)) + o]),
                    "right": (img[ra:rb, int(np.ceil(c1)) + o], img[ra:rb, int(c1) - o - 1]),
                    "top": (img[int(r0) - o - 1, ca:cb], img[int(np.ceil(r0)) + o, ca:cb]),
                    "bottom": (img[int(np.ceil(r1)) + o, ca:cb], img[int(r1) - o - 1, ca:cb]),
                }
                for side, (out_l, in_l) in lines.items():
                    diff = np.abs(out_l.astype(int) - in_l.astype(int)).max(axis=1)
                    share = float((diff > CONT_DIFF).mean()) if diff.size else 0.0
                    if share > CONT_MAX_SHARE:
                        breaks.append(f"p{i+1} piece {k+1} {side} ({share:.0%} of the edge)")
    if bad:
        rep.fail(f"hard edge copied into generated bleed (box/QR/rule mirrored from inside the trim): "
                 f"{'; '.join(bad[:6])}{' …' if len(bad) > 6 else ''} — re-impose with --bleed-mode auto/edge")
    else:
        rep.ok("generated bleed: nothing from inside the trim mirrored into the bleed")
    if breaks:
        rep.fail(f"generated bleed doesn't continue the art at the trim (wrong side / rotated strip): "
                 f"{'; '.join(breaks[:6])}{' …' if len(breaks) > 6 else ''}")
    else:
        rep.ok("generated bleed: continues the art across every trim edge")


def imposition_mode(args, pdf, rep):
    layout = None
    if "/RainbowLayout" in pdf.docinfo:
        layout = json.loads(str(pdf.docinfo["/RainbowLayout"]))
        rep.ok(f"layout record: trim {layout['trim_in'][0]:g}x{layout['trim_in'][1]:g}, bleed {layout['bleed_in']:g}, "
               f"marks {layout['mark_in']:g}, {layout['cols']}x{layout['rows']} on {layout['sheet_in'][0]:g}x{layout['sheet_in'][1]:g}"
               f"{', duplex ' + str(layout['flip']) + '-edge' if layout['duplex'] else ''}")
    elif args.trim:
        layout = synth_layout(args, pdf)
        rep.ok("no layout record in PDF — using the geometry you passed on the command line")
    else:
        rep.warn("no /RainbowLayout record and no --trim given: only checking page boxes. "
                 "Pass --trim/--bleed/--mark/--sheet/--cols/--rows to check marks.")
        x0, y0, x1, y1 = (float(v) for v in pdf.pages[0].mediabox)
        check_pagebox(pdf, [abs(x1 - x0) / IN, abs(y1 - y0) / IN], rep)
        return
    check_pagebox(pdf, layout["sheet_in"], rep)
    imgs = render(args.pdf)
    if len(imgs) != len(layout["sheets"]):
        rep.fail(f"layout describes {len(layout['sheets'])} sheets but PDF has {len(imgs)} pages")
        return
    bleed_pt, mark_pt = layout["bleed_in"] * IN, layout["mark_in"] * IN
    flags = []
    for i, (img, sheet) in enumerate(zip(imgs, layout["sheets"])):
        flags.append(check_sheet(img, sheet["pieces"], bleed_pt, mark_pt, rep, f"p{i+1} {sheet['side']}"))
    blank = [[bool(pc.get("blank")) for pc in sheet["pieces"]] for sheet in layout["sheets"]]
    if any("blank" in pc for sheet in layout["sheets"] for pc in sheet["pieces"]):
        check_planned_blanks(layout, flags, rep)
    if layout["duplex"]:
        cols, rows = layout["cols"], layout["rows"]
        sw, sh = layout["sheet_in"]
        mirror_cols = (layout["flip"] == "long") == (sh >= sw)

        def behind(b):
            grid = [b[r * cols:(r + 1) * cols] for r in range(rows)]
            grid = [row[::-1] for row in grid] if mirror_cols else grid[::-1]
            return [x for row in grid for x in row]
        for i in range(0, len(flags) - 1, 2):
            f, bm = flags[i], behind(flags[i + 1])
            bl = [x or y for x, y in zip(blank[i], behind(blank[i + 1]))]   # a planned blank may back a page
            mism = [k + 1 for k in range(len(f)) if f[k] != bm[k] and not bl[k]]
            if mism:
                rep.fail(f"duplex p{i+1}/p{i+2}: slots {mism} have content on one side but not the other after the {layout['flip']}-edge flip")
            else:
                rep.ok(f"duplex p{i+1}/p{i+2}: every back sits behind a front ({layout['flip']}-edge flip)")
    if layout.get("bleed_in", 0) > 0 and "booklet" not in layout:
        check_seams(args.pdf, layout, rep)
        check_bleed_artifacts(args.pdf, layout, rep)
    if "booklet" in layout:
        booklet_check(args, layout, imgs, rep)


def check_planned_blanks(layout, flags, rep):
    inked, empty, nb = [], [], 0
    for i, sheet in enumerate(layout["sheets"]):
        for k, pc in enumerate(sheet["pieces"]):
            if "blank" not in pc:
                continue
            tag = f"p{i+1} slot {k+1}" + (f" (booklet p{pc['booklet_page']})" if pc.get("booklet_page") else "")
            nb += bool(pc["blank"])
            if pc["blank"] and flags[i][k]:
                inked.append(tag)
            elif not pc["blank"] and not flags[i][k]:
                empty.append(tag)
    if inked:
        rep.fail(f"planned blank(s) carry ink: {', '.join(inked)}")
    elif nb:
        rep.ok(f"all {nb} planned blank page(s) empty")
    if empty:
        rep.warn(f"page slot(s) with almost no ink: {', '.join(empty)} — fine only if that source page is white")


CMP_DPI = 36          # booklet reading check resolution (render at DPI, box-downsample to this)


def _placed_source(src, j, panel_px, panel_in, fit, margin_in):
    """Source page j rendered as the spec says it should land: fit (or 100%), centered in a white panel."""
    mb = cb = rot = None
    node = src.pages[j].obj                      # walk up for inherited boxes / rotation
    while node is not None:
        if mb is None and "/MediaBox" in node: mb = [float(v) for v in node["/MediaBox"]]
        if cb is None and "/CropBox" in node: cb = [float(v) for v in node["/CropBox"]]
        if rot is None and "/Rotate" in node: rot = int(node["/Rotate"]) % 360
        node = node.get("/Parent")
    rot = rot or 0
    box = cb or mb
    w = min(max(box[0], box[2]), max(mb[0], mb[2])) - max(min(box[0], box[2]), min(mb[0], mb[2]))
    h = min(max(box[1], box[3]), max(mb[1], mb[3])) - max(min(box[1], box[3]), min(mb[1], mb[3]))
    dw, dh = (w / IN, h / IN) if rot in (0, 180) else (h / IN, w / IN)
    pw, ph = panel_in
    s = min((pw - 2 * margin_in) / dw, (ph - 2 * margin_in) / dh) if fit else 1.0
    tw, th = max(1, round(dw * s * CMP_DPI)), max(1, round(dh * s * CMP_DPI))
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", str(j + 1), "-l", str(j + 1), "-gray", "-png",
                        "-scale-to-x", str(tw * DPI // CMP_DPI), "-scale-to-y", str(th * DPI // CMP_DPI),
                        src.filename, os.path.join(td, "s")], check=True, capture_output=True)
        f = [x for x in os.listdir(td) if x.endswith(".png")][0]
        im = Image.open(os.path.join(td, f)).convert("L").resize((tw, th), Image.BOX)
    pwp, php = panel_px
    canvas = Image.new("L", (pwp, php), 255)
    canvas.paste(im, (round((pwp - tw) / 2), round((php - th) / 2)))
    return np.asarray(canvas, dtype=np.float32)


def booklet_check(args, layout, imgs, rep):
    """Fold the rendered sheets the way the shop will — stack as printed, sheet 1 outside, one fold —
    and read the booklet page by page. Each reading page is compared with the source page placed by
    the spec (fit or 100%, centered): it must be the right page, and upright. Only the physics of the
    duplex flip and the fold is used here, not booklet.py's page tables. Both faces are tried as the
    outside (and both head directions); one of them has to read correctly from cover to back cover."""
    bk = layout["booklet"]
    src_path = args.source or (os.path.join(os.path.dirname(os.path.abspath(args.pdf)), bk["source"])
                               if bk.get("source") else None)
    if not src_path or not os.path.isfile(src_path):
        rep.warn("booklet reading order NOT checked — pass --source ORIGINAL.pdf")
        return
    n, binding = bk["pages"], bk["binding"]
    S = n // 4
    if n % 4 or len(imgs) != 2 * S:
        rep.fail(f"booklet: {n} pages needs {S} sheets = {2*S} PDF pages, file has {len(imgs)}")
        return
    sw, sh = layout["sheet_in"]
    W, H = round(sw * CMP_DPI), round(sh * CMP_DPI)
    sheets = [np.asarray(Image.fromarray(im).resize((W, H), Image.BOX), dtype=np.float32) for im in imgs]
    axis_vertical = (layout["flip"] == "long") == (sh >= sw)       # the edge the duplex turns over on
    if binding == "top":                                            # fold horizontal, page head at the fold side
        hh = H // 2
        first, second, reflect = (lambda a: a[:hh]), (lambda a: a[H - hh:]), np.flipud
        panel_px, panel_in = (W, hh), (sw, sh / 2)
    else:                                                           # fold vertical, spine on the left
        hw = W // 2
        first, second, reflect = (lambda a: a[:, :hw]), (lambda a: a[:, W - hw:]), np.fliplr
        panel_px, panel_in = (hw, H), (sw / 2, sh)

    def read(inside, up):
        """Reading pages {n: image} if the stack is folded with `inside` face in."""
        pages = {}
        for k in range(S):
            F, B = sheets[2 * k], sheets[2 * k + 1]
            Bp = np.fliplr(B) if axis_vertical else np.flipud(B)   # back ink at its physical spot, front frame
            if inside == "back":                                    # reader looks at the back face
                In, Out = np.fliplr(Bp), np.fliplr(F)
            else:
                In, Out = F, Bp
            if up:
                In, Out = np.rot90(In, 2), np.rot90(Out, 2)
            R = reflect(Out)                                        # a leaf turned over the fold
            pages[2 * k + 2], pages[n - 2 * k - 1] = first(In), second(In)
            pages[2 * k + 1], pages[n - 2 * k] = second(R), first(R)
        return pages

    spdf = pikepdf.open(src_path)
    blanks = set(bk.get("blank_pages", []))
    if bk.get("order"):                                             # booklet.py --order: the requested reading order
        if len(bk["order"]) != n:
            rep.fail(f"booklet: order lists {len(bk['order'])} pages, booklet has {n}")
            return
        seq = {p: (None if v is None else v - 1) for p, v in enumerate(bk["order"], 1)}
    else:
        if len(spdf.pages) + len(blanks) != n:
            rep.fail(f"booklet: source has {len(spdf.pages)} pages + {len(blanks)} blanks != {n}")
            return
        seq, j = {}, 0
        for p in range(1, n + 1):
            seq[p] = None if p in blanks else j
            j += p not in blanks
    expect = {jj: _placed_source(spdf, jj, panel_px, panel_in, bk.get("fit"), bk.get("margin_in", 0))
              for jj in range(len(spdf.pages))}
    mad = lambda a, b: float(np.abs(a - b).mean())

    best = None
    for inside in ("back", "front"):
        for up in (0, 1):
            pages = read(inside, up)
            score = sum(mad(pages[p], expect[seq[p]]) if seq[p] is not None else float((pages[p] < INK).mean() * 255)
                        for p in pages)
            if best is None or score < best[0]:
                best = (score, inside, up, pages)
    _, inside, up, pages = best
    bad, worst = [], 0.0
    for p in range(1, n + 1):
        P = pages[p]
        if seq[p] is None:
            if (P < INK).sum() > 0:
                bad.append(f"p{p} should be blank but carries ink")
            continue
        e = mad(P, expect[seq[p]])
        flipped = mad(P, np.rot90(expect[seq[p]], 2))
        nearest = min(expect, key=lambda jj: mad(P, expect[jj]))
        worst = max(worst, e)
        if flipped < e and flipped <= 6.0:
            bad.append(f"p{p} (source p{seq[p] + 1}) reads upside down")
        elif nearest != seq[p]:
            bad.append(f"p{p} shows source p{nearest + 1}, should be p{seq[p] + 1}")
        elif e > 6.0:
            bad.append(f"p{p} (source p{seq[p] + 1}) differs from the spec placement (MAD {e:.1f})")
        elif flipped < e * 1.5:
            bad.append(f"p{p} (source p{seq[p] + 1}) orientation ambiguous (MAD {e:.1f} vs {flipped:.1f} flipped)")
    face = "PDF front sides" if inside == "back" else "PDF back sides"
    if bad:
        rep.fail(f"booklet fold check vs {os.path.basename(src_path)}: {len(bad)} page(s) wrong — " + "; ".join(bad[:6]))
    else:
        rep.ok(f"booklet fold check vs {os.path.basename(src_path)}: folded {binding}-bound with the {face} outside, "
               f"all {n} pages read in order and upright ({len(blanks)} blank as planned; worst MAD {worst:.1f}/255)")


def synth_layout(args, pdf):
    tw, th = (float(v) for v in args.trim.lower().split("x"))
    bleed, mark = args.bleed, args.mark
    if args.sheet:
        from impose import parse_size
        sw, sh = parse_size(args.sheet)
    else:
        x0, y0, x1, y1 = (float(v) for v in pdf.pages[0].mediabox)
        sw, sh = abs(x1 - x0) / IN, abs(y1 - y0) / IN
    cols, rows = args.cols or 1, args.rows or 1
    cw, ch = tw + 2 * bleed, th + 2 * bleed
    if args.rotated:
        cw, ch = ch, cw
    g = args.gutter
    gw, gh = cols * cw + (cols - 1) * g, rows * ch + (rows - 1) * g
    ox, oy = (sw - gw) / 2, (sh - gh) / 2
    pieces = []
    for r in range(rows):
        for c in range(cols):
            bx = ox + c * (cw + g); by = oy + gh - (r + 1) * ch - r * g
            pieces.append({"trim": [(bx + bleed) * IN, (by + bleed) * IN, (cw - 2 * bleed) * IN, (ch - 2 * bleed) * IN], "label": "?"})
    sheets = [{"side": "front" if not args.duplex or i % 2 == 0 else "back", "pieces": pieces} for i in range(len(pdf.pages))]
    return {"trim_in": [tw, th], "bleed_in": bleed, "mark_in": mark, "sheet_in": [sw, sh], "cols": cols, "rows": rows,
            "duplex": args.duplex, "flip": args.flip, "sheets": sheets}


# --------------------------------------------------------------------------- die-cut mode
def parse_grid(spec):
    if spec.lower() in GRIDS:
        return GRIDS[spec.lower()]
    try:
        parts = spec.split(",")
        shape = parts.pop() if parts[-1].strip().lower() in ("round", "rect") else None
        vals = [float(v) for v in parts]
        assert len(vals) == 8
        g = (int(vals[0]), int(vals[1]), *vals[2:])
        return g + ((shape.strip().lower(),) if shape else ())
    except Exception:
        sys.exit(f"--grid must be a preset ({', '.join(sorted(GRIDS))}) or 'cols,rows,w,h,left,top,pitch_x,pitch_y[,round]' in inches")


def label_cells(g):
    """Yield (x_left, y_top, w, h, shape) in inches from the sheet's top-left, row by row."""
    cols, rows, lw, lh, left, top, pitch_x, pitch_y, *rest = g
    shape = rest[0] if rest else "rect"
    for r in range(rows):
        for k in range(cols):
            yield (left + k * pitch_x, top + r * pitch_y, lw, lh, shape)


def grid_mode(args, rep):
    g = parse_grid(args.grid)
    cells = list(label_cells(g))
    sheet = (8.5, 11)
    if args.alignment:
        out = args.pdf or f"{args.grid}_alignment.pdf"
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import Color
        c = canvas.Canvas(out, pagesize=(sheet[0] * IN, sheet[1] * IN))
        c.setStrokeColor(Color(0.85, 0.1, 0.1)); c.setLineWidth(0.5)
        for (x, yt, lw, lh, shape) in cells:
            y = sheet[1] - yt - lh
            if shape == "round":
                c.circle((x + lw / 2) * IN, (y + lh / 2) * IN, lw / 2 * IN)
                c.line((x + lw / 2 - 0.1) * IN, (y + lh / 2) * IN, (x + lw / 2 + 0.1) * IN, (y + lh / 2) * IN)
                c.line((x + lw / 2) * IN, (y + lh / 2 - 0.1) * IN, (x + lw / 2) * IN, (y + lh / 2 + 0.1) * IN)
            else:
                c.rect(x * IN, y * IN, lw * IN, lh * IN)
        c.setFont("Helvetica", 8)
        c.drawString(0.3 * IN, 0.2 * IN, f"{args.grid} alignment test — print at 100% / Actual Size on plain paper, hold against the label sheet")
        c.save()
        print(f"wrote {out}")
        return 0
    if not args.pdf:
        sys.exit("give a PDF to check (or --alignment to make a test page)")
    pdf = pikepdf.open(args.pdf)
    check_pagebox(pdf, list(sheet), rep)
    imgs = render(args.pdf)
    clear = px(args.clearance * IN)
    flood = px(args.flood * IN)
    for i, img in enumerate(imgs):
        H, W = img.shape
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
        ink = img < INK
        dist = np.full((H, W), -1e9, dtype=np.float32)   # signed px to nearest die edge, + = inside
        tightest, empty, sliver = 1e9, [], []
        for n, (x, yt, lw, lh, shape) in enumerate(cells):
            x0, y0, x1, y1 = px(x * IN), px(yt * IN), px((x + lw) * IN), px((yt + lh) * IN)
            m = int(flood) + 3
            r0, r1, c0, c1 = max(int(y0) - m, 0), min(int(np.ceil(y1)) + m, H), max(int(x0) - m, 0), min(int(np.ceil(x1)) + m, W)
            sy, sx = yy[r0:r1, c0:c1], xx[r0:r1, c0:c1]
            if shape == "round":
                d = (x1 - x0) / 2 - np.hypot(sx - (x0 + x1) / 2, sy - (y0 + y1) / 2)
            else:
                d = np.minimum(np.minimum(sx - x0, x1 - sx), np.minimum(sy - y0, y1 - sy))
            dist[r0:r1, c0:c1] = np.maximum(dist[r0:r1, c0:c1], d)
            cell_ink = ink[r0:r1, c0:c1] & (d >= 0)
            if not cell_ink.any():
                empty.append(n + 1)
                continue
            if flood > 0:
                band = (d <= clear) & (d >= -(flood - 1.5))
                cov = (img[r0:r1, c0:c1][band] < 250).mean()
                if cov < 0.995:
                    sliver.append(f"#{n+1} {cov:.1%}")
            else:
                tightest = min(tightest, float(d[cell_ink].min()))
        outside = int((ink & (dist < -(flood + 1.0))).sum())
        where = f"die-cuts + {args.flood:g} in flood" if flood > 0 else "die-cuts"
        if outside > 10:
            rep.fail(f"p{i+1}: {outside} px of ink outside the {where} (margins/gutters)")
        else:
            rep.ok(f"p{i+1}: no ink outside the {where}")
        if empty:
            rep.warn(f"p{i+1}: empty label(s) {', '.join(map(str, empty))} of {len(cells)}")
        else:
            rep.ok(f"p{i+1}: all {len(cells)} labels carry art")
        if flood > 0:
            if sliver:
                rep.fail(f"p{i+1}: die-edge band not solid on {', '.join(sliver)} — white will show on drift")
            else:
                rep.ok(f"p{i+1}: die edge solid from {args.clearance:g} in inside to {args.flood:g} in outside on every label")
        elif tightest < 1e9:
            t_in = tightest / DPI
            if tightest < clear:
                rep.fail(f"p{i+1}: tightest clearance {t_in:.3f} in < {args.clearance:g} in — die-cut drift can clip it")
            else:
                rep.ok(f"p{i+1}: tightest clearance {t_in:.3f} in (need {args.clearance:g})")
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--grid", help="die-cut mode: preset name or cols,rows,w,h,left,top,pitch_x,pitch_y (in)")
    ap.add_argument("--alignment", action="store_true", help="with --grid: write an alignment test page instead of checking")
    ap.add_argument("--clearance", type=float, default=0.05, help="die-cut mode: required ink-to-edge clearance, in (0.05)")
    ap.add_argument("--flood", type=float, default=0.0, help="die-cut mode: print-to-the-edge art, background runs this far past the die (in)")
    # manual geometry for PDFs without a layout record
    ap.add_argument("--trim"); ap.add_argument("--bleed", type=float, default=0.0); ap.add_argument("--mark", type=float, default=0.0)
    ap.add_argument("--sheet"); ap.add_argument("--cols", type=int); ap.add_argument("--rows", type=int)
    ap.add_argument("--gutter", type=float, default=0.25); ap.add_argument("--rotated", action="store_true")
    ap.add_argument("--duplex", action="store_true"); ap.add_argument("--flip", default="long")
    ap.add_argument("--allow-crush", action="store_true", help="crush colors warn instead of fail")
    ap.add_argument("--source", help="booklet.py output: the original PDF, to fold the sheets in software and check reading order")
    args = ap.parse_args()
    rep = Report()
    if args.grid:
        r = grid_mode(args, rep)
        if r is not None:
            return r
        if args.pdf:
            check_crush(pikepdf.open(args.pdf), rep, args.allow_crush)
        return rep.finish()
    if not args.pdf:
        ap.error("give a PDF")
    print(os.path.basename(args.pdf))
    pdf = pikepdf.open(args.pdf)
    imposition_mode(args, pdf, rep)
    check_crush(pdf, rep, args.allow_crush)
    return rep.finish()


if __name__ == "__main__":
    sys.exit(main())
