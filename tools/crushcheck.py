#!/usr/bin/env python3
"""
crushcheck.py — find (and lift) colors that will crush to black on the Versant.

The problem it solves: a screen shows very dark saturated colors (sRGB #17320B forest
green, L* 18) as clearly colored, because a monitor's black is near L* 0.  The Versant's
darkest solid is around L* 10–14, so anything chromatic below ~L* 24 prints as black with
no visible hue.  Customers see "my green bar printed black".

What it does:
  * Walks every content stream (pages + nested form XObjects) and reads each fill/stroke
    color op (rg/RG, k/K, g/G, sc/scn/SC/SCN in DeviceRGB/DeviceCMYK/DeviceGray/ICCBased/
    CalRGB/Indexed).  Converts to CIE Lab.  A color is a CRUSH color when
        chroma C* >= c_min   (it is meant to be a color, not a black / dark gray)
    and L*        <  l_crush (the press can't separate it from black).
    Neutrals (blacks, rich blacks, grays) are never touched, whatever their L*.
  * Scans image XObjects too.  Reports the share of crush pixels and whether a FLAT crush
    color (one exact RGB covering >= flat_min of the image — rasterised art, not a photo
    shadow) is present.
  * --fix lifts ONLY the crush colors: L* raised to l_fix, hue and chroma kept (chroma
    pulled in only as far as the sRGB gamut requires).  CMYK: K is reduced first, then
    CMY scaled.  Every other color op is left byte-for-byte alone.  Images: fixed only
    when a flat crush color is present (--images auto), never (--images never) or always
    (--images always); the image lift is a smooth shadow ramp on chromatic pixels only.
  * --swatches OUT.pdf writes a calibration sheet: 12 hues x L* 10..40 next to a neutral
    of the same L*.  Print it on the Versant once, find the lowest L* row where the hue
    still reads as a color, and put that number in press.json as l_crush.

Thresholds live in press.json next to this script (l_crush, l_fix, c_min, flat_min).

  crushcheck.py job.pdf                      # report, exit 2 if crush colors found
  crushcheck.py job.pdf --fix job_fixed.pdf  # write a lifted copy, report what changed
  crushcheck.py art.png --fix art_fixed.png  # raster art
  crushcheck.py --swatches versant_swatches.pdf
  crushcheck.py job.pdf --json               # machine-readable report

impose.py and labels.py call this automatically (--no-crush-fix to disable);
verify_print.py fails a file that still carries crush colors.
"""
import argparse, json, os, sys, zlib
from collections import OrderedDict

import numpy as np
import pikepdf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = {"l_crush": 24.0, "l_fix": 30.0, "c_min": 10.0, "flat_min": 0.01}
CMYK_PROFILES = [
    os.path.join(HERE, "cmyk.icc"),
    "/usr/share/texlive/texmf-dist/tex/generic/colorprofiles/FOGRA39L_coated.icc",
    "/usr/share/color/icc/ghostscript/default_cmyk.icc",
    "/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc",
]


def load_press():
    p = dict(DEFAULTS)
    f = os.path.join(HERE, "press.json")
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            p.update({k: v for k, v in json.load(fh).items() if k in DEFAULTS})
    return p


# --------------------------------------------------------------------------- color math (sRGB, D65)
_M = np.array([[0.4124564, 0.3575761, 0.1804375],
               [0.2126729, 0.7151522, 0.0721750],
               [0.0193339, 0.1191920, 0.9503041]])
_MI = np.linalg.inv(_M)
_WHITE = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    """rgb float array (...,3) in 0..1 -> Lab (...,3)."""
    c = np.clip(np.asarray(rgb, dtype=np.float64), 0, 1)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M.T / _WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (841 / 108) * xyz + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_to_srgb(lab, clip=True):
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    def finv(t):
        return np.where(t > 6 / 29, t ** 3, (108 / 841) * (t - 4 / 29))
    xyz = np.stack([finv(fx), finv(fy), finv(fz)], axis=-1) * _WHITE
    lin = xyz @ _MI.T
    lin = np.clip(lin, 0, None) if clip else lin
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(np.clip(lin, 0, None), 1 / 2.4) - 0.055)
    return np.clip(c, 0, 1) if clip else c


