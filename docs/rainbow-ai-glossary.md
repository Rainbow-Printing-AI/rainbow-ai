# Rainbow AI — glossary (plain language, print-shop analogies where they help)

Read this when a word in the plan or architecture doc is new. Claude adds entries as the build introduces new terms.

## The machine and the terminal

- **Terminal / Git Bash / PowerShell** — a text window where you type a command and the computer runs it. Git Bash is the one we use on Windows because it understands the same commands as the Mac. You'll paste, press Enter, read the result.
- **Command** — one line like `py tools/verify_print.py file.pdf`: the program to run, then its arguments. `--flag` arguments switch options on, like checkboxes in a dialog.
- **PATH** — the list of folders Windows searches when you type a program name. "Command not found" usually means the program isn't on PATH.
- **Environment variable** — a named value the system hands to every program that starts (e.g. `CLAUDE_CODE_OAUTH_TOKEN`). We keep secrets there instead of in files that might end up in git.
- **Service / scheduled task** — a program Windows starts by itself at boot and keeps running with nobody logged in. NSSM is a small tool that turns any program into a service.
- **Headless** — a program running without a window on screen (a headless browser loads web pages invisibly).

## Claude pieces

- **Claude Code** — Claude in the terminal; it can read/write files and run commands in a folder. **Cowork** is the desktop-app version with a folder attached. Same brain, different window.
- **`claude -p "…"`** — "print mode": run one request non-interactively and exit, so a script can call Claude like any other command. Our runtime uses this.
- **Agent SDK** — the same engine as a Python/TypeScript library. We start with `claude -p` because you can run it by hand and see what happens.
- **Skill** — a folder with a `SKILL.md` that tells Claude how to do one kind of job (your `rainbow-*` skills). **CLAUDE.md** — the standing-orders file Claude reads at the start of every session in a folder.
- **Token (credential)** — a long random string that proves to Anthropic "this is Andrew's account" without a password. `claude setup-token` makes a one-year one.
- **Token (usage)** — unrelated meaning: the unit text is measured in for usage limits and API billing (~¾ of a word).
- **Model** — which Claude answers: Haiku (cheapest/fastest), Sonnet (the workhorse — our runtime), Opus/Fable (deepest, for design decisions).
- **Structured output / JSON schema** — telling Claude the exact form to fill in (field names and types) so the answer is machine-readable every time, not prose.
- **Agent / agent loop** — Claude deciding which tool to run, reading the result, deciding again, until done. `--max-turns` caps how many rounds.
- **Computer use** — Claude looking at screenshots and clicking. Slow and token-hungry; we avoid it in the daily loop.
- **MCP / connector** — the plug that gives Claude a tool (Gmail connector in claude.ai is one). The runtime token can't use claude.ai connectors, which is why we go through the Gmail API directly.

## Code and files

- **Python** — the language all the `tools/` scripts are written in. `py` or `python` runs a script on Windows.
- **Script** — a file of code that does one job when run. Deterministic: same input, same output, every time.
- **Package / `pip install`** — someone else's code you add to Python (pypdf, Pillow, FastAPI…). `requirements.txt` lists the ones a project needs.
- **JSON** — a text format for structured data: `{"copies": 50, "sides": 2}`. Easy for scripts and Claude to read and write; our specs, presets and rules are JSON.
- **XML** — older cousin of JSON with angle brackets; JDF tickets are XML.
- **Log** — a text file a program appends to as it works; first place to look when something breaks.

## Git and GitHub

- **Git** — a change-tracking system for a folder. Think of it as a hot folder for code: every "commit" is a dated, labelled snapshot you can go back to. It never loses old versions.
- **Repository (repo)** — a folder that git tracks. `C:\Rainbow` will be one.
- **GitHub** — a website that holds a copy of the repo so two machines can share it. Private repo = only you can see it.
- **Commit** — one snapshot with a message ("add colorpages.py"). **Push** — send your commits to GitHub. **Pull** — fetch the latest from GitHub onto this machine. **Clone** — make a first copy of a repo on a new machine.
- **`git status`** — "what changed since the last snapshot?" The one command you'll run most.
- **`.gitignore`** — the list of things git must *not* track (customer jobs, secrets, scratch files). Ours is an allow-list: ignore everything, then un-ignore the few folders we track.
- **Branch** — a parallel line of commits for trying something. We'll mostly stay on `main`.

## Databases

