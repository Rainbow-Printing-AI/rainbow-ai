#!/usr/bin/env python3
"""build_banner.py — banner / sign art from scratch: solid background flood,
a centered logo, and centered lines of text, all vector.

  * logo PNG (black art on transparent or white) is upscaled and traced with
    potrace, so a small web logo holds up at banner size; centered on its
    measured ink box, never the PNG canvas
  * text is shaped with HarfBuzz (kerning) and written as outlines, so no font
    goes to the RIP; tracking in em
  * every line is sized to the largest size that fits --max-width and
    --max-cap; the group (logo + gap + lines) is centered on the page
  * stops if anything lands inside the --safe margin

The art PDF is the source; run impose.py on it (1-up, sheet = trim) and then
verify_print.py, same as any customer file.

Default font: fonts/CormorantGaramond-Bold.ttf next to this script (OFL).
Needs: pip install --user potracer uharfbuzz   (pure-Python potrace + HarfBuzz)

Example (Ritz-Carlton 7x3 ft vinyl, 2026-10-16)
  build_banner.py --size 84x36 --bg D5E9FB --logo ../RNORZ_Primary_RGB.png \\
      --logo-height 15 --gap 4 --text "WELCOME TO WORK" --out ~/scratch/art.pdf
"""
import argparse, os, sys
import numpy as np
from PIL import Image
try:
    import potrace
    import uharfbuzz as hb
except ImportError as e:
    sys.exit(f"{e}\n  -> pip install --user potracer uharfbuzz")
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import FILL_EVEN_ODD, FILL_NON_ZERO

PT = 72.0


def pxy(p):
    return (p.x, p.y) if hasattr(p, "x") else (p[0], p[1])


# ---------------------------------------------------------------- logo trace
def trace_logo(png, scale=4, thresh=0.5, turdsize=4):
    im = Image.open(png).convert("RGBA")
    a = np.asarray(im).astype(float) / 255.0
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    ink = a[..., 3] * (1.0 - lum)                      # black-on-anything
    w, h = im.size
    big = Image.fromarray((ink * 255).astype(np.uint8)).resize(
        (w * scale, h * scale), Image.BICUBIC)
    bm = np.asarray(big) > thresh * 255
    ys, xs = np.where(bm)
    bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)   # px, y down
    # potracer treats True as paper (it inverts), so hand it the paper mask
    path = potrace.Bitmap(~bm).trace(turdsize=turdsize, alphamax=1.0,
                                    opticurve=True, opttolerance=0.2)
    return path, bbox, (w, h)


