#!/bin/bash
# Rainbow tools — one-time Mac setup.
# Installs Python 3.12 + Poppler (pdftoppm) + every library the scripts use,
# into ~/.rainbow (your user account only; no admin password, system Python untouched).
# Safe to re-run.
set -e
R="$HOME/.rainbow"
ENV="$R/env"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
export MAMBA_ROOT_PREFIX="$R/mamba"
mkdir -p "$R"

echo "== 1/4  Getting micromamba (package installer)"
if [ ! -x "$R/bin/micromamba" ]; then
  cd "$R"
  curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xj bin/micromamba
fi

echo "== 2/4  Python 3.12 + Poppler"
if [ ! -x "$ENV/bin/python" ]; then
  "$R/bin/micromamba" create -y -p "$ENV" -c conda-forge python=3.12 poppler
fi

echo "== 3/4  Python libraries"
"$ENV/bin/python" -m pip install --quiet --upgrade pip
"$ENV/bin/python" -m pip install --quiet numpy pillow pikepdf pypdf reportlab openpyxl \
  pdfplumber fonttools img2pdf pillow-heif uharfbuzz potracer

echo "== 4/4  Testing"
export PATH="$ENV/bin:$PATH"
fail=0
pdftoppm -v >/dev/null 2>&1 && echo "  ok   pdftoppm" || { echo "  FAIL pdftoppm"; fail=1; }
for s in impose verify_print pdfinspect photo_prep photopage sheetfit booklet labels textlabels mergelabels crushcheck passport build_banner fetch_links collect_downloads; do
  if "$ENV/bin/python" "$TOOLS/$s.py" --help >/dev/null 2>&1; then echo "  ok   $s.py"; else echo "  FAIL $s.py"; fail=1; fi
done
T=$(mktemp -d)
if "$ENV/bin/python" "$TOOLS/impose.py" "$TOOLS/tests/t_5x7.pdf" --trim 5x7 --nup 2 --sheet letter --out "$T/t.pdf" >"$T/impose.log" 2>&1 \
   && "$ENV/bin/python" "$TOOLS/verify_print.py" "$T/t.pdf" >"$T/verify.log" 2>&1; then
  echo "  ok   real job: 5x7 2-up on letter, imposed + verified"
else
  echo "  FAIL real job test:"; tail -15 "$T/impose.log" "$T/verify.log" 2>/dev/null; fail=1
fi

echo
if [ $fail = 0 ]; then
  echo "ALL GOOD. Run any script with:  ~/Downloads/Rainbow/tools/rbpy tools/impose.py ..."
else
  echo "Something failed — copy everything above and paste it to Claude."
fi