- **Database** — a file (or server) that holds tables and answers questions about them fast. **SQLite** is a database that is just one file (`rainbow.sqlite`), no server, built into Python — perfect for one shop.
- **Table / row / column** — exactly a spreadsheet: `jobs` table, one row per job, columns like `customer`, `status`, `copies`.
- **Schema** — the list of tables and their columns, decided up front.
- **Primary key / id** — the unique number each row gets (job 1042). Other tables point at it (file rows carry `job_id`).
- **SQL** — the question language: `SELECT * FROM jobs WHERE status='ready'`. Claude writes it; you'll learn to read it.
- **Migration** — a scripted change to the schema when we add a column later.

## Web

- **Web server** — a program that answers browser requests. Ours is **FastAPI** (Python) run by **Uvicorn**. It doesn't need the internet; it serves pages on the shop network.
- **Port** — the "door number" on a machine: `http://rainbow-ai:8000` means "talk to the program listening on door 8000". **localhost** = this machine; the hostname or IP = another machine on the LAN.
- **Firewall** — Windows asks once whether other computers may reach door 8000. Yes for the shop network.
- **HTML / template** — the page itself. **Jinja2** fills a template with data (the job list). **HTMX** lets parts of the page refresh without reloading, with no JavaScript build tools.
- **API** — a program's door for other programs (the Gmail API is how our script reads mail; our own app has one so the Setup button can call the backend). **REST** — the common style: a URL per thing, `GET` to read, `POST` to change.
- **Polling** — asking "anything new?" every N minutes. Simple and good enough for email.
- **Tailscale** — a private network between your devices over the internet, so the same `http://rainbow-ai:8000` works from the MacBook at home without opening anything to the public.

## Google

- **OAuth** — "let this program act as this account, without giving it the password, for these permissions only". You click Allow once; the program gets a **refresh token** it can keep using.
- **Scope** — the permission list (`gmail.modify` = read mail and change labels; `drive.readonly`). The consent screen shows them.
- **Google Cloud project / consent screen / client ID** — the paperwork Google requires before it issues OAuth tokens. One-time, clicking through a website. **Testing vs In production** — a project left in *Testing* hands out tokens that expire every 7 days; we set *In production*.
- **App Password** — the simpler Plan B: a 16-character password Google generates for one program (needs 2-Step Verification on). Works with **IMAP**, the old standard mail-reading protocol.
- **Label** — Gmail's folders/tags, visible to the API. **Star colours** are not exposed as a property, but Gmail *search* knows `has:red-star`.

## Fiery and printing

- **Hot folder** — a folder the Fiery Hot Folders app watches; drop a PDF in, it's submitted to the Versant with a saved **preset** (media, tray, sides, colour mode). One folder per configuration = our "print dialog".
- **Preset / job properties** — the saved set of print options. **Paper Catalog** — the Fiery's named stocks; presets refer to them.
- **Held vs Print queue** — Held parks the job for an operator to check/release in **Command WorkStation (CWS)**; Print runs it immediately. We send everything to Held.
- **JDF** — Job Definition Format: an XML ticket that travels with the PDF saying copies, media, sides, finishing. The industry standard for "here's the file and here's how to print it". **JMF** is the messaging side of the same standard (submit, query status).
- **Fiery API** — EFI's REST interface to the Fiery: scripts can submit jobs, set properties, hold/print, and read the queue. Needs enabling on the Fiery and a developer key.
- **Fiery system version (FS150, FS200…)** — the software generation on the Fiery; Server Info in CWS shows it. Decides which of the above are available.
- **Print queue (Windows)** — a printer object with a driver and default settings. Installing the Fiery driver several times with different defaults gives one queue per preset; a script can print to a queue with copies/duplex flags (SumatraPDF, Ghostscript).
- **Impression / click** — one printed side; colour and black clicks are metered separately, which is why the colour/BW call matters for cost.

## Our own terms

- **Datasheet** — the per-job ticket the app generates: size, sides, colour mode, page counts, copies, stock, finishing, warnings, questions.
- **Spec (`spec.json`)** — the machine-readable version of the datasheet, filled by Claude from the email + preflight.
- **Preflight** — the deterministic file facts (`pdfinspect.py`, `colorpages.py`): sizes, pages, dpi, fonts, colour metrics.
- **Override** — a human changing the app's call (colour/BW, copies, stock); logged and used to tune the rules.
- **Crush guard** — `crushcheck.py`: lifts colours that would print black on the Versant; every lift is reported.
- **PRINT READY/** — the subfolder where finished, verified PDFs go. **verify PASS** — `verify_print.py` exit 0; the only sign-off.
- **BUILD-LOG.md** — the running diary of the build, in the repo.
