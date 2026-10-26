---
name: "rainbow-print-imposition"
description: "Rainbow print shop imposition: bleed, crop marks, N-up, duplex, booklets, Avery labels, cut-apart scaled N-up, make customer art press-ready using the tested scripts in the Rainbow repo's tools/ folder."
---

# Rainbow print imposition

Andrew runs Rainbow Printing (Xerox Versant 180 + Fiery, Canon large-format). Most jobs are
customer PDFs/JPGs that need bleed, crop marks, and ganging onto a stock sheet. He knows the
domain: use print terminology, skip the basics, say plainly when a file is unusable.

## Use the tools folder first

Tested scripts live in `tools/` in the Rainbow repo. Run from the Rainbow repo root (`C:\Rainbow` on RAINBOW-AI, `~/Downloads/Rainbow` on the Mac, `$HOME/mnt/Rainbow` in a Cowork VM). Python is `py` on Windows, `tools/rbpy` on the Mac, `python3` in the VM; the examples below say `py`. (pypdf, pikepdf, reportlab, Pillow,
numpy and poppler are installed on every machine.) **Do not re-derive crop-mark geometry or write a
new imposition script when these cover the job.** Read `tools/README.md` for the full option list.

- `pdfinspect.py FILE` — always run first: page boxes in inches, rotation, trim guess, placed-image
  dpi, unembedded fonts, Quartz warning. `--clean` rewrites a fresh copy (Acrobat error 109 fix).
- `impose.py SOURCE [--trim WxH] [--nup N --sheet letter] [--back FILE | --duplex] [--repeat]`
  — bleed + marks + N-up; vector stays vector; bleed generated from the edges when the file has
  none (see Generated bleed below); writes a `/RainbowLayout` record; auto-names the output.
