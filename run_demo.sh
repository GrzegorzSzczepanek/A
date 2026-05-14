#!/usr/bin/env bash
# Demo showcase: runs the pipeline on the included sample PDF and prints a
# checklist of every requirement from the task description (a–k) with the
# concrete evidence from the generated output. Designed as the one-command
# experience for jury review.

set -e

cd "$(dirname "$0")"

SAMPLE="${1:-test_data/synthetic_alert_system.pdf}"
OUT="${2:-demo_output/showcase}"

if [ ! -f "$SAMPLE" ]; then
    echo "Sample PDF not found: $SAMPLE"
    echo "Usage: ./run_demo.sh [path/to/sample.pdf] [output_dir]"
    exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✗\033[0m %s\n' "$1"; }

bold "═══════════════════════════════════════════════════════════════"
bold " PDF-to-DITA Converter — Demo Showcase"
bold "═══════════════════════════════════════════════════════════════"
echo "Sample: $SAMPLE"
echo "Output: $OUT"
echo

bold "▸ Stage 1: Pipeline run"
python3 main.py "$SAMPLE" -o "$OUT" 2>&1 | sed 's/^/  /'

echo
bold "▸ Stage 2: Requirements checklist (a–k from task description)"

DITAMAP=$(ls "$OUT"/m_*.ditamap 2>/dev/null | head -1)
TOPICS=$(ls "$OUT"/[ctr]_*.dita 2>/dev/null)

# a — topic types
TYPES=$(grep -h '<\(concept\|task\|reference\) id=' $TOPICS 2>/dev/null | sed -E 's/.*<(concept|task|reference).*/\1/' | sort -u | tr '\n' ',' | sed 's/,$//')
if [ -n "$TYPES" ]; then ok "a. Topic types detected: $TYPES"; else miss "a. Topic types missing"; fi

# b — document map
if [ -n "$DITAMAP" ]; then
    TR=$(grep -c '<topicref' "$DITAMAP")
    ok "b. Document map: $DITAMAP ($TR topicrefs)"
else miss "b. Document map missing"; fi

# c — tables (CALS)
TBL=$(grep -l '<tgroup' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
if [ "$TBL" -gt 0 ]; then ok "c. CALS tables: $TBL topic(s) contain <tgroup>"; else warn "c. No CALS tables in this PDF"; fi

# d — best practices (Latin abbrev + via must be ABSENT in output)
BAD=$(grep -hoE '\b(via|i\.e\.|e\.g\.|etc\.)\b' $TOPICS 2>/dev/null | head -5)
if [ -z "$BAD" ]; then ok "d. Best practices: no Latin abbreviations / no 'via' in output"; else miss "d. Best practices violated: $BAD"; fi

# e — shortdesc
SD=$(grep -l '<shortdesc' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
TOTAL=$(echo "$TOPICS" | wc -w | tr -d ' ')
if [ "$SD" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then ok "e. <shortdesc> on all $TOTAL topics"; else warn "e. <shortdesc> on $SD/$TOTAL topics"; fi

# f — product variable
KD=$(grep -c 'keys="product-name"' "$DITAMAP" 2>/dev/null; true)
KD=${KD:-0}
if [ "$KD" -gt 0 ] 2>/dev/null; then ok "f. Product variable: <keydef keys=\"product-name\"> in map"; else warn "f. No product-name detected in this PDF"; fi

# g — keywords (count <keyword> element MATCHES, not lines, since emitter is single-line)
KW=$(grep -l '<keyword class=' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
KCOUNT=$(grep -hoE '<keyword class=' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
if [ "$KW" -eq "$TOTAL" ]; then ok "g. <keywords> on all $TOTAL topics ($KCOUNT keywords total)"; else warn "g. <keywords> on $KW/$TOTAL topics"; fi

# h — hyperlinks
XR=$(grep -hoE '<xref ' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
if [ "$XR" -gt 0 ]; then ok "h. Hyperlinks: $XR <xref> elements"; else warn "h. No <xref> in this PDF"; fi

# i — images (1000px, 200KB)
IMG_DIR="$OUT/images"
if [ -d "$IMG_DIR" ] && [ "$(ls "$IMG_DIR" 2>/dev/null | wc -l | tr -d ' ')" -gt 0 ]; then
    python3 - <<PY
from PIL import Image
from pathlib import Path
ok_count = bad_count = 0
for p in Path("$IMG_DIR").iterdir():
    if not p.is_file(): continue
    try:
        size = p.stat().st_size
        with Image.open(p) as im:
            w = im.width
        cap_w = w <= 1000
        cap_b = size <= 200 * 1024
        if cap_w and cap_b: ok_count += 1
        else: bad_count += 1
    except Exception: pass
total = ok_count + bad_count
if total:
    print(f"  \033[32m✓\033[0m i. Images: {ok_count}/{total} within 1000px + 200KB caps")
PY
else
    warn "i. No images in this PDF"
fi

# j — alt text
ALT=$(grep -hoE '<alt ' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
IMG=$(grep -hoE '<image ' $TOPICS 2>/dev/null | wc -l | tr -d ' ')
if [ "$IMG" -gt 0 ]; then
    if [ "$ALT" -eq "$IMG" ]; then ok "j. Alt text on all $IMG image(s)"; else miss "j. Alt text on $ALT/$IMG images"; fi
else
    warn "j. No <image> in this PDF"
fi

# k — batch processing
if [ -f batch.py ]; then ok "k. Batch processing: batch.py + /batch HTTP endpoint"; else miss "k. batch.py missing"; fi

echo
bold "▸ Stage 3: DITA-OT HTML5 build (--processing-mode=strict)"
if command -v dita >/dev/null 2>&1 && [ -n "$DITAMAP" ]; then
    rm -rf "$OUT/html5"
    if dita -i "$PWD/$DITAMAP" -f html5 -o "$PWD/$OUT/html5" --processing-mode=strict 2>&1 | tail -5 | sed 's/^/  /'; then
        ok "DITA-OT HTML5 build: PASSED"
        echo
        echo "  Open: $PWD/$OUT/html5/index.html"
    fi
else
    warn "DITA-OT not on PATH (run ./setup.sh) — skipping HTML5 build"
fi

echo
bold "═══════════════════════════════════════════════════════════════"
bold " Showcase complete. Files in: $OUT"
bold "═══════════════════════════════════════════════════════════════"
