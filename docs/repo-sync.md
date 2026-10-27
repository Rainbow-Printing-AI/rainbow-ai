# Repo sync: one repo, every device (plan step 0.8)

The GitHub repo `Rainbow-Printing-AI/rainbow-ai` (private) is the one copy of the skills (`.claude/skills/`), the tools
(`tools/`), the standing orders (`CLAUDE.md`) and the docs. Every Claude surface reads from it:

| Where | How it gets the repo | How changes get back |
|---|---|---|
| Claude Code on RAINBOW-AI (`C:\Rainbow`) and the Mac (`~/Downloads/Rainbow`): terminal, VS Code, desktop app Code tab | Reads the folder directly. A **SessionStart hook** runs `tools/repo_sync.py` → `git pull --ff-only` every time a session starts | Say **"save it to the repo"** → `rainbow-save` skill: tests green → commit → push |
| Cowork / claude.ai chat (no folder) | The **`rainbow` plugin** from the repo's own marketplace (`.claude-plugin/`), set to sync automatically | Skills made in Cowork land on the account only: `package_skills.py --check` finds them, `--import` copies them into the repo, then "save it" |
| Phone / any browser | Claude Code on the web (claude.ai/code) on the GitHub repo: it opens a pull request, Andrew taps Merge | Both machines pull it at their next session |
| Shop runtime (Phase 2 on) | Service pulls on a timer, runs the tests before using new tools (architecture §12) | n/a |

**Fallback for Cowork** if the plugin ever stops working: `py tools/package_skills.py` builds one zip per skill into
`Claude outputs/skill-uploads-DATE/`; upload each in claude.ai → Settings → Capabilities → Skills, replacing the old one.
`package_skills.py --check` says which account skills are STALE, MISSING or ACCOUNT-ONLY.

## What repo_sync.py does at session start
- Clean folder, GitHub has newer commits → pulls them (fast-forward only) and lists them.
- Folder has **unsaved changes** (edited or new files git would track) → **REPO SYNC WARNING**, nothing pulled.
  Answer: "save it to the repo" if the changes are wanted; otherwise ask Claude to show them first. Nothing is
  ever thrown away automatically.
- This machine and GitHub **both** have new commits (diverged) → warning, nothing merged. Ask Claude to show both sides.
- Not on branch `main`, no internet, GitHub login expired → warning, work continues on the local copy.
- The warning shows on screen and Claude is told to mention it in its first reply.

## Windows side: Andrew's two steps (step 0.8)

**1. Install the hook.** Claude isn't allowed to edit its own settings file, so you copy it in. In the desktop
app's terminal (PowerShell), paste:

```powershell
Copy-Item "C:\Rainbow\Claude outputs\step-0.8\settings.json" "C:\Rainbow\.claude\settings.json"
```

It's the old file (the three `py tools/*` permissions) plus this `hooks` block:

```json
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear",
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && if command -v py >/dev/null 2>&1; then py tools/repo_sync.py --hook; else tools/rbpy tools/repo_sync.py --hook; fi",
            "timeout": 90
          }
        ]
      }
    ]
  }
```

The same file works on both machines: Windows has `py`, the Mac doesn't, so the Mac uses `tools/rbpy`. Claude
Code runs hook commands in Git Bash on Windows (tested 2026-10-26).
Then start a new Claude session in `C:\Rainbow` and say **"save it to the repo"**. That commits `settings.json`,
which is how the Mac gets the hook.
Done when: the session starts with either "repo_sync: Rainbow repo is up to date with GitHub." or a
REPO SYNC WARNING.

**2. Install the plugin for Cowork** (Claude desktop app, not the terminal):
1. Customize → Plugins → Add → **Add marketplace** → type `Rainbow-Printing-AI/rainbow-ai`.
2. The repo is private: when it asks, **Connect GitHub** and install the **Claude GitHub App** on the
   `Rainbow-Printing-AI` organization with access to `rainbow-ai` (only that repo is enough).
