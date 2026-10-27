#!/usr/bin/env python3
"""
package_skills.py — Rainbow AI: keep the account's skills (Cowork / claude.ai) matched to the repo.

The repo's .claude/skills/ is the one copy of every Rainbow skill. Claude Code on a clone
reads it directly. Cowork and claude.ai use the skills stored on the account instead; the
"rainbow" plugin (.claude-plugin/ in the repo) is the normal way they get the repo's
skills. This script is the fallback and the safety net:

  package_skills.py                build one upload zip per repo skill (claude.ai → Settings →
                                   Capabilities → Skills → upload, replacing the old one) into
                                   "Claude outputs/skill-uploads-YYYY-MM-DD/" (or --out DIR)
  package_skills.py --check        compare the account's copies, as synced to this machine in
                                   ~/.claude/skills/synced/<bucket>/, with the repo, and name every
                                   rainbow-* skill that is STALE (differs), MISSING (repo only)
                                   or ACCOUNT-ONLY (made in Cowork, not in git yet)
  package_skills.py --import       copy ACCOUNT-ONLY rainbow-* skills into .claude/skills/ so the
                                   rainbow-save skill can push them. Never overwrites a repo skill:
                                   for a STALE one the repo wins; read the diff and decide by hand.

  --skill NAME   only these skills (repeatable); --repo DIR / --synced DIR for other folders (tests)

Line endings are ignored when comparing (CRLF = LF). --check exits 0 when everything matches,
2 when something differs, 1 when the synced folder can't be found. Skills that reach the
account only through the plugin are not in the synced folder, so --check calls them MISSING:
that is expected once the plugin is installed (see docs/repo-sync.md).
"""
import argparse, datetime, os, shutil, sys, zipfile

PREFIX = "rainbow-"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def skill_dirs(root, prefix=PREFIX):
    """{name: path} of every folder in root holding a SKILL.md whose name starts with prefix."""
    if not root or not os.path.isdir(root):
        return {}
    return {n: os.path.join(root, n) for n in sorted(os.listdir(root))
            if n.startswith(prefix) and os.path.isfile(os.path.join(root, n, "SKILL.md"))}


def files_of(d):
    """{relative/posix/path: bytes with CRLF→LF} for every file under d (skips caches and dotfiles)."""
    out = {}
    for base, dirs, names in os.walk(d):
        dirs[:] = [x for x in dirs if x != "__pycache__" and not x.startswith(".")]
        for n in names:
            if n.startswith(".") or n.endswith(".pyc"):
                continue
            p = os.path.join(base, n)
            with open(p, "rb") as f:
                out[os.path.relpath(p, d).replace(os.sep, "/")] = f.read().replace(b"\r\n", b"\n")
    return out


def find_synced(home=None):
    """The account's synced skills folder: newest bucket under ~/.claude/skills/synced/ with a manifest."""
    top = os.path.join(home or os.path.expanduser("~"), ".claude", "skills", "synced")
    if not os.path.isdir(top):
        return None
    buckets = [os.path.join(top, b) for b in os.listdir(top)
               if not b.startswith(".") and os.path.isfile(os.path.join(top, b, "manifest.json"))]
    return max(buckets, key=lambda b: os.path.getmtime(os.path.join(b, "manifest.json"))) if buckets else None


def compare(repo_sk, acct_sk):
    """[(name, status, detail)] status in OK / STALE / MISSING / ACCOUNT-ONLY."""
    rows = []
    for n in sorted(set(repo_sk) | set(acct_sk)):
        if n not in acct_sk:
            rows.append((n, "MISSING", "in the repo, not on the account"))
        elif n not in repo_sk:
            rows.append((n, "ACCOUNT-ONLY", "on the account, not in the repo (--import copies it in)"))
        else:
            r, a = files_of(repo_sk[n]), files_of(acct_sk[n])
            diff = sorted(p for p in set(r) | set(a) if r.get(p) != a.get(p))
            if diff:
                rows.append((n, "STALE", "differs: " + ", ".join(
                    p + ("" if p in r and p in a else " (repo only)" if p in r else " (account only)")
                    for p in diff[:6]) + (f" … +{len(diff) - 6}" if len(diff) > 6 else "")))
            else:
                rows.append((n, "OK", "same as the repo"))
    return rows


def build_zips(repo_sk, out):
    os.makedirs(out, exist_ok=True)
    made = []
    for n, d in repo_sk.items():
        z = os.path.join(out, n + ".zip")
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in sorted(files_of(d)):
                zf.write(os.path.join(d, *rel.split("/")), f"{n}/{rel}")
        made.append(z)
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="compare account copies with the repo")
    g.add_argument("--import", dest="do_import", action="store_true", help="copy account-only skills into the repo")
    ap.add_argument("--out", help="zip folder (default: Claude outputs/skill-uploads-YYYY-MM-DD)")
    ap.add_argument("--skill", action="append", help="limit to this skill (repeatable)")
    ap.add_argument("--repo", default=REPO, help="repo root (default: the folder above tools/)")
    ap.add_argument("--synced", help="account skills folder (default: newest ~/.claude/skills/synced/<bucket>)")
    a = ap.parse_args()

    repo_root = os.path.join(a.repo, ".claude", "skills")
    repo_sk = skill_dirs(repo_root)
    keep = lambda d: {k: v for k, v in d.items() if not a.skill or k in a.skill}

    if not (a.check or a.do_import):
        repo_sk = keep(repo_sk)
        if not repo_sk:
            print("FAIL  no rainbow-* skills found in", repo_root); return 1
        out = a.out or os.path.join(a.repo, "Claude outputs", f"skill-uploads-{datetime.date.today():%Y-%m-%d}")
        for z in build_zips(repo_sk, out):
            print("OK    ", z)
        print(f"{len(repo_sk)} zip(s). Upload each in claude.ai → Settings → Capabilities → Skills, replacing the old one.")
        return 0

    synced = a.synced or find_synced()
    if not synced or not os.path.isdir(synced):
        print("FAIL  can't find the account's synced skills (~/.claude/skills/synced/<bucket>/manifest.json).",
              "Open the Claude desktop app once so it syncs, or pass --synced DIR."); return 1
    acct_sk = keep(skill_dirs(synced))
    rows = compare(keep(repo_sk), acct_sk)

    if a.do_import:
        n_done = 0
        for n, status, _ in rows:
            if status == "ACCOUNT-ONLY":
                dest = os.path.join(repo_root, n)
                shutil.copytree(acct_sk[n], dest, ignore=shutil.ignore_patterns(".*", "__pycache__", "*.pyc"))
                print(f"IMPORTED  {n} -> {dest}"); n_done += 1
            elif status == "STALE":
                print(f"SKIPPED   {n}: already in the repo and different; the repo copy wins. Compare by hand.")
        print(f"{n_done} skill(s) imported." + (" Say \"save it to the repo\" to push them." if n_done else ""))
        return 0

    print("Account skills:", synced)
    for n, status, detail in rows:
        print(f"{status:<13}{n}: {detail}")
    bad = [r for r in rows if r[1] != "OK"]
    if bad:
        print(f">>> {len(bad)} skill(s) not in sync. STALE/MISSING: install or update the rainbow plugin, or upload "
              "the zips from `package_skills.py`. ACCOUNT-ONLY: `package_skills.py --import`, then save to the repo.")
        return 2
    print("All rainbow-* skills on the account match the repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