- `fitpage.py SOURCE --page WxH --margin IN [--uneven]` — the ONE tool that scales art. Use when
  the job asks for art shrunk onto cut-apart pieces with an even white margin (e.g. letter flyer
  4-up on letter cut into 4.25x5.5 quarters, i.e. handbills: `--page 4.25x5.5 --margin 0.125`, Andrew's
  rule, matching the Versant's 1/8 in edge). Trim scaled to fit, never cropped; the other axis
  filled from the file's own bleed; stops and reports the max even margin when bleed is too thin.
  Write to scratch, then `impose.py SCRATCH --nup 4 --sheet letter --gutter 0 --out "<job>_<piece>_4up_letter.pdf"`
  so the cuts land on the piece edges.
- `booklet.py SOURCE [--binding side|top] [--fit [--margin IN]] [--blanks end|after-cover|"2,23,24"] [--flip long|short]`
  — saddle-stitch booklets (print duplex, fold, staple on the fold; no trim/bleed/marks). `side` =
  portrait booklet stapled on the left; `top` = landscape/calendar booklet stapled along the top
  (letter -> 8.5x5.5 pages). 100% unless `--fit`. Stops when the page count isn't a multiple of 4.
  `--flip long` default (Fiery Top-Top on portrait): some panels are drawn 180 on purpose.
- `labels.py SOURCE --grid PRESET [--art-size WxH] [--bleed 0.1] [--fill auto|none|#hex]` — raster
  art centered on every label of an Avery die-cut preset (rect or round), aspect-fit, clipped to
  the die. `--bleed` floods the art's flat border color past the die for print-to-the-edge stock.
- `verify_print.py OUTPUT` — renders and measures: page box, all crop marks, no ink in gutters,
  bleed coverage, trim/bleed seams, nothing from inside the trim copied into generated bleed,
  duplex alignment. `--grid avery8395` / `--grid avery22877` etc. for die-cut
  stock (round presets measured against the circle), `--flood 0.1` for print-to-the-edge labels,
  `--alignment` for a test page. Booklets: add `--source ORIGINAL.pdf` — it folds the rendered
  sheets in software and checks every reading page is the right one, upright.
  **Never deliver a file that doesn't end in `RESULT  PASS`; paste the report.**
- `bash tests/run_tests.sh` after changing any script.

If a job needs something the scripts can't do (tent cards, odd folds), write
the one-off, then generalise it into `tools/` with `--help`, add it to `README.md`, and tell Andrew
to update this skill.

## Standing specs (apply unless the request overrides them)

- Bleed is **0.1 in** per side unless Andrew names a different amount. Business cards from raster art:
  same 0.1 in, generated from the edges.
- When to add bleed + crop marks (`--bleed 0.1 --marks`) by default, unless the request says otherwise:
  - Business cards: always.
  - Any N-up (2-up, 3-up, 4-up, …) on 8.5x11 or 11x17: yes.
  - Final output page 4x6 or 5x7: no. That goes to the full-bleed photo printer.
  - Handbills: no (see Handbills below).
  - Anything else: only when the job asks.
  `impose.py` itself defaults to neither, so pass the flags explicitly.
- **Handbills** ("handbills" in the request = quarter-sheet flyers): 4 identical copies on 8.5x11,
  cut once in half the short way and once the long way into four 4.25x5.5 pieces. Every piece gets an
  even **1/8 in** white margin all round, matching the Versant's 1/8 in unprintable edge on the
  full sheet, so the art is scaled to fit 4.0x5.25 in. No bleed, no marks. Say the scale %.
  If `fitpage.py` STOPS for lack of bleed (most plain 8.5x11 flyers), re-run with `--uneven`
  (Andrew's call, 2026-10-25): 1/8 in on the tight axis, a bit more on the other (letter is about
  0.125 L/R and 0.162 T/B). Never crop or invent bleed. Pass the margins it prints on to Andrew.
  `fitpage.py SOURCE --page 4.25x5.5 --margin 0.125 [--uneven]` to scratch, then
  `impose.py SCRATCH --nup 4 --sheet letter --gutter 0 --out "<job>_4.25x5.5_4up_letter.pdf"`.
- Crop marks: hairline (0.25 pt) black, **0.125 in** long, start exactly at the bleed edge, never
  drawn into the bleed or the art. Corner marks only unless asked for center marks.
- 1-up sheet with no output size given: **trim + 2×bleed + 2×marks**, no extra white space.
- Output sheet given (letter, 11×17, 12×18, 13×19): center the gang; 0.25 in gutters between bleed
  boxes; equal outer margins.
- Orientation: long side of the art matches the long side of the trim. Rotate, never crop.
- **Never rescale or crop customer art to fit.** If the art box isn't trim or trim+bleed,
  `impose.py` stops and reports the measured size — relay that and ask, don't force it.
  Exception: handbills, or the request itself implies scaling (e.g. a letter page 4-up on letter)
  → `fitpage.py`, and say the scale %.
- Duplex: page 1 fronts, page 2 backs, same grid, backs mirrored for the flip edge (long-edge
  default on portrait letter). Say which flip you assumed.
- Multipage sources: one-page source → repeated N-up; multipage → consecutive pages fill sheets
  (`--repeat` / `--sequence` to override). `--duplex` treats pages as F/B pairs.
- Booklets: `booklet.py`, always printer spreads for saddle stitch. Page count must be a multiple
  of 4 — ask before adding blanks, then pass `--blanks`. Scale only when Andrew asks (`--fit`).
  Say the binding (side/top) and the flip the file was built for. Table tents: top panel rotated
  180°, fold line noted.
- Die-cut label stock (Avery): no marks (`--no-marks`), page box exactly 612×792 pt. White-background
  art: no bleed, ≥0.05 in clearance inside each die-cut. Solid-background art on print-to-the-edge
  stock (e.g. 22877 2 in round): `labels.py --bleed 0.1`, key art still ≥0.05 in inside the die,
  verify with `--flood 0.1`. Print `--alignment` on plain paper before the stock.
- Never write scratch/preview files into the Rainbow folder; render previews into the session
  scratch folder or the system temp folder.

## Generated bleed

Leave `impose.py` on its default `--bleed-mode auto`. It mirrors each side, but any side where a
hard edge (box, QR code, rule, big type) sits within the bleed width of the trim is edge-extended
instead (outermost pixels repeated outward), so the element isn't copied into the bleed. The run
prints which sides were switched and why; pass that line on to Andrew. `verify_print.py` fails any
generated bleed that still shows such an edge. Only force `--bleed-mode reflect|edge|white` when
Andrew asks.

## Workflow

1. `pdfinspect.py` the source. Report trim in inches, existing bleed/marks, rotation, dpi.
   Don't stack a second set of marks on a file that already has them.
2. Confirm geometry in one line (trim, bleed, sheet, N-up, duplex/flip). Only stop for approval
   when the request is ambiguous or the layout is new; for business cards Andrew approves the
   1-up before the 8-up.
3. `impose.py` / `labels.py` / `booklet.py` / `fitpage.py`+`impose.py` → output lands next to the source, named
   `<job>_<trim>_<Nup>_<sheet>_cropmarks[_duplex].pdf` (labels: `<job>_<preset>_<N>up_letter.pdf`;
   booklets: `<job>_<page>_booklet<N>pp_<sheet>_duplex.pdf`). Never overwrite the customer's original.
4. `verify_print.py` on the output (`--source` for booklets). Paste the OK/WARN/FAIL lines in the
   reply. A WARN about an uninked bleed ring is fine only when the art has a white background — say which.
5. Reply: one line of geometry, the verify report, the output path. No essay.

## Known failure modes

- macOS Quartz PDFs → Acrobat error 109 on Windows: `pdfinspect.py --clean`.
- Publisher/Word/Canva exports: hidden second page, wrong page box, baked-in white border — inspect
  and strip before generating bleed.
- Web/HTML exports sized in pixels-as-points (e.g. a 3.5x2 card arriving as 14.583x8.333 in =
  1050x600 pt, i.e. 300 ppi pixels written as points): exact aspect, wrong size. Report it and ask
  before scaling (72/300 = 24%); scale a copy outside the shop folder, never the original.
- Unembedded fonts: flag them; the RIP may substitute. A Type 3 font flagged as unembedded is a
  false alarm — its glyphs live in the file.
- Logo PNGs often have the art off-center inside the canvas; centering the image ≠ centering the
  art. Measure the art bbox and say so.
- Prior outputs in the Rainbow folder predate these rules (different bleeds, padded sheets) —
  don't copy their geometry.
- Customer "prototype" booklets are often a plain 2-up duplex print (sequential pages per side) —
  use them for binding/orientation intent only, never for page order.