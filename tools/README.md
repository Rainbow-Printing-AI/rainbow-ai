# Rainbow/tools — press-prep scripts

Tested, reusable scripts for the layout work that comes through the shop every day.
The Cowork skills (`rainbow-print-imposition`, `rainbow-print-order-packet`,
`rainbow-photo-print-prep`) tell Claude to use these instead of re-deriving the
geometry each session. They run as-is in the Cowork VM on the Mac or the Windows shop PC (python3 +
pypdf/pikepdf/reportlab/Pillow/numpy + poppler are all present there), and natively on Windows after
`windows/SETUP-WINDOWS.cmd` (see the Windows section at the end).

| Script | What it does |
|---|---|
| `impose.py` | 1-up or N-up on a sheet, duplex — **no bleed, no crop marks by default**; `--bleed 0.1` / `--marks` (0.125 in from the bleed edge) only when a job asks. A source that carries bleed is clipped to trim. Vector art stays vector; bleed is mirrored from the edges when the file has none. Bleed mode `auto` (default) mirrors each side but edge-extends (repeats the outermost pixels outward) any side where a hard edge — box, QR code, rule, big type — sits within the bleed width of the trim, so it isn't copied into the bleed; the run says which sides and why. `--bleed-mode reflect|edge|white` forces one method. Writes a `/RainbowLayout` record into the PDF. |
| `bleedscan.py` | Library (no CLI) used by `impose.py` and `verify_print.py`: finds hard edges running parallel to a trim edge within the bleed width. |
| `verify_print.py` | Renders the finished PDF and measures it: page box, every crop mark, no ink in gutters, bleed coverage, no light hairline where mirrored bleed meets the art (600 dpi, no antialias), nothing from inside the trim (box/QR/rule) copied into generated bleed, duplex alignment. Also checks die-cut label sheets (`--grid avery8395` etc.) and prints alignment test pages. Exit 0 = PASS. |
| `pdfinspect.py` | What the customer sent: page boxes in inches, rotation, trim guess, placed-image dpi, unembedded fonts, Quartz warning. `--clean` rewrites a fresh linearized copy (the Acrobat error 109 fix). |
| `labels.py` | Raster art → every label of an Avery die-cut preset (`--grid avery22877`, `avery8395`, …), centered, aspect-fit, clipped to the die (round presets clip to the circle). `--bleed 0.1` floods the art's flat border color past the die for print-to-the-edge stock; verify with `verify_print.py OUT --grid PRESET --flood 0.1`. |
| `textlabels.py` | Vector text on every label of an Avery preset (`--grid avery5167` = 8167 etc.). Black Helvetica-Bold auto-fit with 0.08 in clearance; repeat `--text` to split the sheet into equal row blocks (`--split cols` for columns). Verify with `verify_print.py OUT --grid PRESET`. |
| `mergelabels.py` | **Mail merge.** .xlsx/.csv address list → one address per label (`--grid avery5160` default). Columns found by header name; lines Name / Company / Address1 [+Address2] / City, ST ZIP; embedded Liberation Sans, left-aligned, 10 pt stepping to 9 then balanced wrap, min 7. Reports every cleanup (emails/duplicate Address2 dropped, state names → USPS, ZIP padding) and skips incomplete records; `--fix "ROW:field=value"` overrides a cell without touching the source; `--sort zip`. Writes `<stem>_<preset>_30up_letter.pdf` + `_merge.csv` (what printed, sheet/position). Verify with `verify_print.py OUT --grid PRESET`. |
| `crushcheck.py` | **Crush guard.** Finds colors that print as black on the Versant: chromatic (C* ≥ `c_min`) but darker than the press can show a hue (L* < `l_crush`), in vector fills/strokes/text and in flat image areas. `--fix OUT` lifts *only* those to `l_fix`, same hue; neutrals, blacks and every printable color stay byte-identical. `impose.py` and `labels.py` run it automatically (`--no-crush-fix` to disable), `pdfinspect.py` reports it, `verify_print.py` FAILS a file that still carries one. Thresholds in `press.json`; `--swatches OUT.pdf` prints the calibration sheet. |
| `sheetfit.py` | Every page at 100% on one fixed sheet (e.g. mixed 11x17 drawings + letter scans → all 17x11): no bleed, no marks, never scaled; smaller pages centered, `--rotate "3-5:270; 9:180"` turns sideways/upside-down pages (judge by eye — OSD is unreliable on drawings); `--match-sheet` turns portrait pages to run landscape (long side to long side); stops on any page bigger than the sheet. Keeps bookmarks, runs the crush guard, writes a `/RainbowLayout` record for `verify_print.py`. |
| `fitpage.py` | **The one tool that scales art.** Fits each page's trim into `--page WxH` minus an even `--margin` on every side, never cropped; long side to long side; vector stays vector; crush guard runs. The art almost never matches the window's aspect, so the other axis is filled from the file's own bleed. If there isn't enough bleed it STOPS and reports the largest even margin the file allows; `--uneven` centers the trim instead and reports the unequal margins. **Handbills** (4 quarter-sheet flyers on letter, 1/8 in white all round each piece): `fitpage.py SRC --page 4.25x5.5 --margin 0.125 --out SCRATCH`, then `impose.py SCRATCH --nup 4 --sheet letter --gutter 0` so the cuts land on the piece edges. |
| `booklet.py` | **Saddle-stitch booklets** — print duplex, fold the stack, staple on the fold; no trim, bleed or marks. Printer spreads 2 per side, sheet 1 = cover sheet. `--binding side` (portrait booklet, staples on the left; default) or `--binding top` (landscape/calendar booklet, staples along the top — letter → 8.5x5.5 pages). 100% by default and stops if a page won't fit; `--fit [--margin IN]` scales each page to the largest size that fits its half-sheet panel. Stops when the page count isn't a multiple of 4 until told where the blanks go (`--blanks end` / `after-cover` / `"2,23,24"`). `--order "1,2,5,3-4,b"` sets the reading order (pages left out are dropped, `b` = blank) — use it to reproduce a customer's spreads. `--flip long` default (Fiery Top-Top on a portrait sheet): panels that must land head-to-foot are drawn 180, so those sides look upside down on screen. Verify with `verify_print.py OUT --source ORIGINAL.pdf` — it folds the rendered sheets in software and checks every reading page is the right one, upright. |
| `build_banner.py` | **Banner / sign art from scratch** (no customer file): solid background flood (`--bg` sRGB hex), a logo PNG traced to vector with potrace (small web logos hold up at banner size; centered on the measured ink box), and centered lines of text shaped with HarfBuzz and written as outlines (no fonts for the RIP). Each line auto-sized to `--max-width`/`--max-cap`; stops if anything lands inside `--safe` (2 in). Default font `fonts/CormorantGaramond-Bold.ttf` (OFL). Needs `pip install --user potracer uharfbuzz`. Write the art to scratch, then `impose.py` it 1-up into the shop folder and `verify_print.py`. First job: Ritz-Carlton 7x3 ft vinyl, 2026-10-16. |
| `photopage.py` | Photos onto fixed pages, one per page, white around them — e.g. landscape photo on a portrait 5x7 with 1/8 in L/R margins (`--page 5x7 --margin-x 0.125`). Fit inside the margins, centered, never cropped; keeps its own orientation (`--match` for long side to long side). JPEGs embedded untouched with their ICC (Adobe RGB kept). Then `impose.py` for N-up/marks. |
| `passport.py` | Passport / ID photo. `--grid` writes a pixel-grid preview to read crown/chin/eyes/centre off; then `--crown --chin --cx --eyes` builds the square crop (head 62%, 10% headroom; US spec head 50-69%, eyes 56-69% up), lays it out at exactly 2x2 on 4x6 via photopage -> impose (`--nup 2` = two copies), runs `verify_print.py`, then measures the placed image matrix and the 600 dpi ink box itself. Fails on off-centre/no-headroom/< 200 dpi. `PASSPORT PASS` / exit 0 or it doesn't ship. Writes `_preview.jpg` with the spec bands drawn. |
| `photo_prep.py` | Folder of photos → cropped to 4x6/5x7/8x10/…, long side to long side, dpi flagged, contact sheet. |
| `fetch_links.py` | Customer share links → original files. Paste the email text (`--from-file`, or `pbpaste | ... -`) or URLs; OneDrive personal links (1drv.ms / onedrive.live.com, files) download full-res with original names via the anonymous Badger token — tested 2026-10-08. Dropbox / Google Drive / SharePoint paths are best-effort, untested. Never overwrites; checks size against the API. Private Google Drive links (shared only with the shop) FAIL here with "got a web page" — those, and Gmail attachments (the connector has no bytes), come through Chrome. |
| `repo_sync.py` | **Repo sync (step 0.8).** `git pull --ff-only` of the Rainbow repo at Claude session start (SessionStart hook in `.claude/settings.json`, `--hook` = JSON for the hook). Never fixes anything itself: uncommitted/new files, a diverged branch, not on `main`, or GitHub unreachable → loud `REPO SYNC WARNING` and no pull. `--no-pull` checks only. Exit 1 = warning (always 0 with `--hook`). |
| `package_skills.py` | **Account skills vs repo (step 0.8).** No flags: one upload zip per `.claude/skills/rainbow-*` skill into `Claude outputs/skill-uploads-DATE/` (the zip fallback for Cowork/claude.ai). `--check`: compares the account's synced copies (`~/.claude/skills/synced/<bucket>/`) with the repo, CRLF ignored, and names STALE / MISSING / ACCOUNT-ONLY skills (exit 2 if any). `--import`: copies ACCOUNT-ONLY skills into the repo, never overwrites one. See `docs/repo-sync.md`. |
| `collect_downloads.py` | After Chrome downloads files (Chrome on the shop Mac saves to the Rainbow folder root): waits for `*.crdownload` to finish, moves the named files (or `--any --since T`) into the job folder without overwriting, and rejects HTML sign-in/error pages posing as files. Flags small PNGs as possible logos. Exit 1 lists anything missing or bad. Used by the `rainbow-email-download` skill ("download everything from this email"). |

