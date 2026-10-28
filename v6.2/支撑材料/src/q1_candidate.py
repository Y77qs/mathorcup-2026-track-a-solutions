# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q1_candidate.py — Candidate 1 for Q1: graph-regularised low-rank multi-output regression.

Model.  With Z = [231 z-scored or Rank-Gauss chem features | 9 missing indicators] (240 columns) and Y the
50 standardised sensory targets, fit

    min_B  ||Y - Z B - 1 b^T||^2 / n + lambda ||B||^2 + gamma tr(B^T L B)   s.t. rank(B) <= r

by alternating least squares on B = A C^T (25 sweeps, intercept b refreshed every sweep).  The graph
Laplacian L = blockdiag(L_231, 0_9) is rebuilt inside every training fold from the Spearman network of the
231 chem features (edge weight = rho * 1{|rho| >= 0.5}, zero diagonal, D_{|W|} - W, clipped to the PSD cone
as a numerical-stabilisation step — disclosed as such in the paper).

Selection is train-only 5-fold CV over r in {3,6,10} x lambda in {0.1,1,10} x gamma in {0,0.1,1} (27 cells) on
the z-score representation, then the optimal cell is re-scored on Rank-Gauss and the lower CV MAE is refitted on
the whole train fold and applied to the registered test rows.  Test rows are never used for tuning.

