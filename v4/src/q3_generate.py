"""Q3 candidate — style-conditional generator with defect-constraint projection, cross-style transfer and a
sensory-profile proxy.

WHAT IT IS (and what it is NOT):
  * a style-conditional multivariate Gaussian in standardised compound space: one mean per style, a shared
    covariance shrunk toward its diagonal (n=201 training rows < p=231 compounds, so the sample covariance is
    singular). Fitted ONLY on `style_holdout == "train_style"` rows;
  * a held-out style is not observed at fit time, so conditioning uses a PRE-REGISTERED, a-priori style-family
    mapping (params.priorStyleMapping, e.g. Tripel -> Strong ale/Dubbel). The held-out 49 rows are used ONLY to
    compare distributions; they never enter a fitted parameter;
  * a constrained generator: the seven thresholded defect compounds are clipped to their 8.xlsx threshold (and only
    when they exceed it) in the compound's own scale, with a 1e-9 margin. `constraint-satisfaction` is therefore a
    property the model targets, and the UNCONSTRAINED rate is reported next to it so the effect is visible;
  * a cross-style transfer: real Pils/Lager spectra are moved by (mu_target - mu_Pils/Lager) in standardised space,
    with the defect compounds kept unshifted in the constrained variant; the before/after defect check is reported;
  * a sensory-profile figure produced by a Ridge proxy fitted on the registered Q1 TRAIN rows: this is a SURROGATE
    (mapped grade), not a measured rating and not the Q1 final model.

Wording scope: generation reasonableness / constraint satisfaction / distributional consistency. This is NOT a real
brewing validation and no causal claim is made.
"""

import numpy as np
import pandas as pd

import q3_lib as L
import q_common as C

DEFAULT_SAMPLES_PER_STYLE = 100
DEFAULT_SHRINKAGE_MULTIPLIER = 1.0


def build_covariance(z_train: np.ndarray, multiplier: float):
    lam = float(np.clip(0.5 * multiplier, 0.0, 1.0))
    covariance = L.shrunk_covariance(z_train, lam)
    values, vectors = np.linalg.eigh(covariance)
    root = vectors * np.sqrt(np.clip(values, 1e-12, None))
    return covariance, root, lam


def sample_style(rng, mean: np.ndarray, root: np.ndarray, size: int) -> np.ndarray:
    return mean[None, :] + rng.standard_normal((size, mean.shape[0])) @ root.T


