# Rainbow Price Book

The shop's prices, phone list and open pricing questions, as plain files that Claude
(or anyone) can search, update and re-print.

## Where things are

| Path | What it is |
|---|---|
| `data/prices.csv` | **The master price list.** One row per price point. Opens in Excel. |
| `data/contacts.csv` | Phone list (vendors, staff, accounts). No passwords. |
| `data/conflicts.json` | Open questions from the scans (the conflict-sheet cards). |
| `data/changelog.csv` | Every change ever made: when, who, old -> new, where it came from. |
| `data/settings.json` | Sales tax rate (for quotes), sheet version. |
| `private/` | Logins, passwords, tax IDs. **Never** printed, mirrored or published. Move to a password manager. |
| `build/` | Generated files - don't edit; rebuild instead. |
| `sheets/` + `Counter Sheets/` | The laminated counter price sheets (scan 147 style), generated from prices.csv as .docx + .pdf. `python3 sheets/build_sheets.py` then `python3 sheets/audit_sheets.py` (must PASS). See `sheets/README.md`. |
| `source/` | The original scans, evidence crops, transcriptions and the one-time import scripts. |

## Everyday use (ask Claude, or run it yourself)

```
python3 pricebook.py find 24x36 color          # sizes in any order/format; letter/legal/tabloid work
python3 pricebook.py find b/w letter 150 duplex  # quantity picks the right tier
python3 pricebook.py find laminate --all        # --all also shows superseded/retired rows
python3 pricebook.py get lf-bw-30x42-walkin     # one row + its history
python3 pricebook.py set lf-color-24x36 14.95 --source "Andrew, chat 2026-10-02"
python3 pricebook.py add --category "Laminating" --item "Laminating" --size 12x18 --unit each --price 3.50
python3 pricebook.py retire pen-ergotwist-bk99a-a --note "discontinued"
python3 pricebook.py quote bw-8.5x11-side 300 + comb-half-inch 10   # retired rows are refused
python3 pricebook.py quote lf-color-bond-sqft 2 --w 24 --h 60    # sq-ft items take --w/--h in inches
python3 pricebook.py contacts essendant
python3 pricebook.py history
python3 pricebook.py validate                    # run after any hand edit of the CSVs
python3 pricebook.py build                       # regenerate book PDF, xlsx, HTML, mirror
```

Status column: `active` | `pending` (proposed from the scans, waiting on the conflict sheet) |
`unpriced` (no usable price) | `superseded` (lost to a newer source, kept for history) | `retired`.

## Conflict sheet loop

1. `python3 pricebook.py conflicts-pdf` -> `build/Rainbow_Price_Conflicts_vN.pdf` (open cards only).
2. Print, mark up (OK / write a price / tick an option), scan all pages into the Rainbow folder.
3. Claude reads each card and records the answers: `pricebook.py resolve C02 a=ok`,
   `resolve C06 a=0.08 b=0.07`, `resolve C07 opt=1` ... then `build`.
4. Anything still unclear rolls into the next version of the sheet.

## Rules the import used (and that `set` keeps)

- Handwriting beats print on the same sheet; the last value in a strike-through chain wins.
- Newer sheet beats older (logo-header sheets over the older typed sheets). The red-pen pen list is current (Andrew, 2026-09-30).
- Struck with nothing written in, or unreadable: no price until Andrew decides.
- Nothing is deleted. Old values stay as `superseded`/`retired` rows and in the change log.

## Editing by hand

Fine to edit `data/prices.csv` in Excel - keep it as CSV (UTF-8), don't rename columns, then run
`python3 pricebook.py validate`. Prefer `set`/`add`/`retire` so the change log stays complete.

## Tests

`python3 tests/test_pricebook.py` (runs on a temp copy; never touches the real data).
Needs Python 3.10+, reportlab, openpyxl, Pillow; the counter sheets also need python-docx, LibreOffice
(PDF render) and poppler's pdftotext (audit). On Windows, `tools/windows/SETUP-WINDOWS.cmd` installs all of it.
