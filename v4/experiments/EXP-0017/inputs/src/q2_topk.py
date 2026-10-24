"""Q2 — per-dimension Top-3 key compounds and their stability (rank / ridge / random-forest rankings).

PROTOCOL (pre-registered in the experiment params before the run):
  * data: DATA-0002; only the TRAIN rows of the registered split are used. The 50 sensory columns are the
    association targets of this descriptive analysis, never inputs of a prediction model;
  * three ranking methods per sensory dimension (k = 3):
      spearman_absrho            |Spearman rho| between chem__* and the dimension (univariate, rank-based)
      ridge_coef                 |coefficient| of a multi-output ridge on standardised features (multivariate,
                                 collinearity-aware; alpha by TRAIN-only 5-fold CV)
      random_forest_importance   random-forest IMPURITY importance (non-linear, multivariate; this is NOT
                                 permutation importance and is never described as such)
  * stability: (a) mean pairwise Top-3 Jaccard across methods per dimension -> metrics["topk-jaccard"] (the pack's
    native set-stability definition, so it recomputes from sets.json); (b) train-row bootstrap resamples give the
    empirical Top-3 inclusion frequency for the cheap refittable estimators;
  * 2.csv is used ONLY as a documented co-expression structure (derived Spearman matrix, NOT PSD: min eig is
    reported; if negative an eigenvalue-clipping PSD projection is applied and recorded). 5/6/7.csv are not used as
    external validation and nothing here is a causal claim.

ROBUSTNESS SWITCHES (params; argv mirrors): `ranking_variant` in {spearman, kendall, pearson} replaces the
univariate ranking, and `bootstrap={replicates, seed}` changes the resampling budget. Absent params => defaults,
so the main run is unaffected.
"""

import numpy as np

import q2_lib as L
import q_common as C

DEFAULT_BOOTSTRAP_REPLICATES = 500
UNIVARIATE_VARIANTS = {"spearman": "spearman_absrho", "kendall": "kendall_absrho", "pearson": "pearson_absrho"}


