#!/usr/bin/env python3
"""
pdfinspect.py — what did the customer actually send?

Prints, per page: media/crop/trim/bleed boxes in inches, rotation, whether the
page size matches a common trim (or trim + bleed), image resolution at the
placed size, unembedded fonts, and the producer (macOS Quartz files are flagged —
they are the ones that throw Acrobat error 109 on Windows).

  python3 pdfinspect.py customer.pdf
  python3 pdfinspect.py customer.pdf --clean            # rewrite a clean copy: <name>_clean.pdf
  python3 pdfinspect.py customer.pdf --clean --out fixed.pdf
  python3 pdfinspect.py customer.pdf --json             # machine-readable
"""
import argparse, json, os, sys
import pikepdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crushcheck  # noqa: E402

IN = 72.0
COMMON = {  # name: (w, h) inches
    "business card": (3.5, 2), "4x6": (4, 6), "5x7": (5, 7), "5x5": (5, 5), "3x3": (3, 3), "2x2": (2, 2),
    "3.5x5": (3.5, 5), "4x8": (4, 8), "4x9 rack card": (4, 9), "5.5x8.5 half letter": (5.5, 8.5),
    "8x10": (8, 10), "letter": (8.5, 11), "legal": (8.5, 14), "tabloid": (11, 17), "11x14": (11, 14),
    "12x18": (12, 18), "13x19": (13, 19), "16x20": (16, 20), "18x24": (18, 24), "24x36": (24, 36),
    "a4": (8.27, 11.69), "a5": (5.83, 8.27), "#10 envelope": (9.5, 4.125), "a7 envelope": (7.25, 5.25),
    "a2 envelope": (5.75, 4.375),
}


def box(page, name):
    if name not in page.obj:
        return None
    x0, y0, x1, y1 = (float(v) for v in page.obj[name])
    return (min(x0, x1) / IN, min(y0, y1) / IN, max(x0, x1) / IN, max(y0, y1) / IN)


def match_size(w, h, bleed=0.1, tol=0.03):
    hits = []
    for name, (cw, ch) in COMMON.items():
        for (a, b) in ((cw, ch), (ch, cw)):
            if abs(w - a) <= tol and abs(h - b) <= tol:
                hits.append(f"{name} at trim")
            elif abs(w - a - 2 * bleed) <= tol and abs(h - b - 2 * bleed) <= tol:
                hits.append(f"{name} + {bleed:g} in bleed")
            elif abs(w - a - 0.25) <= tol and abs(h - b - 0.25) <= tol:
                hits.append(f"{name} + 0.125 in bleed")
    return hits


def page_images(page, disp_w_in, disp_h_in):
    """Effective dpi of each placed image, by walking the content stream's CTM.
    Falls back to 'if it filled the page' when the image is drawn inside a form XObject."""
    out = []
    res = page.obj.get("/Resources", {})
    xo = res.get("/XObject", {}) if res else {}
    if not xo:
        return out
    placed = {}  # name -> list of (w_in, h_in)
    try:
        stack, ctm = [], pikepdf.Matrix()
        for operands, op in pikepdf.parse_content_stream(page):
            o = str(op)
            if o == "q":
                stack.append(ctm)
            elif o == "Q":
                ctm = stack.pop() if stack else pikepdf.Matrix()
            elif o == "cm":
                ctm = pikepdf.Matrix(*[float(v) for v in operands]) @ ctm
            elif o == "Do":
                name = str(operands[0])
                # unit square -> device: width = |(a,b)|, height = |(c,d)|
                w = (ctm.a ** 2 + ctm.b ** 2) ** 0.5 / IN
                h = (ctm.c ** 2 + ctm.d ** 2) ** 0.5 / IN
                placed.setdefault(name, []).append((w, h))
    except Exception:
        pass
    for name, ref in xo.items():
        try:
            o = ref
            sub = str(o.get("/Subtype", ""))
            if sub == "/Image":
                w, h = int(o.Width), int(o.Height)
                sizes = placed.get(str(name)) or [(disp_w_in, disp_h_in)]
                exact = str(name) in placed
                for (pw, ph) in sizes[:1]:
                    out.append({"name": str(name), "px": [w, h], "placed_in": [round(pw, 2), round(ph, 2)],
                                "dpi": round(min(w / max(pw, 1e-6), h / max(ph, 1e-6))), "exact": exact,
                                "filter": filt(o), "cs": str(o.get("/ColorSpace", ""))[:24]})
            elif sub == "/Form":
                # look one level down for images inside forms (common in Illustrator/InDesign exports)
                fres = o.get("/Resources", {})
                fxo = fres.get("/XObject", {}) if fres else {}
                for n2, r2 in (fxo.items() if fxo else []):
                    if str(r2.get("/Subtype", "")) == "/Image":
                        w, h = int(r2.Width), int(r2.Height)
                        out.append({"name": f"{name}/{n2}", "px": [w, h], "placed_in": [round(disp_w_in, 2), round(disp_h_in, 2)],
                                    "dpi": round(min(w / disp_w_in, h / disp_h_in)), "exact": False,
                                    "filter": filt(r2), "cs": str(r2.get("/ColorSpace", ""))[:24]})
        except Exception:
            pass
    return out


def filt(o):
    f = o.get("/Filter", "")
    if isinstance(f, pikepdf.Array):
        return "+".join(str(x).lstrip("/") for x in f)
    return str(f).lstrip("/")


