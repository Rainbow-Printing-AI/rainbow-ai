#!/usr/bin/env python3
"""
sheetfit.py — Rainbow Printing: every page at actual size on one fixed sheet.

For plan sets, mixed-size scans and document packets that have to run on one stock
(e.g. a set of 11x17 drawings mixed with letter-size scans, all printed 11x17).
Each source page is placed 1-up at 100% — never scaled, never cropped — centered on
the output sheet. No bleed, no crop marks. Pages already at the sheet size fill it.

  * --rotate fixes pages that are sideways or upside down. Degrees clockwise, on top of
    the page's own /Rotate, as "pages:degrees" groups separated by ';':
        --rotate "3-5,11-18:270; 63-66:90; 96:180"
    Judge orientation by eye from a render (tesseract OSD is unreliable on drawings).
  * --match-sheet turns every page whose orientation differs from the sheet 90 ccw, so
    every page runs long side to long side (portrait pages go sideways on a landscape sheet).
  * a page that doesn't fit the sheet upright but fits turned 90 is turned 90 CCW
    (long side to long side) and reported. A page larger than the sheet either way
    stops the run: nothing is scaled — the measured size is reported.
  * vector stays vector: each page is placed as a form XObject. Bookmarks are kept.
  * crush guard runs exactly as in impose.py (--no-crush-fix disables it).
  * writes a /RainbowLayout record (bleed 0, marks 0, one piece per sheet = the placed
    page) so verify_print.py checks the page box, that no ink falls outside the placed
    page, and crush colors.

Output: <stem>_actual_1up_<sheet>.pdf next to the source, or --out.

  sheetfit.py "Main Level Elevations_combined.pdf" --sheet tabloid --landscape
  sheetfit.py plans.pdf --sheet tabloid --landscape --rotate "2,4:90; 7:180"
  python3 verify_print.py "Main Level Elevations_combined_actual_1up_17x11.pdf"
"""
import argparse, json, os, sys

import pikepdf
from pikepdf import Name, Dictionary, Array, OutlineItem

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crushcheck  # noqa: E402
from impose import parse_size, fmt_size, IN, TOL  # noqa: E402


def inherited(page_obj, key):
    o = page_obj
    while o is not None:
        if key in o:
            return o[key]
        o = o.get("/Parent")
    return None


def parse_rotate(spec, npages):
    """'3-5,11:270; 7:180' -> {page_index0: degrees_cw}"""
    out = {}
    if not spec:
        return out
    for group in spec.split(";"):
        group = group.strip()
        if not group:
            continue
        try:
            pages, deg = group.rsplit(":", 1)
            deg = int(deg) % 360
            assert deg in (0, 90, 180, 270)
        except Exception:
            sys.exit(f"--rotate: bad group '{group}' — use 'pages:degrees', degrees 90/180/270 clockwise")
        for part in pages.split(","):
            a, _, b = part.strip().partition("-")
            lo, hi = int(a), int(b or a)
            for p in range(lo, hi + 1):
                if not 1 <= p <= npages:
                    sys.exit(f"--rotate: page {p} out of range (1-{npages})")
                if p - 1 in out:
                    sys.exit(f"--rotate: page {p} listed twice")
                out[p - 1] = deg
    return out


def matrix(rot, x0, y0, w, h, ox, oy):
    """cm that draws box (x0,y0,w,h) rotated `rot` degrees clockwise with its displayed
    lower-left corner at (ox, oy)."""
    a, b, c, d, e, f = {0: (1, 0, 0, 1, 0, 0),
                        90: (0, -1, 1, 0, 0, w),
                        180: (-1, 0, 0, -1, w, h),
                        270: (0, 1, -1, 0, h, 0)}[rot]
    # pre-translate (-x0,-y0), post-translate (ox,oy)
    e2 = a * -x0 + c * -y0 + e + ox
    f2 = b * -x0 + d * -y0 + f + oy
    return a, b, c, d, e2, f2


