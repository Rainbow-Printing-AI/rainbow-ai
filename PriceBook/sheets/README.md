# Counter price sheets

These are the laminated counter sheets, rebuilt from scan 147 in the original style. They are generated from `data/prices.csv`, so a price change goes into the CSV first (`pricebook.py set ...`) and then the sheets are rebuilt.

```
python3 sheets/build_sheets.py          # rebuild all -> "Counter Sheets/" (.docx + .pdf)
python3 sheets/build_sheets.py 04 06    # just these sheets
python3 sheets/audit_sheets.py          # must print RESULT PASS before printing/laminating
python3 sheets/build_sheets.py --list
```

| # | Sheet | Replaces | Notes |
|---|---|---|---|
| 01 | Large Format Xerox Pricing | scan_147 p01 | |
| 03 | Computer Usage Services and Pricing | p03 | copies, scanning, LF, self-serve |
| 04 | Bindery Prices | p04 | includes laminating, labor |
| 06 | Pens & Markers | p06 (red-pen list) | **2 pages, print duplex.** A-Z with letter bars, brand sub-headers (3+ lines), tints: highlighter / pencil / dry-wet erase. Layout reflows from the CSV; new types go in `TYPE` |
| 07 | Business Cards | p07 / p14 | |
| 08 | Signs & Banners (4over) | p08 | prices pending C16 until Mark confirms |
| 09 | Photo Print Pricing | p09 / p14 | |
| 11 | Personal Label Printing | p11 | |
| 12 | NCR / Envelopes / Special Inks | p12 | landscape, retail prices (x2.5 built in); print on blue stock |

The audit fails if any of these hold:

- a dollar figure on a sheet doesn't match a live price row
- a live row in a sheet's categories is missing
- a sheet runs past its page count (`SHEET['pages']`, default 1; sheet 06 is 2)
- a price has been typed into a sheet module

Hand edits to a .docx are overwritten on the next rebuild. Change wording in the `sNN_*.py` module instead, or tell Claude.

The logo is `assets/rainbow_logo.png`, a crop from the scan. Replace it with the original art file when you have it, keeping the same filename.

Fonts are Times New Roman and Arial. Word on the Mac uses the real fonts, and LibreOffice uses the metric-identical Liberation fonts.
