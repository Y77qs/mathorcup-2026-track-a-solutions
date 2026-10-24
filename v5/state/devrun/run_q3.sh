#!/bin/bash
# Local harness for the Q3 scripts (mirrors docs/AGENT-BRIEF.md §4; Q3 has no split).
# usage: state/devrun/run_q3.sh src/q3_generate.py state/devrun/q3a
set -euo pipefail
cd "$(dirname "$0")/../.."
PROJ=$PWD
PY=/Users/baozhashizitou/Documents/Codex/2026-10-23/qing/work/reference-quality-env/bin/python
PACK=~/.dsh/profiles/desktop/node_modules/dsh-vibe-math/vibe-math-vmu/packs/modeling-contest/python
SCRIPT=${1:-src/q3_generate.py}
OUT=${2:-state/devrun/q3}
export MPLCONFIGDIR=$PROJ/state/mplconfig
export MODELING_PROJECT_DIR=$PROJ
export MODELING_EXPERIMENT_DIR=$PROJ/$OUT
export MODELING_DATA_FILE=$PROJ/data/clean/q3.csv
export MODELING_SEED=${MODELING_SEED:-20261024}
export MODELING_DEPENDENCIES="$(python3 - <<'JSON'
import json, os
p = os.getcwd()
keys = ["src/target_columns.py", "src/q_common.py", "src/q3_lib.py",
        "data/clean/q3_thresholds.json", "data/clean/q3_style_protocol.json",
        "data/processed/q1_grade_params.json"]
print(json.dumps({k: os.path.join(p, k) for k in keys}))
JSON
)"
export PYTHONPATH=$PACK:$PROJ/src
mkdir -p "$MODELING_EXPERIMENT_DIR"
"$PY" "$SCRIPT" "${@:3}"
ls -la "$MODELING_EXPERIMENT_DIR"
