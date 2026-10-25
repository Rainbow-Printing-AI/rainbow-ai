#!/usr/bin/env bash
# change_2026-10-01_copies.sh - Andrew, chat 2026-10-01:
#  * no account pricing any more (account customers pay full price)
#  * copies are charged per side (total page count); no duplex price, no B/W quantity breaks
#    B/W: 8.5x11 $0.15, 8.5x14 $0.20, 11x17 $0.30 per side
#    Color: 8.5x11 $0.79 (1-20 sides) / $0.59 (21+), 8.5x14 $0.99 / $0.79, 11x17 $1.38 / $1.18
#    ("<20 / >20 sides": 20 sides taken at the higher rate)
# Kept for audit. Run from the PriceBook folder. Do not re-run on live data.
set -euo pipefail
cd "$(dirname "$0")/.."
PB="python3 pricebook.py"
SRC="Andrew, chat 2026-10-01"
export PRICEBOOK_USER="Andrew"

# ---- account pricing gone
for s in 18x24 24x36 30x42 36x48; do
  $PB retire lf-bw-$s-account --source "$SRC" --note "No account pricing; account customers pay full price"
  $PB edit lf-bw-$s-walkin "variant=standard (all customers)" --source "$SRC" --note "account discount removed"
done

# ---- old B/W tiered single/duplex prices -> retired
for s in 8.5x11 8.5x14 11x17; do
  for t in 1-20 21-99 100up; do
    $PB retire bw-$s-simplex-$t --source "$SRC" --note "Replaced by per-side pricing"
    $PB retire bw-$s-duplex-$t  --source "$SRC" --note "Replaced by per-side pricing; no duplex price"
  done
  $PB retire color-$s-1-25        --source "$SRC" --note "Replaced by per-side pricing"
  $PB retire color-$s-26up        --source "$SRC" --note "Replaced by per-side pricing"
  $PB retire color-$s-duplex-1-25 --source "$SRC" --note "No duplex price; charged per side"
  $PB retire color-$s-duplex-26up --source "$SRC" --note "No duplex price; charged per side"
done

KW="per side, per page, page count, single-sided, double-sided, duplex, 2-sided, front and back, copies, copy, prints, print"
VAR="per side (double-sided = 2 sides)"

# ---- B/W per side, no quantity breaks
for spec in "8.5x11 0.15" "8.5x14 0.20" "11x17 0.30"; do
  set -- $spec
  $PB add --id bw-$1-side --family bw-$1-side --category "Copies - B/W" --item "B/W copy / print" \
      --variant "$VAR" --size $1 --color B/W --unit side --price $2 \
      --keywords "black and white, b&w, bw, $KW" --source "$SRC" --note "Charged by total page count"
done

# ---- Color per side, 1-20 sides / 21+ sides
for spec in "8.5x11 0.79 0.59" "8.5x14 0.99 0.79" "11x17 1.38 1.18"; do
  set -- $spec
  $PB add --id color-$1-side-1-20 --family color-$1-side --category "Copies - Color" --item "Color copy / print" \
      --variant "$VAR" --size $1 --color Color --unit side --qty-min 1 --qty-max 20 --price $2 \
      --keywords "color, colour, Versant, $KW" --source "$SRC" --note "Up to 20 sides (Andrew: '<20 sides')"
  $PB add --id color-$1-side-21up --family color-$1-side --category "Copies - Color" --item "Color copy / print" \
      --variant "$VAR" --size $1 --color Color --unit side --qty-min 21 --price $3 \
      --keywords "color, colour, Versant, $KW" --source "$SRC" --note "21 sides and up (Andrew: '>20 sides')"
done

$PB validate
