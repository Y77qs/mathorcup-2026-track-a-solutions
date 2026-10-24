#!/bin/bash
# Local dev harness for the modeler-q1q2 scripts (mirrors docs/AGENT-BRIEF.md §4).
# usage: run.sh <q1|q2> <script.py> [expdir-suffix]
set -u
ROOT=/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest-v3
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
PACK="$HOME/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/python"
MODE="$1"; SCRIPT="$2"; SUFFIX="${3:-run}"; shift 3 2>/dev/null || shift 2
export MPLCONFIGDIR="$ROOT/state/mplconfig"
export MODELING_PROJECT_DIR="$ROOT"
export MODELING_EXPERIMENT_DIR="$ROOT/state/devrun/${MODE}_${SUFFIX}"
export MODELING_SEED=20261024
export MODELING_DEPENDENCIES="$(cd "$ROOT" && "$PY" - <<'JSON'
import json, os
p = os.getcwd()
keys = [
    "src/target_columns.py", "src/q_common.py", "src/q1_lib.py", "src/q2_lib.py",
    "data/processed/q1_grade_params.json", "data/clean/q2_chem_meta.json",
    "data/clean/q3_thresholds.json", "data/clean/q3_style_protocol.json",
    "data/splits/SPLIT-0001/train.csv",
    "data/raw/imported/a55004fb0390299a-6.csv",
]
print(json.dumps({k: os.path.join(p, k) for k in keys if os.path.exists(os.path.join(p, k))}))
JSON
)"
export PYTHONPATH="$PACK:$ROOT/src"
mkdir -p "$MODELING_EXPERIMENT_DIR"
if [ "$MODE" = "q1" ]; then
  export MODELING_DATA_FILE="$ROOT/data/clean/q1_mapped.csv"
  export MODELING_TRAIN_FILE="$ROOT/data/splits/SPLIT-0002/train.csv"
  export MODELING_TEST_FILE="$ROOT/data/splits/SPLIT-0002/test.csv"
  export MODELING_ASSIGNMENT_FILE="$ROOT/data/splits/SPLIT-0002/assignment.csv"
elif [ "$MODE" = "q1r" ]; then
  export MODELING_DATA_FILE="$ROOT/data/clean/q1_mapped.csv"
  unset MODELING_TRAIN_FILE MODELING_TEST_FILE MODELING_ASSIGNMENT_FILE
else
  export MODELING_DATA_FILE="$ROOT/data/clean/q2_raw.csv"
  unset MODELING_TRAIN_FILE MODELING_TEST_FILE MODELING_ASSIGNMENT_FILE
fi
start=$(date +%s)
cd "$MODELING_EXPERIMENT_DIR"
"$PY" "$ROOT/$SCRIPT" "$@"
status=$?
end=$(date +%s)
echo "exit=$status runtime=$((end-start))s expdir=$MODELING_EXPERIMENT_DIR"
exit $status
