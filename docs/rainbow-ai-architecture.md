# Rainbow AI — architecture reference (v1, 2026-10-20)

Read with `docs/rainbow-ai-plan.md` (the steps) and `docs/rainbow-ai-glossary.md` (the words). This doc is the "how it fits together" reference that build sessions consult. Update it when a decision changes.

## 1. The shape

```
 shop Gmail ──(Gmail API, OAuth)──► poller ──► Jobs/<job>/source/
 share links ──(fetch_links / Drive API / headless Chromium)──┘
                                      │
                                      ▼
                     preflight (pdfinspect, colorpages, convert) ── deterministic
                                      │
                                      ▼
                     spec extraction (claude -p, JSON schema) ───── Claude, 1 call
                                      │
                                      ▼
                     color/BW rules → Claude for the middle band ── logged
                                      │
                                      ▼
                     datasheet.pdf/html + job row in rainbow.sqlite
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        ▼                                                           ▼
  Job board (FastAPI on RAINBOW-AI:8000, any browser)        Setup button → agent
  toggles: color/BW, copies, stock · corrections box         (claude -p + skills + tools/)
        │                                                     → PRINT READY/ + verify PASS
        ▼
  Print (confirm modal) ──copy──► Fiery hot folder ──► Held queue on the Versant
```

Two Claudes: the **builder** (Cowork / Claude Code sessions, your interactive usage) and the **runtime** (the program calling `claude -p` with the subscription token). Everything deterministic is a script; Claude is used exactly three ways at runtime: spec extraction (one structured call), color judgment on ambiguous pages (one call with thumbnails), and the Setup/corrections agent (a tool-using run capped by `--max-turns`).

## 2. Folder layout on RAINBOW-AI

```
C:\Rainbow\                     ← git repo root, allow-list .gitignore
  CLAUDE.md                     ← standing orders (from the project instructions)
  BUILD-LOG.md                  ← what each build session did
  docs\                         ← this plan, architecture, glossary, windows-port, checklist PDF
  .claude\skills\rainbow-*\     ← exported Cowork skills
  tools\                        ← unchanged press-prep scripts (+ colorpages.py new)
  PriceBook\                    ← sheets + data (private\ ignored by git)
  app\
    server.py                   ← FastAPI: pages + API + background poller
    intake\  poll_gmail.py, links.py, preflight.py, spec.py, color.py, datasheet.py
    agent\   runner.py          ← wraps claude -p for Setup/corrections
    print\   dispatch.py        ← hot folder copy, later JDF/API
    presets.json                ← hot folder ↔ media/sides/color
    color_rules.json            ← thresholds, tuned from overrides
    templates\ static\          ← HTML
    data\rainbow.sqlite         ← NOT in git (backed up nightly)
  secrets\                      ← credentials.json, token.json — NOT in git
  Jobs\                         ← one folder per job — NOT in git
  Hot Folders\                  ← Fiery Hot Folders app owns these — never written by anything but dispatch.py
```

The Mac's `~/Downloads/Rainbow` becomes a second clone of the same repo (same layout, same ignores), so paths in skills keep working on both machines.

## 3. Runtime credential

- `claude setup-token` → one-year OAuth token → environment variable `CLAUDE_CODE_OAUTH_TOKEN` (user-level on RAINBOW-AI). Requires Pro/Max/Team. It "can only make model requests": no claude.ai connectors (so Gmail must go through the Gmail API, not the connector), but local MCP servers and skills work.
- **Do not pass `--bare`** — bare mode ignores the OAuth token and needs an API key. Use plain `claude -p` with `--model sonnet`, `--max-turns`, `--allowedTools`, `--permission-mode`, `--output-format json`.
- Usage draws on Andrew's plan. `--output-format json` returns `total_cost_usd` (an estimate) — log it per run so switching to an API key later is a numbers decision.
- Switching later: Console API key in `ANTHROPIC_API_KEY`; it outranks the OAuth token automatically.

Typical calls:
```
# spec extraction (no tools, strict JSON)
claude -p --model sonnet --output-format json --json-schema "$(cat app/intake/spec_schema.json)" \
  --append-system-prompt-file app/intake/spec_prompt.md --max-turns 1 < job_context.txt

# setup agent (tools, skills from the repo, capped)
cd Jobs/<job> && claude -p "/rainbow-print-imposition <instruction>" --model sonnet \
  --add-dir C:/Rainbow --allowedTools "Read,Bash(py C:/Rainbow/tools/*)" \
  --permission-mode acceptEdits --permission-prompts none --max-turns 25 --output-format json
```

## 4. Gmail integration