def chroma(lab):
    return np.hypot(lab[..., 1], lab[..., 2])


_cmyk_tf = None


def cmyk_transform():
    """PIL ImageCms CMYK->Lab transform through the first CMYK profile found, or None."""
    global _cmyk_tf
    if _cmyk_tf is not None:
        return _cmyk_tf or None
    try:
        from PIL import ImageCms
        for p in CMYK_PROFILES:
            if os.path.exists(p):
                _cmyk_tf = (ImageCms.buildTransform(ImageCms.getOpenProfile(p), ImageCms.createProfile("LAB"),
                                                    "CMYK", "LAB", renderingIntent=1), os.path.basename(p))
                return _cmyk_tf
    except Exception:
        pass
    _cmyk_tf = False
    return None


def cmyk_to_lab(cmyk):
    """cmyk floats 0..1 (single color) -> Lab. ICC if available, else naive."""
    tf = cmyk_transform()
    if tf:
        im = Image.new("CMYK", (1, 1), tuple(int(round(v * 255)) for v in cmyk))
        L, a, b = tf[0].apply(im).getpixel((0, 0))
        return np.array([L * 100 / 255, a - 128, b - 128], dtype=np.float64)
    c, m, y, k = cmyk
    rgb = [(1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)]
    return srgb_to_lab(rgb)


def hexstr(rgb01):
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in rgb01)


# --------------------------------------------------------------------------- the rule
def is_crush(lab, press):
    return chroma(lab) >= press["c_min"] and lab[0] < press["l_crush"]


def lift_rgb(rgb01, press):
    """Raise a crush color to l_fix keeping hue; pull chroma in only if sRGB can't hold it."""
    lab = srgb_to_lab(rgb01)
    L, a, b = press["l_fix"], lab[1], lab[2]
    for _ in range(40):
        raw = lab_to_srgb([L, a, b], clip=False)
        if raw.min() >= -0.002 and raw.max() <= 1.002:
            break
        a *= 0.92; b *= 0.92
    return tuple(float(v) for v in np.clip(raw, 0, 1))


def lift_cmyk(cmyk, press):
    """Reduce K until L* >= l_fix; if K hits 0 and it is still too dark, scale CMY down."""
    c, m, y, k = cmyk
    target = press["l_fix"]
    lo, hi = 0.0, k
    if cmyk_to_lab((c, m, y, 0.0))[0] >= target:
        for _ in range(24):                       # bisection on K
            mid = (lo + hi) / 2
            if cmyk_to_lab((c, m, y, mid))[0] >= target:
                lo = mid
            else:
                hi = mid
        return (c, m, y, round(lo, 3))
    lo, hi = 0.0, 1.0                              # K = 0, bisection on CMY scale
    for _ in range(24):
        mid = (lo + hi) / 2
        if cmyk_to_lab((c * mid, m * mid, y * mid, 0.0))[0] >= target:
            lo = mid
        else:
            hi = mid
    return tuple(round(v * lo, 3) for v in (c, m, y)) + (0.0,)


# --------------------------------------------------------------------------- color space resolution
def page_resources(page):
    obj = page.obj if isinstance(page, pikepdf.Page) else page
    node = obj
    while node is not None:
        if "/Resources" in node:
            return node["/Resources"]
        node = node.get("/Parent")
    return pikepdf.Dictionary()


