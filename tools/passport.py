#!/usr/bin/env python3
"""passport.py — passport / ID photo: square crop sized to the head, laid out on a sheet, verified.

US passport spec by default: 2x2 in, head (chin to top of hair) 50-69% of the height
(1 to 1-3/8 in), eyes 56-69% up from the bottom (1-1/8 to 1-3/8 in).

Two steps, because the head is located by eye (no face detector on the shop Mac):

  1. grid preview — pixel-labelled grid over the photo (EXIF rotation applied):
       python3 passport.py "../Job/photo.jpg" --grid
     -> writes <photo>_grid.jpg beside the photo's PRINT READY folder; read off:
        crown  = y of the top of the hair
        chin   = y of the bottom of the chin
        cx     = x of the face centre line (nose)
        eyes   = y of the pupils (optional, but checked when given)

  2. build:
       python3 passport.py "../Job/photo.jpg" --crown 355 --chin 1320 --cx 1020 --eyes 835
     -> square crop where the head is --head (default 0.62) of the frame and the top of
        the hair sits --top (default 0.10) below the top edge; centred on cx; never
        upscaled, never padded (stops if the photo can't hold the crop).
     -> PRINT READY/<name>_2x2.jpg                 (original ICC kept, q95, 4:4:4)
        PRINT READY/<name>_2x2_<N>up_4x6.pdf        (photopage.py -> impose.py, no bleed/marks)
        PRINT READY/<name>_2x2_preview.jpg          (crop with the spec bands drawn — look at it)
     -> runs verify_print.py, then measures the PDF itself: page box, each placed image's
        matrix size, and the rendered ink box of each copy at 600 dpi (must be square and
        2.000 in +/- 0.005). Exit 0 = everything passed.

Options: --size 2 (square side, in), --sheet 4x6, --nup 1 (2 = two copies on the sheet),
--head 0.62, --top 0.10, --out-dir DIR (default: PRINT READY/ beside the photo).
Print at 100% — no fit-to-page / scaling in the Fiery or the driver.
"""
import argparse, os, subprocess, sys, tempfile
# Mac: find pdftoppm in ~/.rainbow (setup-mac.sh); harmless elsewhere
os.environ["PATH"] = os.path.expanduser("~/.rainbow/env/bin") + os.pathsep + os.environ.get("PATH", "")
from PIL import Image, ImageOps, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HEAD_MIN, HEAD_MAX = 0.50, 0.69      # chin..crown as fraction of frame height
EYES_MIN, EYES_MAX = 0.56, 0.69      # eye line height from the bottom, fraction
DPI_WARN, DPI_FAIL = 300, 200


def load(path):
    im = Image.open(path)
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im).convert("RGB")
    return im, icc


def font(px):
    for f in ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(f, px)
        except Exception:
            pass
    return ImageFont.load_default()


