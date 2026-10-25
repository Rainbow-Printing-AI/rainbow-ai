#!/usr/bin/env python3
"""
booklet.py — Rainbow Printing: saddle-stitch booklet imposition.
Print duplex, fold the stack in half, staple on the fold. No trim, no bleed, no crop marks.

Two reading pages per side of every sheet, in printer spreads, so the folded stack nests
into reading order. Output sheet 1 (PDF pages 1-2) is the outside/cover sheet; its front
carries the front and back covers.

  --binding side  (default) portrait booklet: sheet runs landscape, panels left/right, fold
                  and staples on the left of the reading page (letter -> 5.5x8.5 pages).
  --binding top   landscape / calendar booklet: sheet runs portrait, panels top/bottom, fold
                  and staples along the TOP of the reading page (letter -> 8.5x5.5 pages);
                  each leaf flips up over the fold.

Scale
  default         every page at 100%, centered in its panel; stops if a page is bigger.
  --fit           every page scaled to the largest size that fits its panel (aspect kept,
                  never cropped), centered. --margin IN keeps that much white inside each
                  panel edge first (e.g. 0.125 to stay clear of the press's edge erase).

Page count must be a multiple of 4. If it isn't, the script stops and says how many blanks
are needed — ask where they go, then pass --blanks:
  --blanks end          blanks after the last page (inside back / back cover end up blank)
  --blanks after-cover  first blank right after page 1 (blank inside front), the rest at the end
  --blanks "2,23,24"    exact booklet page numbers to leave blank

Page order: reading order = source order, unless --order lists it — source page numbers and
ranges, "b" for a blank, e.g. to keep a customer's spreads and drop pages:
  --order "1,2,5,6,9,b"      (pages not listed are left out; listed twice = printed twice)
--blanks still pads the end (or wherever) if the --order count isn't a multiple of 4.

Duplex: --flip long (default — Fiery "Top-Top" on a portrait sheet) or --flip short: the paper
edge the sheet turns over on. Panels that must land head-to-foot are drawn 180 in the PDF, so
some sides look upside-down on screen — that is correct for the flip named in the output.
Print with exactly that flip.

Vector stays vector (each page is placed as a form XObject); crush guard runs as in impose.py;
a page whose orientation doesn't match its panel is placed as-is and reported.
Writes a /RainbowLayout record. verify_print.py then checks the page box, ink only inside the
placed pages, planned blanks empty, duplex backing, and — given the source — rebuilds the
folded booklet from the rendered sheets and checks every reading page (order + upright).

Output: <stem>_<page>_booklet<N>pp_<sheet>_duplex.pdf next to the source, or --out.

  booklet.py Jefferies_Oct2026.pdf --binding top --fit --blanks end
  verify_print.py Jefferies_Oct2026_8.5x5.5_booklet24pp_letter_duplex.pdf --source Jefferies_Oct2026.pdf
"""
import argparse, json, os, sys

import pikepdf
from pikepdf import Name, Dictionary, Array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crushcheck  # noqa: E402
from impose import parse_size, fmt_size, sheet_name, IN, TOL  # noqa: E402
from sheetfit import inherited, matrix  # noqa: E402


def page_geometry(page):
    """crop ∩ media box (x0, y0, w, h) in points, and the page's own /Rotate (cw)."""
    mb = [float(v) for v in inherited(page.obj, "/MediaBox")]
    cb = inherited(page.obj, "/CropBox")
    box = [float(v) for v in cb] if cb is not None else mb
    x0, x1 = sorted((box[0], box[2])); y0, y1 = sorted((box[1], box[3]))
    mx0, mx1 = sorted((mb[0], mb[2])); my0, my1 = sorted((mb[1], mb[3]))
    x0, y0, x1, y1 = max(x0, mx0), max(y0, my0), min(x1, mx1), min(y1, my1)
    return (x0, y0, x1 - x0, y1 - y0), int(inherited(page.obj, "/Rotate") or 0) % 360


