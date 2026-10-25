#!/usr/bin/env python3
"""audit_sheets.py - deterministic checks on the built counter sheets.

    python3 sheets/audit_sheets.py            # audit every built sheet
    python3 sheets/audit_sheets.py 04         # one sheet
    python3 sheets/audit_sheets.py --out DIR  # sheets built into DIR

Checks per sheet (FAIL unless noted):
  1. PDF has exactly SHEET['pages'] pages (default 1), each with >= MIN_SLACK_IN (0.35 in)
     free above the bottom margin.
  2. Every money figure printed on the PDF ($4.88, $.25, 3.74, 40 cents ...) is the current
     price / price_max / min_charge of a row the sheet used.  Anything else = stale or typed-in.
  3. Every used row's price actually appears on the PDF.
  4. Every live (active/pending) row in the sheet's SHEET['covers'] categories is used, or was
     explicitly pb.exclude()'d with a reason (exclusions are listed as WARN).
  5. Used rows are live; pending rows are listed as WARN.
  6. The sheet module contains no typed-in dollar amounts.
  7. No trade cost (the 'cost' column) is printed unless it is also a used price.
Prints RESULT PASS / RESULT FAIL.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sheetlib  # noqa: E402
from build_sheets import discover  # noqa: E402

MONEY_RES = [
    re.compile(r"\$\s?(\d[\d,]*\.\d{2})"),       # $4.88  $1,234.50
    re.compile(r"\$\s?(\.\d{2})"),               # $.25
    re.compile(r"\$\s?(\d[\d,]*)(?![\d.,])"),   # $20
    re.compile(r"(?<![\d.$/x])(\d{1,4}\.\d{2})(?![\d])"),  # bare 3.74 (pens, grids)
    re.compile(r"(?<![\d.$])(\.\d{2})(?![\d])"),            # bare .99
    re.compile(r"(\d{1,2}) ?(?:cents|¢)", re.I),       # 40 cents / 40¢
]


def money_tokens(text: str) -> list[tuple[str, Decimal]]:
    found = []
    spans = []
    for i, rx in enumerate(MONEY_RES):
        for m in rx.finditer(text):
            if any(a <= m.start() < b for a, b in spans):
                continue
            raw = m.group(1).replace(",", "")
            if i == 5:
                val = Decimal(raw) / 100
            else:
                val = Decimal(raw if not raw.startswith(".") else "0" + raw)
            found.append((m.group(0).strip(), val.quantize(Decimal("0.01"))))
            spans.append((m.start(), m.end()))
    return found


def pdf_text(pdf: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, encoding="utf-8").stdout


def src_problems(path: Path) -> list[str]:
    probs = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#", 1)[0]
        if re.search(r"""["'][^"']*\$\s?\.?\d""", code):
            probs.append(f"{path.name}:{n}: typed-in dollar amount: {line.strip()[:90]}")
        elif re.search(r"""["']\s*\d+\.\d{2}\s*["']""", code):
            probs.append(f"{path.name}:{n}: typed-in price-like number: {line.strip()[:90]}")
    return probs


def audit_one(mod, out_dir: Path, pb_all: sheetlib.Prices) -> tuple[int, list[str]]:
    s = mod.SHEET
    stem = f"Rainbow_Sheet_{s['num']}_{s['name']}"
    lines = []
    fails = 0

    def F(msg):
        nonlocal fails
        fails += 1
        lines.append("  FAIL " + msg)

    def W(msg):
        lines.append("  warn " + msg)

    manp = out_dir / f"{stem}.manifest.json"
    pdf = out_dir / f"{stem}.pdf"
    if not manp.exists() or not pdf.exists():
        F("not built (run build_sheets.py)")
        return fails, lines
    man = json.loads(manp.read_text(encoding="utf-8"))
    want = s.get("pages", 1)
    if man.get("pages") != want:
        F(f"PDF has {man.get('pages')} pages, must be {want}")
    else:
        need = s.get("min_slack_in", sheetlib.MIN_SLACK_IN)
        for pg in range(1, want + 1):
            sl = sheetlib.bottom_slack_in(pdf, out_dir / f"{stem}.docx", page=pg)
            if sl < need:
                F(f"page {pg}: only {sl:.2f} in free above the bottom margin (need {need:.2f}) - Word/other LibreOffice versions may spill onto another page")
    used = man["used_ids"]
    allowed: dict[Decimal, list[str]] = {}
    for rid in used:
        r = pb_all.by_id.get(rid)
        if r is None:
            F(f"used id {rid} no longer exists")
            continue
        if r["status"] not in sheetlib.LIVE:
            F(f"used id {rid} is {r['status']}")
        if r["status"] == "pending":
            W(f"{rid} is PENDING ({r.get('cards','')}) - printed at proposed price {r['price']}")
        for fld in ("price", "price_max", "min_charge"):
            v = (r.get(fld) or "").strip()
            if v:
                allowed.setdefault(Decimal(v).quantize(Decimal("0.01")), []).append(f"{rid}.{fld}")
    text = pdf_text(pdf)
    toks = money_tokens(text)
    seen = {v for _, v in toks}
    extra_ok = {Decimal(str(x)).quantize(Decimal("0.01")) for x in getattr(mod, "EXTRA_OK", {})}
    for raw, v in toks:
        if v in allowed:
            continue
        if v in extra_ok:
            W(f"non-price figure '{raw}' allowed by EXTRA_OK: {getattr(mod, 'EXTRA_OK')[float(v)] if float(v) in getattr(mod,'EXTRA_OK') else ''}")
            continue
        F(f"money figure on sheet not backed by any used price row: '{raw}'")
    for rid in used:
        r = pb_all.by_id.get(rid)
        if not r or not r["price"].strip():
            continue
        if Decimal(r["price"]).quantize(Decimal("0.01")) not in seen:
            F(f"{rid} used but its price {r['price']} does not appear on the PDF")
    for cat in s.get("covers", []):
        for r in pb_all.live(cat):
            if r["id"] in used:
                continue
            if r["id"] in man.get("excluded", {}):
                W(f"{r['id']} ({cat}) intentionally left off: {man['excluded'][r['id']]}")
            else:
                F(f"{r['id']} ({cat}, {r['status']}, {r['price']}) is live but not on the sheet")
    for msg in src_problems(Path(mod.__file__)):
        F(msg)
    return fails, lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("only", nargs="*")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--csv", type=Path, default=None)
    a = ap.parse_args(argv)
    out_dir = a.out or sheetlib.OUT_DIR
    pb_all = sheetlib.Prices(a.csv or sheetlib.DEFAULT_CSV)
    total = 0
    for m in discover():
        if a.only and m.SHEET["num"] not in a.only:
            continue
        f, lines = audit_one(m, out_dir, pb_all)
        total += f
        print(f"{'PASS' if not f else 'FAIL'}  {m.SHEET['num']} {m.SHEET['name']}")
        for ln in lines:
            print(ln)
    print("RESULT", "PASS" if not total else f"FAIL ({total})")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