def resolve_cs(name_or_obj, resources):
    """-> (family, n, base) where family in DeviceRGB/DeviceCMYK/DeviceGray/Indexed/Other."""
    cs = name_or_obj
    if isinstance(cs, pikepdf.Name):
        s = str(cs)
        if s in ("/DeviceRGB", "/RGB"):
            return ("DeviceRGB", 3, None)
        if s in ("/DeviceCMYK", "/CMYK"):
            return ("DeviceCMYK", 4, None)
        if s in ("/DeviceGray", "/G"):
            return ("DeviceGray", 1, None)
        if s == "/Pattern":
            return ("Other", 0, None)
        csd = resources.get("/ColorSpace", {}) if resources is not None else {}
        if s in csd:
            return resolve_cs(csd[s], resources)
        return ("Other", 0, None)
    if isinstance(cs, pikepdf.Array) and len(cs) > 0:
        fam = str(cs[0])
        if fam == "/ICCBased":
            n = int(cs[1].get("/N", 3))
            return ({1: "DeviceGray", 3: "DeviceRGB", 4: "DeviceCMYK"}.get(n, "Other"), n, None)
        if fam == "/CalRGB":
            return ("DeviceRGB", 3, None)
        if fam == "/CalGray":
            return ("DeviceGray", 1, None)
        if fam in ("/DeviceRGB", "/DeviceCMYK", "/DeviceGray"):
            return resolve_cs(cs[0], resources)
        if fam == "/Indexed":
            base = resolve_cs(cs[1], resources)
            lookup = cs[3]
            data = lookup.read_bytes() if isinstance(lookup, pikepdf.Stream) else bytes(lookup)
            return ("Indexed", 1, (base, data))
        return ("Other", 0, None)
    return ("Other", 0, None)


def color_to_lab(family, vals, base=None):
    """Return (lab, rgb01 or None, cmyk or None) for a color op, or None if not evaluable."""
    if family == "DeviceRGB" and len(vals) == 3:
        rgb = tuple(min(max(float(v), 0), 1) for v in vals)
        return srgb_to_lab(rgb), rgb, None
    if family == "DeviceCMYK" and len(vals) == 4:
        cmyk = tuple(min(max(float(v), 0), 1) for v in vals)
        return cmyk_to_lab(cmyk), None, cmyk
    if family == "DeviceGray" and len(vals) == 1:
        g = float(vals[0])
        return srgb_to_lab((g, g, g)), (g, g, g), None
    if family == "Indexed" and len(vals) == 1 and base:
        (bfam, n, _), data = base
        i = int(vals[0])
        comp = data[i * n:(i + 1) * n]
        if len(comp) == n:
            return color_to_lab(bfam, [c / 255 for c in comp])
    return None


# --------------------------------------------------------------------------- vector scan / fix
FILL_OPS = {"rg": "DeviceRGB", "k": "DeviceCMYK", "g": "DeviceGray"}
STROKE_OPS = {"RG": "DeviceRGB", "K": "DeviceCMYK", "G": "DeviceGray"}


class Finding:
    def __init__(self, family, vals, lab, rgb, cmyk):
        self.family, self.vals, self.lab, self.rgb, self.cmyk = family, vals, lab, rgb, cmyk
        self.count, self.pages, self.fixed = 0, set(), None

    @property
    def key(self):
        return (self.family, tuple(round(float(v), 4) for v in self.vals))

    def describe(self):
        if self.rgb is not None:
            src = hexstr(self.rgb)
        else:
            src = "CMYK %d/%d/%d/%d" % tuple(int(round(v * 100)) for v in self.cmyk)
        s = f"{src} L*{self.lab[0]:.0f} C*{chroma(self.lab):.0f}"
        if self.fixed is not None:
            f = self.fixed
            if self.rgb is not None:
                s += f" -> {hexstr(f)} L*{srgb_to_lab(f)[0]:.0f}"
            else:
                s += " -> CMYK %d/%d/%d/%d L*%.0f" % (tuple(int(round(v * 100)) for v in f) + (cmyk_to_lab(f)[0],))
        return s + f" ({self.count} op{'s' if self.count != 1 else ''}, p{','.join(str(p) for p in sorted(self.pages))})"


