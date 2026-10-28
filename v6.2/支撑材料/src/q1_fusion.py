# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q1_fusion.py — Candidate 2 for Q1: OOF-weighted fusion of median + graph low-rank + HGB.

Components (every one fitted inside the 200-row train fold only):
  * median      per-target train-fold median (the naive reference);
  * graph       the Candidate-1 graph-regularised low-rank model, hyper-parameters chosen by the same
                train-only 5-fold CV (r in {3,6,10} x lambda in {0.1,1,10} x gamma in {0,0.1,1});
  * hgb         HistGradientBoostingRegressor per target (max_iter=200, learning_rate=0.06,
                max_leaf_nodes=15, l2_regularization=0.1, random_state=seed) on the z-scored design.

Fusion weights are fitted on 5-fold OUT-OF-FOLD predictions (train rows only):
w_raw = least squares(y ~ [median, graph, hgb]), then w = simplex projection(w_raw) (w >= 0, sum w = 1).
One global weight vector is used; the Aroma / Flavour / other group weights are reported as diagnostics.

The fused model is DELIVERED only when it improves the OOF MAE over the graph component by at least
DELTA_MIN (a train-only criterion); otherwise the graph model is delivered unchanged and the fusion is
reported as no stable gain.  Test MAE of every component is reported for the record, never used to select.
"""

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from modeling_contract import emit_metrics, emit_predictions
from q_common import (load_split, run_seed, report, figure, save_fig, read_dependency_json,
                      prediction_table, r2_per_target)

import q1_lib as L
from target_columns import (TARGET_COLS, FEATURE_COLUMNS, FLOOR_COLUMNS,
                            CALIBRATED_ZERO_CELLS, FLOOR_CELLS)

RANKS = (3, 6, 10)
LAMBDAS = (0.1, 1.0, 10.0)
GAMMAS = (0.0, 0.1, 1.0)
DELTA_MIN = 1.0e-3
HGB_PARAMS = {"max_iter": 200, "learning_rate": 0.06, "max_leaf_nodes": 15, "l2_regularization": 0.1}


def hgb_predict(design_fit: np.ndarray, targets_fit: np.ndarray, design_eval: np.ndarray,
                seed: int) -> np.ndarray:
    """One HGB per target; deterministic given the registered seed."""
    prediction = np.empty((design_eval.shape[0], targets_fit.shape[1]), dtype=float)
    for position in range(targets_fit.shape[1]):
        model = HistGradientBoostingRegressor(random_state=int(seed), **HGB_PARAMS)
        model.fit(design_fit, targets_fit[:, position])
        prediction[:, position] = model.predict(design_eval)
    return prediction


def oof_median(frame, folds, targets):
    out = np.empty((len(frame), len(targets)), dtype=float)
    for held_out in folds:
        train_index = np.setdiff1d(np.arange(len(frame)), held_out)
        medians = np.median(L.raw_target_matrix(frame.iloc[train_index]), axis=0)
        out[held_out, :] = medians
    return out


def stack_weights(components: list, truth: np.ndarray, columns: list) -> dict:
    """Least squares on OOF predictions restricted to ``columns``, then simplex projection."""
    stacked = np.stack([component[:, columns] for component in components], axis=2)
    design = stacked.reshape(-1, stacked.shape[2])
    response = truth[:, columns].reshape(-1)
    raw = np.linalg.lstsq(design, response, rcond=None)[0]
    weights = L.simplex_projection(raw)
    return {"raw": [float(v) for v in raw], "weights": [float(v) for v in weights],
            "oofMae": float(np.mean(np.abs(response - design @ weights)))}


def fuse(components: list, weights: np.ndarray) -> np.ndarray:
    return sum(float(weight) * component for weight, component in zip(weights, components))


def main() -> int:
    seed = run_seed()
    split = load_split()
    train, test = split["train"], split["test"]
    targets = L.check_targets(train)
    if list(targets) != list(TARGET_COLS):
        raise RuntimeError("the registered table does not carry the frozen target order")
    n_rows = len(train)

    # ------------------------------------------------------------------ graph component: same train-only CV as Candidate 1
    search = L.search_grid(train, seed, RANKS, LAMBDAS, GAMMAS, reps=("zscore", "rankgauss"))
    cells = search["cells"]
    best_z = L.best_cell(cells, "zscore")
    best_rg = L.best_cell(cells, "rankgauss")
    best = best_z if best_z["cv_mae"] <= best_rg["cv_mae"] else best_rg
    rep, rank = best["representation"], int(best["rank"])
    lam, gamma = float(best["lambda"]), float(best["gamma"])
    folds = search["folds"]
    best_blocks = search["blocks"][rep]
    graph_cv = L.cv_mae_for(best_blocks, rank, lam, gamma, "lowrank")
    oof_graph = np.empty((n_rows, len(targets)), dtype=float)
    for block, prediction in zip(best_blocks, graph_cv["predictions"]):
        oof_graph[block["eval_index"], :] = prediction
    fitted_graph = L.FittedModel(train, rep, rank, lam, gamma)
    test_graph = fitted_graph.predict(test)

    # ------------------------------------------------------------------ median component
    y_train = L.raw_target_matrix(train)
    oof_median_prediction = oof_median(train, folds, targets)
    medians_full = np.median(y_train, axis=0)
    test_median = np.broadcast_to(medians_full, (len(test), len(targets))).copy()

    # ------------------------------------------------------------------ HGB component (5-fold OOF + full-train test)
    oof_hgb = np.empty((n_rows, len(targets)), dtype=float)
    for block in L.build_blocks(train, folds, "zscore"):
        oof_hgb[block["eval_index"], :] = hgb_predict(block["z_train"], block["y_train"], block["z_eval"], seed)
    full_design = L.transform_pair(train, test, "zscore")
    test_hgb = hgb_predict(full_design["fit"], y_train, full_design["eval"], seed)

    # ------------------------------------------------------------------ OOF stacking weights
    components_oof = [oof_median_prediction, oof_graph, oof_hgb]
    all_columns = list(range(len(targets)))
    global_fit = stack_weights(components_oof, y_train, all_columns)
    weights = np.asarray(global_fit["weights"], dtype=float)
    group_fits = {}
    for group, members in L.GROUPS.items():
        columns = [targets.index(t) for t in members]
        group_fits[group] = stack_weights(components_oof, y_train, columns)
    fused_oof = fuse(components_oof, weights)
    fused_test = fuse([test_median, test_graph, test_hgb], weights)

    graph_oof_mae = L.pooled_mae(y_train, oof_graph)
    median_oof_mae = L.pooled_mae(y_train, oof_median_prediction)
    hgb_oof_mae = L.pooled_mae(y_train, oof_hgb)
    fused_oof_mae = L.pooled_mae(y_train, fused_oof)

    # ------------------------------------------------------------------ selection (train-only OOF criterion)
    use_fusion = bool(fused_oof_mae < graph_oof_mae - DELTA_MIN)
    if use_fusion:
        prediction = fused_test
        selected = "fusion"
        reason = ("fused OOF MAE %.6f beats the graph OOF MAE %.6f by more than the %.1e stability margin"
                  % (fused_oof_mae, graph_oof_mae, DELTA_MIN))
    else:
        prediction = test_graph
        selected = "graph"
        reason = ("fused OOF MAE %.6f does not beat the graph OOF MAE %.6f by the %.1e stability margin, so the "
                  "graph model is delivered unchanged (no stable gain from the fusion)"
                  % (fused_oof_mae, graph_oof_mae, DELTA_MIN))

    truth = L.raw_target_matrix(test)
    source_rows = test["row"].to_numpy(dtype=int)
    row_ids = np.arange(len(test), dtype=int)  # positional contract (0..49): the validation plan joins by position
    reference = L.median_reference(y_train, truth)
    mae = L.pooled_mae(truth, prediction)
    r2 = L.r2_mean(truth, prediction)
    skill = L.skill_score(mae, reference["mae"])
    mae_per_target = np.mean(np.abs(truth - prediction), axis=0)
    reference_mae_per_target = np.mean(np.abs(truth - reference["prediction"]), axis=0)
    r2_values = np.asarray(r2_per_target(truth, prediction), dtype=float)
    skill_per_target = np.where(reference_mae_per_target > 1e-12,
                                1.0 - mae_per_target / reference_mae_per_target, 0.0)
    improved = [t for position, t in enumerate(targets) if mae_per_target[position] < reference_mae_per_target[position]]
    degraded = [t for position, t in enumerate(targets) if mae_per_target[position] > reference_mae_per_target[position]]

    # ------------------------------------------------------------------ derived 0-6 grading (reporting only)
    grade_params = read_dependency_json("data/processed/q1_grade_params.json")["targets"]
    grade = L.continuous_grade(grade_params, prediction)
    reference_grades = L.reference_grades(test)
    grade_report = L.grade_summary(grade["discrete"], reference_grades, grade["discrete_linear"],
                                   grade["continuous"])
    grade_report["confusionMatrix"] = L.confusion_matrix(grade["discrete"], reference_grades)
    grade_report["rule"] = ("a = midpoint empirical CDF of q1_grade_params trainValues; g = clip(floor(6a+0.5),0,6); "
                            "sensitivity maps the declared [linearReferenceLow, linearReferenceHigh] linearly to 0..1")

    # ------------------------------------------------------------------ reports
    report("settings", {
        "modelKind": "candidate",
        "model": "OOF least-squares + simplex-projection fusion of median / graph low-rank / HGB",
        "delivered": selected,
        "graph": {"representation": rep, "rank": rank, "lambda": lam, "gamma": gamma, "nIter": L.N_ITER, "tau": L.TAU},
        "hgb": dict(HGB_PARAMS, random_state=int(seed)),
        "cvFolds": 5, "stabilityMargin": DELTA_MIN, "seed": int(seed),
        "features": "231 chem__<name> columns of DATA-0002 == 1.csv columns 4..234 (source: target_columns.FEATURE_COLS)",
        "indicators": "9 missing-indicator columns for target_columns.MISSING_COLUMNS",
        "weights": "least squares on out-of-fold predictions, projected onto the probability simplex (global vector; group vectors reported only)",
        "rowIds": "predictions row = positional 0..49 in the registered SPLIT-0002 test-file order (validation contract); source_row carries the original 0-based row id",
        "gradeNote": "0-6 grades are derived for reporting only and are never registered as metrics",
    })
    report("fusion_weights", {
        "global": global_fit,
        "groups": group_fits,
        "components": ["median", "graph", "hgb"],
        "oofMae": {"median": median_oof_mae, "graph": graph_oof_mae, "hgb": hgb_oof_mae, "fused": fused_oof_mae},
        "testMae": {"median": L.pooled_mae(truth, test_median), "graph": L.pooled_mae(truth, test_graph),
                    "hgb": L.pooled_mae(truth, test_hgb), "fused": L.pooled_mae(truth, fused_test),
                    "delivered": mae},
        "selected": selected,
        "reason": reason,
        "graphCvMae": float(best["cv_mae"]),
    })
    report("per_target", {
        t: {"mae": float(mae_per_target[position]),
            "maeMedianReference": float(reference_mae_per_target[position]),
            "r2": float(r2_values[position]) if np.isfinite(r2_values[position]) else 0.0,
            "skill": float(skill_per_target[position]),
            "skillRatio": float(reference_mae_per_target[position] / mae_per_target[position])
            if mae_per_target[position] > 1e-12 else 0.0}
        for position, t in enumerate(targets)})
    report("summary", {
        "mae": mae, "r2_50dim": r2, "skill_50dim": skill,
        "skillRatio_50dim": (float(reference["mae"] / mae) if mae > 1e-12 else 0.0),
        "maeMedianReference": float(reference["mae"]),
        "nTargets": len(targets), "nTestRows": int(len(test)),
        "improvedTargets": improved, "degradedTargets": degraded,
        "nImproved": len(improved), "nDegraded": len(degraded), "delivered": selected,
    })
    report("groups", {
        group: {"nTargets": len(members),
                "macroMae": float(np.mean([mae_per_target[targets.index(t)] for t in members])),
                "macroMaeMedianReference": float(np.mean([reference_mae_per_target[targets.index(t)] for t in members])),
                "macroR2": float(np.nanmean([r2_values[targets.index(t)] for t in members])),
                "macroSkill": float(np.mean([skill_per_target[targets.index(t)] for t in members]))}
        for group, members in L.GROUPS.items()})
    report("grades", grade_report)
    mask = np.abs(truth - prediction)
    rows = np.argsort(-mask.mean(axis=1), kind="mergesort")[:3]
    report("extreme_samples", [
        {"row": int(row_ids[position]), "style": str(test["tasting_category_fine"].iloc[position]),
         "meanAbsoluteError": float(mask[position].mean()),
         "worstTarget": str(targets[int(np.argmax(mask[position]))]),
         "worstAbsoluteError": float(mask[position].max())}
        for position in rows])

    # ------------------------------------------------------------------ figures
    fig_mae = figure(7.2, 4.2)
    axis = fig_mae.add_subplot(1, 1, 1)
    labels = ["median", "graph", "HGB", "fused"]
    oof_values = [median_oof_mae, graph_oof_mae, hgb_oof_mae, fused_oof_mae]
    test_values = [L.pooled_mae(truth, test_median), L.pooled_mae(truth, test_graph),
                   L.pooled_mae(truth, test_hgb), L.pooled_mae(truth, fused_test)]
    positions = np.arange(len(labels))
    axis.bar(positions - 0.19, oof_values, width=0.36, label="OOF MAE (train rows)", color="#4c72b0")
    axis.bar(positions + 0.19, test_values, width=0.36, label="test MAE", color="#dd8452")
    axis.set_xticks(positions, labels)
    axis.set_ylabel("mean absolute error")
    axis.set_title("Q1 components: out-of-fold and test MAE (delivered: %s)" % selected)
    axis.legend(fontsize=8)
    fig_mae.tight_layout()
    save_fig(fig_mae, "q1_fusion_component_mae")

    fig_weights = figure(7.4, 4.0)
    axis = fig_weights.add_subplot(1, 1, 1)
    labels = ["global"] + list(L.GROUPS.keys())
    vectors = [global_fit["weights"]] + [group_fits[g]["weights"] for g in L.GROUPS]
    positions = np.arange(len(labels))
    width = 0.26
    names = ["median", "graph", "HGB"]
    colours = ["#8c8c8c", "#4c72b0", "#dd8452"]
    for index in range(3):
        axis.bar(positions + (index - 1) * width, [vector[index] for vector in vectors], width=width,
                 label=names[index], color=colours[index])
    axis.set_xticks(positions, labels)
    axis.set_ylabel("fusion weight (simplex)")
    axis.set_title("Q1 OOF fusion weights (global vector is the delivered one)")
    axis.legend(fontsize=8)
    fig_weights.tight_layout()
    save_fig(fig_weights, "q1_fusion_weights")

    # ------------------------------------------------------------------ contract outputs
    table = prediction_table(row_ids, truth, prediction, targets)
    table.insert(1, "source_row", source_rows)
    emit_predictions(table, "predictions.csv")
    audit_missing = int(train[FEATURE_COLUMNS].isna().sum().sum()
                      + test[FEATURE_COLUMNS].isna().sum().sum())
    emit_metrics({
        "mae": float(mae),
        "r2_50dim": float(r2),
        "skill_50dim": float(skill),
        "skill_ratio_50dim": float(reference["mae"] / mae) if mae > 1e-12 else 0.0,
        "w_median": float(weights[0]),
        "w_graph": float(weights[1]),
        "w_hgb": float(weights[2]),
        "hgb_oof_mae": float(hgb_oof_mae),
        "graph_oof_mae": float(graph_oof_mae),
        "fused_oof_mae": float(fused_oof_mae),
        "median_oof_mae": float(median_oof_mae),
        "mae_median_reference": float(reference["mae"]),
        "graph_cv_mae": float(best["cv_mae"]),
        "n_targets": int(len(targets)),
        "audit_missing_cells": audit_missing,
        "audit_calibrated_zero_cells": int(CALIBRATED_ZERO_CELLS),
        "audit_floor_columns": int(len(FLOOR_COLUMNS)),
        "audit_floor_cells": int(FLOOR_CELLS),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
