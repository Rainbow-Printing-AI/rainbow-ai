#!/usr/bin/env python3
"""
fitpage.py — Rainbow Printing: scale art onto a fixed page with an even white margin.

For cut-apart jobs where the customer's art has to shrink to a smaller piece with white
all around it — e.g. a letter flyer run 4-up on letter and cut exactly into quarters
(4.25x5.5 pieces), each with the same white margin on all four sides after cutting.
This is the one tool that SCALES art; use it only when the job asks for that.

  * the piece is --page WxH; the art window is the page minus --margin on every side
  * the art's trim (TrimBox, else CropBox) is scaled to fit the window, never cropped
  * the art and the window almost never share an aspect ratio, so the window is
    filled on the other axis from the art's own bleed (BleedBox) — that keeps the white
    margin even without cropping any live art. If the file has too little bleed to do
    that, the run STOPS and reports the largest even margin the file allows;
    --uneven instead centers the trim at the fitted size and reports the
    (unequal) margins
  * long side of the art goes with the long side of the page (turned 90 ccw if needed)
  * vector stays vector (form XObject + clip); crush guard runs as in impose.py
  * writes a /RainbowLayout record (piece = the art window) so verify_print.py checks
    that no ink falls in the margin

Then gang it with impose.py — no gutter, so the cut lines land on the piece edges:

  fitpage.py "Ghost Lamp .pdf" --page 4.25x5.5 --margin 0.1875 --out ~/scratch/gl_fit.pdf
  impose.py ~/scratch/gl_fit.pdf --nup 4 --sheet letter --gutter 0 --out "../Ghost Lamp_4.25x5.5_4up_letter.pdf"
  verify_print.py "../Ghost Lamp_4.25x5.5_4up_letter.pdf"
"""
import argparse, json, os, sys

import pikepdf
from pikepdf import Name, Dictionary, Array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crushcheck  # noqa: E402
from impose import parse_size, fmt_size, IN, TOL  # noqa: E402
from sheetfit import inherited, matrix  # noqa: E402


