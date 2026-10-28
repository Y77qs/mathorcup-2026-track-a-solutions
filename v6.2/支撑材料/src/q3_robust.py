# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q3_robust.py — Q3 robustness / perturbation runner.

WHY THIS FILE EXISTS. The delivery robustness plan perturbs the Q3 generator's hyper-parameters (kappa of the marginal
shrinkage and kappa_R of the copula correlation shrinkage) and the seed, and needs a cheap, reproducible run that
reports the same two headline numbers as the main candidate:
  · constraint-satisfaction   — fraction of delivered rows meeting the four declared constraints;
  · energy-distance-normalized — the within-style 3-fold out-of-fold energy distance of the main flow, with the
    perturbed kappa / kappa_R held fixed (no re-selection, otherwise a perturbation would silently start tuning).

The model for the delivered samples is fitted on all 250 rows (the perturbation is about the generator, not about a
held-out style); the energy-distance metric still uses the frozen fold protocol so its definition equals the one in
`q3_generate.py`. Style-holdout and the Pils/Lager -> Tripel transfer are not recomputed here: neither enters the two
metrics, and the plan's budget is better spent on more perturbation cells.

usage: python q3_robust.py [--seed N] [--kappa 5] [--kappa-r 50]
"""

import numpy as np
import pandas as pd

import q_common
from modeling_contract import emit_metrics, emit_output, seed

import q3_lib as L
import q3_generate as G


def _metric(value, name: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError("metric %r is not finite (%r); this is a defect, not a measurement" % (name, value))
    return out


def resolve_seed(registered) -> int:
    """--seed wins over the registered seed; the receipt still comes from seed()."""
    value = q_common.option("seed", None)
    if value is None:
        return int(registered)
    return int(float(value))


def main():
    registered = seed()                      # requireSeedReceipt: always call the contract seed first
    run_seed = resolve_seed(registered)
    kappa = q_common.option_float("kappa", 5.0)
    kappa_r = q_common.option_float("kappa-r", q_common.option_float("kappa_r", 50.0))
    thresholds = dict(L.THRESHOLD_MEAN)
    sets = G.threshold_sets()

    protocol = L.load_protocol()
    prep = L.prepare(L.load_frame())
    X, styles, rows, Y = prep["X"], prep["styles"], prep["rows"], prep["Y"]
    fold = L.fold_of_row(protocol, rows)
    t2n_index = L.LABEL_COLS.index(L.T2N)

    # ---------------------------------------------------------------- fit on all 250 rows (perturbed hyper-parameters)
    medians = L.column_medians(X)
    Xi = L.apply_median(X, medians)
    centre, scale = L.fit_standardizer(Xi)
    codes = L.floor_code_map(Xi)
    bounds, global_bound = G.t2n_bounds_from_labels(Y, styles, t2n_index)
    model, proxy = L.fit_style_model(Xi, styles, Y, kappa, kappa_r, codes, bounds, global_bound,
                                     centre=centre, scale=scale, proxy=True)
    rng = q_common.rng_for(run_seed, 41)

    blocks = []
    for style in sorted(set(str(s) for s in styles)):
        sel = np.nonzero(styles == style)[0]
        n = sel.size
        uniforms = model.copula.uniforms(style, n, rng)
        normal = model.marginals.inverse(style, uniforms)
        low = L.low_defect_samples(model, normal, np.array([style] * n), thresholds)
        blocks.append((style, sel, low))
    Xgen = np.vstack([block[2] for block in blocks])

    data = {
        "row": np.arange(Xgen.shape[0], dtype=int),
        "group": np.array(["generation"] * Xgen.shape[0]),
        "style": np.concatenate([np.array([block[0]] * len(block[1])) for block in blocks]),
        "fold": np.full(Xgen.shape[0], -1, dtype=int),
        "slot": np.concatenate([block[1] for block in blocks]).astype(int),
    }
    for j, name in enumerate(L.CHEM_COLS):
        data[name] = Xgen[:, j]
    frame = pd.DataFrame(data)
    style_bound = model.t2n_bound(frame["style"].to_numpy())
    parts = L.constraint_arrays(Xgen, style_bound, proxy, codes, thresholds)
    frame = pd.concat([frame, pd.DataFrame({key: np.asarray(value, dtype=float)
                                            for key, value in parts.items()})], axis=1)
    experiment_dir = q_common.experiment_dir()
    frame.to_csv(experiment_dir / "samples.csv", index=False, lineterminator="\n")

    check = pd.read_csv(experiment_dir / "samples.csv")
    recount = L.constraint_satisfied({key: check[key].to_numpy(dtype=float) for key in
                                      ("excess__DMS", "excess__X2.3.butanedione", "excess__X4VG",
                                       "t2n_margin")})
    constraint_satisfaction = float(np.mean(recount))

    # ---------------------------------------------------------------- 3-fold out-of-fold energy distance (fixed hyper)
    fold_infos = []
    for f in (0, 1, 2):
        train, hold = fold != f, fold == f
        medians_f = L.column_medians(X[train])
        Xtr = L.apply_median(X[train], medians_f)
        Xho = L.apply_median(X[hold], medians_f)
        centre_f, scale_f = L.fit_standardizer(Xtr)
        codes_f = L.floor_code_map(Xtr)
        bounds_f, global_f = G.t2n_bounds_from_labels(Y[train], styles[train], t2n_index)
        model_f, proxy_f = L.fit_style_model(Xtr, styles[train], Y[train], kappa, kappa_r, codes_f,
                                             bounds_f, global_f, centre=centre_f, scale=scale_f, proxy=True)
        fold_infos.append({
            "fold": f, "train": train, "hold": hold, "medians": medians_f, "centre": centre_f,
            "scale": scale_f, "codes": codes_f, "kappa": kappa, "kappa_R": kappa_r,
            "model": model_f, "proxy": proxy_f, "t2n_bounds": bounds_f, "global_t2n": global_f,
            "Xtr": Xtr, "Xho": Xho, "Ytr": Y[train], "Yho": Y[hold],
            "styles_tr": styles[train], "styles_ho": styles[hold], "rows_ho": rows[hold],
            "Xraw_hold": X[hold],
        })
    rng_cv = q_common.rng_for(run_seed, 42)
    cells = []
    for info in fold_infos:
        cells.extend(G.evaluate_fold(info, Y, rng_cv, thresholds))
    aggregate = G.aggregate_cells(cells)
    energy = float(aggregate["e_norm"])

    emit_output("run-configuration", {
        "seedUsed": int(run_seed),
        "registeredSeed": None if registered is None else int(registered),
        "kappa": float(kappa), "kappa_R": float(kappa_r),
        "thresholdMean": sets["mean"],
        "note": ("samples.csv is fitted on all 250 rows; the energy distance is the frozen 3-fold out-of-fold "
                 "main flow with the perturbed hyper-parameters held fixed"),
    })
    emit_output("fold-cell-metrics", [{"fold": cell["fold"], "style": cell["style"], "n": cell["n"],
                                       "e_norm": cell["e_norm"], "e_norm_normal": cell["e_norm_normal"],
                                       "satisfied_low": cell["satisfied_low"],
                                       "satisfied_normal": cell["satisfied_normal"]} for cell in cells])
    emit_output("aggregate-metrics", aggregate)
    emit_output("samples-provenance", {
        "rows": int(len(frame)),
        "groups": {str(key): int(value) for key, value in frame["group"].value_counts().items()},
        "note": ("same columns as the candidate's samples.csv; fold=-1 because the delivered samples come from an "
                 "all-250-row fit, slot is the matched real row"),
    })
    emit_output("proxy-notes", {
        "usage": "the 50-label ridge map supplies the t2n bound and the profile diagnostics only",
        "cvR2": {"t2n": float(proxy.cv_r2[L.T2N]), "stale_hops": float(proxy.cv_r2[L.STALE])},
    })

    emit_metrics({
        "constraint-satisfaction": _metric(constraint_satisfaction, "constraint-satisfaction"),
        "energy-distance-normalized": _metric(energy, "energy-distance-normalized"),
        "kappa": _metric(kappa, "kappa"),
        "kappa_r": _metric(kappa_r, "kappa_r"),
        "seed_used": float(run_seed),
        "n-generation": float(Xgen.shape[0]),
    })


if __name__ == "__main__":
    main()
