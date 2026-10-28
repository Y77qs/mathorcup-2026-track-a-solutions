#!/usr/bin/env bash
# build_all.sh — one-shot, deterministic rebuild of the v6.2 final paper.
#
#   bash FINAL_SUBMISSION_v6.2/build/build_all.sh
#
# Order matters: the table fragments are generated first, then the paper source
# is produced from the reviewed draft + those fragments, then the inlined table
# bodies are synchronised, and only then is the PDF compiled.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

echo "== 1/6 Q2 table fragments"
"$PYTHON" "$HERE/make_q2_table.py"
echo "== 2/6 Q3 ablation fragment"
"$PYTHON" "$HERE/make_q3_extra_tables.py"
echo "== 3/6 Q3 entity answer tables"
"$PYTHON" "$HERE/make_q3_answer_tables.py"
echo "== 4/6 paper source"
"$PYTHON" "$HERE/make_paper.py"
echo "== 5/6 table sync"
"$PYTHON" "$HERE/sync_tables.py"
echo "== 6/6 PDF"
"$PYTHON" "$HERE/build_final.py" --pdf
echo "== audit"
"$PYTHON" "$HERE/../../.rework/pdf_audit.py" "$HERE/../论文正式版.pdf" --json "$HERE/out/pdf-audit.json" || true
