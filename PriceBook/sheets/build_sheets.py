#!/usr/bin/env python3
"""build_sheets.py - regenerate Rainbow's laminated counter price sheets from data/prices.csv.

    python3 sheets/build_sheets.py              # build every sheet -> PriceBook/Counter Sheets/
    python3 sheets/build_sheets.py 04 06        # only sheets 04 and 06
    python3 sheets/build_sheets.py --list       # list the sheets
    python3 sheets/build_sheets.py --no-pdf     # .docx only
    python3 sheets/build_sheets.py --out DIR    # write somewhere else (tests)

Each sheet module sheets/sNN_<name>.py defines:
    SHEET = {"num": "04", "name": "Bindery", "title": "...", "source": "scan_147 p04",
             "covers": ["Bindery & Finishing", ...],    # categories this sheet must fully list
             "pages": 1}                                 # optional, default 1 (06 is a 2-page duplex)
    def build(pb: sheetlib.Prices) -> docx.Document
Always follow with:  python3 sheets/audit_sheets.py   (must print RESULT PASS)
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sheetlib  # noqa: E402


def discover():
    mods = []
    for f in sorted(HERE.glob("s[0-9][0-9]_*.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        mods.append(m)
    return mods


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="*", help="sheet numbers to build (default: all)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--csv", type=Path, default=None)
    a = ap.parse_args(argv)
    mods = discover()
    if a.list:
        for m in mods:
            s = m.SHEET
            print(f"{s['num']}  {s['name']:<22} {s['title']}  ({s['source']})")
        return 0
    bad = 0
    for m in mods:
        s = m.SHEET
        if a.only and s["num"] not in a.only:
            continue
        pb = sheetlib.Prices(a.csv or sheetlib.DEFAULT_CSV)
        try:
            doc = m.build(pb)
            man = sheetlib.save_sheet(doc, s, pb, a.out, pdf=not a.no_pdf)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {s['num']} {s['name']}: {e}")
            bad += 1
            continue
        pages = man.get("pages", "-")
        want = s.get("pages", 1)
        flag = "" if pages in (want, "-") else f"   <-- {pages} PAGES (must be {want})"
        pend = f"  ({len(man['pending_ids'])} pending)" if man["pending_ids"] else ""
        print(f"ok    {s['num']} {s['name']:<22} {len(man['used_ids']):>3} prices{pend}  -> {man['docx']}{flag}")
        if flag:
            bad += 1
    print("RESULT", "PASS" if not bad else f"FAIL ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
