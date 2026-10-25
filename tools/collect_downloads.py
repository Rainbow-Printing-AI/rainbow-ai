#!/usr/bin/env python3
"""collect_downloads.py - move files Chrome just downloaded into a job folder, and prove they're real.

Chrome on the shop computer saves to the Rainbow folder root (Mac ~/Downloads/Rainbow, Windows C:/Rainbow). After Claude has
Chrome pull Gmail attachments / private Drive / OneDrive files, run this to:
  1. wait until every expected file has finished (no *.crdownload left, file present),
  2. move each one into the job folder (never overwrites: "name (2).pdf"),
  3. check the bytes are the file type the name says, not an HTML sign-in / error page,
  4. print one line per file and a list of anything missing or bad.

    python3 collect_downloads.py --to "Peter Rulon-Miller - 4 JOBS 10.8.26" "DEMO.pdf" "EDIT GROUP.pdf"
    python3 collect_downloads.py --to OUT --since 1791484500 --any     # everything newer than a unix time

Expected names match Chrome's de-dupe variants too ("DEMO (1).pdf" when DEMO.pdf already existed).
Exit 0 = every expected file collected and valid; 1 = something missing/bad (listed).
"""
import argparse, os, re, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MAGIC = {  # ext -> accepted leading bytes
    ".pdf": [b"%PDF"], ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"], ".png": [b"\x89PNG"],
    ".gif": [b"GIF8"], ".tif": [b"II*\x00", b"MM\x00*"], ".tiff": [b"II*\x00", b"MM\x00*"],
    ".zip": [b"PK"], ".docx": [b"PK"], ".xlsx": [b"PK"], ".pptx": [b"PK"],
    ".doc": [b"\xd0\xcf\x11\xe0"], ".xls": [b"\xd0\xcf\x11\xe0"], ".ppt": [b"\xd0\xcf\x11\xe0"],
    ".psd": [b"8BPS"], ".ai": [b"%PDF", b"%!PS"], ".eps": [b"%!PS", b"\xc5\xd0\xd3\xc6"],
    ".heic": [], ".webp": [b"RIFF"], ".svg": [b"<"],
}


def looks_html(head):
    h = head.lstrip()[:200].lower()
    return h.startswith(b"<!doctype html") or h.startswith(b"<html") or b"<head" in h


def check(path):
    with open(path, "rb") as f:
        head = f.read(512)
    ext = os.path.splitext(path)[1].lower()
    if not head:
        return "EMPTY file"
    if ext != ".svg" and looks_html(head):
        return "HTML page, not the file (sign-in / permission / error page)"
    ok = MAGIC.get(ext)
    if ok and not any(head.startswith(m) for m in ok):
        return f"bytes don't look like {ext} (starts {head[:8]!r})"
    if ext == ".heic" and b"ftyp" not in head[:16]:
        return "bytes don't look like HEIC"
    return None


def variants(src, name):
    base, ext = os.path.splitext(name)
    pat = re.compile(re.escape(base) + r"( \(\d+\))?" + re.escape(ext) + r"$", re.I)
    hits = [f for f in os.listdir(src) if pat.match(f)]
    return sorted(hits, key=lambda f: os.path.getmtime(os.path.join(src, f)), reverse=True)


def unique(dest, name):
    base, ext = os.path.splitext(name)
    p, n = os.path.join(dest, name), 2
    while os.path.exists(p):
        p, n = os.path.join(dest, f"{base} ({n}){ext}"), n + 1
    return p


def describe(path):
    n = os.path.getsize(path)
    extra = ""
    if path.lower().endswith(".png"):
        try:
            from PIL import Image
            with Image.open(path) as im:
                extra = f"  {im.width}x{im.height}px"
                if n < 150_000 and max(im.size) < 800:
                    extra += "  <- small PNG, possibly a logo"
        except Exception:
            pass
    return f"{n/1e6:8.2f} MB{extra}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="filenames Chrome was asked to download")
    ap.add_argument("--to", required=True, help="job folder (created if missing; relative = inside --src)")
    ap.add_argument("--src", default=os.path.dirname(HERE), help="Chrome download folder (default: the Rainbow folder)")
    ap.add_argument("--since", type=float, help="with --any: unix time; collect every file modified after it")
    ap.add_argument("--any", action="store_true", help="collect all new files since --since instead of named ones")
    ap.add_argument("--timeout", type=int, default=150, help="seconds to wait for downloads to finish (default 150)")
    a = ap.parse_args()
    if not a.names and not a.any:
        ap.error("give filenames, or --any --since T")
    dest = a.to if os.path.isabs(a.to) else os.path.join(a.src, a.to)
    os.makedirs(dest, exist_ok=True)

    deadline = time.time() + a.timeout
    while True:
        partial = [f for f in os.listdir(a.src) if f.endswith(".crdownload")]
        missing = [n for n in a.names if not variants(a.src, n)]
        if (not partial and not missing) or time.time() > deadline:
            break
        time.sleep(3)

    picks = []
    if a.any:
        skip = {".DS_Store"}
        for f in os.listdir(a.src):
            p = os.path.join(a.src, f)
            if f in skip or f.endswith(".crdownload") or not os.path.isfile(p):
                continue
            if a.since is None or os.path.getmtime(p) > a.since:
                picks.append((f, f))
    for n in a.names:
        v = variants(a.src, n)
        if v:
            picks.append((v[0], n))

    bad = []
    for f, want in dict.fromkeys(picks):
        srcp = os.path.join(a.src, f)
        problem = check(srcp)
        if problem:
            bad.append(f"{f}: {problem} (left in place)")
            continue
        dst = unique(dest, want)
        shutil.move(srcp, dst)
        print(f"OK    {describe(dst)}  {os.path.basename(dst)}")

    for n in missing:
        bad.append(f"{n}: never arrived in {a.src} within {a.timeout}s")
    for f in partial:
        if os.path.exists(os.path.join(a.src, f)):
            bad.append(f"{f}: download still in progress / stalled")
    if bad:
        print("\nPROBLEMS:")
        for b in bad:
            print("  - " + b)
    print(f"\n{len(picks) - sum(1 for b in bad if 'left in place' in b)} file(s) in {dest}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