def plan_blanks(n_src, spec):
    """-> sorted list of booklet page numbers left blank (total = n_src + len)."""
    need = (-n_src) % 4
    if spec is None:
        if need:
            sys.exit(f"STOP: {n_src} pages is not a multiple of 4 — a saddle-stitch booklet needs {need} blank "
                     f"page(s) to make {n_src + need}. Ask where they go, then rerun with "
                     f"--blanks end | after-cover | \"page,page,...\"")
        return []
    if spec == "end":
        return list(range(n_src + 1, n_src + need + 1))
    if spec == "after-cover":
        if not need:
            return []
        total = n_src + need
        return [2] + list(range(total - need + 2, total + 1))
    try:
        blanks = sorted({int(v) for v in spec.split(",") if v.strip()})
    except ValueError:
        sys.exit(f"--blanks: '{spec}' — use end, after-cover, or booklet page numbers like \"2,23,24\"")
    total = n_src + len(blanks)
    if total % 4:
        sys.exit(f"--blanks {spec}: {n_src} pages + {len(blanks)} blank(s) = {total}, not a multiple of 4 "
                 f"(need {need} or {need + 4} blanks)")
    bad = [b for b in blanks if not 1 <= b <= total]
    if bad:
        sys.exit(f"--blanks: page(s) {bad} outside 1-{total}")
    return blanks


def parse_order(spec, n_src):
    """'1,2,5,3-4,b' -> [0, 1, 4, 2, 3, None] (0-based source pages, None = blank)."""
    out = []
    for part in spec.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part in ("b", "blank"):
            out.append(None)
            continue
        a, _, b = part.partition("-")
        try:
            lo, hi = int(a), int(b or a)
        except ValueError:
            sys.exit(f"--order: bad item '{part}' — use page numbers, ranges like 3-4, or b for a blank")
        step = 1 if hi >= lo else -1
        for pg in range(lo, hi + step, step):
            if not 1 <= pg <= n_src:
                sys.exit(f"--order: page {pg} out of range (source has {n_src})")
            out.append(pg - 1)
    if not out:
        sys.exit("--order is empty")
    return out


def sheet_slots(k, n):
    """Booklet pages on sheet k (0 = outside) of an n-page booklet:
    a = outside leaf-1 (cover side), b = its inside, c = inside leaf-2, d = outside leaf-2."""
    a, b, c, d = 2 * k + 1, 2 * k + 2, n - 2 * k - 1, n - 2 * k
    return a, b, c, d


