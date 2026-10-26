---
name: "rainbow-pricebook"
description: "Look up, quote, or change Rainbow shop prices and phone-list entries, or process a scanned-back price conflict sheet, using the PriceBook kit in the Rainbow repo."
---

# Rainbow price book

Source of truth: `PriceBook/data/prices.csv` (+ `contacts.csv`, `conflicts.json`, `changelog.csv`).
Run everything from `PriceBook/` in the Rainbow repo. The Windows box (RAINBOW-AI) is the master: price changes happen there only. Python is `py` on Windows, `python3` elsewhere; the examples below say `python3`. Never re-derive prices from the old scans.

## Price questions ("how much is 24x36 color?", "what do we charge for 150 letter duplex?")
1. `python3 pricebook.py find <words>` - sizes in any orientation/format, letter/legal/tabloid, a 1-4 digit number = quantity (picks the tier). Add `--all` for superseded/retired rows.
2. For a job total: `python3 pricebook.py quote <id|family> <qty> [+ <id> <qty> ...]` (`--w/--h` inches for sq-ft items, `--length` for linear-ft, `--tax %`).
3. Answer with the price and unit. If the row is PENDING Cxx or NO PRICE, say so and name the card.
4. Repo not reachable: read the project doc mirror (`claude/pricebook-mirror.md` if present) and say it's the mirror.

## Price changes ("24x36 color is now $14.95")
1. `find` the row id; if ambiguous, show the candidates and ask which.
2. `python3 pricebook.py set <id> <price> --source "Andrew, chat YYYY-MM-DD"` (new item: `add --category ... --item ... --unit ... --price ...`; discontinued: `retire <id>`).
3. `python3 pricebook.py validate` must print RESULT PASS, then `python3 pricebook.py build`.
4. Rebuild the laminated counter sheets: `python3 sheets/build_sheets.py`, then `python3 sheets/audit_sheets.py` (must print RESULT PASS). Output: `PriceBook/Counter Sheets/Rainbow_Sheet_NN_<Name>.docx/.pdf`. Tell Andrew which sheet numbers carry the changed rows (check `used_ids` in each `*.manifest.json`) so he knows what to reprint and re-laminate.
5. Reply: old -> new, id, and that the book/xlsx/HTML and counter sheets were rebuilt. If the web page or project mirror exists, republish/re-upload it.
6. Repo not reachable: append the change to project doc `claude/pricebook-pending.md` and apply it next Cowork session.

## Counter sheets (sheets/)
- One module per sheet, `sheets/sNN_<Name>.py`: 01 Large Format, 03 Computer Services, 04 Bindery, 06 Pens & Markers, 07 Business Cards, 08 Signs & Banners, 09 Photo Prints, 11 Labels, 12 NCR/Envelopes/Special Inks. Shared helpers are in `sheets/sheetlib.py`; see `sheets/README.md`.
- Every price on a sheet comes from `pb.money(<row id>)`. Never type a price into a module; the audit fails on it.
- Wording or layout changes go in the module, never the .docx (a rebuild overwrites it). After any module edit run build + audit; keep 1 page and >= 0.35 in free above the bottom margin, because Word and other LibreOffice versions reflow.
- A new live row in a sheet's `covers` categories must be placed on that sheet (the audit fails until it is) or excluded with `pb.exclude(id, reason)`.
- Sheet 12 is printed on blue paper: no colour fills. The logo is `sheets/assets/rainbow_logo.png` (a crop from the scan); replace it with Andrew's original art under the same name when he provides it.

## Conflict sheet scan-back
1. Stage only the scanned PDF, read every page (cards C01...; page header says PBCS-vN-pN).
2. Per card: OK tick = accept proposal; a written $ = that price; Remove = retire; blank = still open. The page-bottom box OKs every unmarked proposal on that page.
3. Show Andrew a decision table before applying. Then `pricebook.py resolve Cxx a=ok b=3.75 ...` or `resolve Cxx opt=N`; non-proposed options need manual `set/add/retire` then `close Cxx`.
4. `validate`, `build`, then rebuild + audit the counter sheets; if cards remain open, bump `version` in data/conflicts.json and run `conflicts-pdf` for the next sheet.

## Phone list
`python3 pricebook.py contacts <words>`. Logins, passwords and tax IDs are only in `private/logins.csv`: never print, mirror, publish or paste them.

## Rules
Handwriting beats print; last value in a strike chain wins; newer sheet beats older; red-pen pen list is current; struck-with-no-replacement or unreadable = no price until Andrew decides. Everything is logged in `data/changelog.csv`; nothing is deleted.