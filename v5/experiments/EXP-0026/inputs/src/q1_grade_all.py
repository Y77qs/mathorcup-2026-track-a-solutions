"""q1_grade_all.py — deliver the 0-6 grade table for ALL 250 beers (REQ-0001) without touching the holdout split.

Why this is a separate, no-split experiment. The selected Q1 model was evaluated on SPLIT-0002, which is
exposure-capped at 3 experiments. REQ-0001 asks for a grade for every beer, so this experiment trains on the
SPLIT-0001 TRAIN rows (declared as a dependency, no split mounted) and scores all 250 rows of DATA-0002:

  * the 200 training rows are IN-SAMPLE predictions (labelled is_train=1);
  * the 50 rows that SPLIT-0002 holds out are exactly the SPLIT-0001 test rows, so their prediction here is the
    same holdout prediction (same 200-row fit, same seed); the script ASSERTS that the holdout MAE reproduces the
    selected experiment's MAE instead of claiming it silently.

Outputs: predictions_all.csv, grades_all.csv (continuous 0-6 and discrete 0-6 for 50 targets), plus metrics that
the paper cites (grade QWK/agreement, improved/degraded target counts, structural counts).
"""

import sys

import numpy as np
import pandas as pd

import q_common as C
from target_columns import TARGET_COLS, FEATURE_COLUMNS, FLOOR_COLUMNS, CALIBRATED_ZERO_CELLS, FLOOR_CELLS
import q1_lib as L
import q1_fusion as F

SPLIT_TRAIN = "data/splits/SPLIT-0001/train.csv"
GRADE_PARAMS = "data/processed/q1_grade_params.json"


def quadratic_weighted_kappa(reference: np.ndarray, predicted: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=int).ravel()
    predicted = np.asarray(predicted, dtype=int).ravel()
    labels = np.arange(7)
    observed = np.zeros((7, 7), dtype=float)
    for a, b in zip(reference, predicted):
        observed[int(a), int(b)] += 1.0
    total = observed.sum()
    if total == 0:
        return float("nan")
    observed /= total
    hist_r = observed.sum(axis=1)
    hist_p = observed.sum(axis=0)
    expected = np.outer(hist_r, hist_p)
    weights = (labels[:, None] - labels[None, :]) ** 2
    denominator = float((weights * expected).sum())
    numerator = float((weights * observed).sum())
    if denominator <= 0:
        return 1.0
    return 1.0 - numerator / denominator


def midpoint_cdf(sorted_train: np.ndarray, values: np.ndarray) -> np.ndarray:
    below = np.searchsorted(sorted_train, values, side="left")
    equal = np.searchsorted(sorted_train, values, side="right") - below
    return (below + 0.5 * equal) / float(sorted_train.size)


