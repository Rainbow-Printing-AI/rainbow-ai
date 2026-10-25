#!/usr/bin/env python3
"""photopage.py — photos onto fixed-size pages, one photo per page, white around it.

For "put this landscape photo on a portrait 5x7 with 1/8 in left/right margins" jobs:
the page is the trim, the photo floats inside it, the rest stays white.

  * one image per page, in the order given; page size --page WxH (inches)
  * the photo is scaled to fit the box left by --margin-x / --margin-y, aspect kept,
    centered on the page — never cropped. Default margins: x 0.125 in, y 0 (so a
    landscape photo on a portrait page is width-bound and top/bottom stay blank)
  * orientation: the photo keeps its own orientation by default (landscape photo on a
    portrait page is the point of this tool); --match turns it so its long side runs
    with the page's long side
  * JPEGs are embedded untouched (no recompression) with their ICC profile
    (Adobe RGB stays Adobe RGB) via img2pdf; EXIF rotation applied
  * prints placed size and effective dpi per photo; flags < 200 dpi (soft), < 150 (bad)

Output is a plain N-page PDF at the page size — feed it to impose.py for N-up/marks:

  python3 photopage.py "../2 faces.jpg" "../golf.jpg" --page 5x7 --out ../photos_5x7.pdf
  python3 impose.py ../photos_5x7.pdf --nup 2 --sheet letter --marks
  python3 photopage.py pics/*.jpg --page 4x6 --margin-x 0.25 --margin-y 0.25 --out p.pdf
  python3 photopage.py pic.jpg --page 8x10 --match --out p.pdf     # long side to long side
"""
import argparse, sys
import img2pdf
from PIL import Image, ImageOps

PT = 72.0

def size(s):
    w, h = s.lower().split("x")
    return float(w), float(h)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+", help="jpg/png/tif, one per page, in order")
    ap.add_argument("--page", required=True, help="page (trim) size WxH inches, e.g. 5x7")
    ap.add_argument("--margin-x", type=float, default=0.125, help="left and right margin, inches (default 0.125)")
    ap.add_argument("--margin-y", type=float, default=0.0, help="top and bottom minimum margin, inches (default 0)")
    ap.add_argument("--match", action="store_true", help="rotate photo so its long side runs with the page's long side")
    ap.add_argument("--out", required=True, help="output PDF")
    a = ap.parse_args()

    pw, ph = size(a.page)
    bw, bh = pw - 2 * a.margin_x, ph - 2 * a.margin_y
    if bw <= 0 or bh <= 0:
        sys.exit("margins leave no room on the page")

    pages = []
    for f in a.images:
        im = ImageOps.exif_transpose(Image.open(f))
        iw, ih = im.size
        rot = 0
        if a.match and ((iw > ih) != (pw > ph)) and iw != ih and pw != ph:
            rot = 90
            iw, ih = ih, iw
        s = min(bw / iw, bh / ih)               # inches per pixel
        w_in, h_in = iw * s, ih * s
        dpi = 1 / s
        flag = "" if dpi >= 200 else ("  SOFT (<200 dpi)" if dpi >= 150 else "  BAD (<150 dpi)")
        print(f"{f}: {iw}x{ih}px -> {w_in:.3f} x {h_in:.3f} in on {pw:g}x{ph:g}, "
              f"{dpi:.0f} dpi, margins L/R {(pw-w_in)/2:.3f} T/B {(ph-h_in)/2:.3f} in"
              f"{'  (rotated 90)' if rot else ''}{flag}")
        layout = img2pdf.get_layout_fun(
            pagesize=(pw * PT, ph * PT),
            imgsize=((img2pdf.ImgSize.abs, w_in * PT), (img2pdf.ImgSize.abs, h_in * PT)),
            fit=img2pdf.FitMode.into, auto_orient=False)
        kw = {"rotation": img2pdf.Rotation.ifvalid}
        if rot:
            # img2pdf rotation turns the whole page; place on a swapped page then turn it back
            layout = img2pdf.get_layout_fun(pagesize=(ph * PT, pw * PT), imgsize=((img2pdf.ImgSize.abs, h_in * PT), (img2pdf.ImgSize.abs, w_in * PT)),
                                             fit=img2pdf.FitMode.into, auto_orient=False)
        pages.append((img2pdf.convert(f, layout_fun=layout, **kw), rot))

    import pikepdf, io
    out = pikepdf.new()
    for data, rot in pages:
        src = pikepdf.open(io.BytesIO(data))
        out.pages.append(src.pages[0])
        if rot:
            out.pages[-1].rotate(90, relative=True)
    out.save(a.out)
    print(f"wrote {a.out}  ({len(pages)} page{'s' if len(pages) != 1 else ''}, {pw:g}x{ph:g} in)")

if __name__ == "__main__":
    main()