0-6 grades are DERIVED for reporting only (midpoint train CDF -> 6a -> round-half-up): they are written to
outputs.json / CSV, never to metrics.
"""

import numpy as np

from modeling_contract import emit_metrics, emit_predictions
from q_common import (load_split, run_seed, report, figure, save_fig, read_dependency_json,
                      prediction_table, r2_per_target)

import q1_lib as L
from target_columns import (TARGET_COLS, FEATURE_COLUMNS, FLOOR_COLUMNS,
                            CALIBRATED_ZERO_CELLS, FLOOR_CELLS)

RANKS = (3, 6, 10)
LAMBDAS = (0.1, 1.0, 10.0)
GAMMAS = (0.0, 0.1, 1.0)


def cv_row(cell: dict) -> dict:
    return {"representation": cell["representation"], "rank": int(cell["rank"]),
            "lambda": float(cell["lambda"]), "gamma": float(cell["gamma"]),
            "cv_mae": float(cell["cv_mae"]), "cv_mae_sd": float(cell["cv_mae_sd"]),
            "fold_maes": [float(v) for v in cell["fold_maes"]]}


def main() -> int:
    seed = run_seed()
    split = load_split()
    train = split["train"]
    test = split["test"]
    targets = L.check_targets(train)
    if list(targets) != list(TARGET_COLS):
        raise RuntimeError("the registered table does not carry the frozen target order")

    # ------------------------------------------------------------------ train-only CV over the 27 cells x 2 representations
    search = L.search_grid(train, seed, RANKS, LAMBDAS, GAMMAS, reps=("zscore", "rankgauss"))
    cells = search["cells"]
    best_z = L.best_cell(cells, "zscore")
    best_rg = L.best_cell(cells, "rankgauss")
    best = best_z if best_z["cv_mae"] <= best_rg["cv_mae"] else best_rg
    rep, rank = best["representation"], int(best["rank"])
    lam, gamma = float(best["lambda"]), float(best["gamma"])

    # ------------------------------------------------------------------ ablations (all train-only 5-fold CV)
    # (1) representation at the selected (rank, lambda, gamma)
    rep_cells = {"zscore": [c for c in cells if c["representation"] == "zscore" and c["rank"] == rank
                           and c["lambda"] == lam and c["gamma"] == gamma][0],
                "rankgauss": [c for c in cells if c["representation"] == "rankgauss" and c["rank"] == rank
                              and c["lambda"] == lam and c["gamma"] == gamma][0]}
    # (2) unrestricted ridge + graph at the selected (lambda, gamma)
    ridge = [c for c in L.ridge_cv(search["blocks"]["zscore"] if rep == "zscore" else search["blocks"]["rankgauss"],
                                   [lam], [gamma])][0]
    # (3) gamma = 0 at the selected (representation, rank, lambda)
    cell_gamma0 = [c for c in cells if c["representation"] == rep and c["rank"] == rank
                   and c["lambda"] == lam and c["gamma"] == 0.0][0]

    # ------------------------------------------------------------------ full-train refit and test prediction
    fitted = L.FittedModel(train, rep, rank, lam, gamma)
    prediction = fitted.predict(test)
    truth = L.raw_target_matrix(test)
    source_rows = test["row"].to_numpy(dtype=int)
    row_ids = np.arange(len(test), dtype=int)  # positional contract (0..49): the validation plan joins by position

    reference = L.median_reference(L.raw_target_matrix(train), truth)
    mae = L.pooled_mae(truth, prediction)
    r2 = L.r2_mean(truth, prediction)
    skill = L.skill_score(mae, reference["mae"])
    reference_mae_per_target = np.mean(np.abs(truth - reference["prediction"]), axis=0)
    mae_per_target = np.mean(np.abs(truth - prediction), axis=0)
    r2_values = np.asarray(r2_per_target(truth, prediction), dtype=float)
    skill_per_target = np.where(reference_mae_per_target > 1e-12,
                                1.0 - mae_per_target / reference_mae_per_target, 0.0)
    improved = [t for position, t in enumerate(targets) if mae_per_target[position] < reference_mae_per_target[position]]
    degraded = [t for position, t in enumerate(targets) if mae_per_target[position] > reference_mae_per_target[position]]
    ties = [t for position, t in enumerate(targets) if mae_per_target[position] == reference_mae_per_target[position]]

    # ------------------------------------------------------------------ derived 0-6 grading (reporting only)
    grade_params = read_dependency_json("data/processed/q1_grade_params.json")["targets"]
    grade = L.continuous_grade(grade_params, prediction)
    reference_grades = L.reference_grades(test)
    grade_report = L.grade_summary(grade["discrete"], reference_grades, grade["discrete_linear"],
                                   grade["continuous"])
    grade_report["confusionMatrix"] = L.confusion_matrix(grade["discrete"], reference_grades)
    grade_report["perTargetAgreement"] = {
        t: float(np.mean(grade["discrete"][:, position] == reference_grades[:, position]))
        for position, t in enumerate(targets)}
    grade_report["perTargetQwk"] = {
        t: L.quadratic_weighted_kappa(reference_grades[:, position], grade["discrete"][:, position])
        for position, t in enumerate(targets)}
    grade_report["rule"] = ("a = midpoint empirical CDF of q1_grade_params trainValues; g = clip(floor(6a+0.5),0,6); "
                            "sensitivity maps the declared [linearReferenceLow, linearReferenceHigh] endpoints linearly to 0..1")

    # ------------------------------------------------------------------ reports
    report("settings", {
        "modelKind": "candidate",
        "model": "graph-regularised low-rank multi-output regression (ALS on B = A C^T)",
        "representation": rep,
        "rank": rank, "lambda": lam, "gamma": gamma,
        "nIter": L.N_ITER, "tau": L.TAU, "nFolds": 5,
        "cvGrid": {"rank": list(RANKS), "lambda": list(LAMBDAS), "gamma": list(GAMMAS),
                   "cells": 2 * len(RANKS) * len(LAMBDAS) * len(GAMMAS)},
        "seed": int(seed),
        "features": "231 chem__<name> columns of DATA-0002 == 1.csv columns 4..234 (source: target_columns.FEATURE_COLS)",
        "indicators": "9 missing-indicator columns for target_columns.MISSING_COLUMNS (1 where the raw cell is blank)",
        "graph": "Spearman network of the 231 train-fold features, edges |rho| >= tau, L = D_|W| - W, eigenvalues clipped at 0 (PSD projection, numerical stabilisation), blockdiag(L_231, 0_9)",
        "gradeNote": "0-6 grades are derived for reporting/sensitivity only and are never registered as metrics",
        "rowIds": "predictions row = positional 0..49 in the registered SPLIT-0002 test-file order (validation contract); source_row carries the original 0-based row id",
    })
    report("cv_grid", {
        "cells": [cv_row(cell) for cell in cells],
        "bestZscore": cv_row(best_z), "bestRankGauss": cv_row(best_rg), "selected": cv_row(best),
    })
    report("per_target", {
        t: {"mae": float(mae_per_target[position]),
            "maeMedianReference": float(reference_mae_per_target[position]),
            "r2": float(r2_values[position]) if np.isfinite(r2_values[position]) else 0.0,
            "skill": float(skill_per_target[position]),
            "skillRatio": float(reference_mae_per_target[position] / mae_per_target[position])
            if mae_per_target[position] > 1e-12 else 0.0,
            "gradeReferenceMean": float(reference_grades[:, position].mean()),
            "gradePredictedMean": float(grade["discrete"][:, position].mean())}
        for position, t in enumerate(targets)})
    report("summary", {
        "mae": mae, "r2_50dim": r2, "skill_50dim": skill,
        "skillRatio_50dim": (float(reference["mae"] / mae) if mae > 1e-12 else 0.0),
        "maeMedianReference": float(reference["mae"]),
        "nTargets": len(targets), "nTestRows": int(len(test)),
        "improvedTargets": improved, "degradedTargets": degraded, "tiedTargets": ties,
        "nImproved": len(improved), "nDegraded": len(degraded), "nTied": len(ties),
    })
    report("groups", {
        group: {
            "nTargets": len(members),
            "macroMae": float(np.mean([mae_per_target[targets.index(t)] for t in members])),
            "macroMaeMedianReference": float(np.mean([reference_mae_per_target[targets.index(t)] for t in members])),
            "macroR2": float(np.nanmean([r2_values[targets.index(t)] for t in members])),
            "macroSkill": float(np.mean([skill_per_target[targets.index(t)] for t in members])),
        } for group, members in L.GROUPS.items()})
    report("grades", grade_report)
    report("ablation_representation", {
        "question": "z-score vs Rank-Gauss at the selected (rank, lambda, gamma)",
        "rank": rank, "lambda": lam, "gamma": gamma,
        "zscore": {"cvMae": float(rep_cells["zscore"]["cv_mae"]), "cvMaeSd": float(rep_cells["zscore"]["cv_mae_sd"]),
                   "foldMaes": [float(v) for v in rep_cells["zscore"]["fold_maes"]]},
        "rankgauss": {"cvMae": float(rep_cells["rankgauss"]["cv_mae"]), "cvMaeSd": float(rep_cells["rankgauss"]["cv_mae_sd"]),
                      "foldMaes": [float(v) for v in rep_cells["rankgauss"]["fold_maes"]]},
        "deltaMaeRankGaussMinusZscore": float(rep_cells["rankgauss"]["cv_mae"] - rep_cells["zscore"]["cv_mae"]),
    })
    report("ablation_rank", {
        "question": "unrestricted ridge + graph vs the low-rank constraint at the selected (lambda, gamma)",
        "lambda": lam, "gamma": gamma,
        "ridge": {"cvMae": float(ridge["cv_mae"]), "cvMaeSd": float(ridge["cv_mae_sd"]),
                  "foldMaes": [float(v) for v in ridge["fold_maes"]]},
        "lowrank": {"rank": rank, "cvMae": float(best["cv_mae"]), "cvMaeSd": float(best["cv_mae_sd"]),
                    "foldMaes": [float(v) for v in best["fold_maes"]]},
        "deltaMaeRidgeMinusLowrank": float(ridge["cv_mae"] - best["cv_mae"]),
    })
    report("ablation_gamma", {
        "question": "gamma = 0 vs the selected graph weight at the selected (representation, rank, lambda)",
        "representation": rep, "rank": rank, "lambda": lam,
        "gammaZero": {"cvMae": float(cell_gamma0["cv_mae"]), "cvMaeSd": float(cell_gamma0["cv_mae_sd"]),
                      "foldMaes": [float(v) for v in cell_gamma0["fold_maes"]]},
        "gammaBest": {"gamma": gamma, "cvMae": float(best["cv_mae"]), "cvMaeSd": float(best["cv_mae_sd"]),
                      "foldMaes": [float(v) for v in best["fold_maes"]]},
        "deltaMaeGammaZeroMinusBest": float(cell_gamma0["cv_mae"] - best["cv_mae"]),
        "bestGammaIsZero": bool(gamma == 0.0),
    })
    mask = np.abs(truth - prediction)
    rows = np.argsort(-mask.mean(axis=1), kind="mergesort")[:3]
    report("extreme_samples", [
        {"row": int(row_ids[position]), "style": str(test["tasting_category_fine"].iloc[position]),
         "meanAbsoluteError": float(mask[position].mean()),
         "worstTarget": str(targets[int(np.argmax(mask[position]))]),
         "worstAbsoluteError": float(mask[position].max()),
         "worstTrue": float(truth[position, int(np.argmax(mask[position]))]),
         "worstPredicted": float(prediction[position, int(np.argmax(mask[position]))])}
        for position in rows])
    report("graph_structure", {
        "tau": float(L.TAU), "nodes": L.N_FEATURES, "edges": int(fitted.graph["edges"]),
        "components": int(fitted.graph["components"]["count"]),
        "minEigenvalueBeforeProjection": float(fitted.graph["minEigenvalue"]),
        "notes": "graph is refit inside each training fold; these numbers describe the final full-train graph",
    })

    # ------------------------------------------------------------------ figures (English text only)
    fig_cv = figure(10.2, 3.6)
    for panel, rank_value in enumerate(RANKS):
        axis = fig_cv.add_subplot(1, len(RANKS), panel + 1)
        grid = np.full((len(GAMMAS), len(LAMBDAS)), np.nan)
        for cell in cells:
            if cell["representation"] == rep and cell["rank"] == rank_value:
                grid[GAMMAS.index(cell["gamma"]), LAMBDAS.index(cell["lambda"])] = cell["cv_mae"]
        image = axis.imshow(grid, cmap="viridis", aspect="auto")
        axis.set_xticks(range(len(LAMBDAS)), ["%.1f" % v for v in LAMBDAS])
        axis.set_yticks(range(len(GAMMAS)), ["%.1f" % v for v in GAMMAS])
        axis.set_xlabel("lambda")
        axis.set_ylabel("gamma")
        axis.set_title("rank r=%d (%s)" % (rank_value, rep), fontsize=9)
        for row in range(len(GAMMAS)):
            for column in range(len(LAMBDAS)):
                axis.text(column, row, "%.3f" % grid[row, column], ha="center", va="center",
                          color="white", fontsize=7)
        fig_cv.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    fig_cv.suptitle("Q1 train-only 5-fold CV MAE of the graph low-rank model", fontsize=10)
    fig_cv.tight_layout(rect=(0, 0, 1, 0.94))
    save_fig(fig_cv, "q1_cv_mae_grid")

    order = np.argsort(mae_per_target - reference_mae_per_target, kind="mergesort")
    fig_targets = figure(10.4, 4.4)
    axis = fig_targets.add_subplot(1, 1, 1)
    improvement = (reference_mae_per_target - mae_per_target)[order]
    colours = ["#2a7f62" if value >= 0 else "#a33b3b" for value in improvement]
    axis.bar(range(len(order)), improvement, color=colours)
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_xticks(range(len(order)), [targets[i] for i in order], rotation=90, fontsize=6)
    axis.set_ylabel("MAE improvement over the train-median reference")
    axis.set_title("Q1 per-target MAE change (test split, positive = better than median baseline)")
    fig_targets.tight_layout()
    save_fig(fig_targets, "q1_per_target_improvement")

    fig_grade = figure(4.8, 4.2)
    axis = fig_grade.add_subplot(1, 1, 1)
    matrix = np.asarray(grade_report["confusionMatrix"], dtype=float)
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xlabel("predicted grade")
    axis.set_ylabel("reference grade (train-CDF of true label)")
    axis.set_title("Q1 derived 0-6 grades, QWK=%.3f" % grade_report["qwk"], fontsize=9)
    axis.set_xticks(range(7))
    axis.set_yticks(range(7))
    for row in range(7):
        for column in range(7):
            axis.text(column, row, "%d" % matrix[row, column], ha="center", va="center", fontsize=6,
                      color="black" if matrix[row, column] < matrix.max() * 0.6 else "white")
    fig_grade.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    fig_grade.tight_layout()
    save_fig(fig_grade, "q1_grade_confusion")

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
        "cv_mae": float(best["cv_mae"]),
        "cv_mae_sd": float(best["cv_mae_sd"]),
        "best_r": int(rank),
        "best_lambda": float(lam),
        "best_gamma": float(gamma),
        "mae_median_reference": float(reference["mae"]),
        "n_targets": int(len(targets)),
        "audit_missing_cells": audit_missing,
        "audit_calibrated_zero_cells": int(CALIBRATED_ZERO_CELLS),
        "audit_floor_columns": int(len(FLOOR_COLUMNS)),
        "audit_floor_cells": int(FLOOR_CELLS),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
