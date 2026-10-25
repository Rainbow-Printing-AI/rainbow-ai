#!/usr/bin/env bash
# apply_v1_answers.sh - applies Andrew's marked-up conflict sheet v1 (scan_153, 2026-10-01)
# plus his chat follow-ups (C06: all tiers $0.15; C17: drop all disc items).
# Kept for audit. Run from the PriceBook folder. Do not re-run on live data.
set -euo pipefail
cd "$(dirname "$0")/.."
PB="python3 pricebook.py"
SRC="conflict sheet v1 marked up (scan_153, 2026-10-01)"
CHAT="Andrew, chat 2026-10-01"
BY="Andrew"
export PRICEBOOK_USER="$BY"

# ---- straight answers from the sheet
$PB resolve C01 a=2.50                      --source "$SRC"
$PB resolve C02 a=ok                        --source "$SRC"
$PB resolve C03 opt=1                       --source "$SRC"
$PB resolve C04 a=ok b=ok c=ok d=ok         --source "$SRC" --note "a-c ticked; d from note: non-blueprints use sq ft pricing"
$PB resolve C05 opt=1                       --source "$SRC"
$PB resolve C06 a=0.15 b=0.15               --source "$SRC"
$PB resolve C07 opt=1                       --source "$SRC"
$PB resolve C08 a=ok b=ok c=ok              --source "$SRC"
$PB resolve C09 a=ok b=remove c=remove d=ok --source "$SRC"
$PB resolve C10 opt=1                       --source "$SRC"
$PB resolve C11 opt=1                       --source "$SRC"
$PB resolve C12 opt=1                       --source "$SRC"
$PB resolve C13 a=1.85 b=ok c=ok d=ok       --source "$SRC"
$PB resolve C14 opt=1                       --source "$SRC"
$PB resolve C15 opt=1                       --source "$SRC"
$PB resolve C16 opt=2                       --source "$SRC"
$PB resolve C17 opt=3 "text=Remove. We don't burn CDs anymore" --source "$SRC"
$PB resolve C18 a=ok b=ok c=ok d=ok         --source "$SRC"
$PB resolve C19 a=ok b=ok c=ok d=ok e=ok    --source "$SRC"
$PB resolve C20 a=ok b=ok c=ok d=ok         --source "$SRC"
$PB resolve C21 opt=1                       --source "$SRC"
$PB resolve C22 opt=1                       --source "$SRC"
$PB resolve C23 opt=1                       --source "$SRC"
$PB resolve C24 opt=2                       --source "$SRC"
$PB resolve C25 opt=1                       --source "$SRC"
$PB resolve C26 a=ok                        --source "$SRC"

# ---- C04 note: flat prices are blueprint (plans) prices; non-blueprints use sq ft pricing
for s in 18x24 24x36 30x42 36x48; do
  $PB edit lf-color-$s "item=Large format color - blueprints / plans" "variant=color blueprints / plans, standard size" \
      "keywords=blueprint, blueprints, plans, plan set, construction drawings, architectural, engineering, color plans, large format color" \
      "notes=Flat price for color blueprints/plans (Andrew, C04). Non-blueprint color work is priced by the sq ft." --source "$SRC"
done
$PB edit lf-color-bond-sqft "item=Large format color - posters / graphics (non-blueprint)" "variant=bond, any size, per sq ft" \
    "keywords=large format color, poster, posters, color plot, signage print, rendering, graphics, banner paper, custom size" \
    "notes=All non-blueprint large-format color on bond, any size (Andrew, C04). Blueprints/plans use the flat prices." --source "$SRC"
$PB edit lf-color-photo-sqft "variant=photo paper, custom sizes only" \
    "notes=Listed photo sizes use the Photo Prints list; \$6/sq ft only for sizes not on that list (C10)." --source "$SRC"

# ---- C06 follow-up: all single-sided 8.5x11 B/W tiers are $0.15
$PB set bw-8.5x11-simplex-1-20 0.15 --source "$CHAT" --note "C06 follow-up: all tiers \$0.15"

# ---- C11: trade sheet business-card block retired (not just superseded)
for q in 250 500 1000 addl-1000; do
  for v in 1s-1ink 2s-black-1std 2color; do
    $PB retire bc-trade-$v-$q --source "$SRC" --note "C11: trade-sheet business-card block retired"
  done
done
$PB edit numbering-per-1000 "notes=Numbering machine (C15)." --source "$SRC"
$PB edit numbering-per-page "notes=Numbers printed on the press: copy cost plus \$0.03 per page (C15)." --source "$SRC"

# ---- C16: Mark to re-check 4over signage prices; rows stay PENDING C16
for id in banner-13oz banner-8oz-mesh foam-core coroplast-4mm coroplast-10mm aluminum-sandwich car-magnet; do
  $PB edit $id "notes=Mark to re-check against 4over (C16, 2026-10-01). Artwork/layout extra." --source "$SRC"
done

# ---- C17: we don't burn CDs anymore -> drop all disc items
$PB retire scan-doc-extra-save --source "$CHAT" --note "C17: no more CDs"
$PB retire media-cd-copy       --source "$CHAT" --note "C17: no more CDs"
$PB retire media-dvd-copy      --source "$CHAT" --note "C17: no more discs"
$PB edit scan-doc-first "variant=first page" --source "$CHAT" --note "C17: dropped 'includes 1 CD'"
$PB edit scan-lf-extra-save "variant=multiple saves (each extra file)" --source "$CHAT" --note "C17: kept; not a disc charge"
$PB close C17 --source "$CHAT"

# ---- C24: Reno closed
for id in rainbow-reno-rainbow-reno-phone rainbow-reno-rainbow-reno-fax essendant-essendant-reno-account-account \
          essendant-essendant-reno-account-address spr-spr-reno-account-account; do
  $PB edit-contact $id status=retired --source "$SRC" --note "C24: Reno closed"
done
$PB close C24 --source "$SRC"

# ---- C25: note on the Inland entries (proposal accepted)
for id in inland-business-systems-lucas-sierra-a-xerox-company-inland-business-systems-phone \
          inland-business-systems-lucas-sierra-a-xerox-company-inland-business-systems-phone-2 \
          inland-business-systems-lucas-sierra-a-xerox-company-inland-business-systems-web; do
  $PB edit-contact $id "role=Versant 180 service & supplies" --source "$SRC"
done

# ---- C26a: color duplex = 2x the single-sided price
for spec in "8.5x11 1.38 0.98" "8.5x14 1.78 1.38" "11x17 2.76 1.96"; do
  set -- $spec
  $PB add --id color-$1-duplex-1-25 --family color-$1-duplex --category "Copies - Color" --item "Color copy" \
      --variant "duplex (price per sheet, both sides)" --size $1 --color Color --sides 2 --qty-min 1 --qty-max 25 \
      --unit each --price $2 --keywords "color copies, colour, duplex, double-sided, 2-sided" \
      --source "$SRC" --note "C26: 2x single-sided price"
  $PB add --id color-$1-duplex-26up --family color-$1-duplex --category "Copies - Color" --item "Color copy" \
      --variant "duplex (price per sheet, both sides)" --size $1 --color Color --sides 2 --qty-min 26 \
      --unit each --price $3 --keywords "color copies, colour, duplex, double-sided, 2-sided" \
      --source "$SRC" --note "C26: 2x single-sided price"
done

$PB validate
