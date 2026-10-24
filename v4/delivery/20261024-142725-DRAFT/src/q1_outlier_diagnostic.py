"""q1_outlier_diagnostic.py — reproducible diagnostic for the ROB-0004 failure (NOT an experiment).

WHY THIS FILE EXISTS: the paper/report needs to say "excluding the single extreme-outlier holdout row, the
ROB-0004 S_b MAE would be 0.6911 instead of 1.9624" — a DIAGNOSTIC, not a ledger metric. Rather than hand-copy
it, this script recomputes it from the registered experiment's own predictions.csv (whose sha256 is in the
ledger) and prints the exact numbers, so anyone can rerun it:

    python src/q1_outlier_diagnostic.py            # defaults to experiments/EXP-0026/predictions.csv

It reads only the prediction table; it does not touch the experiment, its outputs or the ledger.
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="experiments/EXP-0026/predictions.csv")
    parser.add_argument("--row-threshold", type=float, default=10.0,
                        help="a row is flagged as an outlier-dominated prediction when its row-MAE exceeds this")
    args = parser.parse_args()

    frame = pd.read_csv(args.predictions)
    targets = [column[len("y_true__"):] for column in frame.columns if column.startswith("y_true__")]
    if not targets:
        raise SystemExit("the prediction table has no y_true__<target> columns: %s" % args.predictions)
    truth = frame[["y_true__" + target for target in targets]].to_numpy(dtype=float)
    prediction = frame[["y_pred__" + target for target in targets]].to_numpy(dtype=float)
    row_mae = np.mean(np.abs(truth - prediction), axis=1)

    full = float(np.mean(row_mae))
    flagged = np.where(row_mae > args.row_threshold)[0]
    kept = np.setdiff1d(np.arange(len(row_mae)), flagged)
    without = float(np.mean(row_mae[kept])) if len(kept) else float("nan")
    worst = int(np.argmax(row_mae))

    report = {
        "predictionsFile": args.predictions,
        "rows": int(len(frame)),
        "targets": len(targets),
        "maeAllRows": full,
        "maeExcludingFlaggedRows": without,
        "flaggedRowCount": int(len(flagged)),
        "flaggedRows": [
            {"row": int(frame["row"].iloc[i]), "rowMae": float(row_mae[i]),
             "predictionMin": float(prediction[i].min()), "predictionMax": float(prediction[i].max())}
            for i in flagged
        ],
        "worstRow": {"row": int(frame["row"].iloc[worst]), "rowMae": float(row_mae[worst]),
                     "predictionMin": float(prediction[worst].min()),
                     "predictionMax": float(prediction[worst].max())},
        "note": "DIAGNOSTIC only: the ledger metric of the experiment is metrics.mae (all rows). This value must not "
                "be cited as a ledger metric.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
