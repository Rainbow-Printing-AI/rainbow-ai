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

## 2026-10-25 · pdftoppm block fixed — tests green
- Cause: Smart App Control is **on** (not evaluation). Code Integrity log showed every poppler tool (pdftoppm, pdftotext, pdfinfo, pdftocairo, pdffonts, pdfimages) blocked for one reason: loading `C:\Tools\poppler\poppler-26.09.0\Library\bin\lcms2.dll` (unsigned). Blocks started 2026-10-25 3:21 PM; nothing before.
- Not a bad file: a byte-identical copy of the poppler folder ran fine elsewhere. Windows had cached a "blocked" verdict on that one file on disk. Replaced `lcms2.dll` with a fresh copy of itself (same SHA-256; original kept as `lcms2.dll.bak`). All six tools start; SAC stays on. No `tools/` changes.
- `bash tools/tests/run_tests.sh`: exit 0, 46 PASS, 0 FAIL.
- Added a "poppler stops starting" fix-it note to `docs/windows-port.md` in case it happens again.
- Andrew learned: Smart App Control judges each program file by signature/reputation and remembers its verdict per file; the Code Integrity event log names exactly which file it blocked.
- **Next:** step 0.4 — skills into `.claude/skills/`.

## 2026-10-25 · Step 0.4 — skills in the repo
- Copied the six Cowork skills (`rainbow-print-imposition`, `-photo-print-prep`, `-print-order-packet`, `-email-digest`, `-email-reply`, `-pricebook`) from the account's synced copy (`~\.claude\skills\synced\…`) into `C:\Rainbow\.claude\skills\`.
- Made the four layout/price skills machine-neutral: Mac/VM paths (`~/Downloads/Rainbow/tools/`, `device_bash`, `$HOME/mnt/Rainbow`) now say "repo root; `py` on Windows, `tools/rbpy` on Mac, `python3` in the VM". Print rules untouched. The two email skills got a note at the top: they need the Gmail connector, so they're interactive-only until the Gmail API rewire (step 0.6 / Phase 1).
- `CLAUDE.md` already existed (the "project instructions → CLAUDE.md" half of the step was done on 2026-10-20). Two small CLAUDE.md edits and a `.claude/settings.json` (allow `py tools/*`) were held back for Andrew's OK: Claude Code won't change its own permissions or standing orders on its own.
- Done-test passed. Andrew ran `claude -p "/rainbow-print-imposition make tools/card_source.pdf 2-up on letter with marks" --model sonnet --allowedTools "Bash(py tools/*)" "PowerShell(py tools/*)"` and got `tools/card_source_3.38x2.17333_2up_letter_cropmarks.pdf`. `verify_print.py` re-run independently: RESULT PASS (0 fail, 1 warn = crush lift of the navy #001427/#031428/#011327, reported as TELL ANDREW). That PDF is a test output: not committed.
- Open question for Andrew: the imposition skill says "Bleed 0.1 in per side, always", but CLAUDE.md says bleed only when the job asks for it. The runtime followed CLAUDE.md (no bleed). One of them should be changed so they agree.
- Andrew learned: a skill is a folder with a SKILL.md; `claude -p` runs headless and can't ask for permission, so allowed tools are given up front (`--allowedTools` or `.claude/settings.json`).
- **Next:** decide the settings.json and bleed-wording questions; then step 0.5 — the runtime credential (subscription token).

## 2026-10-25 · Bleed/marks defaults and handbills (Andrew's rules)
- Resolved the bleed question from step 0.4. Written into `CLAUDE.md` (standing print rules) and `rainbow-print-imposition`; the photo rule also went into `rainbow-photo-print-prep`:
  - Bleed is 0.1 in per side unless Andrew names another amount.
  - Bleed + marks by default for business cards (always) and for any N-up on 8.5x11 or 11x17. A 4x6 or 5x7 final output page (full-bleed photo printer) gets neither unless asked. Anything else gets them only when asked.
  - Handbills = 4 identical quarter-sheet flyers on 8.5x11 (cut half short way, half long way, giving 4.25x5.5), with an even 1/8 in white margin on every piece to match the Versant's 1/8 in edge. Art scaled to fit 4.0x5.25, no bleed or marks. Margin changed from the skill's old 3/16 to 1/8.
- `impose.py` still defaults to no bleed/marks (unchanged); the skill now tells Claude to pass `--bleed 0.1 --marks` when these rules call for them.
- **Problem found:** `tools/fitpage.py` (the skill's tool for handbills and scaled cut-apart pieces) isn't on RAINBOW-AI and was never committed. It's probably still only on the Mac, written after the 2026-10-20 kit. Handbills can't run on Windows until it's brought over.
- The account copies of the skills (used by Cowork) still have the old wording. Update them from the repo copies.
- **Next:** get `fitpage.py` from the Mac (or rebuild it), test a handbill end to end; then step 0.5.

## 2026-10-25 · fitpage.py tested on Windows (handbills)
- Andrew copied `tools/fitpage.py` over from the Mac. Tested on made-up letter flyers in scratch: with 0.125 in bleed it fits the art at 47.06% to 4.0x5.25 with margins of exactly 0.125 on all four sides; `impose.py --nup 4 --sheet letter --gutter 0` → verify PASS. Measured from a 300 dpi render: all four quarters have identical margins (0.123 in; the 2 px gap is the antialiased edge). On a no-bleed flyer it STOPS (correct: no live art cropped); `--uneven` gives 0.125 L/R and 0.162 T/B.
- Added to `run_tests.sh`: the handbill pipeline (exact 1/8 margins plus verify) and the no-bleed stop. New fixtures `tests/t_flyer_bleed.pdf` and `tests/t_flyer_nobleed.pdf`. Added a `tools/README.md` line. Tests: exit 0, 48 PASS.
- **Open question for Andrew:** most customer flyers arrive with no bleed, and then an even 1/8 margin is impossible without cropping (letter is a hair taller than the 4.0x5.25 window). Choose the default: `--uneven` (1/8 sides, ~5/32 top/bottom, art untouched) or generate mirrored bleed first so the margin stays an even 1/8.
- **Next:** that decision; then step 0.5.
- Decided (Andrew): option 1. A handbill from a no-bleed flyer uses `fitpage.py --uneven` (letter: 0.125 L/R, ~0.162 T/B); never crop, never invent bleed. Written into `CLAUDE.md` and `rainbow-print-imposition`.
- **Next:** step 0.5, the runtime credential.

## 2026-10-25 · Step 0.4 loose ends
- Deleted the 0.4 test output `tools/card_source_3.38x2.17333_2up_letter_cropmarks.pdf` (never committed).
- Account skills: `~\.claude\skills\synced\` is a one-way download cache from the claude.ai account (it gets overwritten on every sync), so editing it would not update Cowork. Zipped the six repo skills into `Claude outputs/skill-uploads-2026-10-25/` for Andrew to upload in claude.ai → Settings → Capabilities → Skills (replacing the old ones). The repo wording is machine-neutral, so it works in Cowork as-is.
- `.claude/settings.json` (allow `py tools/*`, `tools/rbpy tools/*`): Claude Code blocked Claude from writing its own permissions file, as designed. Andrew creates it himself from a copy-paste.
- **Next:** step 0.5 — runtime credential.

## 2026-10-26 · Plan: step 0.8 added (one repo, every device)
- Andrew's goal: change skills/tools from any device; every Claude surface (Claude Code, desktop app, Cowork, phone, shop runtime) uses the latest from the repo; new skills/tools made anywhere get saved to the repo. Written into `docs/rainbow-ai-plan.md` as step 0.8 (plus a "Decisions" line, Phase 6.3 reworded, new open question) and `docs/rainbow-ai-architecture.md` §12. Key point: account skills (Cowork) and repo skills are two separate places; a plugin from the repo, or `package_skills.py` zips as the fallback, joins them.

## 2026-10-26 · Step 0.5 — runtime credential
- Andrew ran `claude setup-token` and stored the token as the user environment variable `CLAUDE_CODE_OAUTH_TOKEN` (`read -rsp … && setx …`, so it's not on screen or in shell history).
- Two tries went wrong. First paste was cut short (99 chars → 401 invalid token). Second was pasted twice (217 chars, the same 108-char token twice with a space). Claude saved one copy (108 chars). Checks only ever printed length/prefix, never the token.
- Done-test passed. Claude ran `claude -p "say ok" --model sonnet` with an empty `CLAUDE_CONFIG_DIR` (no saved browser login, so the token is the only way in): "ok", exit 0.
- Token lasts one year: renew by about 2027-10-26 (`claude setup-token` + the same `read`/`setx` line).
- Andrew learned: environment variables, tokens (treat like a password), why `--bare` can't use this token (API keys only), why the test has to hide the normal login.
- **Next:** step 0.6 — Google OAuth for Gmail + Drive. (0.7 needs the Fiery system version from CWS → Server Info; 0.8 can come any time now.)