def box_of(page_obj, key, clamp):
    v = inherited(page_obj, key)
    if v is None:
        return None
    x0, x1 = sorted((float(v[0]), float(v[2]))); y0, y1 = sorted((float(v[1]), float(v[3])))
    if clamp:
        x0, y0 = max(x0, clamp[0]), max(y0, clamp[1]); x1, y1 = min(x1, clamp[2]), min(y1, clamp[3])
    return [x0, y0, x1, y1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="PDF (every page is fitted to its own output page)")
    ap.add_argument("--page", required=True, help="output piece size WxH in inches, e.g. 4.25x5.5")
    ap.add_argument("--margin", type=float, required=True, help="white margin on every side, inches")
    ap.add_argument("--uneven", action="store_true",
                    help="if the bleed can't fill the window, center the trim and accept unequal margins")
    ap.add_argument("--out", help="output path (default: <stem>_<page>_fit.pdf next to the source)")
    ap.add_argument("--no-crush-fix", action="store_true", help="do not lift colors that crush to black")
    args = ap.parse_args()

    pw_in, ph_in = parse_size(args.page)
    PW, PH, M = pw_in * IN, ph_in * IN, args.margin * IN
    WW, WH = PW - 2 * M, PH - 2 * M
    if WW <= 0 or WH <= 0:
        sys.exit("STOP: margin leaves no room for art")

    src = pikepdf.open(args.source)
    n = len(src.pages)
    crush_log = []
    if not args.no_crush_fix:
        rep = crushcheck.check_pdf(src, fix=True, images="auto")
        lines, _, _ = crushcheck.summarise(rep, verbose=False)
        crush_log = [f"{os.path.basename(args.source)}: {l[6:]}" for l in lines if l.startswith("LIFT")]

    plan, stops = [], []
    for i, page in enumerate(src.pages):
        media = box_of(page.obj, "/MediaBox", None)
        crop = box_of(page.obj, "/CropBox", media) or media
        trim = box_of(page.obj, "/TrimBox", crop) or crop
        avail = box_of(page.obj, "/BleedBox", crop) or crop
        tw, th = trim[2] - trim[0], trim[3] - trim[1]
        rot = int(inherited(page.obj, "/Rotate") or 0) % 360
        turned = False
        dw, dh = (tw, th) if rot in (0, 180) else (th, tw)
        if abs(dw - dh) > TOL and (dw > dh) != (PW > PH):
            rot = (rot + 270) % 360; dw, dh = dh, dw; turned = True
        s = min(WW / dw, WH / dh)
        # bleed available beyond trim, in displayed orientation (x = across, y = up)
        bl, bb, br, bt = trim[0] - avail[0], trim[1] - avail[1], avail[2] - trim[2], avail[3] - trim[3]
        need_x, need_y = (WW / s - dw) / 2, (WH / s - dh) / 2   # source units per side
        have_x = min(bl, br) if rot in (0, 180) else min(bb, bt)
        have_y = min(bb, bt) if rot in (0, 180) else min(bl, br)
        ok = need_x <= have_x + 0.01 and need_y <= have_y + 0.01
        if ok:
            ex, ey = need_x, need_y
            win = (M, M, WW, WH)
        elif args.uneven:
            ex = ey = 0
            fw, fh = dw * s, dh * s
            win = ((PW - fw) / 2, (PH - fh) / 2, fw, fh)
        else:
            # largest even margin m with the shortfall covered: solve per axis
            best = None
            for m in [k / 1000 for k in range(0, int(min(pw_in, ph_in) * 500))]:
                ww, wh = PW - 2 * m * IN, PH - 2 * m * IN
                ss = min(ww / dw, wh / dh)
                if (ww / ss - dw) / 2 <= have_x + 0.01 and (wh / ss - dh) / 2 <= have_y + 0.01:
                    best = m
            stops.append(f"p{i+1}: trim {dw/IN:.3f}x{dh/IN:.3f} in, bleed {have_x/IN:.3f}/{have_y/IN:.3f} in "
                         f"(x/y) — needs {need_x/IN:.3f}/{need_y/IN:.3f} in at margin {args.margin} in"
                         + (f"; largest even margin this file allows: {best:.3f} in" if best is not None else ""))
            continue
        # source region shown (displayed orientation) -> map back to source coords
        if rot in (0, 180):
            rx, ry = ex, ey
        else:
            rx, ry = ey, ex
        region = (trim[0] - rx, trim[1] - ry, tw + 2 * rx, th + 2 * ry)
        plan.append(dict(i=i, region=region, rot=rot, s=s, win=win, turned=turned,
                         shown=((dw + 2 * ex) / IN, (dh + 2 * ey) / IN), trim=(dw / IN, dh / IN),
                         bleed_used=(ex / IN, ey / IN)))
    if stops:
        sys.exit("STOP: not enough bleed to keep the margin even (not cropping live art):\n  " + "\n  ".join(stops)
                 + "\n  options: a different --margin, or --uneven")

    layout = {"tool": "fitpage.py", "trim_in": [pw_in, ph_in], "bleed_in": 0, "mark_in": 0,
              "sheet_in": [pw_in, ph_in], "cols": 1, "rows": 1, "gutter_in": 0, "duplex": False, "flip": None,
              "sheets": [], "crush_fix": not args.no_crush_fix, "crush_lifted": crush_log}
    new = []
    for p in plan:
        page = src.pages[p["i"]]
        x0, y0, w, h = p["region"]
        form = page.as_form_xobject(handle_transformations=False)
        form.BBox = Array([x0, y0, x0 + w, y0 + h])
        a, b, c, d, e, f = matrix(p["rot"], x0, y0, w, h, 0, 0)
        wx, wy, ww, wh = p["win"]
        s = p["s"]
        cs = (f"q {wx:.4f} {wy:.4f} {ww:.4f} {wh:.4f} re W n "
              f"{s:.6f} 0 0 {s:.6f} {wx:.4f} {wy:.4f} cm "
              f"{a:g} {b:g} {c:g} {d:g} {e:.4f} {f:.4f} cm /Pg Do Q\n").encode()
        np_ = src.make_indirect(Dictionary(Type=Name.Page, MediaBox=Array([0, 0, PW, PH]),
                                           Resources=Dictionary(XObject=Dictionary(Pg=form)),
                                           Contents=src.make_stream(cs)))
        new.append(np_)
        layout["sheets"].append({"side": "front", "pieces": [{"trim": [wx, wy, ww, wh], "label": None,
                                 "src_page": p["i"] + 1, "size_in": [round(ww / IN, 3), round(wh / IN, 3)]}]})
    for np_ in new:
        src.pages.append(pikepdf.Page(np_))
    del src.pages[0:n]
    with src.open_outline() as ol:
        ol.root.clear()

    stem = os.path.splitext(os.path.basename(args.source))[0].strip()
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.source)),
                                   f"{stem}_{fmt_size(pw_in, ph_in)}_fit.pdf")
    src.docinfo["/RainbowLayout"] = json.dumps(layout)
    src.docinfo["/Producer"] = "Rainbow fitpage.py"
    src.docinfo["/Title"] = os.path.splitext(os.path.basename(out))[0]
    src.save(out, linearize=True)

    print(f"wrote {out}")
    for p in plan:
        wx, wy, ww, wh = p["win"]
        print(f"  p{p['i']+1}: trim {p['trim'][0]:.3f}x{p['trim'][1]:.3f} in scaled {p['s']*100:.2f}% "
              f"-> art {ww/IN:.4f}x{wh/IN:.4f} in on {fmt_size(pw_in, ph_in)}"
              + (" (turned 90 ccw, long side to long side)" if p["turned"] else ""))
        print(f"      margins L {wx/IN:.4f}  R {(PW-wx-ww)/IN:.4f}  B {wy/IN:.4f}  T {(PH-wy-wh)/IN:.4f} in")
        if p["bleed_used"][0] > 0.0005 or p["bleed_used"][1] > 0.0005:
            print(f"      window filled from the file's bleed: {p['bleed_used'][0]:.3f} in L/R, "
                  f"{p['bleed_used'][1]:.3f} in T/B per side (source scale) — no live art cropped")
    if crush_log:
        print(f"  >>> TELL ANDREW crush guard: {len(crush_log)} color(s) lifted (hue kept):")
        for l in crush_log:
            print(f"    {l}")


if __name__ == "__main__":
    main()
