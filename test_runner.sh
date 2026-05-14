#!/usr/bin/env bash
# Run the pdf2dita pipeline on every PDF in a directory and report pass/fail.
# Usage: ./test_runner.sh <pdfs_dir> [<output_root>]
#
# Each PDF gets its own output subdir under <output_root>/<basename>/.
# Per-PDF log goes to <output_root>/<basename>.log.
# Final summary printed at the end with elapsed time and DITA-OT pass/fail.

set -u

PDFS_DIR=${1:-/Users/olehpytulko/Downloads/pdf2dita-2/test_pdfs}
OUT_ROOT=${2:-/Users/olehpytulko/Downloads/pdf2dita-2/output/batch}
REPO=/Users/olehpytulko/Downloads/pdf2dita-2

mkdir -p "$OUT_ROOT"
SUMMARY="$OUT_ROOT/summary.tsv"
: > "$SUMMARY"

PASS=0
FAIL=0
TOTAL=0
START_ALL=$(date +%s)

shopt -s nullglob
for pdf in "$PDFS_DIR"/*.pdf; do
    TOTAL=$((TOTAL + 1))
    name=$(basename "$pdf" .pdf)
    out_dir="$OUT_ROOT/$name"
    log_file="$OUT_ROOT/$name.log"
    start=$(date +%s)

    echo "=== [$TOTAL] $name ==="
    rm -rf "$out_dir"
    PYTHONUNBUFFERED=1 python3 -u "$REPO/main.py" "$pdf" \
        -o "$out_dir" \
        --provider gemini \
        --model gemini-2.5-pro \
        > "$log_file" 2>&1
    rc=$?
    elapsed=$(($(date +%s) - start))

    dita_ot=$(grep -oE "DITA-OT:[ ]+(PASS|FAIL|N/A)" "$log_file" | head -1 | awk '{print $2}')
    [ -z "$dita_ot" ] && dita_ot="?"
    errors=$(grep -c "^  ✗ " "$log_file" 2>/dev/null || echo 0)
    if [ "$dita_ot" = "PASS" ] && [ "$rc" = "0" ]; then
        PASS=$((PASS + 1))
        status="PASS"
    else
        FAIL=$((FAIL + 1))
        status="FAIL"
    fi
    printf "%s\t%s\t%ds\t%s\trc=%d\terrs=%s\n" "$status" "$name" "$elapsed" "$dita_ot" "$rc" "$errors" | tee -a "$SUMMARY"
done

elapsed_total=$(($(date +%s) - START_ALL))
echo
echo "==================================================="
echo "RESULTS: $PASS/$TOTAL passed, $FAIL failed in ${elapsed_total}s"
echo "Per-file log: $OUT_ROOT/<name>.log"
echo "Summary TSV: $SUMMARY"
echo "==================================================="