def walk_streams(pdf):
    """Yield (page_no, owner_obj, resources, is_page) for every page and nested form once."""
    seen = set()
    for pno, page in enumerate(pdf.pages, 1):
        res = page_resources(page)
        yield pno, page, res, True
        stack = [res]
        while stack:
            r = stack.pop()
            for _, x in (r.get("/XObject", {}) or {}).items():
                if not isinstance(x, pikepdf.Stream) or x.get("/Subtype") != "/Form":
                    continue
                if x.objgen in seen:
                    continue
                seen.add(x.objgen)
                fres = x.get("/Resources", pikepdf.Dictionary())
                yield pno, x, fres, False
                stack.append(fres)


def scan_vectors(pdf, press, fix=False):
    """Collect crush color findings; with fix=True rewrite the streams in place."""
    findings = OrderedDict()
    shadings = 0
    for pno, owner, res, is_page in walk_streams(pdf):
        try:
            instrs = pikepdf.parse_content_stream(owner)
        except Exception:
            continue
        fill_cs = stroke_cs = ("DeviceGray", 1, None)
        stack = []
        changed = False
        for idx, ins in enumerate(instrs):
            if not isinstance(ins, pikepdf.ContentStreamInstruction):
                continue
            op = str(ins.operator)
            ops = ins.operands
            if op == "q":
                stack.append((fill_cs, stroke_cs)); continue
            if op == "Q":
                if stack:
                    fill_cs, stroke_cs = stack.pop()
                continue
            if op == "cs":
                fill_cs = resolve_cs(ops[0], res); continue
            if op == "CS":
                stroke_cs = resolve_cs(ops[0], res); continue
            if op == "sh":
                shadings += 1; continue
            if op in FILL_OPS or op in STROKE_OPS:
                family, base = (FILL_OPS.get(op) or STROKE_OPS.get(op)), None
            elif op in ("sc", "scn"):
                family, _, base = fill_cs
            elif op in ("SC", "SCN"):
                family, _, base = stroke_cs
            else:
                continue
            if family in ("Other",) or any(isinstance(o, pikepdf.Name) for o in ops):
                continue
            vals = [float(o) for o in ops]
            r = color_to_lab(family, vals, base)
            if r is None:
                continue
            lab, rgb, cmyk = r
            if not is_crush(lab, press):
                continue
            f = Finding(family, vals, lab, rgb, cmyk)
            f = findings.setdefault(f.key, f)
            f.count += 1; f.pages.add(pno)
            if fix and family in ("DeviceRGB", "DeviceCMYK"):
                if f.fixed is None:
                    f.fixed = lift_rgb(rgb, press) if rgb is not None else lift_cmyk(cmyk, press)
                new = [round(float(v), 4) for v in f.fixed]
                instrs[idx] = pikepdf.ContentStreamInstruction(new, ins.operator)
                changed = True
        if fix and changed:
            data = pikepdf.unparse_content_stream(instrs)
            if is_page:
                owner.Contents = pdf.make_stream(data)
            else:
                owner.write(data)
    return list(findings.values()), shadings


# --------------------------------------------------------------------------- images
def image_lab(im, max_px=400):
    """PIL image -> (Lab array (h,w,3) downsampled, rgb01 array)."""
    im = im.convert("RGB")
    s = max(im.size) / max_px
    if s > 1:
        im = im.resize((max(1, int(im.width / s)), max(1, int(im.height / s))), Image.BILINEAR)
    rgb = np.asarray(im).astype(np.float64) / 255
    return srgb_to_lab(rgb), rgb


def analyse_image(im, press):
    lab, rgb = image_lab(im)
    mask = (chroma(lab) >= press["c_min"]) & (lab[..., 0] < press["l_crush"])
    share = float(mask.mean())
    flats = []
    if mask.any():
        q = (rgb[mask] * 255).round().astype(int)
        keys, counts = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
        tot = mask.size
        for k, c in sorted(zip(keys, counts), key=lambda t: -t[1])[:3]:
            if c / tot >= press["flat_min"]:
                r, g, b = (k >> 16) & 255, (k >> 8) & 255, k & 255
                flats.append((hexstr((r / 255, g / 255, b / 255)), float(srgb_to_lab([r / 255, g / 255, b / 255])[0]), c / tot))
    return share, flats


