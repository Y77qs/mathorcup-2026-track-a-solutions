"""Q1 baseline — constant-per-target predictor (train median), multi-output mapped grade.

WHAT IT IS: for every one of the 50 mapped sensory targets, predict the TRAIN median of that target for every
holdout row. It declares params.features = [] (no input feature is used) and family
"constant-train-median" (the workbench's allow-listed constant family), and it reports the SAME evaluation
contract as the candidates so the comparison is one protocol:

  evaluation = {kind:"multi-output", metric:"mae", metricKey:"mae", predictionsFile:"predictions.csv",
                idColumn:"row", aggregation:"uniform-average", targetContractId:<TGT>}

Primary metric: metrics["mae"] = uniform average over the 50 targets of the holdout MAE.
Secondary (reported, never cited as the primary): holdout_mae_mean, train_only_oof_mae_mean,
train_mae_mean and the per-target table in outputs.json.

The 0-6 scale is NOT recovered: the targets are mapped grades (transformed values), and the paper must say so.
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

import q_common as C


def main() -> int:
    seed = C.run_seed()
    split = C.load_split()
    targets = split["targets"]
    if not targets:
        raise RuntimeError("no sensory target column was found in the registered dataset")

    train = split["train"]
    test = split["test"]
    Y_train = C.matrix(train, targets)
    Y_test = C.matrix(test, targets)
    if not np.isfinite(Y_train).all():
        raise RuntimeError("the training target block contains missing/NaN values; a constant predictor needs a "
                           "complete training label matrix (this is a data-registration problem, not a model one)")
    if not np.isfinite(Y_test).all():
        raise RuntimeError("the holdout target block contains missing/NaN values; the native metric recompute "
                           "refuses missing truth, so the split must be repaired instead of silently dropped")

    # ---- constant per target = TRAIN median (no holdout information is used to fit) --------------------------
    medians = np.median(Y_train, axis=0)
    prediction = np.tile(medians, (Y_test.shape[0], 1))

    # ---- train-only 5-fold OOF of the same rule (honest secondary number) ------------------------------------
    folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    oof = np.empty_like(Y_train)
    for fit_index, score_index in folds.split(Y_train):
        fold_median = np.median(Y_train[fit_index], axis=0)
        oof[score_index] = fold_median[None, :]
    oof_mae = float(np.mean(np.mean(np.abs(Y_train - oof), axis=0)))
    train_mae = float(np.mean(np.mean(np.abs(Y_train - medians[None, :]), axis=0)))

    per_target = C.per_target_scores(Y_test, prediction, targets)
    holdout_mae = float(np.mean([per_target[t]["mae"] for t in targets]))

    tables = C.emit_prediction_tables(split["test_ids"], Y_test, prediction, targets)

    # ---- figures ------------------------------------------------------------------------------------------
    order = sorted(targets, key=lambda t: per_target[t]["mae"])
    fig = C.figure(width=10.0, height=9.0)
    axis = fig.add_subplot(1, 1, 1)
    axis.barh(range(len(order)), [per_target[t]["mae"] for t in order], color="#4c72b0", height=0.75)
    axis.set_yticks(range(len(order)))
    axis.set_yticklabels(order, fontsize=4.2)
    axis.set_xlabel("holdout MAE (mapped grade)")
    axis.set_title("Q1 baseline (constant per target): per-target holdout MAE\nuniform average = %.4f" % holdout_mae,
                   fontsize=9)
    axis.grid(axis="x", alpha=0.3)
    figures = [C.save_fig(fig, "q1_baseline_per_target_mae")]

    fig = C.figure(width=5.2, height=5.2)
    axis = fig.add_subplot(1, 1, 1)
    truth_flat = Y_test.reshape(-1)
    pred_flat = prediction.reshape(-1)
    axis.scatter(truth_flat, pred_flat, s=6, alpha=0.45, color="#c44e52", edgecolors="none")
    low = float(min(truth_flat.min(), pred_flat.min()))
    high = float(max(truth_flat.max(), pred_flat.max()))
    axis.plot([low, high], [low, high], color="black", linewidth=1.0, label="y = x")
    axis.set_xlabel("holdout mapped grade (y_true)")
    axis.set_ylabel("predicted mapped grade (y_pred)")
    axis.set_title("Q1 baseline: prediction vs truth (50 targets x holdout rows)", fontsize=9)
    axis.legend(loc="upper left", fontsize=8)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q1_baseline_scatter"))

    fig = C.figure(width=6.0, height=4.2)
    axis = fig.add_subplot(1, 1, 1)
    residuals = (pred_flat - truth_flat)
    axis.hist(residuals, bins=60, color="#55a868", edgecolor="white", linewidth=0.4)
    axis.axvline(0.0, color="black", linewidth=0.9)
    axis.set_xlabel("residual (y_pred - y_true), mapped grade")
    axis.set_ylabel("count")
    axis.set_title("Q1 baseline: residual distribution (all 50 targets pooled)", fontsize=9)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q1_baseline_residuals"))

    # ---- metrics / structured outputs ---------------------------------------------------------------------
    C.emit_metrics({
        "mae": C.finite(holdout_mae, "mae"),
        "holdout_mae_mean": C.finite(holdout_mae, "holdout_mae_mean"),
        "train_only_oof_mae_mean": C.finite(oof_mae, "train_only_oof_mae_mean"),
        "train_mae_mean": C.finite(train_mae, "train_mae_mean"),
        "n_targets": len(targets),
        "n_holdout_rows": int(Y_test.shape[0]),
        "n_train_rows": int(Y_train.shape[0]),
    })
    C.emit_report("per_target", per_target)
    C.emit_report("evaluation", {
        "kind": "multi-output", "metric": "mae", "metricKey": "mae",
        "aggregation": "uniform-average over the 50 targets of the holdout MAE",
        "predictionsFile": "predictions.csv", "idColumn": "row",
        "family": "constant-per-target (train median)",
        "features": [],
        "holdoutReuse": 1,
        "scale": "mapped grade, non-original 0-6 (see data quality report)",
        "targets": targets,
    })
    C.emit_report("artifacts", {"predictionTables": tables, "figures": figures,
                                "seed": seed, "note": "no holdout information is used to fit the constant"})
    print("Q1 baseline: mae=%.12f oof=%.12f targets=%d holdout_rows=%d"
          % (holdout_mae, oof_mae, len(targets), Y_test.shape[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