def grid(path, out_dir):
    im, _ = load(path)
    W, H = im.size
    step = 50 if max(W, H) <= 2000 else 100
    d = ImageDraw.Draw(im)
    f = font(max(14, step // 3))
    for y in range(0, H, step):
        major = y % (step * 5) == 0
        d.line([(0, y), (W, y)], fill=(0, 0, 255) if major else (255, 0, 0), width=3 if major else 1)
        d.text((4, y + 2), str(y), fill=(255, 0, 0), font=f)
    for x in range(0, W, step):
        major = x % (step * 5) == 0
        d.line([(x, 0), (x, H)], fill=(0, 140, 0), width=3 if major else 1)
        d.text((x + 2, 4), str(x), fill=(0, 140, 0), font=f)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + "_grid.jpg")
    im.thumbnail((1800, 1800))
    im.save(out, quality=85)
    print(f"image {W}x{H}px (after EXIF rotation), grid every {step}px (heavy line every {step*5})")
    print(f"wrote {out}")
    print("read off: --crown (top of hair)  --chin (bottom of chin)  --cx (nose line)  --eyes (pupils)")


def plan(W, H, crown, chin, cx, head, top):
    if chin <= crown:
        sys.exit("FAIL  --chin must be below --crown")
    hp = chin - crown
    for frac in [head] + [f / 100 for f in range(int(head * 100) + 1, int(HEAD_MAX * 100) + 1)]:
        S = round(hp / frac)
        if S <= min(W, H):
            break
    else:
        sys.exit(f"FAIL  photo {W}x{H}px can't hold a square where the head is <= {HEAD_MAX:.0%} "
                 f"(head is {hp}px, needs a {round(hp / HEAD_MAX)}px square). Need a wider/looser shot.")
    if frac != head:
        print(f"note  head fraction raised {head:.2f} -> {frac:.2f} so the crop fits inside the photo")
    y0 = round(crown - top * S)
    x0 = round(cx - S / 2)
    shift = []
    if y0 < 0: shift.append(f"top {-y0}px"); y0 = 0
    if y0 + S > H: shift.append(f"bottom {y0 + S - H}px"); y0 = H - S
    if x0 < 0: shift.append(f"left {-x0}px"); x0 = 0
    if x0 + S > W: shift.append(f"right {x0 + S - W}px"); x0 = W - S
    if shift:
        print("note  crop shifted to stay inside the photo (" + ", ".join(shift) + ") — check the preview")
    return x0, y0, S


def preview(crop, S, crown, chin, eyes, x0, y0, path):
    p = crop.copy().resize((800, 800))
    k = 800 / S
    d = ImageDraw.Draw(p)
    # allowed chin band given the measured crown, and allowed eye band
    for frac, col in ((HEAD_MIN, (0, 160, 0)), (HEAD_MAX, (0, 160, 0))):
        y = (crown - y0 + frac * S) * k
        d.line([(0, y), (800, y)], fill=col, width=1)
    for frac in (EYES_MIN, EYES_MAX):
        y = 800 - frac * 800
        d.line([(0, y), (800, y)], fill=(0, 0, 255), width=1)
    for y, col in ((crown, (255, 0, 0)), (chin, (255, 0, 0))):
        d.line([(0, (y - y0) * k), (800, (y - y0) * k)], fill=col, width=2)
    if eyes is not None:
        d.line([(0, (eyes - y0) * k), (800, (eyes - y0) * k)], fill=(255, 140, 0), width=2)
    d.line([(400, 0), (400, 800)], fill=(160, 160, 160), width=1)
    p.save(path, quality=85)


def measure(pdf, side, nup):
    """Independent check: page box, placed image matrices, rendered ink boxes."""
    import pdfplumber
    import numpy as np
    ok = True
    with pdfplumber.open(pdf) as doc:
        pg = doc.pages[0]
        print(f"  page {pg.width/72:.4f} x {pg.height/72:.4f} in, rotate {pg.rotation}")
        boxes = [(i["x0"], i["top"], i["x1"], i["bottom"]) for i in pg.images]
    if len(boxes) != nup:
        print(f"  FAIL  {len(boxes)} placed image(s), expected {nup}"); ok = False
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "600", "-png", "-singlefile", pdf, os.path.join(td, "r")], check=True)
        a = np.asarray(Image.open(os.path.join(td, "r.png")).convert("L"))
    for n, (x0, t, x1, b) in enumerate(boxes, 1):
        w, h = (x1 - x0) / 72, (b - t) / 72
        m = int(0.05 * 600)
        X0, Y0 = max(0, int(x0 / 72 * 600) - m), max(0, int(t / 72 * 600) - m)
        sub = a[Y0:int(b / 72 * 600) + m, X0:int(x1 / 72 * 600) + m]
        ys, xs = (sub < 250).nonzero()
        rw = (xs.max() - xs.min() + 1) / 600 if len(xs) else 0
        rh = (ys.max() - ys.min() + 1) / 600 if len(ys) else 0
        good = abs(w - side) < 1e-3 and abs(h - side) < 1e-3 and abs(rw - side) <= 0.005 and abs(rh - side) <= 0.005 \
            and abs(rw - rh) <= 0.002
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'}  copy {n}: placed {w:.5f} x {h:.5f} in at ({x0/72:.4f}, {t/72:.4f}) in; "
              f"rendered ink {rw:.4f} x {rh:.4f} in @600dpi")
    return ok


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--grid", action="store_true", help="step 1: write the pixel grid preview and stop")
    ap.add_argument("--crown", type=int, help="y px, top of the hair")
    ap.add_argument("--chin", type=int, help="y px, bottom of the chin")
    ap.add_argument("--cx", type=int, help="x px, face centre line")
    ap.add_argument("--eyes", type=int, help="y px, pupils (checked against 56-69%% from bottom)")
    ap.add_argument("--size", type=float, default=2.0, help="square side, inches (default 2)")
    ap.add_argument("--sheet", default="4x6", help="output sheet (default 4x6)")
    ap.add_argument("--nup", type=int, default=1, help="copies on the sheet (default 1)")
    ap.add_argument("--head", type=float, default=0.62, help="target chin-to-crown fraction (default 0.62)")
    ap.add_argument("--top", type=float, default=0.10, help="space above the hair, fraction (default 0.10)")
    ap.add_argument("--out-dir", help="default: PRINT READY/ beside the photo")
    a = ap.parse_args()

    src = os.path.abspath(a.image)
    out_dir = a.out_dir or os.path.join(os.path.dirname(src), "PRINT READY")
    if a.grid:
        return grid(src, out_dir)
    if None in (a.crown, a.chin, a.cx):
        sys.exit("need --crown, --chin and --cx (run --grid first)")
    if not (HEAD_MIN <= a.head <= HEAD_MAX):
        sys.exit(f"--head must be within {HEAD_MIN}-{HEAD_MAX}")

    im, icc = load(src)
    W, H = im.size
    x0, y0, S = plan(W, H, a.crown, a.chin, a.cx, a.head, a.top)
    crop = im.crop((x0, y0, x0 + S, y0 + S))
    dpi = S / a.size
    head = (a.chin - a.crown) / S
    fails, warns = [], []
    if not HEAD_MIN <= head <= HEAD_MAX:
        fails.append(f"head {head:.1%} outside {HEAD_MIN:.0%}-{HEAD_MAX:.0%}")
    eyes_txt = "eyes not given"
    if a.eyes is not None:
        ef = 1 - (a.eyes - y0) / S
        eyes_txt = f"eyes {ef:.1%} up ({ef*a.size:.3f} in)"
        if not EYES_MIN <= ef <= EYES_MAX:
            warns.append(f"eye line {ef:.1%} from bottom, spec {EYES_MIN:.0%}-{EYES_MAX:.0%} — adjust --top")
    off = (a.cx - (x0 + S / 2)) / S
    if abs(off) > 0.05:
        fails.append(f"face {abs(off):.0%} of the frame {'right' if off > 0 else 'left'} of centre — photo too tight on that side, reshoot")
    elif abs(off) > 0.02:
        warns.append(f"face {abs(off):.1%} off centre (photo edge) — check the preview")
    crown_f = (a.crown - y0) / S
    if crown_f < 0.03:
        fails.append(f"top of hair {crown_f:.1%} from the top edge — no headroom, reshoot with more space above")
    if dpi < DPI_FAIL:
        fails.append(f"{dpi:.0f} dpi — too soft for a passport photo, reshoot")
    elif dpi < DPI_WARN:
        warns.append(f"{dpi:.0f} dpi — usable but soft")

    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    tag = f"{a.size:g}x{a.size:g}"
    jpg = os.path.join(out_dir, f"{stem}_{tag}.jpg")
    crop.save(jpg, quality=95, subsampling=0, icc_profile=icc, dpi=(round(dpi), round(dpi)))
    prev = os.path.join(out_dir, f"{stem}_{tag}_preview.jpg")
    preview(crop, S, a.crown, a.chin, a.eyes, x0, y0, prev)
    print(f"crop  x {x0}..{x0+S}, y {y0}..{y0+S} of {W}x{H}px -> {S}x{S}px = {dpi:.0f} dpi at {tag} in")
    print(f"      head {head:.1%} ({head*a.size:.3f} in), top of hair {(a.crown-y0)/S:.1%} from top, {eyes_txt}")
    print(f"wrote {jpg}\nwrote {prev}  (red = measured crown/chin, green = allowed chin band, "
          f"blue = allowed eye band, orange = eyes)")

    sheet = a.sheet.lower()
    pdf = os.path.join(out_dir, f"{stem}_{tag}_{a.nup}up_{sheet}.pdf")
    py = [sys.executable, "-W", "ignore"]
    with tempfile.TemporaryDirectory() as td:
        page = os.path.join(td, "page.pdf")
        subprocess.run(py + [os.path.join(HERE, "photopage.py"), jpg, "--page", tag,
                             "--margin-x", "0", "--margin-y", "0", "--out", page], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(py + [os.path.join(HERE, "impose.py"), page, "--trim", tag, "--nup", str(a.nup),
                             "--sheet", sheet, "--out", pdf], check=True)
    v = subprocess.run(py + [os.path.join(HERE, "verify_print.py"), pdf], capture_output=True, text=True)
    print(v.stdout.rstrip())
    if v.returncode != 0:
        fails.append("verify_print.py did not pass")
    print("size check (independent of verify_print):")
    if not measure(pdf, a.size, a.nup):
        fails.append(f"placed/rendered size is not exactly {tag} in square")
    for w in warns:
        print(f"WARN  {w}")
    for f in fails:
        print(f"FAIL  {f}")
    print(f"wrote {pdf}")
    print("PASSPORT  " + ("FAIL" if fails else "PASS") + f"  ({len(fails)} fail, {len(warns)} warn) — print at 100%, no fit-to-page")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