def lift_image(im, press):
    """Smooth shadow lift on chromatic pixels only (neutrals untouched). Returns RGB PIL image."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float64) / 255
    lab = srgb_to_lab(rgb)
    L, C = lab[..., 0], chroma(lab)
    l_hi = press["l_fix"] + 10.0
    l_lo = max(press["l_crush"] - 4.0, 0.0)
    w = np.clip((C - press["c_min"]) / 8.0, 0, 1) * (L < l_hi)
    L2 = l_lo + L * (l_hi - l_lo) / l_hi
    L3 = L + w * (L2 - L)
    # The chroma ramp only half-lifts colors just over c_min (C* 10-18): they stayed below the line
    # and verify_print failed the file. Every pixel the detector flags now clears l_crush, same hue.
    flagged = (C >= press["c_min"]) & (L < press["l_crush"])
    lab[..., 0] = np.where(flagged, np.maximum(L3, press["l_crush"] + 1.0), L3)
    out = (lab_to_srgb(lab) * 255).round().astype(np.uint8)
    return Image.fromarray(out, "RGB")


def walk_images(pdf):
    seen = set()
    for pno, owner, res, _ in walk_streams(pdf):
        for name, x in (res.get("/XObject", {}) or {}).items():
            if isinstance(x, pikepdf.Stream) and x.get("/Subtype") == "/Image" and x.objgen not in seen:
                seen.add(x.objgen)
                yield pno, str(name), x


def scan_images(pdf, press, mode="auto"):
    """-> list of dicts per image with crush share / flats; fixes per mode (never/auto/always)."""
    out = []
    for pno, name, x in walk_images(pdf):
        try:
            pim = pikepdf.PdfImage(x)
            im = pim.as_pil_image()
        except Exception as e:
            out.append({"page": pno, "name": name, "skipped": str(e)[:60]}); continue
        if im.mode in ("1", "L", "LA", "I", "I;16"):
            continue                                  # gray / bilevel can't crush a hue
        share, flats = analyse_image(im, press)
        rec = {"page": pno, "name": name, "w": im.width, "h": im.height, "share": share, "flats": flats, "fixed": False}
        want = mode == "always" or (mode == "auto" and flats)
        can = im.mode in ("RGB", "RGBA", "P", "L", "LA") and "/Mask" not in x and "/Decode" not in x
        if want and share > 0 and can:
            new = lift_image(im, press)
            raw = new.tobytes()
            x.write(zlib.compress(raw, 6), filter=pikepdf.Name("/FlateDecode"))
            x.Width, x.Height = new.width, new.height
            x.ColorSpace = pikepdf.Name("/DeviceRGB")
            x.BitsPerComponent = 8
            for k in ("/DecodeParms", "/Decode", "/Interpolate"):
                if k in x:
                    del x[k]
            rec["fixed"] = True
        elif want and share > 0:
            rec["skipped"] = f"mode {im.mode} / masked image not rewritten"
        out.append(rec)
    return out


# --------------------------------------------------------------------------- public entry points
def check_pdf(path_or_pdf, press=None, fix=False, images="auto"):
    press = press or load_press()
    pdf = path_or_pdf if isinstance(path_or_pdf, pikepdf.Pdf) else pikepdf.open(path_or_pdf)
    vec, shadings = scan_vectors(pdf, press, fix=fix)
    imgs = scan_images(pdf, press, mode=images if fix else "never")
    return {"press": press, "vectors": vec, "shadings": shadings, "images": imgs, "pdf": pdf}


def fix_pil(im, press=None):
    """For raster sources (labels.py / impose.py images): lift only if a flat crush color is present."""
    press = press or load_press()
    share, flats = analyse_image(im, press)
    if flats:
        return lift_image(im, press), share, flats
    return im, share, flats


def summarise(rep, verbose=True):
    """Human report lines. Returns (lines, n_vector_crush, n_image_flat)."""
    p = rep["press"]
    lines = []
    vec = rep["vectors"]
    fixed = [f for f in vec if f.fixed is not None]
    for f in vec:
        lines.append(("LIFT  " if f.fixed is not None else "CRUSH ") + f.describe())
    flat_imgs = [i for i in rep["images"] if i.get("flats")]
    for i in rep["images"]:
        if i.get("skipped") and not i.get("flats"):
            continue
        if i.get("flats"):
            fl = ", ".join(f"{h} L*{L:.0f} {s:.0%}" for h, L, s in i["flats"])
            lines.append((("LIFT  " if i["fixed"] else "CRUSH ") +
                          f"image {i['name']} p{i['page']} {i['w']}x{i['h']}: flat crush color {fl}"
                          + (f" — {i['skipped']}" if i.get("skipped") else "")))
        elif verbose and i.get("share", 0) >= 0.02:
            lines.append(f"note  image {i['name']} p{i['page']}: {i['share']:.0%} of pixels are chromatic below L*{p['l_crush']:g} "
                         f"(photo shadows — left alone{', use --images always to lift' if not i['fixed'] else ''})")
    if rep["shadings"]:
        lines.append(f"note  {rep['shadings']} gradient(s) not evaluated — check dark gradient ends by eye")
    if not vec and not flat_imgs:
        lines.append(f"OK    no chromatic color below L*{p['l_crush']:g} (C* >= {p['c_min']:g}) in vectors or flat image areas")
    return lines, len(vec) - len(fixed), len([i for i in flat_imgs if not i["fixed"]])


# --------------------------------------------------------------------------- swatch sheet
def write_swatches(out, press):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    IN = 72
    c = canvas.Canvas(out, pagesize=letter)
    W, H = letter
    Ls = list(range(10, 42, 2))
    hues = list(range(0, 360, 30))
    cols = len(hues) + 2
    cw, ch = 0.56 * IN, 0.42 * IN
    x0 = (W - cols * cw) / 2
    y0 = H - 1.85 * IN
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x0, H - 0.7 * IN, "Rainbow crush calibration — Xerox Versant 180")
    c.setFont("Helvetica", 8.5)
    intro = ["Print as a normal job (same stock and Fiery preset as customer work).",
             "Each row is one L*. Colored cells: 12 hues at C* 30 (or the most sRGB allows, printed in each cell);",
             "the last two cells are a neutral gray of the same L* and 100K.",
             "Find the LOWEST row where every hue still reads as a color next to its neutral. Put that L* in",
             f"tools/press.json as l_crush (now {press['l_crush']:g}); l_fix should sit about 6 above it (now {press['l_fix']:g})."]
    for i, t in enumerate(intro):
        c.drawString(x0, H - 0.92 * IN - i * 11, t)
    c.setFont("Helvetica", 7)
    for j, hdeg in enumerate(hues):
        c.setFillGray(0)
        c.drawCentredString(x0 + (j + 0.5) * cw, y0 + 4, f"h{hdeg}")
    c.drawCentredString(x0 + (len(hues) + 0.5) * cw, y0 + 4, "neutral")
    c.drawCentredString(x0 + (len(hues) + 1.5) * cw, y0 + 4, "100K")
    for i, L in enumerate(Ls):
        y = y0 - (i + 1) * ch
        c.setFillGray(0); c.setFont("Helvetica-Bold", 8)
        c.drawRightString(x0 - 4, y + ch / 2 - 3, f"L*{L}")
        for j, hdeg in enumerate(hues):
            C = 30.0
            for _ in range(60):
                a, b = C * np.cos(np.radians(hdeg)), C * np.sin(np.radians(hdeg))
                raw = lab_to_srgb([L, a, b], clip=False)
                if raw.min() >= -0.002 and raw.max() <= 1.002:
                    break
                C *= 0.95
            rgb = np.clip(raw, 0, 1)
            c.setFillColorRGB(*rgb); c.rect(x0 + j * cw, y, cw, ch, stroke=0, fill=1)
            c.setFillGray(1 if L < 50 else 0); c.setFont("Helvetica", 5)
            c.drawString(x0 + j * cw + 2, y + 2, f"C{C:.0f}")
        g = float(lab_to_srgb([L, 0, 0])[0])
        c.setFillColorRGB(g, g, g); c.rect(x0 + len(hues) * cw, y, cw, ch, stroke=0, fill=1)
        c.setFillColorCMYK(0, 0, 0, 1); c.rect(x0 + (len(hues) + 1) * cw, y, cw, ch, stroke=0, fill=1)
    c.setFillGray(0); c.setFont("Helvetica", 8)
    c.drawString(x0, y0 - (len(Ls) + 1) * ch - 6,
                 "Rule the tools apply: chromatic (C* >= c_min) AND L* < l_crush  ->  lifted to L*=l_fix, same hue. Neutrals never touched.")
    c.showPage(); c.save()


# --------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="PDF or raster image")
    ap.add_argument("--fix", metavar="OUT", help="write a copy with crush colors lifted")
    ap.add_argument("--images", choices=["auto", "never", "always"], default="auto",
                    help="lift image pixels: auto = only images with a flat crush color (default)")
    ap.add_argument("--l-crush", type=float); ap.add_argument("--l-fix", type=float); ap.add_argument("--c-min", type=float)
    ap.add_argument("--swatches", metavar="OUT", help="write the Versant calibration sheet and exit")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args()
    press = load_press()
    for k in ("l_crush", "l_fix", "c_min"):
        if getattr(args, k) is not None:
            press[k] = getattr(args, k)
    if args.swatches:
        write_swatches(args.swatches, press)
        print(f"wrote {args.swatches} — print on the Versant, set l_crush in press.json")
        return 0
    if not args.source:
        ap.error("give a PDF/image or --swatches")
    ext = os.path.splitext(args.source)[1].lower()
    tf = cmyk_transform()
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        im = Image.open(args.source)
        share, flats = analyse_image(im, press)
        if flats:
            fl = ", ".join(f"{h} L*{L:.0f} {s:.0%}" for h, L, s in flats)
            print(f"CRUSH flat crush color(s): {fl}")
            if args.fix:
                lift_image(im, press).save(args.fix, dpi=im.info.get("dpi"))
                print(f"wrote {args.fix} (chromatic shadows lifted, neutrals untouched)")
                return 0
            return 2
        print(f"OK    no flat crush color ({share:.1%} of pixels chromatic below L*{press['l_crush']:g})")
        return 0
    rep = check_pdf(args.source, press, fix=bool(args.fix), images=args.images)
    lines, n_vec, n_img = summarise(rep)
    if args.json:
        print(json.dumps({"press": press, "vectors": [f.describe() for f in rep["vectors"]],
                          "images": [{k: v for k, v in i.items()} for i in rep["images"]],
                          "shadings": rep["shadings"]}, indent=1, default=str))
    else:
        print(f"{os.path.basename(args.source)}  (l_crush {press['l_crush']:g}, l_fix {press['l_fix']:g}, c_min {press['c_min']:g}"
              f"{', CMYK via ' + tf[1] if tf else ', CMYK naive'})")
        for l in lines:
            print("  " + l)
    if args.fix:
        rep["pdf"].save(args.fix)
        print(f"wrote {args.fix}")
        if n_vec == 0 and any(f.fixed is not None for f in rep["vectors"]) or any(i.get("fixed") for i in rep["images"]):
            print(">>> TELL ANDREW: colors were changed in this file (LIFT lines above). Always report every lift. <<<")
        return 0
    return 2 if (n_vec or n_img) else 0


if __name__ == "__main__":
    sys.exit(main())
