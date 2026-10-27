#!/usr/bin/env python3
"""
repo_sync.py — Rainbow AI: bring this folder up to date with GitHub at the start of a session.

Runs `git pull --ff-only` on the Rainbow repo (the folder above tools/), so every Claude
session on this machine uses the latest skills, tools and CLAUDE.md from GitHub.

It never fixes anything by itself. It pulls only when that is a clean fast-forward, and
prints a loud warning (and does not pull) when:
  * the folder has uncommitted changes (edited or new files git would track)
    -> say "save it to the repo" (the rainbow-save skill), or ask Claude what changed
  * this machine and GitHub both have commits the other doesn't (diverged)
  * the folder is not on branch main, or git/GitHub can't be reached

  repo_sync.py            report in plain text (for a person)
  repo_sync.py --hook     report as JSON for the Claude Code SessionStart hook: the warning
                          is shown to you on screen and also handed to Claude
  repo_sync.py --no-pull  check and report only, change nothing
  --repo DIR              a different repo folder (used by the tests)

Exit code is always 0 in --hook mode (a hook must never block a session); otherwise
0 = up to date / pulled, 1 = warning printed.
"""
import argparse, json, os, subprocess, sys

BRANCH = "main"
LINE = "!" * 70


def git(repo, *args, timeout=30):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", LC_ALL="C")
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                           timeout=timeout, env=env, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 127, "", "git is not installed"
    except subprocess.TimeoutExpired:
        return 124, "", f"git {args[0]} took longer than {timeout} s"
    return r.returncode, r.stdout.rstrip(), r.stderr.strip()   # rstrip: status codes start with a space


def check(repo, pull=True):
    """Return (ok, lines). ok False = something needs Andrew's attention."""
    rc, top, err = git(repo, "rev-parse", "--show-toplevel")
    if rc:
        return False, [f"This folder is not linked to GitHub ({err or 'not a git repo'}).",
                       "Nothing was pulled. Skills and tools here may be out of date."]
    rc, branch, _ = git(repo, "symbolic-ref", "--short", "HEAD")
    if rc or branch != BRANCH:
        return False, [f"The folder is on branch '{branch or 'detached'}', not '{BRANCH}'.",
                       "Nothing was pulled. Ask Claude to switch back to main before working."]

    rc, status, _ = git(repo, "status", "--porcelain", "--untracked-files=all")
    dirty = [l for l in status.splitlines() if l.strip()]

    rc, _, err = git(repo, "fetch", "--quiet", "origin", BRANCH, timeout=45)
    if rc:
        warn = ["Could not reach GitHub, so nothing was pulled (no internet, or the GitHub login "
                "needs renewing).", f"git said: {err.splitlines()[-1] if err else rc}",
                "You are working on this machine's copy, which may be behind."]
        if dirty:
            warn += _dirty_lines(dirty)
        return False, warn

    rc, counts, _ = git(repo, "rev-list", "--left-right", "--count", f"HEAD...origin/{BRANCH}")
    ahead, behind = (int(x) for x in counts.split()) if rc == 0 else (0, 0)

    if ahead and behind:
        return False, [f"This machine and GitHub have BOTH changed: {ahead} local commit(s) not on GitHub, "
                       f"{behind} GitHub commit(s) not here (diverged).",
                       "Nothing was pulled or merged. Ask Claude: \"the Rainbow repo has diverged, "
                       "show me both sides before merging\"."] + (_dirty_lines(dirty) if dirty else [])
    if dirty:
        msg = _dirty_lines(dirty)
        if behind:
            msg.insert(0, f"GitHub has {behind} newer commit(s) that were NOT pulled because of the "
                          "unsaved changes below.")
        return False, msg
    if behind:
        if not pull:
            return False, [f"GitHub has {behind} newer commit(s) (not pulled: --no-pull)."]
        rc, out, err = git(repo, "pull", "--ff-only", "--quiet", "origin", BRANCH, timeout=60)
        if rc:
            return False, ["git pull --ff-only failed; nothing was changed.", err]
        rc, log, _ = git(repo, "log", "--format=  - %s", f"-{min(behind, 10)}")
        return True, [f"Pulled {behind} new commit(s) from GitHub:"] + log.splitlines()
    if ahead:
        return False, [f"{ahead} saved commit(s) on this machine are not on GitHub yet.",
                       "Say \"save it to the repo\" (rainbow-save) to push them."]
    return True, ["Rainbow repo is up to date with GitHub."]


def _dirty_lines(dirty):
    shown = [f"    {l}" for l in dirty[:15]]
    if len(dirty) > 15:
        shown.append(f"    ... and {len(dirty) - 15} more")
    return [f"UNSAVED CHANGES: {len(dirty)} file(s) in the Rainbow folder are changed or new and not "
            "in GitHub yet (M = edited, ?? = new, D = deleted):"] + shown + [
            "Nothing was pulled. If these are wanted, say \"save it to the repo\". "
            "If not, ask Claude to show the changes before anything is thrown away."]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hook", action="store_true", help="JSON output for a Claude Code SessionStart hook")
    ap.add_argument("--no-pull", action="store_true", help="check and report only")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    a = ap.parse_args()

    ok, lines = check(a.repo, pull=not a.no_pull)
    if ok:
        text = "repo_sync: " + "\n".join(lines)
    else:
        text = "\n".join([LINE, "REPO SYNC WARNING (Rainbow)", *lines, LINE])

    if a.hook:
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
        if not ok:
            out["systemMessage"] = text
            out["hookSpecificOutput"]["additionalContext"] = (
                text + "\nTell Andrew about this repo sync warning in your first reply, in plain words, "
                "before doing anything else. Do not commit, stash, reset or discard anything to fix it "
                "unless he asks.")
        print(json.dumps(out))
        return 0
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