3. Install the plugin **rainbow** from the marketplace **rainbow-printing**. Turn on **Sync automatically** for that marketplace.
4. In claude.ai → Settings → Capabilities → Skills, **delete the six old uploaded `rainbow-*` skills**. Otherwise
   Cowork has two copies of each, and the uploaded ones are out of date (as of 2026-10-26 they're still the
   2026-10-22 wording). The plugin's copies are named `rainbow:rainbow-print-imposition` and so on.

Done when: a Cowork chat lists `rainbow:rainbow-save` among its skills, and after a push the plugin shows the
new version (Check for updates, or wait for the automatic sync).
If the GitHub App step won't work: use the zip fallback above and tell Claude, so the build log records it.

Note: after step 4, `package_skills.py --check` reports the plugin's skills as MISSING. That's expected: it only
sees uploaded skills. It still catches ACCOUNT-ONLY skills made in Cowork.

## Mac side: runbook for the session "Rainbow AI step 0.8, Mac side"

This runs in Claude on the Mac (desktop app Code tab or `claude` in Terminal) with the folder `~/Downloads/Rainbow`.
Goal: make that folder a real git clone of `main` **without losing anything**. The Mac folder holds customer jobs,
`PriceBook/private/`, the phone-list files and built books that GitHub does not have and must never get.
Claude: explain each step to Andrew before doing it; he types only the lines you hand him (macOS Terminal is zsh,
so `&&` is fine there). Never use `git clean`, `git checkout -f`, `git reset --hard` or `git stash` in this folder.

**Before starting:** on RAINBOW-AI the hook `settings.json` (Windows step 1) should be saved to GitHub. Check on
github.com, or later in step 5 with `git show origin/main:.claude/settings.json | grep repo_sync`. If it isn't
there, do the rest anyway and add the hook last.

1. **Check the tools.**
   - `git --version`. If macOS offers to install the Command Line Tools, accept and wait.
   - `tools/rbpy -c "import sys; print(sys.version)"` → 3.12.x. If it says "Rainbow Python not installed", run
     `bash tools/setup-mac.sh` first.
   - `df -h ~` and `du -sh ~/Downloads/Rainbow`: there must be room for a full copy.
