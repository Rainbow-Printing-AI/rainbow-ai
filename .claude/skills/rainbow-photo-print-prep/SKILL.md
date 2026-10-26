---
name: rainbow-photo-print-prep
description: "Use when Andrew needs customer photos prepped for printing at a stated size (4x6, 5x7, 8x10, 11x14, 24x30, etc.): cropping to aspect, resolution and orientation checks, scan cleanup, contact sheets, and per-photo size lists."
---

# Rainbow photo print prep

A large share of Rainbow's jobs are folders of phone photos ("please print 4x6", "one each on
11x14 glossy"). Andrew prints them through Lightroom Classic → Canon PRO-4100S with ICC
profiles, or on the Versant for 4x6/5x7 volume. Claude's job is to make the files unambiguous.

## Use the tool first

`py tools/photo_prep.py FOLDER --size 4x6 [--size 5x7] [--border 0.125] [--dry-run]`
(Run from the Rainbow repo root (`C:\Rainbow` on RAINBOW-AI, `~/Downloads/Rainbow` on the Mac, `$HOME/mnt/Rainbow` in a Cowork VM). Python is `py` on Windows, `tools/rbpy` on the Mac, `python3` in the VM; the examples below say `py`.) It applies EXIF rotation, matches long side
to long side, crops to the exact aspect (centered; `--anchor top` etc.), never upscales, keeps the
embedded ICC, writes `<name>_<WxH>.jpg` into `print-ready/<WxH>/`, and makes
`_contact_sheet_<WxH>.jpg` with filename, pixel size, dpi and flags. HEIC needs `pillow-heif`
(installed on every machine; `pip install pillow-heif` if missing).

## Rules

- Orientation: never rotate a portrait photo to fill a landscape crop.
- Crops removing more than 15% on an axis are flagged — look at those (open the contact sheet
  with Read) and re-run with `--anchor` or ask Andrew before committing.
- Report effective dpi: < 200 flag as soft, < 150 say it will look bad and give the largest
  clean size instead. Never upscale silently.
- Scans: deskew, remove the scanner border, gentle levels only. No AI enhancement or invented
  detail on someone's family photo.
- 4x6 and 5x7 final output goes to the full-bleed photo printer: no bleed, no crop marks unless
  Andrew asks for them.
- White-border requests ("WB"): `--border`, then crop marks via `rainbow-print-imposition`.
- Output goes beside the source folder (`print-ready/`), never over the originals.

## Deliverables

1. The contact sheet(s) — Andrew checks the batch in one glance.
2. Sized files in `print-ready/<size>/`, ready for Lightroom or a Fiery hot folder.
3. In the reply: count per size and the flagged list (low-res, awkward crop, duplicates, wrong
   orientation). Nothing else.