def draw_logo(c, path, bbox, x_center, y_top, height_pt, rgb):
    bx0, by0, bx1, by1 = bbox
    s = height_pt / (by1 - by0)
    w_pt = (bx1 - bx0) * s
    x0 = x_center - w_pt / 2

    def T(p):
        x, y = pxy(p)
        return x0 + (x - bx0) * s, y_top - (y - by0) * s

    p = c.beginPath()
    for curve in path:
        p.moveTo(*T(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                p.lineTo(*T(seg.c))
                p.lineTo(*T(seg.end_point))
            else:
                p.curveTo(*T(seg.c1), *T(seg.c2), *T(seg.end_point))
        p.close()
    c.setFillColorRGB(*rgb)
    c.drawPath(p, stroke=0, fill=1, fillMode=FILL_EVEN_ODD)
    return x0, y_top - height_pt, x0 + w_pt, y_top          # ink box, pt


# ---------------------------------------------------------------- text
class RLPen(BasePen):
    def __init__(self, glyphset, path, dx, dy, k):
        super().__init__(glyphset)
        self.p, self.dx, self.dy, self.k = path, dx, dy, k

    def _t(self, pt):
        return self.dx + pt[0] * self.k, self.dy + pt[1] * self.k

    def _moveTo(self, pt): self.p.moveTo(*self._t(pt))
    def _lineTo(self, pt): self.p.lineTo(*self._t(pt))
    def _curveToOne(self, a, b, c): self.p.curveTo(*self._t(a), *self._t(b), *self._t(c))
    def _closePath(self): self.p.close()


class Face:
    def __init__(self, fontfile):
        self.tt = TTFont(fontfile)
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        blob = hb.Blob.from_file_path(fontfile)
        self.hbfont = hb.Font(hb.Face(blob))

    def layout(self, text, tracking_em):
        """[(glyphname, x, y)] in font units + ink bbox in font units."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {"kern": True, "liga": False})
        track = tracking_em * self.upem
        out, x = [], 0.0
        n = len(buf.glyph_infos)
        for i, (gi, gp) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
            name = self.order[gi.codepoint]
            out.append((name, x + gp.x_offset, gp.y_offset))
            x += gp.x_advance + (track if i < n - 1 else 0)
        u = None
        for name, gx, gy in out:
            b = BoundsPen(self.gs)
            self.gs[name].draw(b)
            if b.bounds:
                x0, y0, x1, y1 = b.bounds
                g = (x0 + gx, y0 + gy, x1 + gx, y1 + gy)
                u = g if u is None else (min(u[0], g[0]), min(u[1], g[1]),
                                         max(u[2], g[2]), max(u[3], g[3]))
        return out, u

    def draw(self, c, glyphs, bounds, x_center, y_top, k, rgb):
        """Draw at scale k pt/unit, ink box centered on x_center, top at y_top."""
        bx0, by0, bx1, by1 = bounds
        dx = x_center - (bx0 + bx1) / 2 * k
        dy = y_top - by1 * k
        p = c.beginPath()
        for name, gx, gy in glyphs:
            self.gs[name].draw(RLPen(self.gs, p, dx + gx * k, dy + gy * k, k))
        c.setFillColorRGB(*rgb)
        c.drawPath(p, stroke=0, fill=1, fillMode=FILL_NON_ZERO)
        return dx + bx0 * k, dy + by0 * k, dx + bx1 * k, dy + by1 * k


def strip_unused_font(path):
    """reportlab always selects Helvetica in the page preamble; with all text
    outlined that leaves an unembedded font reference for the RIP to whine
    about. Drop the text-state ops and the /Font resource when no text is drawn."""
    try:
        import pikepdf
    except ImportError:
        return
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            ops = pikepdf.parse_content_stream(page)
            if any(str(op) in ("Tj", "TJ", "'", '"') for _, op in ops):
                continue
            keep = [(o, op) for o, op in ops if str(op) not in ("BT", "ET", "Tf", "TL")]
            page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(keep))
            if "/Font" in page.Resources:
                del page.Resources["/Font"]
        pdf.save(path)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", required=True, help="WxH inches, e.g. 84x36")
    ap.add_argument("--bg", default="FFFFFF", help="background sRGB hex")
    ap.add_argument("--ink", default="000000", help="text + logo sRGB hex")
    ap.add_argument("--logo", help="logo PNG (black art)")
    ap.add_argument("--logo-height", type=float, default=12, help="logo ink height, in")
    ap.add_argument("--gap", type=float, default=3, help="logo-to-text gap, in")
    ap.add_argument("--font", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   "fonts", "CormorantGaramond-Bold.ttf"),
                    help="TTF/OTF (static, not variable); default Cormorant Garamond Bold")
    ap.add_argument("--text", action="append", required=True, help="repeat for more lines")
    ap.add_argument("--tracking", type=float, default=0.06, help="em")
    ap.add_argument("--max-width", type=float, default=72, help="in")
    ap.add_argument("--max-cap", type=float, default=6.5, help="max text ink height, in")
    ap.add_argument("--leading", type=float, default=0.5, help="line gap as fraction of cap")
    ap.add_argument("--safe", type=float, default=2.0, help="min clearance from edge, in")
    ap.add_argument("--raise", dest="raise_", type=float, default=0.0, help="shift group up, in")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    W, H = (float(v) * PT for v in a.size.lower().split("x"))
    bg, ink = hexrgb(a.bg), hexrgb(a.ink)
    face = Face(a.font)

    lines = []
    for t in a.text:
        g, b = face.layout(t, a.tracking)
        k = min(a.max_width * PT / (b[2] - b[0]), a.max_cap * PT / (b[3] - b[1]))
        lines.append((t, g, b, k))
    # one size for all lines (the smallest that fits every line)
    k = min(l[3] for l in lines)
    heights = [(b[3] - b[1]) * k for _, _, b, _ in lines]
    lead = max(heights) * a.leading

    logo_h = a.logo_height * PT if a.logo else 0
    gap = a.gap * PT if a.logo else 0
    total = logo_h + gap + sum(heights) + lead * (len(lines) - 1)
    y = (H + total) / 2 + a.raise_ * PT

    c = canvas.Canvas(a.out, pagesize=(W, H))
    c.setTitle(" / ".join(a.text))
    c.setFillColorRGB(*bg)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    boxes = []
    if a.logo:
        path, bbox, _ = trace_logo(a.logo)
        boxes.append(("logo", draw_logo(c, path, bbox, W / 2, y, logo_h, ink)))
        y -= logo_h + gap
    for (t, g, b, _), h in zip(lines, heights):
        boxes.append((t, face.draw(c, g, b, W / 2, y, k, ink)))
        y -= h + lead
    c.showPage()
    c.save()
    strip_unused_font(a.out)

    bad = False
    for name, (x0, y0, x1, y1) in boxes:
        clr = min(x0, y0, W - x1, H - y1) / PT
        print(f"{name:32s} {(x1-x0)/PT:6.2f} x {(y1-y0)/PT:5.2f} in   "
              f"L {x0/PT:5.2f}  R {(W-x1)/PT:5.2f}  T {(H-y1)/PT:5.2f}  B {y0/PT:5.2f}   "
              f"(min clearance {clr:.2f} in)")
        bad |= clr < a.safe
    print(f"text size {k*face.upem:.1f} pt; page {W/PT:g} x {H/PT:g} in; bg #{a.bg.lstrip('#').upper()}")
    if bad:
        sys.exit(f"STOP: something is inside the {a.safe} in safe margin")


if __name__ == "__main__":
    main()