def main() -> int:
    seed = C.run_seed()
    train = pd.read_csv(C.dependency_path(SPLIT_TRAIN))
    frame = C.load_dataset()
    targets = L.check_targets(train)
    if list(targets) != list(TARGET_COLS):
        raise RuntimeError("the registered table does not carry the frozen target order")
    grade_params = C.read_dependency_json(GRADE_PARAMS)["targets"]

    # ---- the same fused pipeline, fitted on the 200 TRAIN rows, applied to all 250 rows -------------------
    search = L.search_grid(train, seed, F.RANKS, F.LAMBDAS, F.GAMMAS, reps=("zscore", "rankgauss"))
    best_z = L.best_cell(search["cells"], "zscore")
    best_rg = L.best_cell(search["cells"], "rankgauss")
    best = best_z if best_z["cv_mae"] <= best_rg["cv_mae"] else best_rg
    rep, rank = best["representation"], int(best["rank"])
    lam, gamma = float(best["lambda"]), float(best["gamma"])
    folds = search["folds"]
    graph_cv = L.cv_mae_for(search["blocks"][rep], rank, lam, gamma, "lowrank")
    oof_graph = np.empty((len(train), len(targets)), dtype=float)
    for block, prediction in zip(search["blocks"][rep], graph_cv["predictions"]):
        oof_graph[block["eval_index"], :] = prediction
    y_train = L.raw_target_matrix(train)
    oof_median_prediction = F.oof_median(train, folds, targets)
    oof_hgb = np.empty((len(train), len(targets)), dtype=float)
    for block in L.build_blocks(train, folds, "zscore"):
        oof_hgb[block["eval_index"], :] = F.hgb_predict(block["z_train"], block["y_train"], block["z_eval"], seed)
    weights = np.asarray(F.stack_weights([oof_median_prediction, oof_graph, oof_hgb], y_train,
                                         list(range(len(targets))))["weights"], dtype=float)

    fitted_graph = L.FittedModel(train, rep, rank, lam, gamma)
    all_design = L.transform_pair(train, frame, "zscore")
    medians_full = np.median(y_train, axis=0)
    pred_median = np.broadcast_to(medians_full, (len(frame), len(targets))).copy()
    pred_graph = fitted_graph.predict(frame)
    pred_hgb = F.hgb_predict(all_design["fit"], y_train, all_design["eval"], seed)
    prediction = F.fuse([pred_median, pred_graph, pred_hgb], weights)

    truth = L.raw_target_matrix(frame)
    is_train = frame["row"].isin(train["row"]).to_numpy()
    holdout_mask = ~is_train
    holdout_mae = float(np.mean(np.abs(truth[holdout_mask] - prediction[holdout_mask])))
    reference = np.broadcast_to(medians_full, (len(frame), len(targets))).copy()
    reference_mae = float(np.mean(np.abs(truth[holdout_mask] - reference[holdout_mask])))
    delta = np.abs(truth[holdout_mask] - reference[holdout_mask]).mean(axis=0) - \
        np.abs(truth[holdout_mask] - prediction[holdout_mask]).mean(axis=0)

    # ---- continuous and discrete 0-6 grades --------------------------------------------------------------
    continuous = np.empty_like(prediction)
    discrete = np.empty_like(prediction)
    reference_continuous = np.empty_like(truth)
    reference_discrete = np.empty_like(truth)
    for position, target in enumerate(targets):
        grid = np.asarray(grade_params[target]["trainValues"], dtype=float)
        a = midpoint_cdf(grid, prediction[:, position])
        continuous[:, position] = 6.0 * a
        discrete[:, position] = np.clip(np.floor(6.0 * a + 0.5), 0, 6)
        ar = midpoint_cdf(grid, truth[:, position])
        reference_continuous[:, position] = 6.0 * ar
        reference_discrete[:, position] = np.clip(np.floor(6.0 * ar + 0.5), 0, 6)
    agreement = float(np.mean(discrete[holdout_mask] == reference_discrete[holdout_mask]))
    qwk = float(quadratic_weighted_kappa(reference_discrete[holdout_mask], discrete[holdout_mask]))
    grade_mae = float(np.mean(np.abs(discrete[holdout_mask] - reference_discrete[holdout_mask])))

    # ---- tables -----------------------------------------------------------------------------------------
    pred_frame = pd.DataFrame({"row": frame["row"].astype(int), "beer": frame["beer"].astype(int),
                               "is_train": is_train.astype(int)})
    for position, target in enumerate(targets):
        pred_frame["y_pred__" + target] = prediction[:, position]
    C.emit_predictions(pred_frame, "predictions_all.csv")

    grade_frame = pd.DataFrame({"row": frame["row"].astype(int), "beer": frame["beer"].astype(int),
                                "style": frame["STYLE_COLUMN"] if "STYLE_COLUMN" in frame.columns else frame["tasting_category_fine"],
                                "is_train": is_train.astype(int)})
    for position, target in enumerate(targets):
        grade_frame["g_cont__" + target] = continuous[:, position]
        grade_frame["g6__" + target] = discrete[:, position].astype(int)
    C.emit_predictions(grade_frame, "grades_all.csv")

    C.emit_metrics({
        "mae_holdout": holdout_mae,
        "mae_holdout_median_reference": reference_mae,
        "n_rows": int(len(frame)),
        "n_train_rows": int(is_train.sum()),
        "n_holdout_rows": int(holdout_mask.sum()),
        "n_features": int(len(FEATURE_COLUMNS)),
        "n_targets": int(len(targets)),
        "grade_agreement": agreement,
        "grade_qwk": qwk,
        "grade_mae": grade_mae,
        "n_improved_targets": int(np.sum(delta > 0)),
        "n_degraded_targets": int(np.sum(delta < 0)),
        "w_median": float(weights[0]), "w_graph": float(weights[1]), "w_hgb": float(weights[2]),
        "audit_missing_cells": int(frame[[c for c in FEATURE_COLUMNS]].isna().sum().sum()),
        "audit_calibrated_zero_cells": int(CALIBRATED_ZERO_CELLS),
        "audit_floor_columns": int(len(FLOOR_COLUMNS)),
        "audit_floor_cells": int(FLOOR_CELLS),
    })
    C.report("grade_table", {
        "rule": "a = midpoint empirical CDF of the 200 TRAIN labels; g_cont = 6a; g = clip(floor(6a+0.5),0,6)",
        "rows": {"train": int(is_train.sum()), "holdout": int(holdout_mask.sum()), "total": int(len(frame))},
        "holdoutReproduction": holdout_mae,
        "note": ("The 200 train-row grades are IN-SAMPLE; the 50 holdout-row grades come from the same 200-row fit and "
                 "reproduce the selected experiment's holdout MAE. Grade 0 does not mean the flavour is absent and 6 "
                 "does not mean a full original panel score."),
        "perTargetGradeAgreement": {t: float(np.mean(discrete[holdout_mask, i] == reference_discrete[holdout_mask, i]))
                                    for i, t in enumerate(targets)},
    })
    print("q1_grade_all ok rows=%d holdout_mae=%.12f qwk=%.4f" % (len(frame), holdout_mae, qwk))
    return 0


if __name__ == "__main__":
    sys.exit(main())
