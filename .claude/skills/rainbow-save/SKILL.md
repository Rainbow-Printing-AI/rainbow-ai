---
name: rainbow-save
description: "Save the Rainbow folder's changes to GitHub: run the tool tests, then commit with a plain-English message and push. Use when Andrew says \"save it\", \"save it to the repo\", \"push it\", \"commit this\", or at the end of a session that changed skills, tools, CLAUDE.md, docs or app code. Never pushes when the tests fail."
---

# Rainbow save (tests → commit → push)

The Rainbow repo (`C:\Rainbow` on RAINBOW-AI, `~/Downloads/Rainbow` on the Mac) is the one copy of the skills,
tools and standing orders. Every machine pulls it at session start (`tools/repo_sync.py`). This skill puts this
machine's changes into GitHub so the others get them. Andrew has never coded: tell him in plain words what is
being saved and what happened. Run every step from the repo root.

## 1. Look before saving
- `git status --porcelain --untracked-files=all` and `git diff --stat`. Nothing listed → say "nothing to save" and stop.
- `git symbolic-ref --short HEAD` must be `main`. If not, stop and tell Andrew.
- **Never commit** anything under `secrets/` or `PriceBook/private/`, the phone-list files
  (`PriceBook/data/contacts.csv`, `PriceBook/source/contacts_v1.py`, `PriceBook/source/scan_*.pdf`,
  `PriceBook/source/crops/p15_*`, `PriceBook/build/*.pdf|*.xlsx`), `*.env`, `credentials*.json`, `token*.json`,
  customer files, or test outputs. `.gitignore` already keeps these out; if one shows up in the list anyway, stop
  and tell Andrew — do not commit, do not edit `.gitignore` on your own.
- Stage files by name (`git add <path> …`), never `git add -A` / `git add .`. Leave out anything that looks like a
  stray scratch file and say so.
- Line endings: the repo is LF (`.gitattributes` is `* -text`, so git won't fix them). `.cmd`/`.ps1` are CRLF on
  purpose. For every staged text file other than `.cmd`/`.ps1`, check `git diff --cached --numstat` and
  `grep -c $'\r'` on the file; if a file that was LF now has CR characters, convert it back to LF before committing.
- Skills: if a `.claude/skills/<name>/` folder was added or changed, also run
  `py tools/package_skills.py --check` (Mac: `tools/rbpy tools/package_skills.py --check`) and mention in the
  summary that Cowork picks it up through the plugin (or the zip fallback, see `docs/repo-sync.md`).

## 2. Run the tests — red means stop
- Windows: `bash tools/tests/run_tests.sh` (Git Bash; from PowerShell: `bash tools/tests/run_tests.sh`).
- Mac: `PATH="$HOME/.rainbow/env/bin:$PATH" bash tools/tests/run_tests.sh`.
- Exit 0 and no `FAIL` line = green. Anything else = **red: do not commit, do not push.** Show Andrew the FAIL
  lines, say what they mean in plain words, and offer to fix. A red run is never pushed "just this once", and
  tests are never edited to make them pass unless the test itself is wrong and Andrew agrees.
- Changes only under `docs/`, `BUILD-LOG.md` or `CLAUDE.md` still run the tests (they're quick and prove the tools
  on this machine still work).

## 3. Commit
- Message: one plain-English line that says what changed and why, the way Andrew would say it
  ("Imposition skill: handbills default to --uneven"), then a blank line and 1–5 short lines of detail if useful.
  No jargon like "refactor" or "chore".
- End the message with the attribution line the session's system instructions give, if any.
- `git commit -F <message file in the scratch folder>` (avoids quoting trouble in PowerShell).

## 4. Push
- `git push origin main`.
- Rejected because GitHub has newer commits → `git pull --ff-only origin main` is **not** possible after a local
  commit; do `git fetch origin` then `git log --oneline HEAD..origin/main` and show Andrew what's new on GitHub.
  If his commit and theirs touch different files, `git pull --rebase origin main`, re-run the tests, then push. If
  they touch the same files, stop and walk him through it. Never `--force`.
- Sign-in window or "authentication failed" → Andrew runs the push himself in Git Bash / Terminal (give the one
  line); Git Credential Manager (Windows) / Keychain (Mac) remembers it after that.

## 5. Report
Two or three lines: what was saved (files in plain words), the commit's first line, "tests green (N PASS)",
"pushed to GitHub". The other machine picks it up the next time a Claude session starts there.