2. **Back up the whole folder** (customer files included):
   `ditto ~/Downloads/Rainbow ~/Downloads/Rainbow-backup-2026-MM-DD` (today's date). Compare the file counts:
   `find ~/Downloads/Rainbow -type f | wc -l` and the same for the backup must match.
3. **GitHub login on the Mac.** Use the GitHub CLI from the Rainbow Python's own installer (no Homebrew needed):
   `MAMBA_ROOT_PREFIX=~/.rainbow/mamba ~/.rainbow/bin/micromamba install -y -p ~/.rainbow/env -c conda-forge gh`, then
   `~/.rainbow/env/bin/gh auth login --hostname github.com --git-protocol https --web` (Andrew signs in in the
   browser as the account that owns the `Rainbow-Printing-AI` org), then `~/.rainbow/env/bin/gh auth setup-git`.
   Check: `~/.rainbow/env/bin/gh repo view Rainbow-Printing-AI/rainbow-ai --json name` prints the name.
   (Plain HTTPS with a password won't work: GitHub wants a token or the browser sign-in.)
4. **Link the folder to GitHub, changing no files yet.** In `~/Downloads/Rainbow`:
   - If `.git` already exists, stop and look at it with Andrew first (`git status`, `git remote -v`).
   - `git init -b main`
   - `git config user.name "Andrew (Rainbow)"` and `git config user.email "rainbowincline@gmail.com"` (same as Windows)
   - `git remote add origin https://github.com/Rainbow-Printing-AI/rainbow-ai.git`
   - `git fetch origin`
   - `git checkout origin/main -- .gitignore .gitattributes`. This brings the ignore rules over first, so customer
     files, `private/`, the phone list and built books are never offered to git.
   - `git reset origin/main`: the branch now points at GitHub's `main` but **the working files are untouched** (a
     "mixed" reset only changes git's record, not the files).
   - `git branch --set-upstream-to=origin/main main`
5. **Compare the Mac's files with GitHub's, one by one.** Run `git status --short`:
   - Nothing customer-like should appear (the ignore rules hide it). If any job file, anything from `private/`,
     `contacts.csv`, a `scan_*.pdf` or a `build/*.pdf` shows up, stop: the ignore rules need fixing, don't add it.
   - ` D` (in GitHub, missing on the Mac): new on Windows, such as `repo_sync.py`, `package_skills.py`, `rainbow-save`,
     `.claude-plugin/` and `app/`. Take them: `git checkout -- <path>`.
   - ` M` (both have it, contents differ): look at `git diff --stat`, then `git diff <file>` for each. Mostly the
     Mac has the older copy (Windows has been the master since 2026-10-20). Show Andrew anything where the Mac
     looks **newer** (a Mac-only fix, a price the Windows copy doesn't have, a newer skill wording). For each file,
     either take GitHub's (`git checkout -- <file>`) or keep the Mac's to save in step 8. Default when unsure:
     GitHub's, since the backup still has the Mac version. A mode-only change (`old mode 100644 / new mode
     100755`) on a script is fine. Take GitHub's.
     Line endings: if a diff shows every line changed, check `file <path>` for CRLF. GitHub's copy is correct;
     take it.
   - `??` (on the Mac only, not ignored): probably Mac-only scripts or skills (like `fitpage.py` was). List them for
     Andrew; tools and skills worth keeping get saved in step 8, and junk stays put (not deleted, just not added).
   - Finish when `git status --short` shows only the files Andrew chose to keep from the Mac.
6. **Tests:** `PATH="$HOME/.rainbow/env/bin:$PATH" bash tools/tests/run_tests.sh` → exit 0, no FAIL (55 PASS as of
   2026-10-26, more if tools were added since). Red: stop and fix before going on.
7. **Hook and skills.** `cat .claude/settings.json` must show the `repo_sync` hook (it comes from GitHub; Claude
   doesn't write it). Run `tools/rbpy tools/repo_sync.py`: it should say "up to date" or give a warning that lists
   exactly the Mac files kept in step 5. The skills in `.claude/skills/` (including `rainbow-save`) are now read
   straight from the folder by Claude Code on the Mac.
   If the Mac's Claude Code also has the `rainbow` plugin installed, the skills show up twice (`rainbow-save` and
   `rainbow:rainbow-save`). The text is the same, so it does no harm. On the clone the folder copy is the newest.
8. **Save the Mac's keepers.** Say "save it to the repo" (rainbow-save): tests, commit ("Mac: <what was kept>"),
   push. Then `tools/rbpy tools/repo_sync.py` → "up to date".
9. **Done-tests (plan step 0.8):**
   - (1) Change one harmless line of a skill on the Mac (e.g. a wording fix Andrew picks), "save it", see it on
     github.com.
   - (2) Start a new Claude session on RAINBOW-AI (Chrome Remote Desktop once more, or wait until he's at the
     shop): the hook pulls it, with no git typed.
   - (3) Cowork shows the new wording through the plugin, or `package_skills.py --check` names it STALE and the zip fixes it.
   - (4)/(5) A new test skill from the Code tab and a phone edit via claude.ai/code can be done any time later.
10. **Build log:** append the Mac-side entry to `BUILD-LOG.md` and save it to the repo. The backup folder stays
    until Andrew has worked from the Mac for a week; then he can delete it himself.

Phone list and built books (`contacts.csv`, `contacts_v1.py`, `scan_*.pdf`, `p15_*` crops, `build/*.pdf|xlsx`) stay
Mac/USB files, as decided in step 0.3. They're ignored, so git never touches them.
