#!/usr/bin/env python3
"""
textlabels.py — vector text on every label of an Avery die-cut sheet.

Uses the die-cut presets in verify_print.py (--grid), so layout and check share one set
of numbers.  Text stays vector (black, Helvetica-Bold by default), centered on each
die-cut, auto-sized to fit inside the die with --clear inches of clearance (default 0.08),
capped at --max-pt.  Pass --text more than once to split the sheet into equal blocks of
rows (top block = first --text); --split cols splits by columns instead.  A line break
inside a text is written as "\\n".

Output page is exactly 8.5x11 in, no marks, no bleed.  Verify with:
  verify_print.py OUT --grid PRESET

  textlabels.py --grid avery5167 --text "Hot Tub Shutoff" --text "Sauna Shutoff" --out shutoff.pdf
  textlabels.py --grid avery5160 --text "FRAGILE" --max-pt 28
"""
import argparse, os, sys, json
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_print import GRIDS, parse_grid, label_cells  # noqa: E402

IN = 72.0


def fit_size(lines, font, box_w, box_h, max_pt, leading=1.15):
    pt = max_pt
    while pt > 4:
        w = max(stringWidth(l, font, pt) for l in lines)
        h = pt * (1 + leading * (len(lines) - 1))
        if w <= box_w and h <= box_h:
            return pt
        pt -= 0.25
    return pt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grid", required=True, help=f"preset ({', '.join(sorted(GRIDS))}) or cols,rows,w,h,left,top,pitch_x,pitch_y[,round]")
    ap.add_argument("--text", action="append", required=True, help="label text; repeat to split the sheet")
    ap.add_argument("--split", choices=["rows", "cols"], default="rows")
    ap.add_argument("--font", default="Helvetica-Bold", help="reportlab standard font name")
    ap.add_argument("--max-pt", type=float, default=24)
    ap.add_argument("--clear", type=float, default=0.08, help="clearance inside each die, inches")
    ap.add_argument("--uniform", action="store_true", default=True, help="same point size for every text (default)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    g = parse_grid(a.grid)
    cols, rows, lw, lh = g[0], g[1], g[2], g[3]
    texts = [t.replace("\\n", "\n").split("\n") for t in a.text]
    n = len(texts)
    span = rows if a.split == "rows" else cols
    if span % n:
        sys.exit(f"{span} {a.split} don't split evenly into {n} blocks")
    per = span // n
    box_w, box_h = (lw - 2 * a.clear) * IN, (lh - 2 * a.clear) * IN
    if len(g) > 8 and g[8] == "round":
        box_w = box_h = min(box_w, box_h) * 0.707
    pt = min(fit_size(t, a.font, box_w, box_h, a.max_pt) for t in texts)

    c = canvas.Canvas(a.out, pagesize=(8.5 * IN, 11 * IN))
    c.setFillColorRGB(0, 0, 0)
    counts = [0] * n
    left, top, px, py = g[4], g[5], g[6], g[7]
    for r in range(rows):
        for col in range(cols):
            k = (r if a.split == "rows" else col) // per
            lines = texts[k]; counts[k] += 1
            cx = (left + col * px + lw / 2) * IN
            cy = (11 - (top + r * py + lh / 2)) * IN
            lead = pt * 1.15
            # optical centre: cap height ~0.72 em
            y0 = cy + (len(lines) - 1) * lead / 2 - 0.36 * pt
            c.setFont(a.font, pt)
            for i, l in enumerate(lines):
                c.drawCentredString(cx, y0 - i * lead, l)
    c.setTitle(os.path.splitext(os.path.basename(a.out))[0])
    c.save()
    print(f"{a.grid}: {cols}x{rows} = {cols*rows} labels, {a.font} {pt:g} pt black, "
          f"clearance {a.clear} in")
    for t, k in zip(a.text, counts):
        print(f"  {k:3d} × {t!r}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
