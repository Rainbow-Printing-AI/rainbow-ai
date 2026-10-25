# Rainbow tools on Windows (RAINBOW-AI)

Built 2026-10-17 from the Mac. Same scripts, same pinned package versions, same bundled
font (`tools/fonts/LiberationSans-Regular.ttf`) and CMYK profile (`tools/cmyk.icc`), so files
come out the same on either machine. Don't delete those two files.

## What's in your Claude account already (nothing to copy)
Skills (rainbow-*), the Rainbow project and its docs (price book mirror, crush guard, pricing
review), memory, the Gmail / Drive / Calendar connectors, and the price-book web page.

## What the kit carries
`tools/` (all scripts + tests), `PriceBook/` (prices, phone list, change log, counter sheets),
`Claude outputs/`, `Digests/`. Logins/tax IDs (`PriceBook/private/`) travel separately in
`PriceBook_private.zip` - USB stick only, never Drive or email.
Not included: customer job folders (copy them yourself if you want them here) and `Hot Folders/`
(those are Fiery's, rebuild them - step 6).

## Steps
1. **Unzip** `Rainbow_Windows_Kit_2026-10-17.zip` to `C:\` -> you get `C:\Rainbow`. Keep the
   folder name `Rainbow`; the skills find it by that name.
2. **Private logins:** unzip `PriceBook_private.zip` into `C:\Rainbow\PriceBook\`.
3. **Double-click** `C:\Rainbow\tools\windows\SETUP-WINDOWS.cmd`, answer Yes. It installs Python
   3.12, Git, poppler, LibreOffice and the packages, turns on Virtual Machine Platform (Claude's
   Cowork workspace needs it), then runs every test. Wait for `RESULT  PASS`. If it says
   restart, restart. If SmartScreen blocks it: More info -> Run anyway. Safe to run again.
4. **Claude desktop app** (claude.com/download), installed from your admin account. Sign in ->
   Rainbow project -> new task -> attach the folder `C:\Rainbow` -> paste
   `CLAUDE-CHECK-PROMPT.txt`. If there's no Cowork / no way to attach a folder, you got the old
   .exe installer - Cowork only comes with the .msix package.
5. **Chrome:** sign in to the shop Gmail, add the Claude in Chrome extension, then Settings ->
   Downloads -> Location = `C:\Rainbow`, and turn off "Ask where to save each file".
   `collect_downloads.py` expects downloads in the Rainbow folder root. Also sign in to Gmail
   inside Claude's built-in browser once (the email digest reads star colors there).
6. **Fiery Hot Folders** (from Fiery Software Manager): create both in `C:\Rainbow\Hot Folders\`,
   server V180 (199.190.123.134), queue "VP180 print". Leave the Mac's running until these work.
   - **BWSS:** Grayscale; Paper size 8.5x11 LEF; Paper source Tray 6 (oversized); Scale to fit On;
     PDF Print Engine preferred Yes.
   - **BW SS Slip Sheet:** everything in BWSS, plus Slip sheet On, between Copies, before every 1,
     blank sheet from the Post-Fuser Tray (Letter); Copies 1.
7. **One master copy.** Once the Windows check passes, make price changes on Windows only. The
   Mac's PriceBook is a snapshot from 2026-10-17 from then on.

## If you work natively (Claude Code / VS Code instead of Cowork)
Scripts run from `C:\Rainbow\tools` with `python` or `py` instead of `python3`.
Tests: `bash tests/run_tests.sh` in Git Bash. PYTHONUTF8=1 is set machine-wide by the setup;
without it Windows Python mangles the price book's special characters.

## If this Windows is a Hyper-V VM (RAINBOW-VM)
Cowork runs its own VM, so the guest needs nested virtualization. On the host, with the VM shut
down, in admin PowerShell: `Set-VMProcessor -VMName RAINBOW-VM -ExposeVirtualizationExtensions $true`.
The setup script detects this and prints the exact line.