## Standing rules these scripts encode

- **No bleed and no crop marks on any imposition job** (Andrew, 2026-09-30). Only if a job
  explicitly asks: `--bleed 0.1`, `--marks` (0.125 in, hairline, start exactly at the bleed edge,
  never drawn into the bleed). 1-up sheet = trim, no extra white (plus bleed/marks only if asked).
- Art is **never scaled or cropped** to fit a trim. If it doesn't match, the script stops and
  tells you the measured size — fix the source or pass the right `--trim`.
- Long side of the art goes with the long side of the trim.
- Duplex: page 1 fronts, page 2 backs, same grid, backs mirrored for the flip edge
  (`--flip long` default = portrait letter flipped on the long edge).
- Output names: `<job>_<trim>_<Nup>_<sheet>[_cropmarks][_duplex].pdf` (`_cropmarks` only when marks were asked for);
  booklets `<job>_<page>_booklet<N>pp_<sheet>_duplex.pdf`.
- Booklets: page count must be a multiple of 4 — `booklet.py` stops and says how many blanks; ask where
  they go. Print with exactly the flip the script names.
- **Every crush-guard lift gets reported to Andrew, every time** — the tools print a `>>> TELL ANDREW`
  line and `verify_print.py` carries it as a WARN; paste the lifted colors in the reply.
