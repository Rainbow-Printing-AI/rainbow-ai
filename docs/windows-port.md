# Rainbow tools — Windows port (RAINBOW-AI), 2026-10-17 (notes carried into the 2026-10-20 kit)

Kit built on the Mac: `Rainbow/Claude outputs/Windows kit 2026-10-17/`
- `Rainbow_Windows_Kit_2026-10-17.zip` — tools/, PriceBook/ (minus private/), Claude outputs/, Digests/ (192 files, 31 MB). Unzip to `C:\` → `C:\Rainbow`.
- `PriceBook_private_2026-10-17.zip` — PriceBook/private (logins, tax IDs). USB only; unzip into `C:\Rainbow\PriceBook\`.
- Not in the kit: customer job folders (optional copy), Hot Folders/ (rebuild in Fiery Hot Folders on Windows), AddressBook/ (not found in the Rainbow folder on 2026-10-17).
- **2026-10-20 kit** (`Rainbow_AI_Kit_2026-10-20.zip`) supersedes the tools and PriceBook in the 10-17 kit and adds `docs/`, `CLAUDE.md`, `BUILD-LOG.md`. Digests/ and Claude outputs/ were not repeated. The private zip from 10-17 is still the one to use.

## How the tools run on Windows
- **Cowork (Claude desktop, folder C:\Rainbow attached):** same Linux VM as on the Mac; folder mounts at `$HOME/mnt/Rainbow`. No code changes needed. Needs Virtual Machine Platform + VT-x; in a Hyper-V guest also nested virtualization (`Set-VMProcessor -VMName <vm> -ExposeVirtualizationExtensions $true` on the host, VM off). Cowork only ships in the .msix desktop package.
- **Native Windows (Claude Code / VS Code / future automation):** `C:\Rainbow\tools\windows\SETUP-WINDOWS.cmd` installs Python 3.12 (all users), Git, poppler (C:\Tools\poppler), LibreOffice, packages pinned to the Mac VM versions (`tools/windows/requirements.txt`), sets PYTHONUTF8=1 machine-wide, runs all tests. Log: `tools/windows/setup_log.txt`. Use `py`/`python`, not `python3`; tests via Git Bash.

## Portability changes made on the Mac (all tests still pass, counter-sheet PDFs text-identical)
- Bundled `tools/cmyk.icc` (FOGRA39L coated — the profile the crush guard already used) and `tools/fonts/LiberationSans-Regular.ttf` (+ copy in `PriceBook/sheets/assets/`) so output doesn't depend on OS fonts/profiles.
- Explicit UTF-8 on file I/O (crushcheck, mergelabels, photo_prep, sheetlib, audit_sheets); Windows font fallbacks; LibreOffice Windows path + `Path.as_uri()` profile URL in sheetlib.
- `tests/run_tests.sh` picks python3/python/py and strips CR; exits 0 = pass (45 PASS lines on a fresh copy, 46 on re-runs).
- `PriceBook/tests/test_pricebook.py` quote test computes from live prices (it broke when comb went to $4.88 flat on 2026-10-01).
- Pre-change copies of edited files were kept only in that session's scratch; the diffs are small (see tools/README.md "Windows" section).
- **After 10-17 (Mac only, harmless on Windows):** `impose.py`, `verify_print.py`, `passport.py` prepend `~/.rainbow/env/bin` to PATH so the Mac finds its own pdftoppm; `tools/rbpy` + `tools/setup-mac.sh` give the Mac a native Python 3.12 + poppler without the Cowork VM. Windows ignores all of this.

## Fiery hot folders to recreate (server V180 199.190.123.134, queue VP180 print)
- BWSS: Grayscale, 8.5x11 LEF, Tray 6 (oversized), Scale to fit On, PDF Print Engine preferred.
- BW SS Slip Sheet: same + slip sheet On between copies, before every 1, blank from Post-Fuser Tray (Letter), Copies 1.

## Rule after cut-over
One master: once the Windows check passes, price changes happen on Windows only; the Mac PriceBook is a 2026-10-17 snapshot.
