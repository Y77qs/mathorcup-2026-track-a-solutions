# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""prepare_q1mapped.py — DATA-0002: the Q1 evaluation table with train-fitted 0-6 reference grades.

The 0-6 scale is NOT identifiable from the attachments (3.xlsx is an empty scorecard template and 4.csv is a
standardized continuous label). The blueprint therefore defines an explicitly RELATIVE grade: the midpoint
empirical CDF of the TRAIN rows maps a standardized intensity to a percentile a, the continuous grade is 6a, and
the delivered discrete grade is round-half-up clipped to 0..6. This script fits that reference on the registered
SPLIT-0001 train rows only and stores

  data/clean/q1_mapped.csv        q2_raw + 50 g6__<target> reference-grade columns (derived, never features)
  data/processed/q1_grade_params.json   per-target sorted train labels, endpoints and the linear sensitivity map
  data/processed/fields_q1mapped.json   complete field list (each column exactly once)

Usage: prepare_q1mapped.py --split SPLIT-0001
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
CLEAN = PROJECT / "data" / "clean"
PROCESSED = PROJECT / "data" / "processed"


def field_records(frame: pd.DataFrame, target_cols: list, chem_cols: list) -> list:
    meta = {"row": ("integer", None, "0-based position in 1.csv/4.csv (row-aligned); the holdout assignment uses this id."),
            "beer": ("integer", None, "1.csv/4.csv beer label (permutation of 1..250); join key."),
            "beer_id": ("string", None, "1.csv EAN-like code; the 4.csv/7.csv copies are truncated, so it is not a join key."),
            "tasting_category_fine": ("string", None, "tasting_category_fine, 22 styles; stratifier and Q3 conditioning label.")}
    records = []
    for column in frame.columns:
        if column in meta:
            kind, unit, description = meta[column]
            records.append({"name": column, "type": kind, "unit": unit, "description": description})
        elif column in chem_cols:
            raw = column[len("chem__"):]
            records.append({"name": column, "type": "number", "unit": "stored chemistry value",
                            "description": "1.csv column %r, value unchanged from the raw attachment (missing cells stay blank; Q1 imputes inside the training fold)." % raw})
        elif column.startswith("g6__"):
            records.append({"name": column, "type": "number", "unit": "grade 0-6",
                            "description": "Derived continuous 0-6 reference grade of observed label %r under the SPLIT-0001 TRAIN midpoint CDF; reporting/sensitivity only, never a feature." % column[4:]})
        elif column in target_cols:
            records.append({"name": column, "type": "number", "unit": "standardized sensory label",
                            "description": "4.csv standardized sensory target %r (continuous, mean 0; NOT an original 0-6 score)." % column})
        else:
            raise RuntimeError("unclassified column: %s" % column)
    return records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="SPLIT-0001")
    args = parser.parse_args(argv)
    split_dir = PROJECT / "data" / "splits" / args.split
    assignment_path = split_dir / "assignment.csv"
    if not assignment_path.exists():
        raise SystemExit("the split assignment does not exist yet: %s" % assignment_path)
    assignment = pd.read_csv(assignment_path)
    train_mask = (assignment["split"] == "train").to_numpy()
    if train_mask.sum() != 200:
        raise RuntimeError("expected 200 train rows in %s, got %d" % (args.split, int(train_mask.sum())))

    base = pd.read_csv(CLEAN / "q2_raw.csv")
    target_cols = [c for c in base.columns if c in set(pd.read_csv(PROJECT / "data" / "raw" / "imported" / "43a7b38682ed81ce-4.csv", nrows=1).columns)]
    target_cols = [c for c in target_cols if c not in ("beer", "beer_id", "tasting_category_fine")]
    chem_cols = [c for c in base.columns if c.startswith("chem__")]
    assert len(target_cols) == 50 and len(chem_cols) == 231

    params = {"splitId": args.split, "nTrain": int(train_mask.sum()), "nTotal": int(len(base)),
              "rule": "a = midrank empirical CDF of the TRAIN labels; g_cont = 6a; g = clip(floor(6a+0.5),0,6)",
              "targets": {}}
    grades = {}
    for column in target_cols:
        values = base[column].to_numpy(dtype=float)
        assert np.isfinite(values).all(), column
        train_values = np.sort(values[train_mask])
        # midpoint empirical CDF evaluated on every row (vectorised over the sorted train grid)
        below = np.searchsorted(train_values, values, side="left")
        equal = np.searchsorted(train_values, values, side="right") - below
        a = (below + 0.5 * equal) / float(train_values.size)
        continuous = 6.0 * a
        grades["g6__" + column] = continuous
        q05 = float(np.quantile(train_values, 0.05))
        q95 = float(np.quantile(train_values, 0.95))
        if q95 - q05 < 1e-9:
            q05, q95 = float(train_values.min()), float(train_values.max() + 1e-9)
        params["targets"][column] = {
            "trainValues": [float(v) for v in train_values],
            "nTrain": int(train_values.size),
            "min": float(train_values.min()), "max": float(train_values.max()),
            "linearReferenceLow": q05, "linearReferenceHigh": q95,
            "linearSlope": float(6.0 / (q95 - q05)), "linearIntercept": float(-6.0 * q05 / (q95 - q05)),
        }

    mapped = pd.concat([base, pd.DataFrame(grades)], axis=1)
    mapped_path = CLEAN / "q1_mapped.csv"
    mapped.to_csv(mapped_path, index=False, lineterminator="\n")
    (PROCESSED / "q1_grade_params.json").write_text(json.dumps(params, ensure_ascii=False) + "\n", encoding="utf-8")

    fields = field_records(mapped, target_cols, chem_cols)
    assert len(fields) == len(mapped.columns)
    assert len({r["name"] for r in fields}) == len(mapped.columns)
    (PROCESSED / "fields_q1mapped.json").write_text(json.dumps(fields, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # grade distribution summary (a reference, not a result)
    summary = {}
    for column in target_cols:
        discrete = np.clip(np.floor(grades["g6__" + column] + 0.5), 0, 6).astype(int)
        counts = np.bincount(discrete, minlength=7)
        summary[column] = {"meanGrade": float(np.mean(discrete)), "gradeCounts": counts.tolist()}
    (PROCESSED / "q1_grade_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "rows": int(len(mapped)), "columns": int(mapped.shape[1]),
                      "targets": len(target_cols), "chem": len(chem_cols), "trainRows": int(train_mask.sum()),
                      "g6Mean": float(np.mean([np.mean(v) for v in grades.values()]))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
