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

## 2026-10-25 · Step 0.3 — GitHub repo
- `C:\Rainbow` is now the git repo; first commit pushed to `github.com/Rainbow-Printing-AI/rainbow-ai` (private), branch `main` (renamed from `master`). Git identity: `Andrew (Rainbow) <rainbowincline@gmail.com>`.
- Allow-list `.gitignore`: ignores everything at the top level, then tracks only `tools/`, `PriceBook/` (minus `private/`), `.claude/` (minus `settings.local.json`), `app/`, `docs/`, `CLAUDE.md`, `BUILD-LOG.md`, `.gitignore`, `.gitattributes`. Always ignored anywhere: `secrets/`, `*.env`, `credentials*.json`, `token*.json`, `__pycache__/`, `.venv/`. Top-level `README-WINDOWS.md` is ignored (same-name copy tracked in `tools/windows/`).
- Kept out on Andrew's call: owner/staff phone numbers and supplier account numbers — `PriceBook/data/contacts.csv`, `source/contacts_v1.py`, `source/scan_*.pdf`, `source/crops/p15_*`, `build/*.pdf`, `build/*.xlsx`. A fresh clone (the Mac) won't have the phone list or built books until we decide how to carry them (private/ via USB, like the logins).
- Also ignored: files `run_tests.sh` regenerates every run (`tools/tests/out/`, `*_tmp.pdf`, `merge_t.*`, `passport_synth*`) and `tools/windows/setup_log.txt`.
- Found and fixed before the first commit: `pricebook.py validate` and `tests/test_pricebook.py` had real login/tax-ID fragments written in the code. They now live in `PriceBook/private/secret_check.txt` (git-ignored); the check works the same. Mark's home number blanked to `831-xxxx` in the conflict-sheet example text (`conflicts.json`, `cards_v1.py`); the privacy test now reads internal numbers from `contacts.csv` when present. Price-book tests 10/10 OK, `validate` PASS.
- `.gitattributes` `* -text`: git never converts line endings, so PDFs, `.sh` (LF) and `.cmd`/`.ps1` (CRLF) stay byte-exact on both machines. Checked all files byte-for-byte after commit.
- Push from Claude's shell couldn't show the GitHub sign-in window; Andrew ran the first push in Git Bash himself. The login is now saved by Git Credential Manager.
- **Problem found:** `bash tools/tests/run_tests.sh` now fails at the first test — Windows refuses to start `pdftoppm.exe` (exit `0xC0E90002`, code-integrity block, almost certainly Smart App Control on Windows 11 Home). Passed on 2026-10-22. Not caused by this step (no `tools/` changes).
- Andrew learned: repo, commit, staging, push/pull, remote/`origin`, branch, allow-list `.gitignore`, why secrets and personal numbers never go in git (history keeps them even after deletion), line endings, amending an unpushed commit.
- **Next:** fix the `pdftoppm` block (Smart App Control / Windows Security → App & browser control) and get `run_tests.sh` green again; then step 0.4 — skills into `.claude/skills/`.