def main() -> int:
    seed = C.run_seed()
    generator_block = C.option("generator") or {}
    if not isinstance(generator_block, dict):
        generator_block = {}
    # TOP-LEVEL scalars are the authoritative robustness inputs (the pack's perturbationEvidence only compares
    # top-level scalar params); the nested `generator` block is kept as a backward-compatible fallback.
    top_samples = C.option("n_samples_per_style", None)
    top_shrinkage = C.option("shrinkage_multiplier", None)
    samples_per_style = int(top_samples if top_samples is not None
                            else generator_block.get("n_samples_per_style", DEFAULT_SAMPLES_PER_STYLE))
    shrinkage_multiplier = float(top_shrinkage if top_shrinkage is not None
                                 else generator_block.get("shrinkage_multiplier", DEFAULT_SHRINKAGE_MULTIPLIER))
    if samples_per_style < 1:
        raise ValueError("n_samples_per_style must be a positive integer")

    q3 = L.load_q3()
    frame = q3["data"]
    chem = q3["chem"]
    audit = L.load_scale_audit()
    thresholds = L.threshold_map(frame)

    styles = frame[q3["style"]].astype(str).to_numpy()
    train_mask = (frame[q3["holdout"]].astype(str) == "train_style").to_numpy()
    holdout_mask = ~train_mask
    if train_mask.sum() == 0 or holdout_mask.sum() == 0:
        raise RuntimeError("style_holdout does not split the rows into a training and a held-out block")
    train_styles = sorted(set(styles[train_mask]))
    # The robustness pools (DATA-0006) can drop rows; a mapped prior style may therefore be absent from the pool.
    # It is FILTERED OUT and recorded (never silently kept, never invented back).
    prior_pools = {}
    for heldstyle, pool in L.PRIOR_STYLE_MAPPING.items():
        present = [style for style in pool if style in train_styles]
        dropped = [style for style in pool if style not in train_styles]
        if sum(int(np.sum((styles == style) & train_mask)) for style in present) < 5:
            raise RuntimeError("the prior style pool for %s has fewer than 5 training rows after filtering "
                               "(present=%s, dropped=%s)" % (heldstyle, present, dropped))
        prior_pools[heldstyle] = {"present": present, "dropped": dropped,
                                  "nRows": int(sum(int(np.sum((styles == style) & train_mask)) for style in present))}
    empty_holdout = [style for style in L.HOLDOUT_STYLES if int(np.sum((styles == style) & holdout_mask)) == 0]
    if empty_holdout:
        raise RuntimeError("held-out style(s) with zero real rows in this dataset pool: %s; the style-holdout "
                           "comparison is undefined and no row may be invented" % ", ".join(empty_holdout))
    style_counts = {"trainStyle": {style: int(np.sum((styles == style) & train_mask)) for style in train_styles},
                    "heldoutStyle": {style: int(np.sum((styles == style) & holdout_mask)) for style in L.HOLDOUT_STYLES}}

    values = C.matrix(frame, chem)
    if not np.isfinite(values[train_mask]).all():
        raise RuntimeError("the training compound block contains missing values after data registration")
    mean = values[train_mask].mean(axis=0)
    scale = values[train_mask].std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)
    z_all = (np.where(np.isfinite(values), values, mean[None, :]) - mean) / scale
    z_train = z_all[train_mask]

    covariance, root, shrinkage = build_covariance(z_train, shrinkage_multiplier)
    rng = np.random.default_rng(seed)

    # ---- conditional generation for the held-out styles (prior mapping; no held-out row is fitted) ---------
    generated_blocks, generated_raw_blocks, per_style = {}, {}, {}
    for style in L.HOLDOUT_STYLES:
        pool = prior_pools[style]["present"]
        pool_mask = np.isin(styles, pool) & train_mask
        if pool_mask.sum() < 5:
            raise RuntimeError("the prior style pool %s for %s has too few training rows (%d)"
                               % (pool, style, int(pool_mask.sum())))
        prototype = z_all[pool_mask].mean(axis=0)
        z_generated = sample_style(rng, prototype, root, samples_per_style)
        raw_generated = z_generated * scale[None, :] + mean[None, :]
        generated_blocks[style] = z_generated
        generated_raw_blocks[style] = raw_generated
        per_style[style] = {"priorStyles": pool, "droppedPriorStyles": prior_pools[style]["dropped"],
                            "nPoolRows": int(pool_mask.sum()), "nSamples": int(samples_per_style)}

    # unconstrained stacking
    unconstrained = pd.concat(
        [pd.DataFrame(generated_raw_blocks[style], columns=chem).assign(style=style,
                                                                       sample_id=["%s-%03d" % (style, i)
                                                                                  for i in range(samples_per_style)])
         for style in L.HOLDOUT_STYLES],
        ignore_index=True)
    unconstrained = unconstrained[["sample_id", "style"] + chem]
    excess_unconstrained = L.defect_table(unconstrained, thresholds, audit)
    satisfaction_unconstrained = L.constraint_satisfaction(excess_unconstrained)

    # ---- constraint projection on the seven defect compounds ----------------------------------------------
    constrained, clipped = L.project_defects(unconstrained, thresholds, audit)
    excess_constrained = L.defect_table(constrained, thresholds, audit)
    satisfaction = L.constraint_satisfaction(excess_constrained)
    if not np.isfinite(C.matrix(constrained, chem)).all():
        raise RuntimeError("the constrained spectra contain non-finite values")

    samples_frame = pd.concat([constrained.reset_index(drop=True),
                               excess_constrained.reset_index(drop=True)], axis=1)
    samples_frame.to_csv(C.experiment_dir() / "generated_profiles.csv", index=False, lineterminator="\n")
    # the unconstrained pool is kept as a separate, clearly named artifact (never the registered samples file)
    unconstrained_frame = pd.concat([unconstrained.reset_index(drop=True),
                                     excess_unconstrained.reset_index(drop=True)], axis=1)
    unconstrained_frame.to_csv(C.experiment_dir() / "generated_profiles_unconstrained.csv", index=False,
                               lineterminator="\n")

    # ---- cross-style transfer: real Pils/Lager -> Tripel ---------------------------------------------------
    source_mask = (styles == L.SOURCE_STYLE) & train_mask
    if source_mask.sum() < 3:
        raise RuntimeError("the source style %r has too few real spectra to transfer (%d)"
                           % (L.SOURCE_STYLE, int(source_mask.sum())))
    tripel_pool = np.isin(styles, prior_pools["Tripel"]["present"]) & train_mask
    delta = z_all[tripel_pool].mean(axis=0) - z_all[source_mask].mean(axis=0)
    defect_index = [chem.index(C.CHEM_PREFIX + column) for column in L.DEFECT_COLUMNS]
    delta_constrained = delta.copy()
    delta_constrained[defect_index] = 0.0
    source_z = z_all[source_mask]
    transferred = {}
    for name, shift in (("constrained", delta_constrained), ("rawshift", delta)):
        z_target = source_z + shift[None, :]
        transferred[name] = pd.DataFrame(z_target * scale[None, :] + mean[None, :], columns=chem)
    source_frame = pd.DataFrame(z_all[source_mask] * scale[None, :] + mean[None, :], columns=chem)
    excess_source = L.defect_table(source_frame, thresholds, audit)
    excess_transfer = {name: L.defect_table(block, thresholds, audit)
                       for name, block in transferred.items()}

    def nonworsen_rate(before: pd.DataFrame, after: pd.DataFrame) -> float:
        values_before = np.stack([before[column].to_numpy(dtype=float) for column in before.columns], axis=1)
        values_after = np.stack([after[column].to_numpy(dtype=float) for column in after.columns], axis=1)
        return float(np.mean(values_after <= values_before + 1e-12))

    nonworsen = {name: nonworsen_rate(excess_source, excess) for name, excess in excess_transfer.items()}
    satisfy_source = L.constraint_satisfaction(excess_source)
    satisfy_transfer = {name: L.constraint_satisfaction(excess) for name, excess in excess_transfer.items()}
    transfer_blocks = {}
    for name, block in transferred.items():
        frame_out = block.copy()
        frame_out.insert(0, "style", "transferred-to-Tripel-" + name)
        frame_out.insert(0, "sample_id", ["%s-%03d" % (name, i) for i in range(len(block))])
        transfer_blocks[name] = pd.concat([frame_out.reset_index(drop=True),
                                           excess_transfer[name].reset_index(drop=True)], axis=1)
    pd.concat([transfer_blocks["constrained"], transfer_blocks["rawshift"]], ignore_index=True).to_csv(
        C.experiment_dir() / "transfer_profiles.csv", index=False, lineterminator="\n")

    # ---- distributional comparison against the REAL held-out spectra --------------------------------------
    real_holdout_z = z_all[holdout_mask]
    energy, profile = {}, {}
    for style in L.HOLDOUT_STYLES:
        block = z_all[(styles == style) & holdout_mask]
        if len(block) == 0:
            continue
        generated_z = generated_blocks[style]
        constrained_z = (constrained[constrained["style"] == style][chem].to_numpy(dtype=float) - mean) / scale
        energy[style] = {"unconstrained": L.energy_distance(generated_z, block),
                         "constrained": L.energy_distance(constrained_z, block),
                         "nReal": int(len(block))}
        profile[style] = {"unconstrained": L.profile_spearman(generated_z, block),
                          "constrained": L.profile_spearman(constrained_z, block)}
    energy_mean = float(np.mean([energy[s]["constrained"] for s in energy])) if energy else float("nan")
    energy_mean_unconstrained = float(np.mean([energy[s]["unconstrained"] for s in energy])) if energy else float("nan")
    profile_mean = float(np.mean([profile[s]["constrained"] for s in profile])) if profile else float("nan")

    # ---- real sample base rate (the paper quotes this through the ledger, not by hand) --------------------
    real_all_excess = L.defect_table(frame, thresholds, audit)
    base_rate_all = L.constraint_satisfaction(real_all_excess)
    base_rate_holdout = L.constraint_satisfaction(real_all_excess[holdout_mask])
    real_counts = L.exceedance_counts(real_all_excess)

    # ---- sensory profile (Q1-train-only Ridge proxy; explicitly a surrogate) ------------------------------
    proxy = L.fit_sensory_proxy(seed)
    sensory_targets = proxy["targets"]
    profile_rows, profile_labels = [], []
    for style in L.HOLDOUT_STYLES:
        generated_profile = L.predict_sensory_proxy(proxy, constrained[constrained["style"] == style])
        real_block = frame[(styles == style) & holdout_mask]
        real_profile = L.predict_sensory_proxy(proxy, real_block)
        profile_rows.append(generated_profile.mean(axis=0))
        profile_labels.append(style + " (generated, constraint-projected)")
        profile_rows.append(real_profile.mean(axis=0))
        profile_labels.append(style + " (real held-out, proxy)")

    # ======================================================================================================
    # figures
    # ======================================================================================================
    fig = C.figure(width=13.0, height=4.4)
    axis = fig.add_subplot(1, 1, 1)
    image = axis.imshow(np.vstack(profile_rows), aspect="auto", cmap="RdYlBu_r", vmin=0.0, vmax=6.0)
    axis.set_xticks(range(len(sensory_targets)))
    axis.set_xticklabels(sensory_targets, rotation=90, fontsize=4.0)
    axis.set_yticks(range(len(profile_labels)))
    axis.set_yticklabels(profile_labels, fontsize=6.5)
    axis.set_title("Q3: style sensory profile (mapped grade 0-6 scale via a Ridge PROXY fitted on Q1 TRAIN rows)\n"
                   "SURROGATE prediction, not measured ratings; not the Q1 final model", fontsize=8)
    fig.colorbar(image, ax=axis, shrink=0.75, label="proxy mapped grade")
    figures = [C.save_fig(fig, "q3_sensory_profiles")]

    fig = C.figure(width=7.0, height=4.2)
    axis = fig.add_subplot(1, 1, 1)
    names = ["conditional\n(unconstrained)", "conditional\n(constraint-projected)", "real beers\n(all 250)",
             "real held-out\nstyles (49)"]
    values_bar = [satisfaction_unconstrained, satisfaction, base_rate_all, base_rate_holdout]
    bars = axis.bar(names, values_bar, color=["#c44e52", "#4c72b0", "#55a868", "#8172b3"])
    for bar, value in zip(bars, values_bar):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.01, "%.3f" % value, ha="center", fontsize=8)
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("fraction satisfying all 7 defect constraints")
    axis.set_title("Q3: constraint satisfaction vs the real base rate\n(constraints are NOT loosened)", fontsize=9)
    axis.grid(axis="y", alpha=0.3)
    figures.append(C.save_fig(fig, "q3_constraint_satisfaction"))

    fig = C.figure(width=9.0, height=4.4)
    axis = fig.add_subplot(1, 1, 1)
    labels = list(L.DEFECT_COLUMNS)
    positions = np.arange(len(labels))
    before = [float(np.mean(excess_source["excess__" + c].to_numpy() > 0)) for c in labels]
    after_raw = [float(np.mean(excess_transfer["rawshift"]["excess__" + c].to_numpy() > 0)) for c in labels]
    after_constrained = [float(np.mean(excess_transfer["constrained"]["excess__" + c].to_numpy() > 0))
                         for c in labels]
    axis.bar(positions - 0.27, before, width=0.27, label="Pils/Lager before transfer", color="#4c72b0")
    axis.bar(positions, after_raw, width=0.27, label="after transfer, all compounds shifted", color="#c44e52")
    axis.bar(positions + 0.27, after_constrained, width=0.27, label="after transfer, defect compounds unshifted",
             color="#55a868")
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    axis.set_ylabel("fraction of source spectra over threshold")
    axis.set_title("Q3: cross-style transfer Pils/Lager -> Tripel; defect exceedance before/after", fontsize=9)
    axis.legend(fontsize=7)
    axis.grid(axis="y", alpha=0.3)
    figures.append(C.save_fig(fig, "q3_transfer_defects"))

    fig = C.figure(width=13.0, height=8.0)
    for position, style in enumerate([s for s in L.HOLDOUT_STYLES if s in energy]):
        axis = fig.add_subplot(len([s for s in L.HOLDOUT_STYLES if s in energy]), 1, position + 1)
        constrained_block = constrained[constrained["style"] == style][chem].to_numpy(dtype=float)
        real_block = values[(styles == style) & holdout_mask]
        difference = ((constrained_block - mean) / scale).mean(axis=0) - ((real_block - mean) / scale).mean(axis=0)
        order = np.argsort(-np.abs(difference))[:15]
        axis.bar(range(len(order)), difference[order],
                 color=["#c44e52" if value > 0 else "#4c72b0" for value in difference[order]])
        axis.set_xticks(range(len(order)))
        axis.set_xticklabels([chem[i][len(C.CHEM_PREFIX):] for i in order], rotation=75, ha="right", fontsize=5.5)
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.set_ylabel("std mean diff")
        axis.set_title("%s: generated (constraint-projected) minus real held-out, top-15 |difference|; "
                       "energy distance = %.3f" % (style, energy[style]["constrained"]), fontsize=8)
        axis.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    figures.append(C.save_fig(fig, "q3_generated_vs_real"))

    # ======================================================================================================
    # metrics / outputs
    # ======================================================================================================
    C.emit_metrics({
        "constraint-satisfaction": C.finite(satisfaction, "constraint-satisfaction"),
        "constraint-satisfaction-unconstrained": C.finite(satisfaction_unconstrained, "constraint-satisfaction-unconstrained"),
        "energy-distance": C.finite(energy_mean, "energy-distance"),
        "energy-distance-unconstrained": C.finite(energy_mean_unconstrained, "energy-distance-unconstrained"),
        "profile-consistency": C.finite(profile_mean, "profile-consistency"),
        "defect-nonworsen-rate": C.finite(nonworsen["constrained"], "defect-nonworsen-rate"),
        "defect-nonworsen-rate-rawshift": C.finite(nonworsen["rawshift"], "defect-nonworsen-rate-rawshift"),
        "transfer-satisfaction-constrained": C.finite(satisfy_transfer["constrained"], "transfer-sat-constrained"),
        "transfer-satisfaction-rawshift": C.finite(satisfy_transfer["rawshift"], "transfer-sat-rawshift"),
        "transfer-satisfaction-source": C.finite(satisfy_source, "transfer-sat-source"),
        "real_sample_constraint_satisfaction": C.finite(base_rate_all, "real_sample_constraint_satisfaction"),
        "heldout-real-base-rate": C.finite(base_rate_holdout, "heldout-real-base-rate"),
        "n_samples": int(len(constrained)),
        "n_samples_per_style": int(samples_per_style),
        "n_holdout_rows": int(holdout_mask.sum()),
        "n_train_rows": int(train_mask.sum()),
        "shrinkage": C.finite(shrinkage, "shrinkage"),
    })
    C.emit_report("evaluation", {
        "kind": "constraint-satisfaction", "metricKey": "constraint-satisfaction",
        "modelContractId": "MCON-0001", "samplesFile": "generated_profiles.csv", "tolerance": 1e-09,
        "definition": "fraction of generated rows with all seven excess__<compound> <= 0, "
                      "excess = inverse_transform(chem__<compound>)/thr__<compound> - 1 ; generated_profiles.csv "
                      "carries BOTH chem__ values and excess__ values so excess is independently recomputable",
        "family": "style-conditional multivariate Gaussian + defect-constraint projection",
        "priorStyleMapping": L.PRIOR_STYLE_MAPPING,
        "priorStylePoolsUsed": prior_pools, "styleCounts": style_counts,
        "holdoutStyles": list(L.HOLDOUT_STYLES),
        "generator": {"n_samples_per_style": samples_per_style,
                      "shrinkageMultiplier": shrinkage_multiplier,
                      "topLevelParams": {"n_samples_per_style": top_samples,
                                         "shrinkage_multiplier": top_shrinkage},
                      "shrinkage": shrinkage,
                      "covariance": "shared covariance shrunk toward its diagonal: (1-lam)*Cov + lam*diag(Cov)"},
        "transfer": {"sourceStyle": L.SOURCE_STYLE, "targetStyle": "Tripel",
                     "shift": "x' = x_source + (mu_target - mu_source) in standardised space; the seven defect "
                              "compounds stay unshifted in the constrained variant"},
        "sensoryProfile": "Ridge proxy fitted on the registered Q1 TRAIN rows; SURROGATE, not measured ratings, "
                          "not the Q1 final model",
        "unassessableDefects": list(L.UNASSESSABLE_DEFECTS),
        "scope": "generation reasonableness / constraint satisfaction / distributional consistency; "
                 "NOT a real brewing validation; no causal claim",
    })
    C.emit_report("defectCounts", {
        "thresholdsOriginalUnits": thresholds,
        "realAll250": real_counts,
        "realAll250SatisfyingAll7": int(round(base_rate_all * len(real_all_excess))),
        "realHeldoutSatisfyingAll7": int(round(base_rate_holdout * int(holdout_mask.sum()))),
        "generatedConstrained": L.exceedance_counts(excess_constrained),
        "generatedUnconstrained": L.exceedance_counts(excess_unconstrained),
        "sourcePilsLager": L.exceedance_counts(excess_source),
        "transferRawshift": L.exceedance_counts(excess_transfer["rawshift"]),
        "transferConstrained": L.exceedance_counts(excess_transfer["constrained"]),
        "clippedPerCompound": clipped,
        "scaleAuditBasis": audit["basis"],
        "unassessableDefects": list(L.UNASSESSABLE_DEFECTS),
    })
    C.emit_report("perStyle", {"generation": per_style, "energy": energy, "profile": profile,
                               "styleCounts": style_counts})
    C.emit_report("transfer", {"nonworsen": nonworsen,
                               "satisfaction": {"source": satisfy_source, **satisfy_transfer},
                               "nSourceRows": int(source_mask.sum()),
                               "deltaDefectZeroed": True})
    C.emit_report("sensoryProxy", {"label": proxy["label"], "alpha": proxy["alpha"], "nRows": proxy["nRows"],
                                   "features": len(proxy["features"]), "targets": sensory_targets,
                                   "basis": proxy["basis"],
                                   "note": "profiles in figures/metrics come from this surrogate model"})
    C.emit_report("artifacts", {"figures": figures, "seed": seed,
                                "samplesFile": "generated_profiles.csv",
                                "unconstrainedFile": "generated_profiles_unconstrained.csv",
                                "transferFile": "transfer_profiles.csv"})
    print("Q3 generate: constraint-satisfaction=%.12f unconstrained=%.12f energy=%.6f profile=%.6f "
          "nonworsen=%.6f nonworsen_raw=%.6f base_rate=%.6f"
          % (satisfaction, satisfaction_unconstrained, energy_mean, profile_mean,
             nonworsen["constrained"], nonworsen["rawshift"], base_rate_all))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