- **Auth:** OAuth 2.0 Desktop client, scopes `gmail.modify` (read + labels; readonly can't label) and `drive.readonly`. Consent screen External → publishing status **In production** (a project left in *Testing* issues refresh tokens that die after 7 days). Unverified-app warning is expected; click through once.
- **Polling:** every 2 min, `users.threads.list` with `q="newer_than:2d -label:RainbowAI/Seen has:attachment OR (…link words…)"`. Attachments via `messages.attachments.get`. Thread id is the join key between inbox page and job.
- **Red stars:** the API exposes no star colour on a message, but `q` accepts Gmail search syntax, and `has:red-star` is a Gmail search operator → `threads.list(q="has:red-star newer_than:30d")` should return the owners' "done" set. **Verify in step 1.2.** Fallback: headless Chromium logged into Gmail reads the star class names (scripted, no tokens). The app never sets or removes stars.
- **Labels the app owns:** `RainbowAI/Seen`, `RainbowAI/Job`, `RainbowAI/Printed`, `RainbowAI/NeedsFile`. Owners keep using red stars; the Inbox page shows both.
- **Plan B (no Cloud project):** IMAP + Gmail App Password (needs 2-Step Verification). `X-GM-RAW` search accepts Gmail syntax too; labels = folders. Loses Drive API.

## 5. Share links

Tiers, tried in order; each returns files into `source/` or a reason:
1. `tools/fetch_links.py` — OneDrive personal (tested), Dropbox (`?dl=1`), public Drive.
2. Drive API with the shop OAuth — Drive files shared with the shop address (today's "FAIL: got a web page" cases).
3. Headless Chromium (Playwright) with a persistent profile — WeTransfer, Hightail, SharePoint; `collect_downloads.py` logic reused to reject HTML-posing-as-file.
4. Give up → status `needs_file`, link listed on the job page, drag-and-drop upload box.

## 6. Preflight and the color/BW decision

**Facts (scripts):** `pdfinspect.py` per file (boxes, rotation, dpi, fonts, crush report). Images → PDF (Pillow; "two JPEGs, front and back" → 2-page PDF when the spec says so). Office/text → PDF via LibreOffice headless. New `tools/colorpages.py`: render each page at ~50 dpi, convert to Lab, chroma threshold C* ≥ 12 (ignores scanner tint), report per page: `coverage` (fraction of pixels with chroma), `largest_blob` (connected-component area fraction), `color_text_only` (thin strokes only). Writes `preflight.json`.

**Decision ladder (`app/intake/color.py`):**
1. Customer explicitly says ("print in color", "black and white is fine") → that, source `customer`.
2. Any page with `coverage ≥ 0.20` or `largest_blob ≥ 0.05` → `color`, source `rule:graphic`.
3. All pages `coverage < 0.02` and `largest_blob < 0.005` → `bw`, source `rule:logo-only`.
4. Otherwise → Claude sees the page thumbnails + email text + metrics, answers `{mode, confidence, reason}`; `confidence < 0.7` flags the job "check color" on the board. Source `claude`.
5. UI toggle by Andrew/Mark/Dave → source `override`, logged with the metrics and the previous call.

Thresholds live in `app/color_rules.json`. Monthly: dump `overrides` → adjust thresholds → eventually feed overrides back as few-shot examples in the Claude prompt. Decision is per job; a per-page-range split (colour pages pulled out as a separate hot-folder submission) is a backlog item.

**Impression counts on the datasheet** follow the chosen mode: `bw` → all pages BW; `color` → pages with detected color count as color, the rest BW (the Fiery meters a mixed job per page when sent in color mode — confirm this matches how the shop bills).

## 7. Spec (what Claude fills in)

`spec.json` fields: `customer {name,email}`, `received`, `due` (if stated), `files[] {name, pages, size_in, kind}`, `finished_size`, `sheet_size`, `sides` (simplex/duplex), `color_mode` + `color_source`, `copies`, `pages_per_copy`, `color_pages`, `bw_pages`, `impressions {color,bw}`, `stock` (preset id or free text), `finishing[]` (staple/fold/cut/laminate/…), `setup_needed` + `setup_description`, `warnings[]`, `questions_for_customer[]`, `confidence`. Schema is enforced by `--json-schema`; the datasheet is rendered from it, never from free text.

## 8. Job states

`new → needs_file → preflighted → (needs_setup → setup_running → ) ready → sent_to_fiery → printed → done`, plus `awaiting_customer`, `setup_failed`, `error`. Every transition is a row in `events` (who/what/when). The board's columns are these states.

## 9. Setup agent

- Runs in the job folder; skills + CLAUDE.md from `--add-dir C:/Rainbow`; tools limited to reading and running `tools/*.py`; output only in `PRINT READY/`.
- Must end with `verify_print.py` exit 0; the runner parses the JSON result, re-renders previews, stores the transcript path and cost.
- Corrections: the box's text is sent with `--resume <session_id>` so the agent remembers the job. Guard: `--max-turns 25`, 5-minute wall clock, one run at a time per job.
- Crush-guard lifts: `>>> TELL ANDREW` lines are captured and shown as a banner (project rule: report every lift).

## 10. Printing

**Hot folders (Phase 4.1).** Fiery Hot Folders app on RAINBOW-AI; one folder per configuration; all point at the **Held** queue. `presets.json` example:
```json
{"V180_CLR_SS_Letter_Cardstock110": {"color":"color","sides":1,"sheet":"8.5x11","media":"Cardstock 110 lb cover","tray":"Tray 6","path":"C:/Rainbow/Hot Folders/V180_CLR_SS_Letter_Cardstock110"}}
```
`dispatch.py` copies the verified PDF with the job id in the filename, polls the folder until the Hot Folders app consumes it, sets `sent_to_fiery`. Copies are set at release in Command WorkStation until 4.2.

**Copies without CWS (Phase 4.2) — three routes, pick after checking the Fiery version:**
- **JDF ticket.** A small XML job ticket (copies, media, sides) submitted with the PDF. Fiery servers support JDF submission when enabled in Configure; exact mechanics (JMF endpoint vs ticket-aware hot folder) to be confirmed against this Fiery's Configure pages. Free; standard.
- **Fiery API.** EFI's REST interface (FS150+; must be enabled; needs a developer key from EFI). Lets a script set job properties, hold/print, read the queue → the board can show "printing / done" live. Most capable, most setup.
- **Windows print queue per preset.** Install the Fiery driver N times, each queue's defaults = one preset; print with `SumatraPDF -print-to "<queue>" -print-settings "3x,duplex"` (copies/duplex are flags). No Fiery config; crude but dependable. Same trick covers the PlotWave 300 and the Canon large-format through their drivers.

**Not automated:** PRO-4100S photo prints via Lightroom + ICC profiles. That's a screen-driving job and stays manual.

## 11. Web app

- **Stack:** Python 3.12, FastAPI + Uvicorn, Jinja2 templates, HTMX for refresh without a JavaScript build step, SQLite via the standard library. Chosen because every piece is Python (same as `tools/`), nothing to compile, one process.
- **One process does everything:** the server also runs the poller loop and a small job queue (so there's one thing to start, one log). Installed as a Windows service with NSSM; auto-start at boot; log to `app/data/logs/`.
- **Network:** LAN only, `http://rainbow-ai:8000` (Windows Firewall inbound rule for 8000). No login at first; add a shop PIN before exposing over Tailscale. Tailscale gives the MacBook the same URL from anywhere.
- **Previews:** `pdftoppm` → PNG thumbnails per page, cached in the job folder.

## 12. Git sync model

- Repo = `C:\Rainbow` with an allow-list `.gitignore`. Tracked: `tools/`, `PriceBook/` (minus `private/`), `.claude/`, `app/` (minus `data/`), `docs/`, `CLAUDE.md`, `BUILD-LOG.md`. Everything else (jobs, secrets, hot folders, customer files, `__pycache__`, `.bak`) ignored.
- Mac: second clone. Claude commits/pushes from whichever machine the change was made on; the other machine `git pull`s (the service pulls on a timer and re-runs `tests/run_tests.sh` before swapping in new tools — if tests fail it keeps the old version and shows it on the health page).
- Price book data is in the DB on Windows and edited through the app; the repo holds only the sheet templates and generator scripts.
- **Every Claude surface reads the repo (plan step 0.8):** Claude Code on a clone reads `.claude/skills/` + `CLAUDE.md` directly, kept current by a SessionStart hook (`tools/repo_sync.py`, `git pull --ff-only`, warns on dirty/diverged). Changes are saved with the `rainbow-save` skill (tests green → commit → push). Cowork/claude.ai use account skills, fed from the repo by a plugin marketplace in the repo, with `tools/package_skills.py` as the zip fallback and stale-check. Phone/browser edits go through Claude Code on the web as pull requests.

## 13. Backups and safety

- Nightly: copy `rainbow.sqlite` + `Jobs/` to shop storage; keep 30 days.
- Secrets only in `C:\Rainbow\secrets\` and environment variables.
- The app writes only inside `Jobs/`, `app/data/`, and the hot folders. Customer source files are never modified (project rule).
- Nothing prints, sends email, or changes a price without a click in the UI.
