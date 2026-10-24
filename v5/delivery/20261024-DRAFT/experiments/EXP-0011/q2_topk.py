"""q2_topk.py — Q2 Candidate 1: Top-3 key single compounds per sensory dimension.

Three ingredient scores are computed on the 200 SPLIT-0001 train rows (read as a registered dependency, no split):
total Spearman, within-style Spearman (rank residualised on style dummies + intercept) and the |B| matrix of the
Q1 graph low-rank multi-output regression (tau=0.5, lambda=1, gamma=0.1, r=6, un-tuned).  The consensus score is
the mean of the three within-dimension percentile ranks over the 219 single-compound candidates.

500 style-stratified bootstrap resamples refit every ingredient from scratch; the delivered Top-3 per dimension
and method orders the candidates by bootstrap selection frequency pi (ties broken by the point-estimate score).

The four DELIVERED methods (sets.json, the evidence the registered metric is recomputed from) are the
point-estimate rankings: total Spearman, within-style Spearman, graph low-rank |B|, and the consensus score
S = mean of the three within-dimension percentile ranks (consensus = Top-3 by S).  The bootstrap is a stability
instrument: it produces the selection-frequency table pi and the pi-first ordering that is reported as the
"final Top-3" (pi first, S breaks ties), but it does not move the delivered sets, so ``topk-jaccard`` is
recomputable from sets.json, independent of the bootstrap size, and directly comparable with the robustness runs.

The registered metric ``topk-jaccard`` is the mean, over the 50 dimensions and the 6 method pairs, of the plugin
Jaccard J = |A n B| / (2k - |A n B|) with k = 3.
"""

import json

import matplotlib.colors as colors
import numpy as np
import pandas as pd

from modeling_contract import emit_metrics
from q_common import run_seed, report, figure, save_fig, dataset_path

import q2_lib as Q
from target_columns import TARGET_COLS


