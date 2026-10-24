"""Q3 baseline — unconditional global generator: every compound sampled independently from its TRAIN distribution.

This is the naive comparator: it ignores the style label, so it cannot represent any style-specific profile.
It is scored with the SAME registered evaluation object as the candidate:

  evaluation = {kind:"constraint-satisfaction", metricKey:"constraint-satisfaction",
                modelContractId:"MCON-0001", samplesFile:"generated_profiles.csv", tolerance:1e-9}

`constraint-satisfaction` = fraction of generated rows whose SEVEN `excess__<compound>` values are all <= 0,
where `excess = concentration / threshold - 1` and the concentration is recovered per column from the registered
`data_quality.json` scale audit (log10 / raw / zero-floor). trans-2-nonenal and "Stale hops" have no numeric
threshold in 8.xlsx and are therefore reported as NOT ASSESSABLE, never assigned an invented threshold.

The reference base rate (real beers satisfying the same seven constraints) is emitted next to the generated one:
the defect constraints are hard, and hiding that by loosening them would be the wrong result.
"""

import numpy as np
import pandas as pd

import q3_lib as L
import q_common as C

SAMPLES = 300


def main() -> int:
    seed = C.run_seed()
    q3 = L.load_q3()
    frame = q3["data"]
    chem = q3["chem"]
    audit = L.load_scale_audit()
    thresholds = L.threshold_map(frame)

    train_mask = (frame[q3["holdout"]].astype(str) == "train_style").to_numpy()
    holdout_mask = ~train_mask
    if train_mask.sum() == 0 or holdout_mask.sum() == 0:
        raise RuntimeError("style_holdout does not split the rows into a training and a held-out block")
    values = C.matrix(frame, chem)
    values = np.where(np.isfinite(values), values, np.nan)
    train_values = values[train_mask]
    mean = np.nanmean(train_values, axis=0)
    scale = np.nanstd(train_values, axis=0)
    scale = np.where(scale > 0, scale, 1.0)

    rng = np.random.default_rng(seed)
    samples = rng.normal(mean, scale, size=(SAMPLES, len(chem)))
    generated = pd.DataFrame(samples, columns=chem)
    generated.insert(0, "style", "unconditional")
    generated.insert(0, "sample_id", ["unconditional-%03d" % i for i in range(SAMPLES)])

    excess = L.defect_table(generated, thresholds, audit)
    satisfaction = L.constraint_satisfaction(excess)

    real_all = L.defect_table(frame, thresholds, audit)
    real_holdout = real_all[holdout_mask]
    base_rate_all = L.constraint_satisfaction(real_all)
    base_rate_holdout = L.constraint_satisfaction(real_holdout)

    # energy distance / profile consistency (standardised space; held-out rows only for the comparison)
    z_generated = (samples - mean) / scale
    z_holdout = (values[holdout_mask] - mean) / scale
    z_holdout = np.where(np.isfinite(z_holdout), z_holdout, 0.0)
    energy = L.energy_distance(z_generated, z_holdout)
    profile = L.profile_spearman(z_generated, z_holdout)
    per_style = {}
    styles = frame[q3["style"]].astype(str).to_numpy()
    for style in L.HOLDOUT_STYLES:
        block = values[(styles == style) & holdout_mask]
        if len(block) == 0:
            continue
        block = np.where(np.isfinite(block), block, 0.0)
        z_style = (block - mean) / scale
        per_style[style] = {"n": int(len(block)),
                            "energyDistance": L.energy_distance(z_generated, z_style),
                            "profileSpearman": L.profile_spearman(z_generated, z_style)}

    samples_frame = pd.concat([generated.reset_index(drop=True), excess.reset_index(drop=True)], axis=1)
    samples_frame.to_csv(C.experiment_dir() / "generated_profiles.csv", index=False, lineterminator="\n")

    # ---- figures ------------------------------------------------------------------------------------------
    fig = C.figure(width=6.6, height=4.2)
    axis = fig.add_subplot(1, 1, 1)
    bars = axis.bar(["unconditional\nbaseline", "real beers\n(all 250)", "real held-out\nstyles (49)"],
                    [satisfaction, base_rate_all, base_rate_holdout],
                    color=["#4c72b0", "#55a868", "#c44e52"])
    for bar, value in zip(bars, [satisfaction, base_rate_all, base_rate_holdout]):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.01, "%.3f" % value, ha="center", fontsize=8)
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("fraction satisfying all 7 defect constraints")
    axis.set_title("Q3 baseline: constraint satisfaction vs the real base rate\n"
                   "(7 thresholded defect compounds; no loosening applied)", fontsize=9)
    axis.grid(axis="y", alpha=0.3)
    figures = [C.save_fig(fig, "q3_baseline_constraint_satisfaction")]

    fig = C.figure(width=5.6, height=4.8)
    axis = fig.add_subplot(1, 1, 1)
    real_profile = np.nanmean(values[holdout_mask], axis=0)
    axis.scatter(real_profile, (z_generated.mean(axis=0) * scale + mean), s=8, alpha=0.5,
                 color="#4c72b0", edgecolors="none")
    low = float(np.nanmin(np.concatenate([real_profile, mean])))
    high = float(np.nanmax(np.concatenate([real_profile, mean])))
    axis.plot([low, high], [low, high], color="black", linewidth=0.9, label="y = x")
    axis.set_xlabel("real held-out mean (data scale)")
    axis.set_ylabel("unconditional generated mean (data scale)")
    axis.set_title("Q3 baseline: generated vs real held-out compound means\nSpearman(profile)=%.3f" % profile,
                   fontsize=9)
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3)
    figures.append(C.save_fig(fig, "q3_baseline_profile_scatter"))

    fig = C.figure(width=8.6, height=4.4)
    axis = fig.add_subplot(1, 1, 1)
    labels = list(excess.columns)
    generated_rate = [float(np.mean(excess[column].to_numpy() > 0)) for column in labels]
    real_rate = [float(np.mean(real_all[column].to_numpy() > 0)) for column in labels]
    positions = np.arange(len(labels))
    axis.bar(positions - 0.2, generated_rate, width=0.4, label="unconditional baseline", color="#4c72b0")
    axis.bar(positions + 0.2, real_rate, width=0.4, label="real beers (250)", color="#55a868")
    axis.set_xticks(positions)
    axis.set_xticklabels([label.replace("excess__", "") for label in labels], rotation=30, ha="right", fontsize=8)
    axis.set_ylabel("fraction of samples over threshold")
    axis.set_title("Q3 baseline: per-compound defect exceedance rate", fontsize=9)
    axis.legend(fontsize=8)
    axis.grid(axis="y", alpha=0.3)
    figures.append(C.save_fig(fig, "q3_baseline_defect_rates"))

    C.emit_metrics({
        "constraint-satisfaction": C.finite(satisfaction, "constraint-satisfaction"),
        "energy-distance": C.finite(energy, "energy-distance"),
        "profile-consistency": C.finite(profile, "profile-consistency"),
        "real_sample_constraint_satisfaction": C.finite(base_rate_all, "real_sample_constraint_satisfaction"),
        "heldout-real-base-rate": C.finite(base_rate_holdout, "heldout-real-base-rate"),
        "all-real-base-rate": C.finite(base_rate_all, "all-real-base-rate"),
        "n_samples": int(SAMPLES),
        "n_holdout_rows": int(holdout_mask.sum()),
        "n_train_rows": int(train_mask.sum()),
    })
    C.emit_report("evaluation", {
        "kind": "constraint-satisfaction", "metricKey": "constraint-satisfaction",
        "modelContractId": "MCON-0001", "samplesFile": "generated_profiles.csv", "tolerance": 1e-09,
        "definition": "fraction of generated rows with all seven excess__<compound> <= 0, "
                      "excess = inverse_transform(chem__<compound>)/thr__<compound> - 1 ; "
                      "generated_profiles.csv carries BOTH the chem__ values and their excess__ values so a reviewer "
                      "can recompute excess independently",
        "family": "unconditional global Gaussian, independent per compound (baseline)",
        "unassessableDefects": list(L.UNASSESSABLE_DEFECTS),
        "scope": "generation reasonableness / constraint satisfaction; NOT a real brewing validation",
    })
    C.emit_report("defectCounts", {
        "thresholdsOriginalUnits": thresholds,
        "realAll250": L.exceedance_counts(real_all),
        "realHeldoutStyles": L.exceedance_counts(real_holdout),
        "generated": L.exceedance_counts(excess),
        "realAll250SatisfyingAll7": int(round(base_rate_all * len(real_all))),
        "realHeldoutSatisfyingAll7": int(round(base_rate_holdout * len(real_holdout))),
        "scaleAuditBasis": audit["basis"],
    })
    C.emit_report("perStyle", per_style)
    C.emit_report("artifacts", {"figures": figures, "seed": seed, "samplesFile": "generated_profiles.csv"})
    print("Q3 baseline: constraint-satisfaction=%.12f energy=%.6f profile=%.6f base_rate_all=%.6f holdout=%.6f"
          % (satisfaction, energy, profile, base_rate_all, base_rate_holdout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
