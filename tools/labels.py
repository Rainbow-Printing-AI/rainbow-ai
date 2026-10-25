#!/usr/bin/env python3
"""
labels.py — place one piece of raster art on every label of an Avery die-cut sheet.

Uses the die-cut presets in verify_print.py (--grid), so the layout and the check
share one set of numbers.  Art is centered on each die-cut, aspect-fit (never
stretched) into --art-size (default: the label size), long side to long side.
Round presets clip to the circle.

Print-to-the-edge art (solid background to the die): pass --bleed 0.1.  Each label is
then clipped to the die grown by the bleed and the gap between the art box and the
bleed edge is flooded with --fill (default "auto" = the art's border color, which must
be a flat color).  Verify with:  verify_print.py OUT --grid PRESET --flood 0.1

Output page is exactly 8.5x11 in, no marks.  Default output name, next to the source:
  <source stem>_<preset>_<N>up_letter.pdf

  labels.py logo.png --grid avery22877 --bleed 0.1
  labels.py badge.jpg --grid avery8395 --art-size 3x2
  labels.py sticker.png --grid avery22877 --art-size 1.8 --bleed 0.1 --fill "#233622"

Raster sources only (png/jpg/tif).  A vector PDF: impose.py --no-marks, or extend this.
"""
import argparse, os, sys
from collections import Counter

import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_print import GRIDS, parse_grid, label_cells  # noqa: E402
import crushcheck  # noqa: E402

IN = 72.0
SHEET = (8.5, 11.0)


def border_color(im, tol=8):
    a = np.asarray(im.convert("RGB")).astype(int)
    ring = np.concatenate([a[:3].reshape(-1, 3), a[-3:].reshape(-1, 3),
                           a[:, :3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)])
    mode = np.array(Counter(map(tuple, ring)).most_common(1)[0][0])
    share = (np.abs(ring - mode).max(1) <= tol).mean()
    return tuple(int(v) for v in mode), share


def parse_size(s, default):
    if not s:
        return default
    if "x" in s.lower():
        w, h = s.lower().split("x")
        return float(w), float(h)
    return float(s), float(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--grid", required=True, help=f"preset ({', '.join(sorted(GRIDS))}) or cols,rows,w,h,left,top,pitch_x,pitch_y[,round]")
    ap.add_argument("--art-size", help="box the art is fit into, inches W[xH] (default: label size)")
    ap.add_argument("--bleed", type=float, default=0.0, help="flood past the die, inches (0 = clip at the die / white-background art)")
    ap.add_argument("--fill", default="auto", help='bleed flood: auto (art border color), none, or "#rrggbb"')
    ap.add_argument("--count", type=int, help="fill only the first N labels")
    ap.add_argument("--out")
    ap.add_argument("--no-crush-fix", action="store_true", help="do not lift colors that crush to black on the Versant")
    a = ap.parse_args()

    g = parse_grid(a.grid)
    cells = list(label_cells(g))
    lw, lh = g[2], g[3]
    im = Image.open(a.source)
    if im.mode not in ("RGB", "L", "CMYK"):
        im = im.convert("RGB")
    if im.mode == "RGB" and not a.no_crush_fix:
        im, _share, flats = crushcheck.fix_pil(im)
        if flats:
            print("crush guard: flat color(s) too dark for the Versant to show a hue — lifted, hue kept: "
                  + ", ".join(f"{h} L*{L:.0f} ({s:.0%})" for h, L, s in flats))
            print(">>> TELL ANDREW: colors were changed in this file (above). Always report every lift. <<<")
    pw, ph = im.size
    bw, bh = parse_size(a.art_size, (lw, lh))
    if (pw >= ph) != (bw >= bh) and abs(pw - ph) > 1 and abs(bw - bh) > 1e-6:
        im = im.rotate(90, expand=True); pw, ph = im.size
        print("rotated art 90° (long side to long side)")
    scale = min(bw / pw, bh / ph)            # inches per pixel
    aw, ah = pw * scale, ph * scale
    print(f"art {pw}x{ph}px -> {aw:.3f}x{ah:.3f} in on each label = {1/scale:.0f} ppi effective")
    if 1 / scale < 250:
        print(f"WARN  {1/scale:.0f} ppi — soft at label size")

    fill = None
    if a.bleed > 0 and a.fill != "none":
        if a.fill == "auto":
            fill, share = border_color(im)
            if share < 0.97:
                sys.exit(f"art border is not a flat color ({share:.0%} match) — pass --fill '#rrggbb' or --fill none")
            print(f"bleed flood rgb{fill} (matches {share:.1%} of the art border)")
        else:
            h = a.fill.lstrip("#"); fill = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    stem = os.path.splitext(os.path.basename(a.source))[0]
    tag = a.grid if a.grid.lower() in GRIDS else "custom"
    n = min(a.count or len(cells), len(cells))
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.source)), f"{stem}_{tag}_{n}up_letter.pdf")
    c = canvas.Canvas(out, pagesize=(SHEET[0] * IN, SHEET[1] * IN))
    c.setTitle(f"{stem} — {tag} {n}-up")
    reader = ImageReader(im)
    b = a.bleed
    for (x, yt, w, h, shape) in cells[:n]:
        cx, cy = (x + w / 2) * IN, (SHEET[1] - yt - h / 2) * IN
        c.saveState()
        p = c.beginPath()
        if shape == "round":
            p.circle(cx, cy, (w / 2 + b) * IN)
        else:
            p.rect((x - b) * IN, (SHEET[1] - yt - h - b) * IN, (w + 2 * b) * IN, (h + 2 * b) * IN)
        c.clipPath(p, stroke=0, fill=0)
        if fill:
            c.setFillColorRGB(*(v / 255 for v in fill))
            c.rect(cx - (w / 2 + b) * IN - 1, cy - (h / 2 + b) * IN - 1, (w + 2 * b) * IN + 2, (h + 2 * b) * IN + 2, stroke=0, fill=1)
        c.drawImage(reader, cx - aw / 2 * IN, cy - ah / 2 * IN, aw * IN, ah * IN)
        c.restoreState()
    c.showPage(); c.save()
    print(f"wrote {out}")
    print(f"check: python3 verify_print.py \"{out}\" --grid {a.grid}" + (f" --flood {b:g}" if b else ""))


if __name__ == "__main__":
    main()
