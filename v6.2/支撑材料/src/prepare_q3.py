# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""prepare_q3.py — DATA-0003: the style-conditional view used by question 3.

The table keeps the same 250 row-aligned beers, the 231 stored chemistry columns, the fine style label and the 50
standardized sensory labels. The sensory labels are EVALUATION-ONLY reference: the generator is fit on the
chemistry columns and the style label, and 4.csv never enters the likelihood. The style-holdout protocol (repeat
3-fold inside style; Tripel/Kriek/Lambic excluded entirely as an extension) is registered as a JSON dependency so
the experiment does not invent folds at run time.

  data/clean/q3.csv                    row, beer, beer_id, style, chem__<231>, <50 sensory labels>
  data/clean/q3_style_protocol.json     style groups, 3-fold assignment seed and the excluded styles
  data/processed/fields_q3.json         complete field list (each column exactly once)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
CLEAN = PROJECT / "data" / "clean"
PROCESSED = PROJECT / "data" / "processed"
FOUR = PROJECT / "data" / "raw" / "imported" / "43a7b38682ed81ce-4.csv"
SEED = 20261024
EXCLUDED_STYLES = ["Tripel", "Kriek", "Lambic"]


def main() -> int:
    base = pd.read_csv(CLEAN / "q2_raw.csv")
    four_header = pd.read_csv(FOUR, nrows=1)
    target_cols = [c for c in four_header.columns if c not in ("beer", "beer_id", "tasting_category_fine")]
    keep = ["row", "beer", "beer_id", "tasting_category_fine"] + [c for c in base.columns if c.startswith("chem__")] + target_cols
    q3 = base[keep].copy()
    path = CLEAN / "q3.csv"
    q3.to_csv(path, index=False, lineterminator="\n")

    styles = q3["tasting_category_fine"].astype(str)
    counts = styles.value_counts().sort_index()
    fold_of_style = {}
    rng = np.random.default_rng(SEED)
    for style in sorted(counts.index):
        indices = np.where((styles == style).to_numpy())[0]
        order = rng.permutation(len(indices))
        folds = np.empty(len(indices), dtype=int)
        folds[order] = np.arange(len(indices)) % 3
        for position, fold in zip(indices, folds):
            fold_of_style[str(position)] = int(fold)
    protocol = {
        "seed": SEED,
        "withinStyleFolds": 3,
        "foldByRow": fold_of_style,
        "styleCounts": {str(k): int(v) for k, v in counts.items()},
        "excludedStyles": EXCLUDED_STYLES,
        "nExcluded": int(styles.isin(EXCLUDED_STYLES).sum()),
        "note": ("Within-style 3-fold CV is the main task (a held-out real sample of a style that is in training). "
                 "Excluding Tripel/Kriek/Lambic entirely is an extension for unseen-style generalisation, reported "
                 "separately and never merged with the main score."),
    }
    (CLEAN / "q3_style_protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    meta = {"row": ("integer", None, "0-based position in 1.csv/4.csv (row-aligned)."),
            "beer": ("integer", None, "1.csv/4.csv beer label (permutation of 1..250); join key."),
            "beer_id": ("string", None, "1.csv EAN-like code; truncated in 4.csv/7.csv, so not a join key."),
            "tasting_category_fine": ("string", None, "tasting_category_fine, 22 styles: the Q3 conditioning label.")}
    records = []
    for column in q3.columns:
        if column in meta:
            kind, unit, description = meta[column]
            records.append({"name": column, "type": kind, "unit": unit, "description": description})
        elif column.startswith("chem__"):
            records.append({"name": column, "type": "number", "unit": "stored chemistry value",
                            "description": "1.csv column %r, stored value; the generator works in this space and inverts the calibrated scale for threshold checks." % column[len("chem__"):]})
        elif column in target_cols:
            records.append({"name": column, "type": "number", "unit": "standardized sensory label",
                            "description": "4.csv standardized sensory label %r, EVALUATION-ONLY reference for the sensory profile comparison; never a generator input." % column})
        else:
            raise RuntimeError("unclassified column: %s" % column)
    assert len(records) == len(q3.columns)
    (PROCESSED / "fields_q3.json").write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "rows": int(len(q3)), "columns": int(q3.shape[1]),
                      "styles": int(counts.size), "excludedRows": int(protocol["nExcluded"]),
                      "targetColumn": "chem__ethanol..v.v.", "hasTargetColumn": "chem__ethanol..v.v." in q3.columns}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
