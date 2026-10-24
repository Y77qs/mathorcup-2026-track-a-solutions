"""Q2 baseline — two GLOBAL (dimension-independent) Top-3 selectors, one set reused for every sensory dimension.

WHY THIS IS THE BASELINE: the contest asks for a Top-3 per sensory dimension. The naive alternative is a single
"important compounds" list shared by all dimensions. Two independent global rankings make the baseline's own
set-stability measurable with the SAME definition as the candidate:

  topk-jaccard = per dimension: mean pairwise Jaccard of the Top-3 sets; value: mean over the 50 dimensions.

For a dimension-independent baseline every dimension has the same two sets, so the value is simply the Jaccard
between the two global sets — a low bar the per-dimension candidate must clear. Scope: descriptive association on
TRAIN rows only; not causal, not an external validation.
"""

import numpy as np

import q2_lib as L
import q_common as C


def main() -> int:
    seed = C.run_seed()
    split = C.load_split()
    features = split["chem"]
    dimensions = split["targets"]
    if not features or not dimensions:
        raise RuntimeError("Q2 needs both the chem__* block and the 50 sensory target columns")

    train = split["train"]
    X_raw, _ = C.impute_train(train, features)
    Y = C.matrix(train, dimensions)
    if not np.isfinite(Y).all():
        raise RuntimeError("the training sensory block contains missing values; Q2 ranking needs complete labels")

    compounds = [name[len(C.CHEM_PREFIX):] for name in features]
    X_standardised, _ = L.standardise(X_raw, X_raw)
    alpha, alpha_table = L.select_alpha(X_standardised, Y, seed)

    pooled_rho = L.spearman_abs(X_raw, Y).mean(axis=1)
    pooled_coefficient = np.abs(L.ridge_coefficients(X_standardised, Y, alpha)).mean(axis=1)
    methods = ["global_uniform_top3", "global_uniform_top3_ridgecoef"]
    rankings = {"global_uniform_top3": np.tile(pooled_rho[:, None], (1, len(dimensions))),
                "global_uniform_top3_ridgecoef": np.tile(pooled_coefficient[:, None], (1, len(dimensions)))}
    sets = L.build_sets(rankings, compounds, dimensions, L.TOP_K)
    C.write_json("sets.json", sets["rows"])
    C.write_json("sets_nested.json", sets["selected"])

    value, per_dimension = L.topk_jaccard(sets["selected"], dimensions, methods, L.TOP_K)
    overlap = L.method_overlap(sets["selected"], dimensions, methods)

    # ---- figures ------------------------------------------------------------------------------------------
    order = np.lexsort((np.arange(len(features)), -pooled_rho))[:15]
    fig = C.figure(width=9.0, height=5.0)
    axis = fig.add_subplot(1, 1, 1)
    positions = np.arange(len(order))
    axis.bar(positions - 0.2, pooled_rho[order], width=0.4, label="mean |Spearman rho| over the 50 dimensions",
             color="#4c72b0")
    axis.bar(positions + 0.2, pooled_coefficient[order] / max(pooled_coefficient.max(), 1e-12),
             width=0.4, label="mean |ridge coef| (rescaled to max=1)", color="#c44e52")
    axis.set_xticks(positions)
    axis.set_xticklabels([compounds[i] for i in order], rotation=70, ha="right", fontsize=6)
    axis.set_ylabel("pooled importance score")
    axis.set_title("Q2 baseline: global (dimension-independent) compound importance\n"
                   "one Top-3 set is reused for every sensory dimension", fontsize=9)
    axis.legend(fontsize=7)
    axis.grid(axis="y", alpha=0.3)
    figures = [C.save_fig(fig, "q2_baseline_global_importance")]

    fig = C.figure(width=4.6, height=3.8)
    axis = fig.add_subplot(1, 1, 1)
    pair = methods[0] + "|" + methods[1]
    grid = np.array([[1.0, overlap[pair]], [overlap[pair], 1.0]])
    image = axis.imshow(grid, cmap="Blues", vmin=0.0, vmax=1.0)
    axis.set_xticks([0, 1])
    axis.set_yticks([0, 1])
    axis.set_xticklabels(methods, rotation=20, ha="right", fontsize=7)
    axis.set_yticklabels(methods, fontsize=7)
    for row in range(2):
        for column in range(2):
            axis.text(column, row, "%.2f" % grid[row, column], ha="center", va="center", fontsize=8)
    axis.set_title("Q2 baseline: Jaccard between the two global Top-3 selectors", fontsize=9)
    fig.colorbar(image, ax=axis, shrink=0.8)
    figures.append(C.save_fig(fig, "q2_baseline_jaccard"))

    C.emit_metrics({
        "topk-jaccard": C.finite(value, "topk-jaccard"),
        "ridge_alpha": C.finite(alpha, "ridge_alpha"),
        "n_dimensions": len(dimensions),
        "n_methods": len(methods),
        "n_features": len(features),
    })
    C.emit_report("evaluation", {
        "kind": "set-stability", "metricKey": "topk-jaccard", "topK": L.TOP_K,
        "setsFile": "sets.json", "dimensions": dimensions, "methods": methods,
        "compoundNaming": "sets.json items are the registered chem__ column names with the chem__ prefix removed",
        "definition": "per dimension: mean pairwise Jaccard of the Top-3 sets; value: mean over the 50 dimensions; "
                      "both baseline methods are dimension-independent, so the value is the Jaccard of two global sets",
        "scope": "naive global comparator on TRAIN rows only; not causal, not external validation",
    })
    C.emit_report("selections", {"methods": methods, "topK": L.TOP_K,
                                 "globalSet": {method: sets["selected"][method][dimensions[0]] for method in methods}})
    C.emit_report("stability", {"topk-jaccard": value, "perDimension": per_dimension, "methodOverlap": overlap})
    C.emit_report("cv_alpha_selection", {"grid": list(L.ALPHA_GRID), "meanCvMae": alpha_table, "selected": alpha})
    C.emit_report("artifacts", {"figures": figures, "seed": seed, "setsFile": "sets.json"})
    print("Q2 baseline: topk-jaccard=%.12f alpha=%g globalA=%s globalB=%s"
          % (value, alpha, sets["selected"][methods[0]][dimensions[0]],
             sets["selected"][methods[1]][dimensions[0]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