def fonts(page):
    bad = set()
    res = page.obj.get("/Resources", {})
    fd = res.get("/Font", {}) if res else {}
    for name, f in (fd.items() if fd else []):
        try:
            desc = f.get("/FontDescriptor")
            if f.get("/Subtype") == "/Type0":
                desc = f.DescendantFonts[0].get("/FontDescriptor")
            if desc is None or not any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                base = str(f.get("/BaseFont", name))
                if base.lstrip("/") not in ("Helvetica", "Times-Roman", "Courier", "Symbol", "ZapfDingbats"):
                    bad.add(base)
        except Exception:
            pass
    return sorted(bad)


def inspect(path, bleed):
    pdf = pikepdf.open(path)
    info = {"file": os.path.basename(path), "pages": len(pdf.pages), "producer": str(pdf.docinfo.get("/Producer", "")),
            "creator": str(pdf.docinfo.get("/Creator", "")), "warnings": [], "page_info": []}
    if "Quartz" in info["producer"] or "Quartz" in info["creator"]:
        info["warnings"].append("macOS Quartz PDF — known to throw Acrobat error 109 on Windows; use --clean before sending to the Fiery")
    if pdf.is_encrypted:
        info["warnings"].append("encrypted")
    sizes = set()
    for i, page in enumerate(pdf.pages):
        mb, cb, tb, bb = box(page, "/MediaBox"), box(page, "/CropBox"), box(page, "/TrimBox"), box(page, "/BleedBox")
        rot = int(page.obj.get("/Rotate", 0)) % 360
        vis = cb or mb
        w, h = vis[2] - vis[0], vis[3] - vis[1]
        if rot in (90, 270):
            w, h = h, w
        sizes.add((round(w, 2), round(h, 2)))
        p = {"page": i + 1, "size_in": [round(w, 3), round(h, 3)], "rotate": rot,
             "mediabox": [round(v, 3) for v in mb] if mb else None,
             "cropbox": [round(v, 3) for v in cb] if cb else None,
             "trimbox": [round(v, 3) for v in tb] if tb else None,
             "bleedbox": [round(v, 3) for v in bb] if bb else None,
             "looks_like": match_size(w, h, bleed), "images": page_images(page, w, h), "unembedded_fonts": fonts(page)}
        if tb:
            p["trim_size_in"] = [round(tb[2] - tb[0], 3), round(tb[3] - tb[1], 3)]
            p["bleed_available_in"] = round(min(tb[0] - vis[0], tb[1] - vis[1], vis[2] - tb[2], vis[3] - tb[3]), 3)
        if p["unembedded_fonts"]:
            info["warnings"].append(f"p{i+1}: unembedded fonts {p['unembedded_fonts']} — text may reflow/substitute on the RIP")
        for im in p["images"]:
            if im["exact"] and im["dpi"] < 200:
                info["warnings"].append(f"p{i+1}: image {im['px'][0]}x{im['px'][1]} px placed at {im['placed_in'][0]:g}x{im['placed_in'][1]:g} in = {im['dpi']} dpi")
        info["page_info"].append(p)
    if len(sizes) > 1:
        info["warnings"].append(f"mixed page sizes: {sorted(sizes)}")
    return pdf, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--bleed", type=float, default=0.1, help="bleed to test page sizes against (default 0.1)")
    ap.add_argument("--clean", action="store_true", help="rewrite a clean, linearized copy (fixes Quartz/Acrobat 109, stale xref, incremental saves)")
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    pdf, info = inspect(args.pdf, args.bleed)
    if args.json:
        print(json.dumps(info, indent=1))
    else:
        print(f"{info['file']}: {info['pages']} page(s)  producer: {info['producer'] or '?'}  creator: {info['creator'] or '?'}")
        for p in info["page_info"]:
            line = f"  p{p['page']}: {p['size_in'][0]:g}x{p['size_in'][1]:g} in"
            if p["rotate"]:
                line += f" (/Rotate {p['rotate']})"
            if p.get("trim_size_in"):
                line += f"  TrimBox {p['trim_size_in'][0]:g}x{p['trim_size_in'][1]:g}, {p['bleed_available_in']:g} in bleed available"
            if p["looks_like"]:
                line += "  ~ " + " | ".join(p["looks_like"])
            print(line)
            for im in p["images"]:
                print(f"       image {im['px'][0]}x{im['px'][1]} px  placed {im['placed_in'][0]:g}x{im['placed_in'][1]:g} in  "
                      f"{'' if im['exact'] else '<= '}{im['dpi']} dpi  {im['filter']} {im['cs']}")
        for w in info["warnings"]:
            print(f"  WARN  {w}")
        if not info["warnings"]:
            print("  no warnings")
        try:
            rep = crushcheck.check_pdf(pikepdf.open(args.pdf))
            lines, n_vec, n_img = crushcheck.summarise(rep, verbose=False)
            if n_vec or n_img:
                print(f"  CRUSH {n_vec + n_img} color(s) will print as black on the Versant — impose.py/labels.py lift them automatically:")
                for l in lines:
                    if l.startswith("CRUSH"):
                        print(f"        {l[6:]}")
            else:
                print(f"  crush check: clean (no chromatic color below L*{rep['press']['l_crush']:g})")
        except Exception as e:
            print(f"  crush check skipped: {e}")
    if args.clean:
        out = args.out or os.path.splitext(args.pdf)[0] + "_clean.pdf"
        # Full rewrite: drops incremental-update junk, normalises objects, linearizes.
        pdf.remove_unreferenced_resources()
        pdf.save(out, linearize=True, object_stream_mode=pikepdf.ObjectStreamMode.generate,
                 fix_metadata_version=True)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
