#!/bin/bash
# Smoke tests for Rainbow/tools. Run from the tools folder: bash tests/run_tests.sh
set -e
cd "$(dirname "$0")/.."
T=tests/out; mkdir -p "$T"   # --out overwrites; no rm (connected folder)
# Python: python3 on Mac/Linux and in the Cowork VM; python or the py launcher on Windows (Git Bash).
export PYTHONUTF8=1   # Windows: UTF-8 for files and pipes (no-op on Mac/Linux)
PY=; for c in python3 python py; do "$c" -c "import sys; sys.exit(sys.version_info < (3, 10))" >/dev/null 2>&1 && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "FAIL  no Python 3.10+ found (python3 / python / py)"; exit 1; }
py() { "$PY" -W ignore "$@"; }
py impose.py tests/t_5x7.pdf --out "$T/1up.pdf" >/dev/null
py impose.py tests/t_5x7.pdf --bleed 0.1 --marks --out "$T/1up_bleed_marks.pdf" >/dev/null
py impose.py tests/t_canva_offset.pdf --bleed 0.1 --marks --out "$T/canva_offset_bleed.pdf" >/dev/null 2>&1   # off-origin box: mirrored bleed must not leave a trim hairline
py impose.py tests/t_bleedpage.pdf --trim 5x7 --nup 2 --sheet letter --out "$T/bleedpage_clipped_2up.pdf" >/dev/null 2>&1
py impose.py tests/t_5x7.pdf --duplex --nup 2 --sheet letter --out "$T/2up_duplex.pdf" >/dev/null
py impose.py tests/bc_front.png --back tests/bc_back.png --trim 3.5x2 --nup 8 --sheet letter --out "$T/bc_8up.pdf" >/dev/null
py impose.py tests/t_withbleed2.pdf --trim 5x7 --nup 2 --sheet letter --out "$T/withbleed_2up.pdf" >/dev/null
py impose.py tests/t_rot90.pdf --nup 4 --sheet 12x18 --out "$T/rot_4up.pdf" >/dev/null
py impose.py tests/t_qr_edge.png --trim 3.5x2 --bleed 0.1 --marks --out "$T/qr_edge_auto.pdf" | grep -q "edge-extended on bottom/right" || { echo "FAIL  auto bleed did not edge-extend the QR sides"; exit 1; }
py impose.py tests/t_photo_edge.jpg --trim 3.5x2 --bleed 0.1 --marks --out "$T/photo_edge_auto.pdf" | grep -q "bleed mirrored, 300" || { echo "FAIL  auto bleed edge-extended a photo"; exit 1; }
py impose.py tests/t_crush.pdf --nup 2 --sheet letter --out "$T/crush_2up.pdf" | grep -q "were lifted" || { echo "FAIL  impose did not lift crush colors"; exit 1; }
py labels.py tests/bc_front.png --grid avery22877 --art-size 1.6 --out "$T/round_12up.pdf" >/dev/null
py sheetfit.py tests/t_5x7.pdf --sheet letter --out "$T/sheetfit_letter.pdf" >/dev/null
py sheetfit.py tests/t_5x7.pdf --sheet letter --landscape --match-sheet --out "$T/sheetfit_match.pdf" >/dev/null
py sheetfit.py tests/t_rot90.pdf --sheet letter --landscape --rotate "1:90" --out "$T/sheetfit_rot.pdf" >/dev/null
py textlabels.py --grid avery5167 --text "A side" --text "B side" --out "$T/text_5167.pdf" >/dev/null
py photopage.py tests/bc_front.png --page 5x7 --out "$T/../photopage_tmp.pdf" >/dev/null
py impose.py "$T/../photopage_tmp.pdf" --nup 2 --sheet letter --marks --out "$T/photopage_2up_marks.pdf" >/dev/null
py booklet.py tests/t_deck6.pdf --binding top --fit --blanks end --out "$T/booklet_top_long.pdf" >/dev/null
py booklet.py tests/t_deck6.pdf --binding side --fit --blanks after-cover --flip short --out "$T/booklet_side_short.pdf" >/dev/null
py booklet.py tests/t_deck6.pdf --binding top --fit --order "1,3,2,b,6" --blanks end --out "$T/booklet_order.pdf" >/dev/null
py fitpage.py tests/t_flyer_bleed.pdf --page 4.25x5.5 --margin 0.125 --out "$T/../handbill_fit_tmp.pdf" | grep -q "margins L 0.1250  R 0.1250  B 0.1250  T 0.1250" || { echo "FAIL  fitpage handbill margins not an even 1/8 in"; exit 1; }
py impose.py "$T/../handbill_fit_tmp.pdf" --nup 4 --sheet letter --gutter 0 --out "$T/handbill_4.25x5.5_4up_letter.pdf" >/dev/null
"$PY" -W ignore -c "from PIL import Image,ImageDraw;im=Image.new('RGB',(1200,1600),(235,232,225));d=ImageDraw.Draw(im);d.ellipse((400,300,800,900),fill=(200,150,120));im.save('tests/passport_synth.jpg',quality=92)"
py passport.py tests/passport_synth.jpg --crown 300 --chin 900 --cx 600 --eyes 560 --out-dir "$T" | tail -1 | grep -q "PASSPORT  PASS" || { echo "FAIL  passport.py synthetic head"; exit 1; }
fail=0
for f in "$T"/*.pdf; do
  if py verify_print.py "$f" | tail -1 | grep -q PASS; then echo "PASS  $(basename "$f")"; else echo "FAIL  $(basename "$f")"; fail=1; fi
done
py verify_print.py tests/badges_ok.pdf --grid avery8395 | tail -1 | grep -q PASS && echo "PASS  badges_ok (die-cut)" || { echo "FAIL  badges_ok"; fail=1; }
py verify_print.py tests/badges_bad.pdf --grid avery8395 | tail -1 | grep -q FAIL && echo "PASS  badges_bad correctly rejected" || { echo "FAIL  badges_bad not rejected"; fail=1; }
py verify_print.py "$T/round_12up.pdf" --grid avery22877 | tail -1 | grep -q PASS && echo "PASS  labels round (die-cut)" || { echo "FAIL  labels round"; fail=1; }
py impose.py tests/t_crush.pdf --no-crush-fix --out "$T/../crush_unfixed_tmp.pdf" >/dev/null
py verify_print.py "$T/../crush_unfixed_tmp.pdf" | tail -1 | grep -q FAIL && echo "PASS  crush colors rejected when unfixed" || { echo "FAIL  unfixed crush file not rejected"; fail=1; }
rc=0; py crushcheck.py tests/t_crush.pdf >/dev/null || rc=$?; [ "$rc" -eq 2 ] && echo "PASS  crushcheck finds crush colors" || { echo "FAIL  crushcheck missed crush colors"; fail=1; }
py crushcheck.py tests/t_5x7.pdf >/dev/null && echo "PASS  crushcheck leaves a clean file alone" || { echo "FAIL  crushcheck false positive on t_5x7"; fail=1; }
py sheetfit.py tests/t_5x7.pdf --sheet 4x6 --out "$T/../sheetfit_toobig_tmp.pdf" >/dev/null 2>&1 && { echo "FAIL  sheetfit scaled/placed an oversize page"; fail=1; } || echo "PASS  sheetfit refuses a page larger than the sheet"
py verify_print.py "$T/text_5167.pdf" --grid avery5167 | tail -1 | grep -q PASS && echo "PASS  textlabels (die-cut)" || { echo "FAIL  textlabels"; fail=1; }
py verify_print.py "$T/booklet_order.pdf" --source tests/t_deck6.pdf | grep -q "fold check.*all 8 pages read in order and upright (4 blank" && echo "PASS  booklet --order (reorder, drop, blank) fold check" || { echo "FAIL  booklet --order"; fail=1; }
mkdir -p "$T/dl_src"; printf '%%PDF-1.4 t' > "$T/dl_src/dl_ok (1).pdf"; printf '<!DOCTYPE html><html>' > "$T/dl_src/dl_bad.pdf"
rc=0; py collect_downloads.py --src "$T/dl_src" --to "$PWD/$T/dl_dest" --timeout 1 dl_ok.pdf dl_bad.pdf >/dev/null || rc=$?
[ "$rc" -eq 1 ] && ls "$T/dl_dest" | grep -q "^dl_ok" && [ -f "$T/dl_src/dl_bad.pdf" ] && echo "PASS  collect_downloads moves real files, rejects HTML" || { echo "FAIL  collect_downloads"; fail=1; }
for b in booklet_top_long booklet_side_short; do
  py verify_print.py "$T/$b.pdf" --source tests/t_deck6.pdf | grep -q "fold check.*all 8 pages read in order and upright" && echo "PASS  $b fold check" || { echo "FAIL  $b fold check"; fail=1; }
done
py booklet.py tests/t_deck6.pdf --binding top --fit >/dev/null 2>&1 && { echo "FAIL  booklet added blanks without being told where"; fail=1; } || echo "PASS  booklet stops when blanks are needed"
py fitpage.py tests/t_flyer_nobleed.pdf --page 4.25x5.5 --margin 0.125 --out "$T/../handbill_nobleed_tmp.pdf" >/dev/null 2>&1 && { echo "FAIL  fitpage cropped or faked an even margin on a no-bleed flyer"; fail=1; } || echo "PASS  fitpage stops when the bleed can't keep the margin even"
py booklet.py tests/t_deck6.pdf --binding top --fit --blanks end --flip short --out "$T/../booklet_lie_tmp.pdf" >/dev/null
"$PY" -W ignore -c "import pikepdf,json,sys;p=pikepdf.open(sys.argv[1],allow_overwriting_input=True);l=json.loads(str(p.docinfo['/RainbowLayout']));l['flip']='long';p.docinfo['/RainbowLayout']=json.dumps(l);p.save(sys.argv[1])" "$T/../booklet_lie_tmp.pdf"
py verify_print.py "$T/../booklet_lie_tmp.pdf" --source tests/t_deck6.pdf | grep -q "fold check.*wrong" && echo "PASS  fold check rejects a booklet printed with the wrong flip" || { echo "FAIL  fold check missed a wrong-flip booklet"; fail=1; }
rec() { "$PY" -W ignore -c "import pikepdf,json,sys;p=pikepdf.open(sys.argv[1]);l=json.loads(str(p.docinfo['/RainbowLayout']));b=p.pages[0].mediabox;print(l['bleed_in'],l['mark_in'],round(float(b[2])/72,3),round(float(b[3])/72,3))" "$1" | tr -d '\r'; }
"$PY" -W ignore -c "import pikepdf,json,sys;p=pikepdf.open(sys.argv[1]);l=json.loads(str(p.docinfo['/RainbowLayout']));sys.exit(0 if all(s['pieces'][0]['size_in']==[7.0,5.0] for s in l['sheets']) else 1)" "$T/sheetfit_match.pdf" && echo "PASS  sheetfit --match-sheet turns portrait pages landscape" || { echo "FAIL  sheetfit --match-sheet"; fail=1; }
[ "$(rec "$T/1up.pdf")" = "0.0 0.0 5.0 7.0" ] && echo "PASS  defaults: no bleed, no marks, sheet = trim" || { echo "FAIL  defaults not no-bleed/no-marks: $(rec "$T/1up.pdf")"; fail=1; }
py impose.py tests/t_qr_edge.png --trim 3.5x2 --bleed 0.1 --marks --bleed-mode reflect --out "$T/../qr_reflect_tmp.pdf" >/dev/null
py verify_print.py "$T/../qr_reflect_tmp.pdf" | grep -q "FAIL  hard edge copied into generated bleed" && echo "PASS  verify rejects a QR box mirrored into the bleed" || { echo "FAIL  verify missed a mirrored QR box"; fail=1; }
py verify_print.py "$T/canva_offset_bleed.pdf" | grep -q "OK    trim/bleed joins" && echo "PASS  mirrored bleed joins the art with no hairline (Canva off-origin box)" || { echo "FAIL  trim hairline seam on off-origin page"; fail=1; }
[ "$(rec "$T/1up_bleed_marks.pdf")" = "0.1 0.125 5.45 7.45" ] && echo "PASS  --bleed 0.1 --marks still available on request" || { echo "FAIL  opt-in bleed/marks: $(rec "$T/1up_bleed_marks.pdf")"; fail=1; }
py pdfinspect.py tests/t_withbleed2.pdf | grep -q "TrimBox 5x7" && echo "PASS  pdfinspect" || { echo "FAIL  pdfinspect"; fail=1; }
py passport.py tests/passport_synth.jpg --crown 300 --chin 900 --cx 1150 --out-dir "$T/../" >/dev/null 2>&1 && { echo "FAIL  passport accepted an off-centre face"; fail=1; } || echo "PASS  passport rejects an off-centre face"
[ "$(py passport.py tests/passport_synth.jpg --crown 300 --chin 900 --cx 600 --eyes 560 --out-dir "$T" | grep -c 'OK    copy 1: placed 2.00000 x 2.00000')" = 1 ] && echo "PASS  passport 2x2 placed exactly" || { echo "FAIL  passport placed size"; fail=1; }
printf 'Company,RepName,Address1,Address2,City,State,Zip\nAcme Long Name Holdings - Regional Office of Northern Nevada,Pat Q,PO Box 1,pat@x.com,Reno,Nevada,895\nBeta,Lee,10 Main St,#2,Truckee,CA,96161\nGamma,,,,Truckee,CA,\n' > "$T/../merge_t.csv"
py mergelabels.py "$T/../merge_t.csv" --grid avery5160 --out "$T/merge_5160.pdf" > "$T/../merge_t.log"
grep -q "SKIPPED (1)" "$T/../merge_t.log" && grep -q "Reno, NV 00895" "$T/merge_5160_merge.csv" && grep -q "10 Main St #2" "$T/merge_5160_merge.csv" && ! grep -q "pat@x.com" "$T/merge_5160_merge.csv" && echo "PASS  mergelabels cleanup/skip" || { echo "FAIL  mergelabels cleanup/skip"; fail=1; }
py verify_print.py "$T/merge_5160.pdf" --grid avery5160 | tail -1 | grep -q PASS && echo "PASS  mergelabels (die-cut)" || { echo "FAIL  mergelabels die-cut"; fail=1; }
# --- repo sync tools (step 0.8): throwaway skill folders and git repos in a temp dir outside the Rainbow folder ---
S=$(mktemp -d)
mkdir -p "$S/repo/.claude/skills/rainbow-a" "$S/repo/.claude/skills/rainbow-b" "$S/repo/.claude/skills/rainbow-c" "$S/acct/rainbow-a" "$S/acct/rainbow-b" "$S/acct/rainbow-d/scripts" "$S/acct/other-skill"
printf 'a\nsame\n' > "$S/repo/.claude/skills/rainbow-a/SKILL.md"; printf 'a\r\nsame\r\n' > "$S/acct/rainbow-a/SKILL.md"
printf 'b new\n' > "$S/repo/.claude/skills/rainbow-b/SKILL.md"; printf 'b old\n' > "$S/acct/rainbow-b/SKILL.md"
printf 'c\n' > "$S/repo/.claude/skills/rainbow-c/SKILL.md"; printf 'd\n' > "$S/acct/rainbow-d/SKILL.md"; printf 'x\n' > "$S/acct/rainbow-d/scripts/x.py"; printf 'o\n' > "$S/acct/other-skill/SKILL.md"
rc=0; py package_skills.py --check --repo "$S/repo" --synced "$S/acct" > "$S/check.txt" || rc=$?
[ "$rc" -eq 2 ] && grep -q "^OK *rainbow-a" "$S/check.txt" && grep -q "^STALE *rainbow-b: differs: SKILL.md" "$S/check.txt" && grep -q "^MISSING *rainbow-c" "$S/check.txt" && grep -q "^ACCOUNT-ONLY *rainbow-d" "$S/check.txt" && ! grep -q other-skill "$S/check.txt" && echo "PASS  package_skills --check names stale/missing/account-only (CRLF ignored)" || { echo "FAIL  package_skills --check"; cat "$S/check.txt"; fail=1; }
py package_skills.py --import --repo "$S/repo" --synced "$S/acct" >/dev/null
[ -f "$S/repo/.claude/skills/rainbow-d/scripts/x.py" ] && grep -q "b new" "$S/repo/.claude/skills/rainbow-b/SKILL.md" && echo "PASS  package_skills --import copies account-only, never overwrites the repo" || { echo "FAIL  package_skills --import"; fail=1; }
py package_skills.py --repo "$S/repo" --out "$S/zips" >/dev/null
"$PY" -c "import zipfile,sys;n=zipfile.ZipFile(sys.argv[1]).namelist();sys.exit(0 if sorted(n)==['rainbow-d/SKILL.md','rainbow-d/scripts/x.py'] else 1)" "$S/zips/rainbow-d.zip" && [ "$(ls "$S/zips" | wc -l)" -eq 4 ] && echo "PASS  package_skills builds one upload zip per skill" || { echo "FAIL  package_skills zips"; fail=1; }
if command -v git >/dev/null 2>&1; then
  G() { git -c user.name=t -c user.email=t@t -c init.defaultBranch=main -c commit.gpgsign=false "$@" >/dev/null 2>&1; }
  G init --bare "$S/origin.git"; G clone "$S/origin.git" "$S/a"; printf 'one\n' > "$S/a/f.txt"; G -C "$S/a" add f.txt; G -C "$S/a" commit -m one; G -C "$S/a" push origin main; G clone "$S/origin.git" "$S/b"
  printf 'two\n' >> "$S/a/f.txt"; G -C "$S/a" commit -am two; G -C "$S/a" push origin main
  py repo_sync.py --repo "$S/b" | grep -q "Pulled 1 new commit" && grep -q two "$S/b/f.txt" && echo "PASS  repo_sync fast-forwards a clean clone" || { echo "FAIL  repo_sync pull"; fail=1; }
  printf 'three\n' >> "$S/a/f.txt"; G -C "$S/a" commit -am three; G -C "$S/a" push origin main; printf 'edit\n' >> "$S/b/f.txt"; printf 'n\n' > "$S/b/new.txt"
  rc=0; py repo_sync.py --repo "$S/b" > "$S/sync.txt" || rc=$?
  [ "$rc" -eq 1 ] && grep -q "REPO SYNC WARNING" "$S/sync.txt" && grep -q "UNSAVED CHANGES: 2 file" "$S/sync.txt" && grep -q "^     M f.txt" "$S/sync.txt" && grep -q "1 newer commit(s) that were NOT pulled" "$S/sync.txt" && ! grep -q three "$S/b/f.txt" && grep -q edit "$S/b/f.txt" && echo "PASS  repo_sync warns on a dirty tree and changes nothing" || { echo "FAIL  repo_sync dirty tree"; cat "$S/sync.txt"; fail=1; }
  py repo_sync.py --repo "$S/b" --hook | "$PY" -c "import json,sys;d=json.load(sys.stdin);sys.exit(0 if 'UNSAVED' in d['systemMessage'] and d['hookSpecificOutput']['hookEventName']=='SessionStart' else 1)" && echo "PASS  repo_sync --hook shows the warning (exit 0)" || { echo "FAIL  repo_sync --hook"; fail=1; }
  G -C "$S/b" commit -am local; rm "$S/b/new.txt"
  rc=0; py repo_sync.py --repo "$S/b" > "$S/sync.txt" || rc=$?
  [ "$rc" -eq 1 ] && grep -q "diverged" "$S/sync.txt" && echo "PASS  repo_sync warns when diverged, no merge" || { echo "FAIL  repo_sync diverged"; cat "$S/sync.txt"; fail=1; }
else
  echo "SKIP  repo_sync tests (git not installed here)"
fi
rm -rf "$S"
exit $fail