def outline_entries(pdf, index_of):
    """Flatten the outline to [(depth, title, page_index)]."""
    res = []
    with pdf.open_outline() as ol:
        def walk(items, depth):
            for it in items:
                idx = None
                dest = it.destination
                if dest is None and it.action is not None and it.action.get("/S") == Name.GoTo:
                    dest = it.action.get("/D")
                if isinstance(dest, Array) and len(dest) and isinstance(dest[0], Dictionary):
                    idx = index_of.get(dest[0].objgen)
                elif isinstance(dest, int):
                    idx = dest
                res.append((depth, it.title, idx))
                walk(it.children, depth + 1)
        walk(ol.root, 0)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="PDF")
    ap.add_argument("--sheet", required=True, help="output sheet: tabloid, letter, 12x18, 13x19, WxH (in)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--landscape", action="store_true", help="sheet long side horizontal")
    g.add_argument("--portrait", action="store_true", help="sheet long side vertical")
    ap.add_argument("--match-sheet", action="store_true",
                    help="turn every page whose orientation differs from the sheet 90 ccw (long side to long side; "
                         "portrait pages end up sideways on a landscape sheet)")
    ap.add_argument("--rotate", help="pages to turn, clockwise: \"3-5,11:270; 63-66:90; 96:180\"")
    ap.add_argument("--out", help="output path (default: <stem>_actual_1up_<sheet>.pdf next to the source)")
    ap.add_argument("--no-crush-fix", action="store_true",
                    help="do not lift colors that crush to black on the Versant (see crushcheck.py / press.json)")
    args = ap.parse_args()

    sw_in, sh_in = parse_size(args.sheet)
    if args.landscape and sw_in < sh_in or args.portrait and sw_in > sh_in:
        sw_in, sh_in = sh_in, sw_in
    SW, SH = sw_in * IN, sh_in * IN

    src = pikepdf.open(args.source)
    n = len(src.pages)
    extra = parse_rotate(args.rotate, n)
    index_of = {p.obj.objgen: i for i, p in enumerate(src.pages)}
    outline = outline_entries(src, index_of)

    crush_log = []
    if not args.no_crush_fix:
        rep = crushcheck.check_pdf(src, fix=True, images="auto")
        lines, _, _ = crushcheck.summarise(rep, verbose=False)
        crush_log = [f"{os.path.basename(args.source)}: {l[6:]}" for l in lines if l.startswith("LIFT")]

    # --- measure every page first; stop before writing anything if one won't fit
    plan, too_big, turned, matched = [], [], [], []
    for i, page in enumerate(src.pages):
        mb = [float(v) for v in inherited(page.obj, "/MediaBox")]
        cb = inherited(page.obj, "/CropBox")
        box = [float(v) for v in cb] if cb is not None else mb
        x0, x1 = sorted((box[0], box[2])); y0, y1 = sorted((box[1], box[3]))
        mx0, mx1 = sorted((mb[0], mb[2])); my0, my1 = sorted((mb[1], mb[3]))
        x0, y0, x1, y1 = max(x0, mx0), max(y0, my0), min(x1, mx1), min(y1, my1)   # crop ∩ media
        w, h = x1 - x0, y1 - y0
        own = int(inherited(page.obj, "/Rotate") or 0) % 360
        rot = (own + extra.get(i, 0)) % 360
        dw, dh = (w, h) if rot in (0, 180) else (h, w)
        if args.match_sheet and abs(dw - dh) > TOL and (dw > dh) != (SW > SH):
            rot = (rot + 270) % 360
            dw, dh = dh, dw
            matched.append(i + 1)
        if not (dw <= SW + TOL and dh <= SH + TOL):
            if dh <= SW + TOL and dw <= SH + TOL:
                rot = (rot + 270) % 360
                dw, dh = dh, dw
                turned.append(i + 1)
            else:
                too_big.append(f"p{i+1} {dw/IN:.3f}x{dh/IN:.3f} in")
                continue
        ox, oy = max((SW - dw) / 2, 0), max((SH - dh) / 2, 0)
        plan.append(dict(i=i, box=(x0, y0, w, h), rot=rot, fix=extra.get(i, 0), disp=(dw, dh), at=(ox, oy)))
    if too_big:
        sys.exit(f"STOP: {len(too_big)} page(s) larger than the {fmt_size(sw_in, sh_in)} sheet either way "
                 f"(not scaling): {', '.join(too_big)}")

    # --- build the new sheets inside the source document, then drop the old pages
    layout = {"tool": "sheetfit.py", "trim_in": [sw_in, sh_in], "bleed_in": 0, "mark_in": 0,
              "sheet_in": [sw_in, sh_in], "cols": 1, "rows": 1, "gutter_in": 0, "duplex": False, "flip": None,
              "sheets": [], "crush_fix": not args.no_crush_fix, "crush_lifted": crush_log}
    new = []
    for p in plan:
        page = src.pages[p["i"]]
        x0, y0, w, h = p["box"]
        form = page.as_form_xobject(handle_transformations=False)
        form.BBox = Array([x0, y0, x0 + w, y0 + h])
        a, b, c, d, e, f = matrix(p["rot"], x0, y0, w, h, *p["at"])
        cs = f"q {a:g} {b:g} {c:g} {d:g} {e:.4f} {f:.4f} cm /Pg Do Q\n".encode()
        np_ = src.make_indirect(Dictionary(Type=Name.Page, MediaBox=Array([0, 0, SW, SH]),
                                           Resources=Dictionary(XObject=Dictionary(Pg=form)),
                                           Contents=src.make_stream(cs)))
        new.append(np_)
        dw, dh = p["disp"]
        layout["sheets"].append({"side": "front", "pieces": [{"trim": [p["at"][0], p["at"][1], dw, dh], "label": None,
                                 "src_page": p["i"] + 1, "size_in": [round(dw / IN, 3), round(dh / IN, 3)],
                                 "rotate_fix": p["fix"]}]})
    for np_ in new:
        src.pages.append(pikepdf.Page(np_))
    del src.pages[0:n]

    with src.open_outline() as ol:
        ol.root.clear()
        stack = [(-1, ol.root)]
        for depth, title, idx in outline:
            item = OutlineItem(title, idx if idx is not None else 0)
            while stack[-1][0] >= depth:
                stack.pop()
            stack[-1][1].append(item) if stack[-1][0] == -1 else stack[-1][1].children.append(item)
            stack.append((depth, item))

    stem = os.path.splitext(os.path.basename(args.source))[0]
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.source)),
                                   f"{stem}_actual_1up_{fmt_size(sw_in, sh_in)}.pdf")
    src.docinfo["/RainbowLayout"] = json.dumps(layout)
    src.docinfo["/Producer"] = "Rainbow sheetfit.py"
    src.docinfo["/Title"] = os.path.splitext(os.path.basename(out))[0]
    src.save(out, linearize=True)

    full = sum(1 for p in plan if abs(p["disp"][0] - SW) <= TOL and abs(p["disp"][1] - SH) <= TOL)
    print(f"wrote {out}")
    print(f"  sheet {fmt_size(sw_in, sh_in)} in, {len(plan)} page(s), 100% — no bleed, no marks")
    print(f"  {full} page(s) already sheet size; {len(plan) - full} smaller page(s) centered at actual size")
    sizes = {}
    for p in plan:
        k = f"{p['disp'][0]/IN:.2f}x{p['disp'][1]/IN:.2f}"
        sizes.setdefault(k, []).append(p["i"] + 1)
    for k, v in sorted(sizes.items(), key=lambda kv: -len(kv[1])):
        print(f"    {k} in: {len(v)} page(s)")
    fixed = sorted((p["i"] + 1, p["fix"]) for p in plan if p["fix"])
    if fixed:
        by = {}
        for pg, deg in fixed:
            by.setdefault(deg, []).append(pg)
        for deg, pgs in sorted(by.items()):
            print(f"  turned {deg} cw: {len(pgs)} page(s) — {pgs}")
    if turned:
        print(f"  turned 90 ccw to fit the sheet: {turned}")
    if matched:
        print(f"  turned 90 ccw to match the sheet orientation (--match-sheet): {matched}")
    if crush_log:
        print(f"  crush guard: {len(crush_log)} color(s) too dark for the Versant to show a hue were lifted (hue kept):")
        for l in crush_log:
            print(f"    {l}")
        print("  >>> TELL ANDREW: colors were changed in this file (list above). Always report every lift. <<<")
    elif not args.no_crush_fix:
        print("  crush guard: no color will crush to black")
    else:
        print("  crush guard OFF (--no-crush-fix) — verify_print.py will flag any crush color")
    print(f"  next: python3 verify_print.py \"{out}\"")


if __name__ == "__main__":
    main()