- **Crush guard.** A screen shows sRGB #17320B (L* 18) as forest green; the Versant's darkest solid is
  ~L* 12, so it prints black. `press.json` holds the line (`l_crush` 22, lift to `l_fix` 28, only
  when chroma ≥ `c_min` 10). Never rasterise a vector job to fit a trim — that turns text into RGB
  rich black and hides fills from the guard. Calibrate once: `crushcheck.py --swatches`, print,
  set `l_crush` to the lowest row where every hue still reads.
  (2026-10-07: image lifts now push every flagged pixel past `l_crush`; colors just over `c_min`
  used to half-lift and then fail `verify_print.py`.)
- **Bleed seam (2026-10-13).** `impose.py` renders the page to mirror its edges; pdftoppm rounded a Canva
  5.5x8.5 page (box not at the origin) to 1651 px with a blank last column, which mirrored into a white
  hairline exactly on the trim. The raster is now forced to box x dpi, and `verify_print.py` FAILS any
  trim edge lighter than the art on both sides of it (`tests/t_canva_offset.pdf` covers it).

## Typical runs

```bash
cd ~/Downloads/Rainbow/tools

# what did they send?
python3 pdfinspect.py "../pleaseprint/card.pdf"

# 1-up, sheet = trim, no bleed, no marks (the standing default)
python3 impose.py "../pleaseprint/card.pdf"

# only when a job explicitly asks for bleed + crop marks
python3 impose.py "../pleaseprint/card.pdf" --bleed 0.1 --marks

# 4x6 postcard 2-up on letter
python3 impose.py "../Crystal Bay/postcard.pdf" --trim 4x6 --nup 2 --sheet letter

# business cards, image front + back, 8-up duplex
python3 impose.py front.png --back back.png --trim 3.5x2 --nup 8 --sheet letter

# 16-page 5x7 table numbers → 2-up letter, consecutive pages (8 sheets)
python3 impose.py "Table_Numbers.pdf" --trim 5x7 --nup 2 --sheet letter

# source already has bleed (page = 5.2x7.2 or has a TrimBox) → clipped to trim
python3 impose.py art.pdf --trim 5x7 --nup 2 --sheet letter

# always, before it goes to the Fiery
python3 verify_print.py "card_3.5x2_8up_letter_duplex.pdf"

# Avery stock
python3 verify_print.py --grid avery8395 --alignment      # test page on plain paper first
python3 verify_print.py badges.pdf --grid avery8395        # then the real file
python3 labels.py logo.png --grid avery22877 --bleed 0.1   # 2in round print-to-the-edge, 12-up
python3 verify_print.py logo_avery22877_12up_letter.pdf --grid avery22877 --flood 0.1

# will anything print black? (impose/labels do this automatically)
python3 crushcheck.py "../pleaseprint/card.pdf"              # exit 2 + list if yes
python3 crushcheck.py "../pleaseprint/card.pdf" --fix card_lifted.pdf
python3 crushcheck.py --swatches versant_crush_swatches.pdf  # calibration sheet for press.json

# plan set / mixed-size packet, everything 100% on 17x11, fix sideways + upside-down scans
python3 sheetfit.py "../Main level elevations/Main Level Elevations_combined.pdf" --sheet tabloid --landscape \
    --rotate "3-5,11-18:270; 63-66:90; 96:180" --match-sheet --out "../Main level elevations/Main Level Elevations_actual_1up_17x11.pdf"

# booklets: 21-slide 10x7.5 deck → landscape booklet on letter, top-stapled, slides fit to the 8.5x5.5 half
python3 booklet.py ../Jefferies_Oct2026.pdf --binding top --fit --blanks end
python3 verify_print.py ../Jefferies_Oct2026_8.5x5.5_booklet24pp_letter_duplex.pdf --source ../Jefferies_Oct2026.pdf
# same deck, keeping the spreads from the customer's prototype (2 faces 5, 6 faces 9 …), leftovers paired in deck order
python3 booklet.py ../Jefferies_Oct2026.pdf --binding top --fit --blanks end \
    --order "1,2,5,3,4,6,9,7,8,10,13,11,12,14,17,15,16,19,20,18,21"
# 5.5x8.5 portrait pages → standard booklet on letter, 100%, stapled on the left
python3 booklet.py ../program.pdf

# banner from scratch: 7x3 ft, light blue, logo over one line of text (art to scratch, then impose + verify)
python3 build_banner.py --size 84x36 --bg D5E9FB --logo ../RNORZ_Primary_RGB.png --logo-height 15 --gap 4 \
    --text "WELCOME TO WORK" --out ~/scratch/RitzCarlton_WelcomeToWork.pdf
python3 impose.py ~/scratch/RitzCarlton_WelcomeToWork.pdf --out ../RitzCarlton_WelcomeToWork_84x36_1up.pdf
python3 verify_print.py ../RitzCarlton_WelcomeToWork_84x36_1up.pdf

# photos
python3 photopage.py "../2 faces.jpg" "../golf.jpg" --page 5x7 --out ../photos_5x7.pdf   # landscape on portrait 5x7, 1/8 in sides
python3 impose.py ../photos_5x7.pdf --nup 2 --sheet letter --marks
python3 photo_prep.py "../Ginger B 9-1" --size 4x6 --size 5x7

# passport photo: read the grid, then build + verify (2x2 on 4x6)
python3 passport.py "../Headshot 2x2/headshot_original.jpg" --grid
python3 passport.py "../Headshot 2x2/headshot_original.jpg" --crown 355 --chin 1320 --cx 1020 --eyes 835
```

