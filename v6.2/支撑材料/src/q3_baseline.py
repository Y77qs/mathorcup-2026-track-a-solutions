# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q3_baseline.py — Q3 baseline: one unconditional global Gaussian over the 231 stored chemical values and the
50 sensory labels.

WHAT IT DOES
  · No style information is used at all: one mean vector and one shrunk covariance over the 281 standardised columns
    (231 chemistry + 50 sensory labels), fitted on all 250 rows.
  · 250 samples are drawn from N(0, Sigma) in the standardised space and mapped back to the storage scale.
  · No defect constraint is applied, so `constraint-satisfaction` is whatever the Gaussian happens to produce.
  · The four constraint columns are still written so the baseline is scored on exactly the same predicate as the
    candidate: excess__<defect> = max(c/T - 1, 0) with c the physical concentration, and t2n_margin = global q90 minus
    the ridge-proxy t2n prediction (no per-style bound exists for a model that ignores styles).

The ridge proxy and the energy-distance definition are shared with the candidate (`q3_lib`), so the two numbers are
directly comparable. The baseline scores its samples against the same real rows of each style (by slot), because an
unconditional model is exchangeable across styles.
"""

import json

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

import q_common
from modeling_contract import emit_metrics, emit_output, save_figure, seed

import q3_lib as L

REFERENCE_DRAWS = 20
N_SAMPLES = 250


def _metric(value, name: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError("metric %r is not finite (%r); this is a defect, not a measurement" % (name, value))
    return out


def real_defect_rates(X, codes, thresholds):
    rates = {}
    any_above = np.zeros(X.shape[0], dtype=bool)
    for name in L.DEFECT_KEYS:
        j = L.FEATURE_COLS.index(name)
        conc = L.physical_conc(name, X[:, j], codes)
        above = conc / thresholds[name] > 1.0
        rates[name] = float(np.nanmean(above))
        any_above |= np.nan_to_num(above).astype(bool)
    return rates, float(np.mean(any_above))


def make_figures(style_table, rates, thresholds):
    figures = []
    order = sorted(style_table, key=lambda style: -style_table[style]["n"])
    fig = q_common.figure()
    ax = fig.add_subplot(1, 1, 1)
    positions = np.arange(len(order))
    ax.bar(positions, [style_table[s]["energy"] for s in order], color="#7f8c8d",
           label="global Gaussian")
    ax.plot(positions, [style_table[s]["realRef"] for s in order], "o", color="#c0392b", markersize=4,
            label="real-vs-real reference")
    ax.set_xticks(positions)
    ax.set_xticklabels(["%s (%d)" % (s, style_table[s]["n"]) for s in order], rotation=90, fontsize=7)
    ax.set_ylabel("normalised energy distance")
    ax.set_title("Baseline: unconditional Gaussian vs real samples by style")
    ax.legend(fontsize=8)
    fig.tight_layout()
    figures.append((fig, "baseline-energy-distance"))

    labels = [L.DEFECT_DISPLAY.get(name, name) for name in L.DEFECT_KEYS]
    fig = q_common.figure()
    ax = fig.add_subplot(1, 1, 1)
    x = np.arange(len(labels))
    width = 0.35
    ax.bar(x - width / 2, [rates["real"][name] for name in L.DEFECT_KEYS], width, color="#7f8c8d",
           label="real (all 250)")
    ax.bar(x + width / 2, [rates["generated"][name] for name in L.DEFECT_KEYS], width, color="#e67e22",
           label="baseline generated")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, fontsize=8)
    ax.set_ylabel("exceedance rate")
    ax.set_title("Baseline: defect exceedance with no constraint")
    ax.legend(fontsize=8)
    fig.tight_layout()
    figures.append((fig, "baseline-defect-exceedance"))
    return figures


def main():
    run_seed = int(seed())
    thresholds = dict(L.THRESHOLD_MEAN)
    protocol = L.load_protocol()
    prep = L.prepare(L.load_frame())
    X, Y, styles, rows = prep["X"], prep["Y"], prep["styles"], prep["rows"]
    fold = L.fold_of_row(protocol, rows)

    medians = L.column_medians(X)
    Xi = L.apply_median(X, medians)
    centre_chem, scale_chem = L.fit_standardizer(Xi)
    codes = L.floor_code_map(Xi)

    joint = np.hstack([Xi, Y])
    joint_centre, joint_scale = L.fit_standardizer(joint)
    joint_standard = (joint - joint_centre) / joint_scale
    shrinker = LedoitWolf().fit(joint_standard)
    covariance = 0.5 * (shrinker.covariance_ + shrinker.covariance_.T)
    values, vectors = np.linalg.eigh(covariance)
    values = np.maximum(values, 1e-12)
    factor = vectors * np.sqrt(values)[None, :]

    rng = q_common.rng_for(run_seed, 31)
    normal_draws = rng.standard_normal((N_SAMPLES, joint.shape[1]))
    generated = (normal_draws @ factor.T) * joint_scale + joint_centre
    Xgen = generated[:, : len(L.FEATURE_COLS)]

    proxy = L.LabelProxy(centre_chem, scale_chem).fit(Xi, Y)
    t2n_index = L.LABEL_COLS.index(L.T2N)
    t2n_global = float(np.quantile(Y[:, t2n_index], 0.9))
    parts = L.constraint_arrays(Xgen, np.full(N_SAMPLES, t2n_global), proxy, codes, thresholds)

    data = {
        "row": np.arange(N_SAMPLES, dtype=int),
        "group": np.array(["generation"] * N_SAMPLES),
        "slot": rows.astype(int).copy(),
    }
    for j, name in enumerate(L.CHEM_COLS):
        data[name] = Xgen[:, j]
    for key, value in parts.items():
        data[key] = np.asarray(value, dtype=float)
    frame = pd.DataFrame(data)
    experiment_dir = q_common.experiment_dir()
    frame.to_csv(experiment_dir / "samples.csv", index=False, lineterminator="\n")

    check = pd.read_csv(experiment_dir / "samples.csv")
    satisfied = L.constraint_satisfied({key: check[key].to_numpy(dtype=float) for key in
                                        ("excess__DMS", "excess__X2.3.butanedione", "excess__X4VG",
                                         "t2n_margin")})
    constraint_satisfaction = float(np.mean(satisfied))
    exceeded = L.defect_exceeded({key: check[key].to_numpy(dtype=float) for key in
                                  ("excess__DMS", "excess__X2.3.butanedione", "excess__X4VG",
                                   "t2n_margin")})
    exceedance_rate = float(np.mean(exceeded))

    # Score with the *same* (fold, style) cell structure as the candidate: identical block sizes, identical
    # standardiser and identical D_ref definition, so the two energy distances are directly comparable. The samples
    # are exchangeable (the model ignores styles), so the assignment of samples to cells is arbitrary but fixed.
    excluded = ("Tripel", "Kriek", "Lambic")
    cells = []
    cursor = 0
    for f in (0, 1, 2):
        hold = fold == f
        train = ~hold
        medians_f = L.column_medians(X[train])
        Xtr_f = L.apply_median(X[train], medians_f)
        centre_f, scale_f = L.fit_standardizer(Xtr_f)
        train_pos = -np.ones(len(styles), dtype=int)
        train_pos[np.nonzero(train)[0]] = np.arange(int(train.sum()))
        for style in sorted(set(str(s) for s in styles[hold])):
            sel = np.nonzero(hold & (styles == style))[0]
            n = sel.size
            index = np.arange(cursor, cursor + n)
            cursor += n
            tr_style = train_pos[np.nonzero(train & (styles == style))[0]]
            train_z = (L.standardize(Xtr_f[tr_style], centre_f, scale_f) if tr_style.size >= 2
                       else L.standardize(Xtr_f, centre_f, scale_f))
            real_z = L.standardize(L.apply_median(X[sel], medians_f), centre_f, scale_f)
            gen_z = L.standardize(Xgen[index], centre_f, scale_f)
            dref = L.reference_scale(train_z, n, rng, repeats=REFERENCE_DRAWS)
            value, e2 = L.normalized_energy_distance(gen_z, real_z, dref)
            reference = L.real_reference_energy(real_z, dref, rng, draws=REFERENCE_DRAWS)
            cells.append({"fold": int(f), "style": style, "n": int(n), "energy": float(value), "e2": float(e2),
                          "realRef": float(reference), "dref": float(dref),
                          "gen_profile": proxy.predict_storage(Xgen[index]).mean(axis=0),
                          "real_profile": np.nanmean(Y[sel], axis=0)})
    if cursor != N_SAMPLES:
        raise RuntimeError("cell partition consumed %d samples, expected %d" % (cursor, N_SAMPLES))

    style_table = {}
    for style in sorted(set(cell["style"] for cell in cells)):
        subset = [cell for cell in cells if cell["style"] == style]
        style_table[style] = {
            "n": int(sum(cell["n"] for cell in subset)),
            "energy": float(np.mean([cell["energy"] for cell in subset])),
            "realRef": float(np.mean([cell["realRef"] for cell in subset])),
            "dref": float(np.mean([cell["dref"] for cell in subset])),
        }

    weights = np.array([cell["n"] for cell in cells], dtype=float)
    energy = float(np.sum(weights * np.array([cell["energy"] for cell in cells])) / weights.sum())
    reference = float(np.sum(weights * np.array([cell["realRef"] for cell in cells])) / weights.sum())
    hold_cells = [cell for cell in cells if cell["style"] in excluded]
    hold_weights = np.array([cell["n"] for cell in hold_cells], dtype=float)
    holdout_energy = float(np.sum(hold_weights * np.array([cell["energy"] for cell in hold_cells]))
                           / hold_weights.sum())

    gen_sum = np.zeros(len(L.LABEL_COLS))
    real_sum = np.zeros(len(L.LABEL_COLS))
    weight_total = 0.0
    per_style_profile = {}
    for style in sorted(set(cell["style"] for cell in cells)):
        subset = [cell for cell in cells if cell["style"] == style]
        n = float(sum(cell["n"] for cell in subset))
        gen_profile = np.sum([cell["n"] * cell["gen_profile"] for cell in subset], axis=0) / n
        real_profile = np.sum([cell["n"] * cell["real_profile"] for cell in subset], axis=0) / n
        gen_sum += n * gen_profile
        real_sum += n * real_profile
        weight_total += n
        rho, mae = L.profile_scores(gen_profile, real_profile)
        per_style_profile[style] = {"n": int(n), "spearman": float(rho), "mae": float(mae)}
    profile_rho, profile_mae = L.profile_scores(gen_sum / weight_total, real_sum / weight_total)

    real_rates, real_any = real_defect_rates(X, codes, thresholds)
    generated_rates = {}
    for name in L.DEFECT_KEYS:
        j = L.FEATURE_COLS.index(name)
        conc = L.physical_conc(name, Xgen[:, j], codes)
        generated_rates[name] = float(np.nanmean(conc / thresholds[name] > 1.0))

    figures = make_figures(style_table, {"real": real_rates, "generated": generated_rates}, thresholds)
    figure_records = [save_figure(fig, name) for fig, name in figures]

    metrics = {
        "constraint-satisfaction": _metric(constraint_satisfaction, "constraint-satisfaction"),
        "constraint-satisfaction-from-csv": _metric(constraint_satisfaction, "constraint-satisfaction-from-csv"),
        "energy-distance-normalized": _metric(energy, "energy-distance-normalized"),
        "energy-distance-real-reference": _metric(reference, "energy-distance-real-reference"),
        "defect-exceedance-rate": _metric(exceedance_rate, "defect-exceedance-rate"),
        "defect-exceedance-rate-real": _metric(real_any, "defect-exceedance-rate-real"),
        "profile-spearman": _metric(profile_rho, "profile-spearman"),
        "profile-mae": _metric(profile_mae, "profile-mae"),
        "style-holdout-energy-distance-normalized": _metric(holdout_energy,
                                                            "style-holdout-energy-distance-normalized"),
        "covariance-shrinkage": _metric(shrinker.shrinkage_, "covariance-shrinkage"),
        "covariance-condition-number": _metric(float(values.max() / values.min()),
                                              "covariance-condition-number"),
        "n-samples": float(N_SAMPLES),
        "n-features": float(len(L.FEATURE_COLS)),
        "n-labels": float(len(L.LABEL_COLS)),
    }

    emit_output("style-table", style_table)
    emit_output("profile-table", per_style_profile)
    emit_output("defect-rates", {"real": real_rates, "generated": generated_rates})
    emit_output("constraint-definitions", {
        "thresholdMean": thresholds,
        "t2nBound": "global q90 of the t2n label (the baseline has no style information)",
        "constraintSatisfaction": "fraction of generated rows with all three excesses <= 0 and t2n_margin >= 0",
        "storageScale": "log10 tier -> 10**x, linear tier -> x; a non-detect cell counts as 0",
        "energyDistance": ("E^2 = 2E||X-Y|| - E||X-X'|| - E||Y-Y'|| in the standardised chemical space; "
                          "E_norm = sqrt(max(E^2,0)/D_ref) at the real sample size"),
        "slotEvaluation": ("the unconditional samples are exchangeable; sample k is compared with real row k's "
                           "style, so the per-style energy distances are a fair unconditional reference"),
    })
    emit_output("model", {
        "family": "unconditional multivariate Gaussian",
        "dimension": int(joint.shape[1]),
        "covarianceEstimator": "Ledoit-Wolf shrinkage on standardised columns",
        "shrinkage": float(shrinker.shrinkage_),
        "topEigenvalues": [float(v) for v in values[::-1][:10]],
        "sampling": "250 draws from N(0, Sigma) in the 281-dim standardised space, then un-standardised",
        "constraintHandling": "none (the four constraint columns are reported, not enforced)",
    })
    emit_output("samples-provenance", {
        "rows": int(len(frame)),
        "groups": {str(key): int(value) for key, value in frame["group"].value_counts().items()},
        "note": ("row is a 0-based baseline sample id; slot is the real row whose style is used for the "
                 "per-style energy distance"),
    })
    emit_output("figure-manifest", [record.get("path") for record in figure_records])
    emit_output("proxy-notes", {
        "usage": "the 50-label ridge map is a proxy for the t2n constraint and profile reporting only",
        "alphaSelection": "5-fold CV inside the 250 rows, per target",
        "cvR2": {"t2n": float(proxy.cv_r2[L.T2N]), "stale_hops": float(proxy.cv_r2[L.STALE])},
        "leakage": ("the baseline is fitted on all 250 rows by definition, so the proxy is also fitted on all "
                    "250 rows; the candidate's main score fits its proxy inside the training folds"),
    })

    emit_metrics(metrics)


if __name__ == "__main__":
    main()
