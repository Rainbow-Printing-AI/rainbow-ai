#!/usr/bin/env python3
"""
photo_prep.py — get a folder of customer photos ready to print at a stated size.

  * orientation: the image's long side goes with the size's long side (never
    rotated to fill the other way)
  * crop to the exact aspect, centred (or --anchor top/bottom/left/right);
    crops that remove more than --flag-crop (15%; a 4:3 phone shot to 4x6 loses 11%) are flagged
  * never upscales; reports effective dpi and flags < 200 (soft) and < 150 (bad)
  * applies EXIF rotation, converts HEIC (needs pillow-heif), keeps embedded ICC
  * writes <name>_<WxH>.jpg into <out>/<WxH>/ and a _contact_sheet.jpg with
    filename, pixel size, dpi and flags for a one-glance check

  python3 photo_prep.py "photostoprint" --size 4x6
  python3 photo_prep.py "Ginger B 9-1" --size 5x7 --size 8x10       # two runs, two folders
  python3 photo_prep.py pics --size 4x6 --border 0.125               # white border inside the trim
  python3 photo_prep.py pics --size 4x6 --dry-run                    # just the report + contact sheet
"""
import argparse, glob, json, os, sys
from PIL import Image, ImageOps, ImageDraw, ImageFont

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif", ".webp", ".bmp")


def parse_size(s):
    w, h = (float(v) for v in s.lower().split("x"))
    return w, h


def prep_one(path, size_in, out_dir, anchor, border_in, flag_crop, dry):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    icc = im.info.get("icc_profile")
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    W, H = im.size
    label = f"{size_in[0]:g}x{size_in[1]:g}"
    sw, sh = size_in
    # long side to long side
    if (W >= H) != (sw >= sh) and sw != sh:
        sw, sh = sh, sw
    target = sw / sh
    src = W / H
    if src > target:      # too wide → crop width
        cw, ch = int(round(H * target)), H
    else:                 # too tall → crop height
        cw, ch = W, int(round(W / target))
    dx, dy = W - cw, H - ch
    ox = {"left": 0, "right": dx}.get(anchor, dx // 2)
    oy = {"top": 0, "bottom": dy}.get(anchor, dy // 2)
    crop_frac = max(dx / W, dy / H)
    dpi = min(cw / sw, ch / sh)
    flags = []
    if crop_frac > flag_crop:
        flags.append(f"crop removes {crop_frac*100:.0f}% on one axis — check subject")
    if dpi < 150:
        flags.append(f"{dpi:.0f} dpi: too soft at {sw:g}x{sh:g}")
    elif dpi < 200:
        flags.append(f"{dpi:.0f} dpi: slightly soft")
    rec = {"file": os.path.basename(path), "px": [W, H], "print_in": [sw, sh], "crop_px": [cw, ch],
           "effective_dpi": round(dpi), "flags": flags, "out": None}
    if dry:
        return rec, im
    out = im.crop((ox, oy, ox + cw, oy + ch))
    if border_in > 0:
        # white border inside the trim: shrink image, pad with white to the same crop size
        bx, by = int(round(border_in * dpi)), int(round(border_in * dpi))
        inner = out.resize((cw - 2 * bx, ch - 2 * by), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (cw, ch), "white")
        canvas.paste(inner, (bx, by))
        out = canvas
    stem = os.path.splitext(os.path.basename(path))[0]
    sub = os.path.join(out_dir, label)
    os.makedirs(sub, exist_ok=True)
    dest = os.path.join(sub, f"{stem}_{label}.jpg")
    kw = {"quality": 95, "dpi": (round(dpi), round(dpi)), "subsampling": 0}
    if icc:
        kw["icc_profile"] = icc
    out.convert("RGB").save(dest, "JPEG", **kw)
    rec["out"] = dest
    return rec, out


def contact_sheet(records, thumbs, path, size_label):
    cols = 5
    tw, th = 260, 260
    rows = (len(records) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw + 20, rows * (th + 70) + 60), "white")
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except Exception:
        font = small = ImageFont.load_default()
    d.text((10, 10), f"{len(records)} photos → {size_label}   (red = flagged)", fill="black", font=font)
    for i, (rec, im) in enumerate(zip(records, thumbs)):
        x = 10 + (i % cols) * tw
        y = 40 + (i // cols) * (th + 70)
        t = im.copy(); t.thumbnail((tw - 20, th - 20))
        sheet.paste(t, (x + (tw - t.width) // 2, y + (th - t.height) // 2))
        col = "red" if rec["flags"] else "black"
        d.text((x + 4, y + th + 2), rec["file"][:34], fill=col, font=small)
        d.text((x + 4, y + th + 18), f"{rec['px'][0]}x{rec['px'][1]} px  {rec['effective_dpi']} dpi", fill=col, font=small)
        for j, f in enumerate(rec["flags"][:2]):
            d.text((x + 4, y + th + 34 + 14 * j), f[:40], fill="red", font=small)
    sheet.save(path, quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder of photos (or a single file)")
    ap.add_argument("--size", action="append", required=True, help="print size WxH inches; repeatable")
    ap.add_argument("--out", help="output folder (default: <folder>/print-ready)")
    ap.add_argument("--anchor", choices=["center", "top", "bottom", "left", "right"], default="center")
    ap.add_argument("--border", type=float, default=0.0, help="white border inside the trim, inches")
    ap.add_argument("--flag-crop", type=float, default=0.15, help="flag crops removing more than this fraction (0.15; a 4:3 phone photo to 4x6 loses 11%%)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if os.path.isfile(args.folder):
        files = [args.folder]; base = os.path.dirname(os.path.abspath(args.folder))
    else:
        base = args.folder
        files = sorted(p for p in glob.glob(os.path.join(args.folder, "*")) if p.lower().endswith(EXTS))
    if not files:
        sys.exit("no images found")
    heics = [f for f in files if f.lower().endswith((".heic", ".heif"))]
    if heics and pillow_heif is None:
        sys.exit(f"{len(heics)} HEIC files but pillow-heif is not installed: pip3 install pillow-heif")
    out_dir = args.out or os.path.join(base, "print-ready")
    os.makedirs(out_dir, exist_ok=True)
    summary = {}
    for s in args.size:
        size_in = parse_size(s)
        recs, thumbs = [], []
        for f in files:
            try:
                rec, im = prep_one(f, size_in, out_dir, args.anchor, args.border, args.flag_crop, args.dry_run)
            except Exception as e:
                rec, im = {"file": os.path.basename(f), "px": [0, 0], "effective_dpi": 0, "flags": [f"could not open: {e}"], "out": None}, Image.new("RGB", (10, 10), "gray")
            recs.append(rec); thumbs.append(im)
        label = f"{size_in[0]:g}x{size_in[1]:g}"
        cs = os.path.join(out_dir, f"_contact_sheet_{label}.jpg")
        contact_sheet(recs, thumbs, cs, label)
        summary[label] = recs
        flagged = [r for r in recs if r["flags"]]
        print(f"{label}: {len(recs)} photos, {len(flagged)} flagged  → {os.path.join(out_dir, label) if not args.dry_run else '(dry run)'}")
        for r in flagged:
            print(f"   ! {r['file']}: {'; '.join(r['flags'])}")
        print(f"   contact sheet: {cs}")
    with open(os.path.join(out_dir, "_photo_prep_report.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)


if __name__ == "__main__":
    main()