`impose.py --help` lists every option (gutter, `--bleed`/`--marks` when a job asks,
mark width, white vs mirrored bleed, `--cols/--rows` for uneven grids, `--repeat` vs
`--sequence` for multipage sources, `--flip short`).

## Adding to this folder

Keep one script per job type. When Claude writes a one-off script for a new layout
(a tent card, a booklet, a label template), ask it to generalise the script into this
folder with a `--help`, run it on the job, and add a line to the table above. Then tell it
to update the matching skill so the next session reaches for it.

Test fixtures used during development live in `tests/` — run `tests/run_tests.sh` after
editing anything; every output must end in `RESULT  PASS`.

## Windows (RAINBOW-AI, 2026-10-17)

- The folder lives at `C:\Rainbow` on the shop PC; the name must stay `Rainbow` (Cowork mounts it at
  `$HOME/mnt/Rainbow` on either machine). Migration steps: `windows/README-WINDOWS.md`.
  `windows/SETUP-WINDOWS.cmd` installs Python 3.12, Git, poppler, LibreOffice and the pinned
  `windows/requirements.txt` (same versions as the Mac VM), sets `PYTHONUTF8=1`, and runs every test suite.
  `windows/CLAUDE-CHECK-PROMPT.txt` is the paste-in check for the first Claude session on Windows.
- `cmyk.icc` (FOGRA39L coated - the profile the crush guard was already using in the VM) and
  `fonts/LiberationSans-Regular.ttf` (mergelabels; the price book's sheet 06 has its own copy) are
  bundled so output never depends on the OS's fonts or profiles. Don't delete them.
- Native Windows (Claude Code / VS Code): `python` or `py` instead of `python3`; run the tests in Git Bash
  (`bash tests/run_tests.sh` finds the interpreter itself); `pbpaste | python3 fetch_links.py -` becomes
  `Get-Clipboard | py fetch_links.py -` in PowerShell.