def slots_for(k, n, flip_axis_vertical, binding):
    """Front/back slot contents for sheet k. Derived from folding: outside face = front
    (covers on it), inside face = back; reading pages upright when the sheet turns over on
    the axis that leaves the fold edge in place (or rotated 180 when it doesn't)."""
    a, b, c, d = sheet_slots(k, n)
    front = [(d, 0), (a, 0)]
    # The back reads straight (no 180) when the sheet turns over on an axis parallel to the fold:
    #   top binding  (fold horizontal) -> short-edge flip of a portrait sheet
    #   side binding (fold vertical)   -> short-edge flip of a landscape sheet
    # A long-edge flip turns the back head-to-foot, so its panels are drawn 180 and swapped.
    fold_vertical = binding == "side"
    straight = flip_axis_vertical == fold_vertical
    back = [(b, 0), (c, 0)] if straight else [(c, 180), (b, 180)]
    return front, back


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="PDF, pages in reading order")
    ap.add_argument("--binding", choices=["side", "top"], default="side",
                    help="side = portrait booklet stapled on the left (default); top = landscape/calendar booklet stapled along the top")
    ap.add_argument("--sheet", default="letter", help="press sheet, folded in half: letter (default), tabloid, 12x18, WxH")
    ap.add_argument("--fit", action="store_true", help="scale every page to the largest size that fits its panel (aspect kept)")
    ap.add_argument("--margin", type=float, default=0.0, help="with --fit: white kept inside every panel edge, in (default 0)")
    ap.add_argument("--blanks", help="where blank pages go when the count isn't a multiple of 4: end | after-cover | \"2,23,24\"")
    ap.add_argument("--order", help="reading order as source pages/ranges, b = blank: \"1,2,5,3-4,b\" (default: source order)")
    ap.add_argument("--flip", choices=["long", "short"], default="long", help="paper edge the duplex turns over on (default long)")
    ap.add_argument("--out", help="output path (default: next to the source)")
    ap.add_argument("--no-crush-fix", action="store_true",
                    help="do not lift colors that crush to black on the Versant (see crushcheck.py / press.json)")
    args = ap.parse_args()
    if args.margin and not args.fit:
        sys.exit("--margin only applies with --fit")

    sw_in, sh_in = parse_size(args.sheet)
    sw_in, sh_in = sorted((sw_in, sh_in))                      # portrait
    if args.binding == "side":
        sw_in, sh_in = sh_in, sw_in                            # landscape, fold vertical
        pw_in, ph_in = sw_in / 2, sh_in
    else:
        pw_in, ph_in = sw_in, sh_in / 2                        # portrait, fold horizontal
    SW, SH, PW, PH = sw_in * IN, sh_in * IN, pw_in * IN, ph_in * IN
    flip_axis_vertical = (args.flip == "long") == (sh_in > sw_in)
    if args.binding == "side":
        panels = [(0, 0), (PW, 0)]                             # slot 0 left, slot 1 right
    else:
        panels = [(0, PH), (0, 0)]                             # slot 0 top, slot 1 bottom

    src = pikepdf.open(args.source)
    n_src = len(src.pages)
    order = parse_order(args.order, n_src) if args.order else list(range(n_src))
    pad = plan_blanks(len(order), args.blanks)
    n = len(order) + len(pad)
    seq, it = {}, iter(order)
    for p in range(1, n + 1):
        seq[p] = None if p in pad else next(it)
    blanks = [p for p in range(1, n + 1) if seq[p] is None]
    used = [i for i in seq.values() if i is not None]
    left_out = [i + 1 for i in range(n_src) if i not in used]
    twice = sorted({i + 1 for i in used if used.count(i) > 1})

    crush_log = []
    if not args.no_crush_fix:
        rep = crushcheck.check_pdf(src, fix=True, images="auto")
        lines, _, _ = crushcheck.summarise(rep, verbose=False)
        crush_log = [f"{os.path.basename(args.source)}: {l[6:]}" for l in lines if l.startswith("LIFT")]

    # measure every page; stop before writing if one won't fit at 100%
    geo, too_big, mismatch, scales = {}, [], [], {}
    m = args.margin * IN
    for i, page in enumerate(src.pages):
        (x0, y0, w, h), own = page_geometry(page)
        dw, dh = (w, h) if own in (0, 180) else (h, w)
        if args.fit:
            s = min((PW - 2 * m) / dw, (PH - 2 * m) / dh)
        else:
            s = 1.0
            if dw > PW + TOL or dh > PH + TOL:
                too_big.append(f"p{i+1} {dw/IN:.3f}x{dh/IN:.3f} in")
        if abs(dw - dh) > TOL and (dw > dh) != (PW > PH):
            mismatch.append(i + 1)
        geo[i] = (x0, y0, w, h, own, dw, dh)
        scales[i] = s
    if too_big:
        sys.exit(f"STOP: {len(too_big)} page(s) larger than the {fmt_size(pw_in, ph_in)} in panel at 100% "
                 f"(not scaling without --fit): {', '.join(too_big)}")

    layout = {"tool": "booklet.py", "trim_in": [pw_in, ph_in], "bleed_in": 0, "mark_in": 0,
              "sheet_in": [sw_in, sh_in], "cols": 2 if args.binding == "side" else 1,
              "rows": 1 if args.binding == "side" else 2, "gutter_in": 0, "duplex": True, "flip": args.flip,
              "booklet": {"binding": args.binding, "pages": n, "src_pages": n_src, "blank_pages": blanks,
                          "order": [None if seq[p] is None else seq[p] + 1 for p in range(1, n + 1)],
                          "fit": args.fit, "margin_in": args.margin, "source": os.path.basename(args.source)},
              "sheets": [], "crush_fix": not args.no_crush_fix, "crush_lifted": crush_log}
    forms = {}
    new_pages, order_lines = [], []
    for k in range(n // 4):
        front, back = slots_for(k, n, flip_axis_vertical, args.binding)
        desc = []
        for side, slots in (("front", front), ("back", back)):
            res, cs, pieces, tags = Dictionary(), [], [], []
            for slot, (bp, rot) in enumerate(slots):
                pxo, pyo = panels[slot]
                i = seq[bp]
                tags.append(("-" if i is None else str(bp)) + ("↻" if rot == 180 and i is not None else ""))
                if i is None:
                    pieces.append({"trim": [pxo, pyo, PW, PH], "label": None, "src_page": None,
                                   "booklet_page": bp, "blank": True, "rotate": 0, "scale": None})
                    continue
                x0, y0, w, h, own, dw, dh = geo[i]
                s = scales[i]
                if i not in forms:
                    f = src.pages[i].as_form_xobject(handle_transformations=False)
                    f.BBox = Array([x0, y0, x0 + w, y0 + h])
                    forms[i] = f
                a, b, c, d, e, f_ = matrix((own + rot) % 360, x0, y0, w, h, 0, 0)
                ox, oy = pxo + (PW - dw * s) / 2, pyo + (PH - dh * s) / 2
                nm = f"/P{slot}"
                res[nm] = forms[i]
                cs.append(f"q {a*s:.6f} {b*s:.6f} {c*s:.6f} {d*s:.6f} {e*s+ox:.4f} {f_*s+oy:.4f} cm {nm} Do Q")
                pieces.append({"trim": [ox, oy, dw * s, dh * s], "label": None, "src_page": i + 1,
                               "booklet_page": bp, "blank": False, "rotate": rot, "scale": round(s, 6)})
            pg = src.make_indirect(Dictionary(Type=Name.Page, MediaBox=Array([0, 0, SW, SH]),
                                              Resources=Dictionary(XObject=res),
                                              Contents=src.make_stream(("\n".join(cs) + "\n").encode())))
            new_pages.append(pg)
            layout["sheets"].append({"side": side, "pieces": pieces})
            desc.append(f"{side[0].upper()}[{tags[0]}|{tags[1]}]")
        order_lines.append(f"sheet {k+1}: " + "  ".join(desc))

    for pg in new_pages:
        src.pages.append(pikepdf.Page(pg))
    del src.pages[0:n_src]
    for key in ("/Outlines", "/PageLabels", "/StructTreeRoot", "/MarkInfo", "/OpenAction", "/Names"):
        if key in src.Root:
            del src.Root[key]

    stem = os.path.splitext(os.path.basename(args.source))[0]
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.source)),
                                   f"{stem}_{fmt_size(pw_in, ph_in)}_booklet{n}pp_{sheet_name(sw_in, sh_in)}_duplex.pdf")
    src.docinfo["/RainbowLayout"] = json.dumps(layout)
    src.docinfo["/Producer"] = "Rainbow booklet.py"
    src.docinfo["/Title"] = os.path.splitext(os.path.basename(out))[0]
    src.save(out, linearize=True)

    fold = "top of the page" if args.binding == "top" else "left of the page"
    print(f"wrote {out}")
    print(f"  {len(used)} page(s)" + (f" + {len(blanks)} blank(s) at booklet p{', p'.join(map(str, blanks))}" if blanks else "")
          + f" = {n} pp on {n // 4} sheet(s) of {sheet_name(sw_in, sh_in)} ({fmt_size(sw_in, sh_in)} in)")
    if args.order:
        rd = [("b" if seq[p] is None else str(seq[p] + 1)) for p in range(1, n + 1)]
        spreads = [rd[0]] + [f"{rd[i]}/{rd[i+1]}" for i in range(1, n - 1, 2)] + [rd[-1]]
        print(f"  reading order (source pages; spreads shown a/b): {' | '.join(spreads)}")
        if left_out:
            print(f"  left out (not in --order): source p{', p'.join(map(str, left_out))}")
        if twice:
            print(f"  WARN printed more than once: source p{', p'.join(map(str, twice))}")
    print(f"  binding {args.binding}: finished {fmt_size(pw_in, ph_in)} in, fold + staples along the {fold}")
    ss = sorted(set(round(v, 4) for v in scales.values()))
    if args.fit:
        szs = sorted({f"{geo[i][5]/IN:g}x{geo[i][6]/IN:g} -> {geo[i][5]*scales[i]/IN:.3f}x{geo[i][6]*scales[i]/IN:.3f} in"
                      for i in geo})
        print(f"  scale: fit to panel" + (f" with {args.margin:g} in margin" if args.margin else "")
              + f" — {', '.join(f'{v*100:.2f}%' for v in ss)} ({'; '.join(szs)}), centered")
    else:
        print("  scale: 100%, centered in each panel")
    print(f"  duplex: flip on the {args.flip.upper()} edge"
          + (" (Fiery Top-Top on this portrait sheet)" if args.flip == "long" and sh_in > sw_in else "")
          + ". Panels marked ↻ are drawn 180 — correct for this flip.")
    print("  printer spreads, front | back (booklet page numbers, - = blank):")
    for l in order_lines:
        print(f"    {l}")
    if mismatch:
        print(f"  WARN orientation differs from the {fmt_size(pw_in, ph_in)} panel (placed as-is): pages {mismatch}")
    if crush_log:
        print(f"  crush guard: {len(crush_log)} color(s) too dark for the Versant to show a hue were lifted (hue kept):")
        for l in crush_log:
            print(f"    {l}")
        print("  >>> TELL ANDREW: colors were changed in this file (list above). Always report every lift. <<<")
    elif not args.no_crush_fix:
        print("  crush guard: no color will crush to black")
    print(f"  next: python3 verify_print.py \"{out}\" --source \"{args.source}\"")


if __name__ == "__main__":
    main()