def main() -> int:
    seed = C.run_seed()
    split = C.load_split()
    features = split["chem"]
    dimensions = split["targets"]
    if not features or not dimensions:
        raise RuntimeError("Q2 needs both the chem__* block and the 50 sensory target columns")

    variant = str(C.option("ranking_variant", "spearman") or "spearman").strip().lower()
    if variant not in UNIVARIATE_VARIANTS:
        raise ValueError("unknown ranking_variant %r (supported: %s)" % (variant, ", ".join(UNIVARIATE_VARIANTS)))
    univariate = UNIVARIATE_VARIANTS[variant]

    bootstrap_block = C.option("bootstrap") or {}
    if not isinstance(bootstrap_block, dict):
        bootstrap_block = {}
    replicates = int(bootstrap_block.get("replicates", DEFAULT_BOOTSTRAP_REPLICATES))
    bootstrap_seed = int(bootstrap_block.get("seed", seed))
    if replicates < 1:
        raise ValueError("bootstrap replicates must be a positive integer")

    train = split["train"]
    X_raw, medians = C.impute_train(train, features)
    Y = C.matrix(train, dimensions)
    if not np.isfinite(Y).all():
        raise RuntimeError("the training sensory block contains missing values; Q2 ranking needs complete labels")

    compounds = [name[len(C.CHEM_PREFIX):] for name in features]
    X_standardised, _ = L.standardise(X_raw, X_raw)
    alpha, alpha_table = L.select_alpha(X_standardised, Y, seed)

    scored = L.score_estimators([univariate, "ridge_coef"], X_raw, Y, alpha)
    rankings = {
        univariate: scored[univariate],
        "ridge_coef": np.abs(L.ridge_coefficients(X_standardised, Y, alpha)),
        "random_forest_importance": L.forest_importance(X_standardised, Y, seed),
    }
    methods = list(rankings.keys())
    sets = L.build_sets(rankings, compounds, dimensions, L.TOP_K)
    C.write_json("sets.json", sets["rows"])
    C.write_json("sets_nested.json", sets["selected"])

    value, per_dimension = L.topk_jaccard(sets["selected"], dimensions, methods, L.TOP_K)
    overlap = L.method_overlap(sets["selected"], dimensions, methods)

    # A full Kendall recomputation inside every resample is not affordable (11 550 pair computations per
    # replicate); the kendall variant therefore bootstraps only the ridge estimator and says so in the outputs.
    bootstrapped = [method for method in (univariate, "ridge_coef") if method != "kendall_absrho"] or ["ridge_coef"]
    bootstrap = L.bootstrap_inclusion(X_standardised, Y, dimensions, compounds, rankings,
                                      bootstrapped, alpha, bootstrap_seed, replicates)
    frequency = L.frequency_table(bootstrap["frequencies"], sets["selected"], dimensions, compounds)

    coexpression = L.load_correlation_matrix(features)

    # ---- figure 1: selected compounds x sensory dimension, colour = |univariate score| ----------------------
    selected_union = []
    for method in methods:
        for dimension in dimensions:
            for name in sets["selected"][method][dimension]:
                if name not in selected_union:
                    selected_union.append(name)
    index_of = {name: i for i, name in enumerate(compounds)}
    columns = [index_of[name] for name in selected_union]
    univariate_block = rankings[univariate][columns, :]
    selection_mask = np.zeros((len(selected_union), len(dimensions)))
    for method in methods:
        for column, dimension in enumerate(dimensions):
            for name in sets["selected"][method][dimension]:
                selection_mask[selected_union.index(name), column] += 1
    matrix = np.where(selection_mask > 0, univariate_block, np.nan)

    fig = C.figure(width=13.0, height=11.0)
    axis = fig.add_subplot(1, 1, 1)
    image = axis.imshow(matrix, aspect="auto", cmap="viridis", vmin=0.0, vmax=float(np.nanmax(matrix)))
    axis.set_xticks(range(len(dimensions)))
    axis.set_xticklabels(dimensions, rotation=90, fontsize=4.0)
    axis.set_yticks(range(len(selected_union)))
    axis.set_yticklabels(selected_union, fontsize=4.0)
    axis.set_title("Q2: Top-3 selected compounds x sensory dimension\n"
                   "colour = |%s| (train rows); blank = not selected by any method" % variant, fontsize=9)
    fig.colorbar(image, ax=axis, shrink=0.5, label="|%s|" % variant)
    figures = [C.save_fig(fig, "q2_top3_selection_heatmap")]

    # ---- figure 2: bootstrap Top-3 inclusion frequency -----------------------------------------------------
    boot_columns = sorted({name for dimension in dimensions for method in bootstrapped
                           for name in sets["selected"][method][dimension]})
    boot_index = {name: i for i, name in enumerate(boot_columns)}
    boot_matrix = np.zeros((len(dimensions), len(boot_columns)))
    picked = np.zeros_like(boot_matrix)
    for row, dimension in enumerate(dimensions):
        names = {name for method in bootstrapped for name in sets["selected"][method][dimension]}
        for name in names:
            values = [bootstrap["frequencies"][method][dimension].get(name, 0.0) for method in bootstrapped]
            boot_matrix[row, boot_index[name]] = float(np.mean(values))
            picked[row, boot_index[name]] = 1.0
    boot_matrix = np.where(picked > 0, boot_matrix, np.nan)
    fig = C.figure(width=13.0, height=11.0)
    axis = fig.add_subplot(1, 1, 1)
    image = axis.imshow(boot_matrix, aspect="auto", cmap="magma", vmin=0.0, vmax=1.0)
    axis.set_xticks(range(len(boot_columns)))
    axis.set_xticklabels(boot_columns, rotation=90, fontsize=3.6)
    axis.set_yticks(range(len(dimensions)))
    axis.set_yticklabels(dimensions, fontsize=4.0)
    axis.set_title("Q2: bootstrap Top-3 inclusion frequency (%d train-row resamples)\n"
                   "mean over refittable estimators (%s); blank = never selected"
                   % (replicates, ", ".join(bootstrapped)), fontsize=9)
    fig.colorbar(image, ax=axis, shrink=0.5, label="inclusion frequency")
    figures.append(C.save_fig(fig, "q2_bootstrap_inclusion"))

    # ---- figure 3: method x method Jaccard ----------------------------------------------------------------
    fig = C.figure(width=5.4, height=4.6)
    axis = fig.add_subplot(1, 1, 1)
    grid = np.full((len(methods), len(methods)), np.nan)
    for index_a, method_a in enumerate(methods):
        grid[index_a, index_a] = 1.0
        for index_b, method_b in enumerate(methods):
            if index_b < index_a:
                grid[index_a, index_b] = grid[index_b, index_a]
            elif index_b > index_a:
                grid[index_a, index_b] = overlap[method_a + "|" + method_b]
    image = axis.imshow(grid, cmap="Blues", vmin=0.0, vmax=1.0)
    axis.set_xticks(range(len(methods)))
    axis.set_yticks(range(len(methods)))
    axis.set_xticklabels(methods, rotation=30, ha="right", fontsize=7)
    axis.set_yticklabels(methods, fontsize=7)
    for index_a in range(len(methods)):
        for index_b in range(len(methods)):
            text = "" if not np.isfinite(grid[index_a, index_b]) else "%.2f" % grid[index_a, index_b]
            axis.text(index_b, index_a, text, ha="center", va="center", fontsize=7,
                      color="black" if grid[index_a, index_b] < 0.6 else "white")
    axis.set_title("Q2: mean per-dimension Top-3 Jaccard between methods", fontsize=9)
    fig.colorbar(image, ax=axis, shrink=0.8)
    figures.append(C.save_fig(fig, "q2_method_jaccard"))

    # ---- figure 4: co-expression structure (2.csv) --------------------------------------------------------
    projected = coexpression["projected"]
    correlation_compounds = coexpression["compounds"]
    chosen = [name for name in correlation_compounds if name in set(selected_union)]
    if len(chosen) < 2:
        connectivity = np.abs(projected).sum(axis=0)
        chosen = [correlation_compounds[i] for i in np.argsort(-connectivity)[:20]]
    elif len(chosen) > 34:
        order = np.argsort(-np.abs(projected[np.ix_([correlation_compounds.index(c) for c in chosen],
                                                    [correlation_compounds.index(c) for c in chosen])]).sum(axis=0))
        chosen = [chosen[i] for i in order[:34]]
    block_index = [correlation_compounds.index(name) for name in chosen]
    block = projected[np.ix_(block_index, block_index)]

    fig = C.figure(width=13.0, height=6.0)
    axis = fig.add_subplot(1, 2, 1)
    axis.plot(coexpression["rawBlockEigen"], label="2.csv block as delivered", color="#c44e52")
    axis.plot(coexpression["projectedBlockEigen"], label="after PSD projection", color="#4c72b0")
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_xlabel("eigenvalue index")
    axis.set_ylabel("eigenvalue")
    axis.set_title("Q2: 2.csv is not PSD (full-matrix min eig %.4f; block %.4f)"
                   % (coexpression["minEigenFullMatrix"], coexpression["minEigenBefore"]), fontsize=8)
    axis.legend(fontsize=7)
    axis.grid(alpha=0.3)
    axis2 = fig.add_subplot(1, 2, 2)
    image = axis2.imshow(block, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    axis2.set_xticks(range(len(chosen)))
    axis2.set_xticklabels(chosen, rotation=90, fontsize=3.6)
    axis2.set_yticks(range(len(chosen)))
    axis2.set_yticklabels(chosen, fontsize=3.6)
    axis2.set_title("co-expression block (PSD-projected), compounds that appear in a Top-3 set", fontsize=8)
    fig.colorbar(image, ax=axis2, shrink=0.7)
    figures.append(C.save_fig(fig, "q2_coexpression"))

    # ---- metrics / outputs --------------------------------------------------------------------------------
    bootstrap_metrics = {"bootstrap_mean_top3_inclusion": C.finite(bootstrap["value"], "bootstrap_mean_top3_inclusion")}
    for method_name, method_value in bootstrap["perMethodMeanInclusion"].items():
        bootstrap_metrics["bootstrap_mean_top3_inclusion_" + method_name] = C.finite(
            method_value, "bootstrap_mean_top3_inclusion_" + method_name)
    C.emit_metrics({
        "topk-jaccard": C.finite(value, "topk-jaccard"),
        **bootstrap_metrics,
        "ridge_alpha": C.finite(alpha, "ridge_alpha"),
        "n_dimensions": len(dimensions),
        "n_methods": len(methods),
        "n_features": len(features),
        "bootstrap_replicates": replicates,
        "coexpression_min_eigen_raw": C.finite(coexpression["minEigenBefore"], "minEigenBefore"),
        "coexpression_min_eigen_full_matrix": C.finite(coexpression["minEigenFullMatrix"], "minEigenFull"),
        "coexpression_min_eigen_projected": C.finite(coexpression["minEigenAfter"], "minEigenAfter"),
        "coexpression_compounds_matched": coexpression["nCompounds"],
    })
    C.emit_report("evaluation", {
        "kind": "set-stability", "metricKey": "topk-jaccard", "topK": L.TOP_K,
        "setsFile": "sets.json", "dimensions": dimensions, "methods": methods,
        "definition": "per dimension: mean pairwise Jaccard of the Top-3 sets; value: mean over the 50 dimensions",
        "compoundNaming": "sets.json items are the registered chem__ column names with the chem__ prefix removed",
        "bootstrap": {"estimators": bootstrapped, "replicates": replicates, "seed": bootstrap_seed},
        "rankingVariant": variant,
        "scope": "descriptive contemporaneous association on TRAIN rows only; not causal, not external validation",
    })
    C.emit_report("selections", {"methods": methods, "topK": L.TOP_K,
                                 "compoundNaming": "dataset column names with the chem__ prefix removed",
                                 "top10": {method: {dimension: [compounds[i] for i in
                                                               np.lexsort((np.arange(len(compounds)),
                                                                           -rankings[method][:, column]))[:10]]
                                                    for column, dimension in enumerate(dimensions)}
                                           for method in methods},
                                 "selected": sets["selected"]})
    C.emit_report("stability", {"topk-jaccard": value, "perDimension": per_dimension,
                                "methodOverlap": overlap,
                                "bootstrap": {"value": bootstrap["value"],
                                              "perMethodMeanInclusion": bootstrap["perMethodMeanInclusion"],
                                              "estimators": bootstrapped,
                                              "replicates": replicates,
                                              "seed": bootstrap_seed,
                                              "frequency": frequency}})
    C.emit_report("coexpression", {
        "source": coexpression["source"], "basis": coexpression["basis"],
        "thresholdNameBasis": coexpression["thresholdNameBasis"],
        "minEigenBefore": coexpression["minEigenBefore"], "minEigenAfter": coexpression["minEigenAfter"],
        "minEigenFullMatrix": coexpression["minEigenFullMatrix"],
        "projection": "eigenvalue clipping (negative eigenvalues -> 0) then diagonal renormalised to 1",
        "nCompounds": coexpression["nCompounds"], "nUnmatched": coexpression["nUnmatched"],
        "role": coexpression["role"],
    })
    C.emit_report("cv_alpha_selection", {"grid": list(L.ALPHA_GRID), "meanCvMae": alpha_table, "selected": alpha,
                                         "criterion": "TRAIN-only 5-fold CV, pooled mean |residual| over the 50 dimensions"})
    C.emit_report("artifacts", {"figures": figures, "seed": seed, "setsFile": "sets.json"})
    print("Q2 topk: topk-jaccard=%.12f bootstrap=%.12f alpha=%g methods=%s dims=%d replicates=%d"
          % (value, bootstrap["value"], alpha, ",".join(methods), len(dimensions), replicates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
