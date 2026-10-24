"""Q1 candidate 2 — per-target histogram gradient boosting (non-linear family).

PROTOCOL (declared before the run):
  * inputs: the registered chem__* block of DATA-Q1mapped (231 columns; the 50 sensory columns are the targets);
  * preprocessing fitted on TRAIN rows only: median imputation (the tree model itself needs no scaling);
  * family: HistGradientBoostingRegressor fitted independently for each of the 50 targets with a FIXED,
    a-priori hyper-parameter set (no holdout-driven tuning; the holdout is touched once for the reported number);
  * 5-fold TRAIN-ONLY OOF supplies the secondary selection number train_only_oof_mae_mean;
  * primary metric: metrics["mae"] = uniform average over the 50 targets of the holdout MAE (mapped grade).

Seed determinism: random_state=seed on every estimator and single-threaded BLAS/OMP (set in q_common), so a
rerun with the same seed reproduces the metrics.
"""

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold

import q_common as C

HYPERPARAMETERS = {
    "max_iter": 120,
    "learning_rate": 0.05,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 10,
    "l2_regularization": 1.0,
    "early_stopping": False,
    "random_state": None,  # replaced by the registered seed in estimator()
}


def hyperparameters() -> dict:
    """Fixed a priori hyper-parameters, optionally perturbed by a PRE-REGISTERED params.tuning block."""
    tuning = C.option("tuning") or {}
    params = dict(HYPERPARAMETERS)
    if isinstance(tuning, dict):
        if "max_iter_multiplier" in tuning:
            params["max_iter"] = max(10, int(round(params["max_iter"] * float(tuning["max_iter_multiplier"]))))
        if "l2_multiplier" in tuning:
            params["l2_regularization"] = float(params["l2_regularization"] * float(tuning["l2_multiplier"]))
    return params


def estimator(seed: int, hyper: dict = None) -> HistGradientBoostingRegressor:
    params = dict(hyper if hyper is not None else hyperparameters())
    params["random_state"] = int(seed)
    return HistGradientBoostingRegressor(**params)


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
    X_train, medians = C.impute_train(train, features)
    X_test = C.apply_impute(test, features, medians)
    Y_train = C.matrix(train, targets)
    Y_test = C.matrix(test, targets)
    if not np.isfinite(Y_test).all():
        raise RuntimeError("the holdout target block contains missing/NaN values; the native metric recompute refuses "
                           "missing truth, so the split must be repaired instead of silently dropped")

    hyper = hyperparameters()

    # ---- TRAIN-ONLY 5-fold OOF (secondary selection number) -------------------------------------------------
    folds = list(KFold(n_splits=5, shuffle=True, random_state=seed).split(X_train))
    oof = np.empty_like(Y_train)
    for index, target in enumerate(targets):
        y = Y_train[:, index]
        for fit_index, score_index in folds:
            model = estimator(seed, hyper)
            model.fit(X_train[fit_index], y[fit_index])
            oof[score_index, index] = model.predict(X_train[score_index])
    oof_mae = float(np.mean(np.mean(np.abs(Y_train - oof), axis=0)))

    # ---- final fit on all training rows, one prediction pass over the holdout --------------------------------
    prediction = np.empty_like(Y_test)
    for index, target in enumerate(targets):
        model = estimator(seed, hyper)
        model.fit(X_train, Y_train[:, index])
        prediction[:, index] = model.predict(X_test)

    per_target = C.per_target_scores(Y_test, prediction, targets)
    holdout_mae = float(np.mean([per_target[t]["mae"] for t in targets]))

    tables = C.emit_prediction_tables(split["test_ids"], Y_test, prediction, targets)

    # ---- figures ------------------------------------------------------------------------------------------
    order = sorted(targets, key=lambda t: per_target[t]["mae"])
    fig = C.figure(width=10.0, height=9.0)
    axis = fig.add_subplot(1, 1, 1)
    axis.barh(range(len(order)), [per_target[t]["mae"] for t in order], color="#8172b3", height=0.75)
    axis.set_yticks(range(len(order)))
    axis.set_yticklabels(order, fontsize=4.2)
    axis.set_xlabel("holdout MAE (mapped grade)")
    axis.set_title("Q1 histogram gradient boosting: per-target holdout MAE\nuniform average = %.4f" % holdout_mae,
                   fontsize=9)
    axis.grid(axis="x", alpha=0.3)
    figures = [C.save_fig(fig, "q1_hgb_per_target_mae")]

    truth_flat = Y_test.reshape(-1)
    pred_flat = prediction.reshape(-1)
    fig = C.figure(width=5.2, height=5.2)
    axis = fig.add_subplot(1, 1, 1)
    axis.scatter(truth_flat, pred_flat, s=6, alpha=0.45, color="#8172b3", edgecolors="none")
    low = float(min(truth_flat.min(), pred_flat.min()))
    high = float(max(truth_flat.max(), pred_flat.max()))
    axis.plot([low, high], [low, high], color="black", linewidth=1.0, label="y = x")
    axis.set_xlabel("holdout mapped grade (y_true)")
    axis.set_ylabel("predicted mapped grade (y_pred)")
    axis.set_title("Q1 histogram gradient boosting: prediction vs truth", fontsize=9)
    axis.legend(loc="upper left", fontsize=8)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q1_hgb_scatter"))

    fig = C.figure(width=6.0, height=4.2)
    axis = fig.add_subplot(1, 1, 1)
    axis.hist(pred_flat - truth_flat, bins=60, color="#55a868", edgecolor="white", linewidth=0.4)
    axis.axvline(0.0, color="black", linewidth=0.9)
    axis.set_xlabel("residual (y_pred - y_true), mapped grade")
    axis.set_ylabel("count")
    axis.set_title("Q1 histogram gradient boosting: residual distribution (all targets pooled)", fontsize=9)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q1_hgb_residuals"))

    C.emit_metrics({
        "mae": C.finite(holdout_mae, "mae"),
        "holdout_mae_mean": C.finite(holdout_mae, "holdout_mae_mean"),
        "train_only_oof_mae_mean": C.finite(oof_mae, "train_only_oof_mae_mean"),
        "n_features": len(features),
        "n_targets": len(targets),
        "n_holdout_rows": int(Y_test.shape[0]),
        "n_train_rows": int(Y_train.shape[0]),
    })
    C.emit_report("per_target", per_target)
    C.emit_report("hyperparameters", dict(hyper, random_state=seed, tuning=C.option("tuning") or {},
                                         note="fixed a priori; no holdout-driven tuning; params.tuning only carries "
                                              "a pre-registered robustness perturbation"))
    C.emit_report("evaluation", {
        "kind": "multi-output", "metric": "mae", "metricKey": "mae",
        "aggregation": "uniform-average over the 50 targets of the holdout MAE",
        "predictionsFile": "predictions.csv", "idColumn": "row",
        "family": "per-target HistGradientBoostingRegressor (non-linear)",
        "features": features,
        "holdoutReuse": 1,
        "scale": "mapped grade, non-original 0-6 (see data quality report)",
        "targets": targets,
    })
    C.emit_report("artifacts", {"predictionTables": tables, "figures": figures, "seed": seed})
    print("Q1 hgb: mae=%.12f oof=%.12f features=%d" % (holdout_mae, oof_mae, len(features)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