def main() -> int:
    seed = run_seed()
    frame = Q.load_train_frame()
    dataset = pd.read_csv(dataset_path())
    coverage = {"nDatasetRows": int(len(dataset)), "nTrainRows": int(len(frame)),
                "trainRowsFoundInDataset": int(frame["row"].isin(dataset["row"]).sum())}

    # ------------------------------------------------------------------ point estimates and bootstrap
    scores = Q.ingredient_scores(frame)
    ranked = Q.percentile_block(scores)
    counts = Q.bootstrap_counts(frame, seed, Q.N_BOOTSTRAP)
    pi = Q.frequencies(counts, Q.N_BOOTSTRAP)
    sets_point = Q.topk_from_scores(ranked)
    sets_pi = Q.topk_from_pi(pi, ranked)

    pairs = Q.pairwise_jaccard(sets_point)
    summary = Q.jaccard_summary(pairs)
    pi_pairs = Q.pairwise_jaccard(sets_pi)
    pi_summary = Q.jaccard_summary(pi_pairs)
    modules = Q.module_table(scores["graph"])
    strict_modules = Q.module_table(Q.ingredient_scores(frame, tau=0.6)["graph"])
    final_rows = Q.final_table(sets_pi, scores, pi, modules)
    external = Q.external_corroboration(scores["signedTotal"])

    # ------------------------------------------------------------------ delivered (point) vs pi-first (bootstrap) ordering
    point_vs_bootstrap = {method: {
        "meanJaccard": float(np.mean([Q.jaccard(sets_point[method][d], sets_pi[method][d])
                                      for d in range(len(TARGET_COLS))])),
        "changedDimensions": int(sum(1 for d in range(len(TARGET_COLS))
                                     if set(sets_point[method][d]) != set(sets_pi[method][d])))}
        for method in Q.METHODS}

    # ------------------------------------------------------------------ tau sensitivity (point estimates)
    tau_report = {}
    for tau in (0.4, 0.5, 0.6):
        scores_tau = Q.ingredient_scores(frame, tau=tau)
        sets_tau = Q.topk_from_scores(Q.percentile_block(scores_tau))
        tau_report[str(tau)] = {
            "edges": int(scores_tau["graph"]["edges"]),
            "components": int(scores_tau["graph"]["components"]["count"]),
            "methods": {method: {
                "meanJaccardVs05": float(np.mean([Q.jaccard(sets_tau[method][d], sets_point[method][d])
                                                  for d in range(len(TARGET_COLS))])),
                "changedDimensionsVs05": int(sum(1 for d in range(len(TARGET_COLS))
                                                 if set(sets_tau[method][d]) != set(sets_point[method][d])))}
                for method in Q.METHODS},
        }

    # ------------------------------------------------------------------ ablation 4: overall vs within-style
    ablation = {
        "question": "does style residualisation change the delivered Top-3? (point-estimate sets)",
        "jaccardTotalVsWithin": float(np.mean([Q.jaccard(sets_point["total_spearman"][d],
                                                         sets_point["within_style_spearman"][d])
                                               for d in range(len(TARGET_COLS))])),
        "jaccardConsensusVsTotal": float(np.mean([Q.jaccard(sets_point["consensus"][d],
                                                            sets_point["total_spearman"][d])
                                                  for d in range(len(TARGET_COLS))])),
        "jaccardConsensusVsWithin": float(np.mean([Q.jaccard(sets_point["consensus"][d],
                                                             sets_point["within_style_spearman"][d])
                                                   for d in range(len(TARGET_COLS))])),
        "dimensionsTotalDiffersFromWithin": int(sum(1 for d in range(len(TARGET_COLS))
                                                    if set(sets_point["total_spearman"][d])
                                                    != set(sets_point["within_style_spearman"][d]))),
        "perDimension": [{"dimension": target,
                          "total": [Q.CANDIDATE_NAMES[p] for p in sets_point["total_spearman"][d]],
                          "within": [Q.CANDIDATE_NAMES[p] for p in sets_point["within_style_spearman"][d]],
                          "consensus": [Q.CANDIDATE_NAMES[p] for p in sets_point["consensus"][d]],
                          "jaccardTotalWithin": Q.jaccard(sets_point["total_spearman"][d],
                                                          sets_point["within_style_spearman"][d])}
                         for d, target in enumerate(TARGET_COLS)],
    }

    # ------------------------------------------------------------------ bootstrap stability summary
    selected_pi = [row["pi"] for row in final_rows]
    stability = {
        "nBootstrap": Q.N_BOOTSTRAP,
        "meanSelectedPi": float(np.mean(selected_pi)),
        "minSelectedPi": float(np.min(selected_pi)),
        "shareSelectedAtPiOne": float(np.mean([value == 1.0 for value in selected_pi])),
        "perMethodMeanSelectedPi": {
            method: float(np.mean([pi[method][position, dimension]
                                   for dimension, row in enumerate(Q.TARGET_COLS)
                                   for position in sets_pi[method][dimension]]))
            for method in Q.METHODS},
        "perDimensionMeanPi": {target: float(np.mean([row["pi"] for row in final_rows
                                                      if row["dimension"] == target]))
                               for target in TARGET_COLS},
    }

    # ------------------------------------------------------------------ persist the audit artefacts
    with open("sets.json", "w", encoding="utf-8") as handle:
        json.dump(Q.sets_payload(sets_point), handle, ensure_ascii=False, indent=1)
    with open("sets_pi_first.json", "w", encoding="utf-8") as handle:
        json.dump(Q.sets_payload(sets_pi), handle, ensure_ascii=False, indent=1)
    bootstrap_rows = []
    for method in Q.METHODS:
        for dimension, target in enumerate(TARGET_COLS):
            for position, name in enumerate(Q.CANDIDATE_NAMES):
                value = float(pi[method][position, dimension])
                if value > 0.0:
                    bootstrap_rows.append({"method": method, "dimension": target, "compound": name, "pi": value})
    pd.DataFrame(bootstrap_rows).to_csv("bootstrap_pi.csv", index=False, lineterminator="\n")

    # ------------------------------------------------------------------ reports
    report("settings", {
        "modelKind": "candidate",
        "method": "consensus of total Spearman / within-style Spearman / graph low-rank |B|",
        "seed": int(seed), "bootstrapReps": Q.N_BOOTSTRAP, "tau": Q.TAU, "k": Q.K,
        "graph": {"representation": "zscore", "rank": Q.GRAPH_SETTINGS["rank"],
                  "lambda": Q.GRAPH_SETTINGS["lambda"], "gamma": Q.GRAPH_SETTINGS["gamma"],
                  "nIter": 25, "tau": Q.TAU},
        "candidates": "%d single-compound columns (COMPOUND_CANDIDATES); the 5 derived sums and 7 physical parameters are excluded" % len(Q.CANDIDATE_NAMES),
        "trainingRows": "200 rows of data/splits/SPLIT-0001/train.csv (registered dependency; the Q2 experiment hangs no split)",
        "scoring": "ingredient scores are |Spearman|, |within-style partial Spearman on ranks| and |B_jt|; consensus = mean of the three within-dimension percentile ranks over the 219 candidates",
        "delivery": "sets.json (and therefore topk-jaccard) uses the point-estimate Top-3 per method; consensus = Top-3 by the score S. The pi-first ordering (pi, then S, then frozen candidate order) is reported as the final Top-3 table and saved as sets_pi_first.json",
        "direction": "sign of the total Spearman correlation for the delivered (consensus) rows",
        "styleConfoundRule": "style-driven if |rho_total| >= 0.25 and |rho_within| < 0.5|rho_total|; within-consistent if |rho_within| >= 0.8|rho_total|; otherwise mixed",
        "external": "6.csv is used only as external corroboration (rank correlation), never for fitting",
        "coverage": coverage,
    })
    report("final_top3", final_rows)
    report("method_jaccard", {
        "pairs": pairs, "summary": summary,
        "deliveredSets": "point estimates (sets.json)",
        "bootstrapPiFirst": {"pairs": pi_pairs, "summary": pi_summary},
        "definition": "J = |A n B| / (2k - |A n B|), k = 3; mean over 50 dimensions and the 6 method pairs",
    })
    report("point_vs_bootstrap", point_vs_bootstrap)
    report("tau_sensitivity", tau_report)
    report("external_6csv", external)
    report("ablation_confounding", ablation)
    report("bootstrap_stability", stability)
    report("bootstrap_pi_path", "bootstrap_pi.csv")
    report("sets_path", "sets.json")
    report("sets_pi_first_path", "sets_pi_first.json")
    report("modules", {
        "count": modules["count"], "edgeCount": modules["edgeCount"],
        "moduleSizes": modules["moduleSizes"],
        "compoundModules": modules["perCompound"],
        "note": "modules are connected components of the |W| graph built on the 231 train-fold features (tau = 0.5); built on the train graph, not on the test rows",
        "stricterPartition": {"tau": 0.6, "count": strict_modules["count"],
                              "edgeCount": strict_modules["edgeCount"],
                              "moduleSizes": strict_modules["moduleSizes"],
                              "compoundModules": strict_modules["perCompound"]},
    })

    # ------------------------------------------------------------------ figures
    fig_stability = figure(6.6, 4.6)
    axis = fig_stability.add_subplot(1, 1, 1)
    flat_pi = pi["consensus"].reshape(-1)
    flat_score = ranked["consensus"].reshape(-1)
    histogram = axis.hist2d(flat_score, flat_pi, bins=(60, 40), cmap="viridis",
                            norm=colors.LogNorm(), cmin=1)
    axis.set_xlabel("consensus percentile score (point estimate)")
    axis.set_ylabel("bootstrap selection frequency pi")
    axis.set_title("Q2 bootstrap stability of the consensus score")
    fig_stability.colorbar(histogram[3], ax=axis, fraction=0.046, pad=0.04)
    fig_stability.tight_layout()
    save_fig(fig_stability, "q2_bootstrap_stability")

    fig_jaccard = figure(5.4, 4.6)
    axis = fig_jaccard.add_subplot(1, 1, 1)
    matrix = np.eye(len(Q.METHODS))
    for pair, values in pairs.items():
        left, right = pair.split("|")
        i, j = Q.METHODS.index(left), Q.METHODS.index(right)
        matrix[i, j] = values["mean"]
        matrix[j, i] = values["mean"]
    image = axis.imshow(matrix, cmap="magma", vmin=0.0, vmax=1.0)
    axis.set_xticks(range(len(Q.METHODS)), Q.METHODS, rotation=35, ha="right", fontsize=7)
    axis.set_yticks(range(len(Q.METHODS)), Q.METHODS, fontsize=7)
    axis.set_title("Q2 mean Top-3 Jaccard between methods (delivered sets)")
    for i in range(len(Q.METHODS)):
        for j in range(len(Q.METHODS)):
            axis.text(j, i, "%.2f" % matrix[i, j], ha="center", va="center", fontsize=7,
                      color="white" if matrix[i, j] < 0.6 else "black")
    fig_jaccard.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    fig_jaccard.tight_layout()
    save_fig(fig_jaccard, "q2_method_jaccard")

    fig_modules = figure(6.4, 5.2)
    axis = fig_modules.add_subplot(1, 1, 1)
    order = np.argsort(np.asarray(modules["labels"], dtype=int), kind="mergesort")
    weight = np.abs(scores["graph"]["weight"])[order][:, order]
    image = axis.imshow(weight, cmap="viridis", interpolation="nearest")
    axis.set_title("Q2 chemistry modules: |W| adjacency ordered by connected component")
    axis.set_xlabel("231 chem features (module order)")
    axis.set_ylabel("231 chem features (module order)")
    fig_modules.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    fig_modules.tight_layout()
    save_fig(fig_modules, "q2_module_graph")

    # ------------------------------------------------------------------ contract metric
    emit_metrics({
        "topk-jaccard": float(summary["overall"]),
        "topk-jaccard-bootstrap-mean": float(pi_summary["overall"]),
        "n_dimensions": int(len(TARGET_COLS)),
        "n_methods": int(len(Q.METHODS)),
        "n_candidates": int(len(Q.CANDIDATE_NAMES)),
        "bootstrap_reps": int(Q.N_BOOTSTRAP),
        "mean_selected_pi": float(stability["meanSelectedPi"]),
        "external_6csv_mean_spearman": float(external["meanSpearman"]),
        "tau": float(Q.TAU),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
