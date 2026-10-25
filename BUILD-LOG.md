# Rainbow AI — build log

Newest at the bottom. Every build session appends an entry: date · step · what was done · what Andrew learned · next.

## 2026-10-17 · Windows port kit
- Built `Rainbow_Windows_Kit_2026-10-17.zip` on the Mac (tools, PriceBook minus private, Claude outputs, Digests) and `PriceBook_private_2026-10-17.zip` (USB only). Portability fixes in `tools/` (bundled font + CMYK profile, UTF-8 I/O, Windows paths). `tools/windows/SETUP-WINDOWS.cmd` installs Python 3.12, Git, poppler, LibreOffice and runs the tests. Details: `docs/windows-port.md`.
- Dave bought RAINBOW-AI (Core 7 265, 32 GB, 1 TB, Windows 11).

## 2026-10-20 · Plan written (no code yet)
- Decided the shape of Rainbow AI and wrote `docs/rainbow-ai-plan.md`, `docs/rainbow-ai-architecture.md`, `docs/rainbow-ai-glossary.md`, plus the printable checklist PDF. Decisions: subscription token for the runtime (Sonnet), Fiery hot folders for printing, zero computer use in the daily loop, color/BW decided the way the shop prints (rules → Claude → always overridable), Gmail/Drive via OAuth on the shop account (owners OK'd), Windows is the master, git repo with the Mac as a second clone.
- Wrote this `CLAUDE.md` and `BUILD-LOG.md`; packaged `Rainbow_AI_Kit_2026-10-20.zip` (current tools, PriceBook minus private, docs, CLAUDE.md, BUILD-LOG.md) for the Windows box.
- Andrew learned: builder vs runtime Claude; why hot folders beat print-dialog automation; what the datasheet is for.
- **Next:** step 0.1 — confirm the Windows box state (`bash tools/tests/run_tests.sh` passes natively). Also: Fiery system version from CWS → Server Info; Windows 11 Home or Pro.

## 2026-10-20 · Kit check in the Cowork VM (before step 0.1)
- Kit found at `C:\Users\rainb\OneDrive\Documentos\Rainbow AI\Rainbow` (not `C:\Rainbow`); mounts at `$HOME/mnt/Rainbow AI/Rainbow`. Native setup not run yet (no `tools/windows/setup_log.txt`).
- Tested in the Cowork VM on a copy: `tools/tests/run_tests.sh` exit 0 (45 PASS fresh, 46 re-run); every script's `--help`; build_banner (with the optional pip extras), photo_prep, pdfinspect --clean, crushcheck --fix/--swatches, labels --bleed, alignment page, mergelabels from .xlsx, collect_downloads --any, fetch_links link extraction (no real share link tested). PriceBook: unit tests, validate, audit (9/9), every CLI command, build, conflicts-pdf, counter-sheet rebuild (text-identical to the current PDFs). All 14 pinned packages have Windows py3.12 wheels.
- Fixed: `pricebook.py quote` priced retired rows silently (README example added $13.80 of retired comb covers). Now refuses them; test added. Stale lines fixed in `PriceBook/README.md` (quote example) and `tools/README.md` (crush thresholds 22/28 per press.json).
- **Next:** move the folder to `C:\Rainbow` (out of OneDrive), run `SETUP-WINDOWS.cmd`, then step 0.1.

## 2026-10-22 · Step 0.1 — Windows box state confirmed
- Ran `bash tools/tests/run_tests.sh` in Git Bash on RAINBOW-AI: all tests passed.
- Andrew learned: what a terminal is, what PATH is, and why Windows uses `py` instead of `python3`.

## 2026-10-22 · Step 0.2 (in progress) — Claude Code CLI
- Installed the Claude Code CLI with the PowerShell installer. It landed in `C:\Users\rainb\.local\bin` but that folder wasn't on PATH, so we added it to the user PATH. Logged in.
- Andrew learned: the Claude desktop app and the `claude` command-line tool are separate programs.
- **Next:** VS Code + the Claude Code extension, then the 0.2 done-test.

## 2026-10-22 · Step 0.2 — complete
- Installed VS Code with the Claude Code extension; set the default terminal to Git Bash.
- `claude` wasn't found inside VS Code at first: VS Code had started with an old copy of PATH (from before `C:\Users\rainb\.local\bin` was added). Fixed.
- Done-test passed: `claude -p "list the scripts in tools/"` listed all 18 scripts.
- Andrew learned: the difference between the Claude desktop app, Claude Code, and Claude on the web; `CLAUDE.md` is the standing-orders file Claude reads every session.
- **Next:** step 0.3 — the GitHub repo.
