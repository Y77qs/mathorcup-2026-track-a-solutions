"""Q1 candidate 1 — multi-output ridge regression on the registered chemical/physical features.

PROTOCOL (declared before the run, and the same evaluation object as the baseline):
  * inputs: the registered chem__* block of DATA-Q1mapped (all 231 columns; the 50 sensory columns are NEVER
    features -- they are the targets);
  * preprocessing fitted on TRAIN rows only: median imputation, then z-standardisation;
  * family: ridge (L2) multi-output linear regression; alpha chosen by TRAIN-ONLY 5-fold cross-validation over a
    fixed grid (the holdout is touched exactly once, for the reported number);
  * primary metric: metrics["mae"] = uniform average over the 50 targets of the holdout MAE (mapped grade);
  * secondary: train_only_oof_mae_mean (the selection criterion), per-target table in outputs.json.

No holdout row is used to choose alpha: `select_alpha` reads only (X_train, Y_train).
"""

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

import q_common as C

ALPHA_GRID = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)


def standardise(X_train: np.ndarray, X_other: list):
    mean = X_train.mean(axis=0)
    scale = X_train.std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)
    return (X_train - mean) / scale, [(X - mean) / scale for X in X_other], mean, scale


def oof_at_alpha(X: np.ndarray, Y: np.ndarray, alpha: float, folds) -> np.ndarray:
    oof = np.empty_like(Y)
    for fit_index, score_index in folds:
        model = Ridge(alpha=alpha)
        model.fit(X[fit_index], Y[fit_index])
        oof[score_index] = model.predict(X[score_index])
    return oof


def select_alpha(X: np.ndarray, Y: np.ndarray, seed: int, multiplier: float = 1.0) -> tuple:
    """Train-only 5-fold CV over the fixed grid -> (gridBest, effective, cvTable, OOF at the effective alpha).

    `multiplier` is a PRE-REGISTERED robustness perturbation of the selected regularisation (params.tuning);
    the grid selection itself never sees the holdout, and the effective alpha is reported explicitly.
    """
    folds = list(KFold(n_splits=5, shuffle=True, random_state=seed).split(X))
    cv_table = {}
    for alpha in ALPHA_GRID:
        errors = []
        for fit_index, score_index in folds:
            model = Ridge(alpha=alpha)
            model.fit(X[fit_index], Y[fit_index])
            errors.append(np.abs(Y[score_index] - model.predict(X[score_index])))
        cv_table[alpha] = float(np.mean(np.concatenate(errors, axis=0)))
    best = float(min(ALPHA_GRID, key=lambda a: (cv_table[a], a)))
    effective = float(np.clip(best * float(multiplier), 1e-6, 1e8))
    oof = oof_at_alpha(X, Y, effective, folds)
    return best, effective, cv_table, oof


def main() -> int:
    seed = C.run_seed()
    split = C.load_split()
    features = split["chem"]
    targets = split["targets"]
    if not features:
        raise RuntimeError("the registered dataset has no chem__* feature block")
    if not targets:
        raise RuntimeError("no sensory target column was found in the registered dataset")

    train, test = split["train"], split["test"]
    X_train_raw, medians = C.impute_train(train, features)
    X_test_raw = C.apply_impute(test, features, medians)
    Y_train = C.matrix(train, targets)
    Y_test = C.matrix(test, targets)
    if not np.isfinite(Y_test).all():
        raise RuntimeError("the holdout target block contains missing/NaN values; the native metric recompute refuses "
                           "missing truth, so the split must be repaired instead of silently dropped")

    X_train, (X_test,), _, _ = standardise(X_train_raw, [X_test_raw])

    tuning = C.option("tuning") or {}
    multiplier = float(tuning.get("alpha_multiplier", 1.0)) if isinstance(tuning, dict) else 1.0
    grid_best, alpha, cv_table, oof = select_alpha(X_train, Y_train, seed, multiplier)
    oof_mae = float(np.mean(np.mean(np.abs(Y_train - oof), axis=0)))

    model = Ridge(alpha=alpha)
    model.fit(X_train, Y_train)
    prediction = model.predict(X_test)

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
    axis.set_title("Q1 ridge (alpha=%.3g): per-target holdout MAE\nuniform average = %.4f" % (alpha, holdout_mae),
                   fontsize=9)
    axis.grid(axis="x", alpha=0.3)
    figures = [C.save_fig(fig, "q1_ridge_per_target_mae")]

    truth_flat = Y_test.reshape(-1)
    pred_flat = prediction.reshape(-1)
    fig = C.figure(width=5.2, height=5.2)
    axis = fig.add_subplot(1, 1, 1)
    axis.scatter(truth_flat, pred_flat, s=6, alpha=0.45, color="#4c72b0", edgecolors="none")
    low = float(min(truth_flat.min(), pred_flat.min()))
    high = float(max(truth_flat.max(), pred_flat.max()))
    axis.plot([low, high], [low, high], color="black", linewidth=1.0, label="y = x")
    axis.set_xlabel("holdout mapped grade (y_true)")
    axis.set_ylabel("predicted mapped grade (y_pred)")
    axis.set_title("Q1 ridge: prediction vs truth (50 targets x holdout rows)", fontsize=9)
    axis.legend(loc="upper left", fontsize=8)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q1_ridge_scatter"))

    fig = C.figure(width=6.0, height=4.2)
    axis = fig.add_subplot(1, 1, 1)
    axis.hist(pred_flat - truth_flat, bins=60, color="#55a868", edgecolor="white", linewidth=0.4)
    axis.axvline(0.0, color="black", linewidth=0.9)
    axis.set_xlabel("residual (y_pred - y_true), mapped grade")
    axis.set_ylabel("count")
    axis.set_title("Q1 ridge: residual distribution (all 50 targets pooled)", fontsize=9)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q1_ridge_residuals"))

    C.emit_metrics({
        "mae": C.finite(holdout_mae, "mae"),
        "holdout_mae_mean": C.finite(holdout_mae, "holdout_mae_mean"),
        "train_only_oof_mae_mean": C.finite(oof_mae, "train_only_oof_mae_mean"),
        "alpha": C.finite(alpha, "alpha"),
        "n_features": len(features),
        "n_targets": len(targets),
        "n_holdout_rows": int(Y_test.shape[0]),
        "n_train_rows": int(Y_train.shape[0]),
    })
    C.emit_report("per_target", per_target)
    C.emit_report("cv_alpha_selection", {"grid": list(ALPHA_GRID), "meanCvMae": cv_table,
                                         "gridSelected": grid_best, "alphaMultiplier": multiplier,
                                         "effectiveAlpha": alpha,
                                         "criterion": "TRAIN-only 5-fold CV, pooled mean MAE over the 50 targets",
                                         "seed": seed})
    C.emit_report("evaluation", {
        "kind": "multi-output", "metric": "mae", "metricKey": "mae",
        "aggregation": "uniform-average over the 50 targets of the holdout MAE",
        "predictionsFile": "predictions.csv", "idColumn": "row",
        "family": "ridge (L2) multi-output linear",
        "features": features,
        "holdoutReuse": 1,
        "scale": "mapped grade, non-original 0-6 (see data quality report)",
        "targets": targets,
    })
    C.emit_report("artifacts", {"predictionTables": tables, "figures": figures, "seed": seed})
    print("Q1 ridge: mae=%.12f oof=%.12f alpha=%g features=%d" % (holdout_mae, oof_mae, alpha, len(features)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
