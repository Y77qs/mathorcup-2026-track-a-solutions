"""q1_baseline.py — B0: per-target TRAIN median (no chemistry information).

Registered as modelKind=baseline on DATA-0002 + SPLIT-0002. It writes the same prediction table shape the
candidates write (row 0..49 in test order, y_pred__<target>, y_true__<target>) so the multi-output evaluator can
recompute the 50-dimension MAE from the registered truth. skill_50dim is 1 by construction here and the candidates
are measured against THIS experiment's MAE.
"""

import sys

import numpy as np

import q_common as C
from target_columns import TARGET_COLS


def main() -> int:
    seed = C.run_seed()
    split = C.load_split()
    train, test = split["train"], split["test"]
    targets = C.target_columns(train, TARGET_COLS)
    assert test is not None and len(test) == 50, len(test)

    train_target = C.matrix(train, targets)
    test_target = C.matrix(test, targets)
    medians = np.nanmedian(train_target, axis=0)
    prediction = np.tile(medians, (len(test), 1))

    ids = np.arange(len(test), dtype=int)
    wide = C.prediction_table(ids, test_target, prediction, targets)
    C.emit_predictions(wide, "predictions.csv")
    C.emit_predictions(C.long_table(ids, test_target, prediction, targets), "predictions_long.csv")

    per_target_mae = C.mae_per_target(test_target, prediction)
    # the median baseline's own reference: MAE of predicting the TRAIN median on the TRAIN rows
    train_reference = C.mae_per_target(train_target, np.tile(medians, (len(train), 1)))
    C.emit_metrics({
        "mae": float(np.mean(per_target_mae)),
        "r2_50dim": float(np.nanmean(C.r2_per_target(test_target, prediction))),
        "skill_50dim": 1.0,
        "n_targets": int(len(targets)),
        "n_train_rows": int(len(train)),
        "n_holdout_rows": int(len(test)),
        "train_mae_reference": float(np.mean(train_reference)),
    })
    C.report("baseline", {
        "family": "constant-train-median",
        "seed": int(seed),
        "targets": targets,
        "perTargetMae": {t: float(v) for t, v in zip(targets, per_target_mae)},
        "trainReferenceMae": {t: float(v) for t, v in zip(targets, train_reference)},
        "note": "A target-only constant baseline: features=[] and the median is fitted on the 200 TRAIN rows only.",
    })
    print("q1_baseline ok mae=%.6f" % float(np.mean(per_target_mae)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
