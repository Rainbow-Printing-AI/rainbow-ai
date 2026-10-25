# Rainbow — standing orders for Claude in this folder

This folder is the Rainbow print shop's working folder on this machine (`C:\Rainbow` on RAINBOW-AI, `~/Downloads/Rainbow` on the Mac) and, from Phase 0.3 on, the Rainbow AI git repo. Same layout on both machines.

**Read first, every session:** `BUILD-LOG.md` (what's been done, what's next). For any "Rainbow AI step N" request also read `docs/rainbow-ai-plan.md` and the matching section of `docs/rainbow-ai-architecture.md`. For any layout job read `tools/README.md`. Words you need are in `docs/rainbow-ai-glossary.md`.

## Context
Rainbow Printing & Office Supply, Incline Village NV. Andrew runs production; owners Mark and Dave also answer shop email (rainbowincline@gmail.com / print@rainbowofficesupply.com). Mark does all 4over outside-vendor ordering. Equipment: Xerox Versant 180 + Fiery (server V180 199.190.123.134, queue "VP180 print"), Canon PRO-4100S (photos, via Lightroom Classic + ICC profiles), Canon large-format, PlotWave 300. Andrew knows the domain — use print terminology, skip basics, say plainly when a file is unusable. Tell it like it is.

## Folder map
- `tools/` — tested scripts (`pdfinspect.py`, `impose.py`, `verify_print.py`, `labels.py`, `photo_prep.py`, `booklet.py`, `sheetfit.py`, `crushcheck.py`, `fetch_links.py`, …). Read `tools/README.md` before any layout work. Never re-derive geometry these scripts already handle.
- `docs/` — Rainbow AI plan, architecture, glossary, Windows port notes, printable checklist.
- `PriceBook/` — price data, sheets, generators. `PriceBook/private/` holds logins/tax IDs: never copy it anywhere, never commit it.
- `Hot Folders/` — live Fiery hot folders. **Never move, rename, or write into** (only the app's `dispatch.py` may write there, from Phase 4).
- `app/` — the Rainbow AI program (from Phase 1). `app/data/` and `secrets/` are never committed.
- `Jobs/` — one folder per job made by the app (from Phase 1).
- `AddressBook/`, `Digests/`, `Claude outputs/` — address-book kit, digest PDFs, misc deliverables.
- Everything else at the root is a customer job folder or loose email attachment. Treat as customer files: never modify originals; write outputs beside them or in a `PRINT READY/` subfolder.

## Standing print rules (the scripts encode these; don't override without being told)
- Bleed 0.1 in per side. Crop marks 0.125 in, hairline, start exactly at the bleed edge, never into the bleed. 1-up sheet = trim + 2×bleed + 2×marks, no extra white, unless an output sheet size is given.
- Bleed and crop marks only when a job asks for them (`--bleed 0.1`, `--marks`); plain impositions get neither.
- Art is never scaled or cropped to fit a trim — stop and report the measured size.
- Long side of the art goes with the long side of the trim.
- Duplex: page 1 fronts, page 2 backs, backs mirrored for the flip edge (long-edge default).
- Output names: `<job>_<trim>_<Nup>_<sheet>[_cropmarks][_duplex].pdf`.
- Crush guard lifts colors that print black on the Versant; **always report every lift** (`>>> TELL ANDREW` lines).
- **Always run `verify_print.py` before delivering. Exit 0 / `RESULT PASS` or it doesn't ship.**

## Which skill (when the rainbow-* skills are present in `.claude/skills/` or the account)
- Bleed, crop marks, N-up, duplex, Avery labels, "make this press-ready" → `rainbow-print-imposition`
- Folders of photos at a stated size → `rainbow-photo-print-prep`
- "Catch me up on [customer]" / one customer's job → `rainbow-print-order-packet`
- "What's open in the shop email" / inbox over a window → `rainbow-email-digest` (red star = owners' done mark; never work around that convention)
- Price lookups, quotes, price changes → `rainbow-pricebook`

## Running the scripts
- **Windows (native):** `py tools/<script>.py …` from `C:\Rainbow`; tests `bash tools/tests/run_tests.sh` in Git Bash. `PYTHONUTF8=1` is set machine-wide by `tools/windows/SETUP-WINDOWS.cmd`.
- **Mac (native):** `tools/rbpy tools/<script>.py …` (Python 3.12 + poppler in `~/.rainbow`, installed by `tools/setup-mac.sh`).
- **Cowork VM (either machine):** `python3 tools/<script>.py …` with the folder at `$HOME/mnt/Rainbow`.
- Check `which`/imports before assuming a package is missing. Keep scratch files out of this folder.

## Usage discipline
- No parallel subagents for bulk work. For mechanical, high-volume tasks build the deterministic part as a script and hand Andrew a ready-to-paste prompt to run on Sonnet in a new session.
- One job or one build step per task; don't chain unrelated work in one thread.
- When a one-off script solves a new layout type, generalise it into `tools/` with `--help`, run `tests/run_tests.sh`, add a README line, and update the matching skill.

## Rainbow AI build sessions
- Andrew has never coded. Explain what each thing is and why before doing it; he types only the copy-paste lines you hand him; every step ends with a visible test ("Done when").
- Append to `BUILD-LOG.md` after every step: date, step, what was done, what Andrew learned, what's next.
- Runtime Claude is `claude -p` on Andrew's subscription token (`CLAUDE_CODE_OAUTH_TOKEN`), model Sonnet, never `--bare`. Nothing prints, sends email or changes a price without a click in the UI.

## Delivery
Finished files go beside the customer's source files (or `PRINT READY/`), named per the convention above. Say the folder and filename. Don't paste long explanations of what's in a PDF — Andrew will open it. Verified PASS output from `verify_print.py` is the sign-off.

## Shop-floor facts
- Rainbow does not offer notary, UPS drop-off, or FedEx drop-off. Referrals: Pak Mail (930 Tahoe Blvd), Postal Express (774 Mays Blvd).
- Fiery hosts a network folder "Scans".
- Owners' red star on an email = job done. Never work around that convention.
