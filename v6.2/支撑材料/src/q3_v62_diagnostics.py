#!/usr/bin/env python
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q3_v62_diagnostics.py — v6.2 review-response diagnostics for Q3 (task-2).

Two deterministic post-processing diagnostics on FROZEN artifacts. Nothing is trained, nothing under experiments/
is written, and the delivered Q3 primary metrics are left untouched.

TASK A — anchor-direct-projection ablation (review §4.1)
    The delivered Q3 transfer QP is
        min_z (z-zref)'Q_t(z-zref) + lambda||z-z_anchor||^2 + eta*sum|z-z_source|   s.t. low <= z <= up, a'z <= b
    with z_anchor the quantile-preserving anchor. The ablation keeps that SAME z_anchor and projects it DIRECTLY onto
    the SAME declared feasible set (same low/up, same arow, same corrected stale half-space b that
    "qp-quantile-anchor" uses), i.e. no PCA quadratic term and no L1 term:
        z = _project_box_halfspace(z_anchor, low, up, arow, b).
    The target-training transfer energy V is then pooled exactly as the delivered pipeline pools it (cells weighted
    by m; V computed against the fold's target reference Z_target, normalised by the fold's D_target). The five
    existing strategies are recomputed in the same run and asserted against experiments/EXP-0110.

TASK B — beer156 (Kriek) coordinate-sensitivity diagnosis (review §4.2)
    data/clean/q3.csv stores chem__X2.methyltetrahydrofuran.3.one = 12596.43287 for beer 156 (Kriek), while the
    second-largest value in that column is 76.83280489. On the three outer folds that hold beer156 out its
    fold-standardised coordinate is ~1900, which dominates the Kriek energy. Recomputing the EXP-0109 design-stage
    energy from the FROZEN generated samples and dropping that ONE coordinate simultaneously from generated, real
    and the D_train normalisation denominator gives the review's sensitivity numbers. The delivered primary metric
    keeps all 231 coordinates and is recorded unchanged (main vs "sensitivity diagnostic" are labelled separately).

TASK C — cross-set proximity of the delivered design spectra (review §3.4 follow-up)
    The delivered `copula-selected` design spectra are compared with the SAME fold's training rows
    (`X_train`, median-imputed, fold-standardised): (i) the exact whole-row cross-set duplication rate
    (any of the 231 chem__ cells differing by <= 1e-12 breaks a match) and (ii) the mean standardised
    Euclidean distance from each generated spectrum to its nearest training row. Both are reported next
    to the within-batch duplicate share (0.0000) so "no within-batch repeats" and "no training-row copies"
    are two separately measured statements. Read-only and deterministic.

Outputs (all under outputs/q3, plus the required delivery copies):
    outputs/q3/v62_diagnostics/v62_diagnostics.json
    outputs/q3/v62_tables/anchor_direct_projection.csv
    outputs/q3/v62_tables/beer156_sensitivity.csv
    copies of the three files under FINAL_SUBMISSION_v6.2/支撑材料/outputs/q3/v62_tables/

Usage (from the repo root):
    MPLCONFIGDIR=outputs/q3/v62_diagnostics/mpl python src/q3_v62_diagnostics.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT_Q3 = ROOT / "outputs" / "q3"
DIAG_DIR = OUT_Q3 / "v62_diagnostics"
TABLE_DIR = OUT_Q3 / "v62_tables"
FINAL_DIR = ROOT / "FINAL_SUBMISSION_v6.2" / "支撑材料" / "outputs" / "q3" / "v62_tables"
EXP0109 = ROOT / "experiments" / "EXP-0109"
EXP0110 = ROOT / "experiments" / "EXP-0110"
DATA_Q3 = ROOT / "data" / "clean" / "q3.csv"
SPLITS_CSV = ROOT / "data" / "splits" / "NESTED-CV-1" / "splits.csv"
FEATURE_DICTIONARY = ROOT / "data" / "processed" / "v6_feature_dictionary.csv"

# matplotlib and the frozen helper modules must not write outside outputs/q3
(DIAG_DIR / "mpl").mkdir(parents=True, exist_ok=True)
(DIAG_DIR / "run").mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(DIAG_DIR / "mpl")
os.environ["MODELING_EXPERIMENT_DIR"] = str(DIAG_DIR / "run")
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import q3_transfer_fix as TR  # noqa: E402  (installs the modeling_contract shim, then imports q3_lib)
import q3_lib as L  # noqa: E402
import v6_common as V6  # noqa: E402
import q3_v62_answer_tables as AT  # noqa: E402  (read-only: 12 reference compounds + calibration helpers)

ANCHOR_DIRECT = "anchor-direct-projection"
REFERENCE_ITEMS = tuple(name for name, _display, _note in AT.CHEM_ITEMS)
DEFECT_ITEMS = ("DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal")
COORD_FEATURE = "X2.methyltetrahydrofuran.3.one"
COORD_COLUMN = V6.CHEM_PREFIX + COORD_FEATURE
SUBSET_STYLES = ("Tripel", "Kriek", "Lambic")

# delivered by experiments/EXP-0110 (read-only cross-check of the recomputation)
CONTROL_EXPECTED = {
    "source-fixed": 7.196326285149654,
    "target-mean-projection": 6.94148284204317,
    "target-mean-projection-full": 6.379240954520166,
    "qp-source-anchor": 7.090616932081723,
    "qp-quantile-anchor": 2.0798861351916886,
}
CONTROL_EXPECTED_U = {
    "source-fixed": 4.817735233962364,
    "target-mean-projection": 5.8913686262015315,
    "target-mean-projection-full": 5.2545558755628745,
    "qp-source-anchor": 4.731512559497442,
    "qp-quantile-anchor": -0.3456899316462696,
}
# delivered by experiments/EXP-0109/energy_summary.csv (the "before" state of the sensitivity diagnostic)
SENSITIVITY_BEFORE = {
    "allStyles": 0.8726874826148657,
    "Kriek": 7.40790657499428,
    "TripelKriekLambicSubset": 1.8078909138627393,
}
SENSITIVITY_AFTER_ROUNDED = {
    "allStyles": 0.5975,
    "Kriek": 0.7186,
    "TripelKriekLambicSubset": 0.4427,
}

ASSERTIONS: dict[str, dict] = {}


# -------------------------------------------------------------------------------------------------- helpers
def json_safe(value):
    """Recursively replace non-finite floats with JSON null so the JSON is strict (no NaN/Infinity tokens)."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weighted_mean(values, weights) -> float:
    total = 0.0
    numerator = 0.0
    for value, weight in zip(values, weights):
        total += float(weight)
        numerator += float(value) * float(weight)
    return numerator / total


def record(name: str, expected, actual, passed: bool, note: str = "") -> None:
    ASSERTIONS[name] = {"expected": expected, "actual": actual, "passed": bool(passed)}
    if note:
        ASSERTIONS[name]["note"] = note


def check_close(name: str, expected: float, actual: float, tol: float = 1e-9) -> None:
    record(name, expected, actual, abs(float(actual) - float(expected)) <= tol,
           note="abs tolerance %g" % tol)


def check_rounded(name: str, expected: float, actual: float, ndigits: int) -> None:
    record(name, expected, actual, round(float(actual), ndigits) == expected,
           note="round(actual, %d) == expected" % ndigits)


def fold_indices(splits, index_of, repeat: int, fold: int) -> tuple:
    train_beers = test_beers = None
    for rep, f, train, test in V6.iter_outer(splits):
        if rep == repeat and f == fold:
            train_beers, test_beers = train, test
            break
    if train_beers is None:
        raise RuntimeError("frozen splits have no outer fold repeat=%d fold=%d" % (repeat, fold))
    return (np.array([index_of[int(b)] for b in train_beers], dtype=int),
            np.array([index_of[int(b)] for b in test_beers], dtype=int))


def fold_standardizer(X_raw, train_idx):
    """The EXP-0109 fold standardisation: train-fold median imputation, then mean/std of the imputed training rows."""
    raw_train = np.asarray(X_raw[train_idx], dtype=float)
    medians = L.column_medians(raw_train)
    X_train = L.apply_median(raw_train, medians)
    centre, scale = L.fit_standardizer(X_train)
    return medians, X_train, centre, scale


def load_data():
    frame, X_raw, Y, styles, beers = TR.load_data()
    return {"frame": frame, "X_raw": X_raw, "Y": Y, "styles": styles, "beers": beers,
            "index_of": {int(b): i for i, b in enumerate(beers)}}


def load_samples() -> pd.DataFrame:
    """The delivered 750 design spectra, read from the per-repeat files and checked against samples.csv."""
    parts = [pd.read_csv(EXP0109 / ("samples-repeat-%d.csv" % repeat)) for repeat in range(3)]
    samples = pd.concat(parts, ignore_index=True)
    if samples.shape[0] != 750:
        raise RuntimeError("samples-repeat-*.csv hold %d rows, expected 750" % samples.shape[0])
    if not bool(samples[L.CHEM_COLS].notna().all().all()):
        raise RuntimeError("generated samples contain NaN in a chem__ column")
    delivered = pd.read_csv(EXP0109 / "samples.csv")
    if sorted(samples["sample_id"].tolist()) != sorted(delivered["sample_id"].tolist()):
        raise RuntimeError("samples-repeat-*.csv do not cover the same sample ids as samples.csv")
    return samples


def load_feature_meta() -> dict:
    """Per-column tier / storage scale / unit, from the same dictionary the v6.2 entity tables use."""
    table = pd.read_csv(FEATURE_DICTIONARY)
    if table.shape[0] != 231:
        raise RuntimeError("feature dictionary holds %d columns, expected 231" % table.shape[0])
    return {str(record["name"]): record for record in table.to_dict("records")}


def column_tier(meta: dict) -> str:
    tier = str(meta["tier"])
    return tier if tier in ("calibrated_log10", "calibrated_linear") else "uncalibrated"


def storage_scale_label(tier: str) -> str:
    return tier if tier in ("calibrated_log10", "calibrated_linear") else "uncalibrated"


def unit_declared_text(unit: str) -> str:
    return "no" if unit in ("not declared in 8.xlsx", "A.U.") else "yes"


def anchor_physical_value(name: str, tier: str, stored: float) -> float:
    """Exactly the entity-table calibration (src/q3_v62_answer_tables.to_physical); uncalibrated -> NaN."""
    if tier == "uncalibrated":
        return float("nan")
    return float(AT.to_physical(name, np.array([float(stored)], dtype=float))[0])


# ================================================================================================== TASK A
def task_a_anchor_direct(data, splits) -> tuple:
    X_raw, Y, styles, beers, index_of = (data["X_raw"], data["Y"], data["styles"],
                                         data["beers"], data["index_of"])
    all_beers = np.asarray(beers, dtype=int)
    source_rows_all = np.nonzero(styles == TR.SOURCE_STYLE)[0]
    if source_rows_all.size != 11:
        raise RuntimeError("expected 11 Pils/Lager source beers, found %d" % source_rows_all.size)
    strategies = list(TR.STRATEGIES) + [ANCHOR_DIRECT]
    feature_meta = load_feature_meta()
    anchor_rows = []
    anchor_feasibility = {"nPoints": 0, "nInsideBox": 0, "nStaleSatisfied": 0,
                          "maxBoxViolation": 0.0, "maxStaleResidual": 0.0,
                          "boxViolationColumnCounts": {}}
    anchor_stored_vs_quantile_max = 0.0
    representative = None
    representative_reconstruction_error = None
    cells = []
    point_rows = []
    point_l1 = {strategy: [] for strategy in strategies}
    point_mean_abs = {strategy: [] for strategy in strategies}
    chemistry_residual_max = 0.0
    max_chemistry_residual = 0.0
    qp_status = {"solves": 0, "optimal": 0, "not_converged": 0, "infeasible": 0, "fallback": 0}

    for repeat in range(3):
        for fold in range(3):
            train_idx, _ = fold_indices(splits, index_of, repeat, fold)
            context_idx = train_idx[styles[train_idx] != TR.SOURCE_STYLE]
            ctx = TR.fit_transfer_context(X_raw, Y, styles, context_idx, repeat, fold)
            training_source = np.nonzero((styles == TR.SOURCE_STYLE)
                                         & np.isin(all_beers, all_beers[train_idx]))[0]
            reference_rows = training_source if training_source.size >= 2 else source_rows_all
            raw_reference = np.asarray(X_raw[reference_rows], dtype=float)
            X_reference = L.apply_median(raw_reference, ctx["medians"])
            source_marginals = L.StyleMarginals(0.0, ctx["codes"]).fit(
                X_reference, np.array([TR.SOURCE_STYLE] * X_reference.shape[0]),
                valid=np.isfinite(raw_reference))
            point_records = {strategy: [] for strategy in strategies}
            for source_row in source_rows_all:
                beer = int(beers[source_row])
                raw_source = np.asarray(X_raw[source_row], dtype=float)
                x_source = L.apply_median(raw_source.reshape(1, -1), ctx["medians"])[0]
                uniforms = source_marginals.forward(TR.SOURCE_STYLE, x_source.reshape(1, -1))
                quantile_anchor = ctx["marginals"].inverse(TR.TARGET_STYLE, uniforms)[0]
                problem = TR.build_problem(ctx, x_source, quantile_anchor, x_raw_source=raw_source)
                if not problem["feasible_set_nonempty"]:
                    raise RuntimeError("declared feasible set is empty at R%d-F%d-B%03d"
                                       % (repeat, fold, beer))
                # ---- the REAL quantile anchor fed to build_problem; exported for the paper's transfer table
                z_anchor = np.asarray(problem["z_anchor"], dtype=float)
                anchor_stored = ctx["centre"] + ctx["scale"] * z_anchor
                anchor_stored_vs_quantile_max = max(
                    anchor_stored_vs_quantile_max,
                    float(np.max(np.abs(anchor_stored - np.asarray(quantile_anchor, dtype=float)))))
                box_violation = (np.maximum(problem["low"] - z_anchor, 0.0)
                                 + np.maximum(z_anchor - problem["up"], 0.0))
                anchor_feasibility["nPoints"] += 1
                if float(box_violation.max()) <= 1e-12:
                    anchor_feasibility["nInsideBox"] += 1
                anchor_feasibility["maxBoxViolation"] = max(anchor_feasibility["maxBoxViolation"],
                                                            float(box_violation.max()))
                for j in np.nonzero(box_violation > 1e-12)[0]:
                    column_name = L.FEATURE_COLS[int(j)]
                    counts = anchor_feasibility["boxViolationColumnCounts"]
                    counts[column_name] = counts.get(column_name, 0) + 1
                stale_residual = float(problem["arow"] @ z_anchor - problem["stale_cap"])
                anchor_feasibility["maxStaleResidual"] = max(anchor_feasibility["maxStaleResidual"],
                                                             stale_residual)
                if stale_residual <= 1e-12:
                    anchor_feasibility["nStaleSatisfied"] += 1
                for j, column_name in enumerate(L.FEATURE_COLS):
                    meta = feature_meta[column_name]
                    tier = column_tier(meta)
                    stored = float(anchor_stored[j])
                    note = ""
                    if tier == "uncalibrated":
                        note = "storage scale only (uncalibrated): physical value not identified"
                    elif column_name in ctx["codes"] and np.isclose(stored, ctx["codes"][column_name],
                                                                    rtol=1e-6, atol=0.0):
                        note = ("anchor sits on the detected non-detect atom; physical = 10**storage per the "
                                "calibrated_log10 rule")
                    anchor_rows.append({
                        "repeat": int(repeat), "fold": int(fold), "source_beer": beer,
                        "column": L.CHEM_COLS[j], "src_stored": float(raw_source[j]),
                        "anchor_stored": stored,
                        "anchor_physical": anchor_physical_value(column_name, tier, stored),
                        "storage_scale": storage_scale_label(tier),
                        "unit": str(meta["unit_or_scale"]),
                        "unit_declared": unit_declared_text(str(meta["unit_or_scale"])),
                        "note": note,
                    })
                if representative is None and repeat == 0 and fold == 0 and beer == 28:
                    # independent route: refit the source empirical CDF, push through the target marginal inverse
                    source_marginals_check = L.StyleMarginals(0.0, ctx["codes"]).fit(
                        X_reference, np.array([TR.SOURCE_STYLE] * X_reference.shape[0]),
                        valid=np.isfinite(raw_reference))
                    uniforms_check = source_marginals_check.forward(TR.SOURCE_STYLE, x_source.reshape(1, -1))
                    reconstructed = ctx["marginals"].inverse(TR.TARGET_STYLE, uniforms_check)[0]
                    representative_reconstruction_error = float(
                        np.max(np.abs(np.asarray(reconstructed, dtype=float) - anchor_stored)))
                    representative_items = []
                    for name in list(REFERENCE_ITEMS) + list(DEFECT_ITEMS):
                        j = L.FEATURE_COLS.index(name)
                        meta = feature_meta[name]
                        tier = column_tier(meta)
                        stored = float(anchor_stored[j])
                        representative_items.append({
                            "column": L.CHEM_COLS[j], "name": name,
                            "group": ("reference_compound" if name in REFERENCE_ITEMS else "defect"),
                            "storage_scale": storage_scale_label(tier),
                            "unit": str(meta["unit_or_scale"]),
                            "unit_declared": unit_declared_text(str(meta["unit_or_scale"])),
                            "z_anchor": float(z_anchor[j]),
                            "anchor_stored": stored,
                            "anchor_physical": anchor_physical_value(name, tier, stored),
                        })
                    stale_anchor_score = float(problem["arow"] @ z_anchor
                                               + problem["stale_intercept_c"])
                    representative = {
                        "selectionRule": "repeat=0, outer fold=0, smallest Pils/Lager source_beer id",
                        "repeat": 0, "fold": 0, "source_beer": 28,
                        "seed": int(V6.SEEDS[0]),
                        "nSourceBeers": int(source_rows_all.size),
                        "sourceBeerIds": [int(beers[i]) for i in source_rows_all],
                        "columnNaming": ("column = the q3.csv storage name including the chem__ prefix; "
                                         "anchor_stored = centre + scale * z_anchor = the quantile_anchor_storage "
                                         "vector actually passed to build_problem"),
                        "items": representative_items,
                        "staleHopsProxy": {
                            "column": "stale_hops (sensory ridge proxy, NOT one of the 231 chem__ features)",
                            "unit": "standardized sensory label", "unit_declared": "no",
                            "proxy_score_at_anchor": stale_anchor_score,
                            "proxy_score_at_source": float(problem["stale_prediction_source"]),
                            "halfspace_b": float(problem["stale_cap"]),
                            "halfspace_residual_at_anchor": float(problem["arow"] @ z_anchor
                                                                  - problem["stale_cap"]),
                            "satisfied": bool(float(problem["arow"] @ z_anchor
                                                    - problem["stale_cap"]) <= 1e-12),
                        },
                        "reconstruction": {
                            "maxAbsError": representative_reconstruction_error,
                            "tolerance": 1e-12,
                            "route": ("refit StyleMarginals(omega=0) on the fold's Pils/Lager training rows -> "
                                      "source empirical CDF -> target StyleMarginals(KAPPA).inverse -> storage "
                                      "vector; compared with centre + scale*z_anchor from build_problem"),
                        },
                        "feasibility": {
                            "insideDeclaredBox": bool(float(box_violation.max()) <= 1e-12),
                            "boxViolationMax": float(box_violation.max()),
                            "boxViolationColumns": [L.FEATURE_COLS[int(j)] for j in
                                                    np.nonzero(box_violation > 1e-12)[0]],
                            "staleHalfspaceSatisfied": bool(stale_residual <= 1e-12),
                            "staleHalfspaceResidual": stale_residual,
                            "note": ("reported honestly: the raw quantile anchor is NOT required to be feasible. "
                                     "The declared box caps the four source-capped chemistry columns at c_source "
                                     "and the stale proxy row is a'z<=b; the QP/projection enforces both. "
                                     "Box violations occur only on those capped chemistry coordinates."),
                        },
                    }
                for strategy in strategies:
                    fallback = False
                    if strategy == "source-fixed":
                        z = np.array(problem["z_source"], dtype=float, copy=True)
                    elif strategy == "target-mean-projection":
                        z = np.clip(problem["zref"], problem["low"], problem["up"])
                    elif strategy == "target-mean-projection-full":
                        z = TR._project_box_halfspace(problem["zref"], problem["low"], problem["up"],
                                                      problem["arow"], problem["stale_cap"])
                    elif strategy == ANCHOR_DIRECT:
                        # THE ablation: direct projection of the SAME quantile anchor onto the SAME feasible set.
                        z = TR._project_box_halfspace(problem["z_anchor"], problem["low"], problem["up"],
                                                      problem["arow"], problem["stale_cap"])
                    else:
                        anchor = (problem["z_anchor"] if strategy == "qp-quantile-anchor"
                                  else problem["z_source"])
                        solved = TR.admm_qp(ctx, problem["zref"], anchor, problem["z_source"],
                                            problem["low"], problem["up"], problem["arow"],
                                            problem["stale_cap"], TR.LAMBDA, TR.ETA)
                        qp_status["solves"] += 1
                        converged = (solved["primal_residual"] < TR.ADMM_TOL
                                     and solved["dual_residual"] < TR.ADMM_TOL)
                        violation = max(float(np.max(np.maximum(problem["low"] - solved["w"], 0.0))),
                                        float(np.max(np.maximum(solved["w"] - problem["up"], 0.0))),
                                        max(0.0, float(problem["arow"] @ solved["w"]) - problem["stale_cap"]))
                        feasible = violation <= 1e-8
                        if converged:
                            qp_status["optimal"] += 1
                        else:
                            qp_status["not_converged"] += 1
                        fallback = not (converged and feasible)
                        if fallback:
                            qp_status["fallback"] += 1
                        z = (np.array(problem["z_source"], dtype=float, copy=True) if fallback
                             else solved["w"])
                    # deliver in storage space and re-standardise there, exactly as the delivered pipeline does
                    x_new = ctx["centre"] + ctx["scale"] * np.asarray(z, dtype=float)
                    z_eval = (np.asarray(x_new, dtype=float) - ctx["centre"]) / ctx["scale"]
                    delivered = TR.delivered_metrics(
                        ctx, x_source, x_new, problem, strategy,
                        {"repeat": int(repeat), "fold": int(fold), "source_beer": beer})
                    box_lower = float(np.max(np.maximum(problem["low"] - z_eval, 0.0)))
                    box_upper = float(np.max(np.maximum(z_eval - problem["up"], 0.0)))
                    halfspace = max(0.0, float(problem["arow"] @ z_eval) - problem["stale_cap"])
                    point_records[strategy].append({
                        "beer": beer, "fallback": bool(fallback), "z": z_eval,
                        "box_lower": box_lower, "box_upper": box_upper, "halfspace": halfspace,
                        "max_violation": max(box_lower, box_upper, halfspace),
                        "halfspace_residual": float(delivered["stale_halfspace_residual"]),
                        "n_constraint_violations": int(delivered["n_constraint_violations"]),
                        "l1_change_z": float(delivered["l1_change_z"]),
                        "mean_abs_change_z": float(delivered["mean_abs_change_z"]),
                    })
                    point_l1[strategy].append(float(delivered["l1_change_z"]))
                    point_mean_abs[strategy].append(float(delivered["mean_abs_change_z"]))
                    if strategy == ANCHOR_DIRECT:
                        chemistry_residual_max = 0.0
                        for name in TR.CAPPED_CHEMISTRY:
                            j = L.FEATURE_COLS.index(name)
                            before = float(L.physical_conc(name, np.array([x_source[j]]), ctx["codes"])[0])
                            after = float(L.physical_conc(name, np.array([x_new[j]]), ctx["codes"])[0])
                            chemistry_residual_max = max(chemistry_residual_max, after - before)
                        max_chemistry_residual = max(max_chemistry_residual, chemistry_residual_max)
                        point_rows.append({
                            "repeat": int(repeat), "fold": int(fold), "source_beer": beer,
                            "box_lower_violation": box_lower, "box_upper_violation": box_upper,
                            "stale_halfspace_residual": float(delivered["stale_halfspace_residual"]),
                            "stale_halfspace_violation": halfspace,
                            "max_violation": max(box_lower, box_upper, halfspace),
                            "chemistry_nonincrease_residual": chemistry_residual_max,
                            "n_constraint_violations": int(delivered["n_constraint_violations"]),
                            "l1_change_z": float(delivered["l1_change_z"]),
                            "mean_abs_change_z": float(delivered["mean_abs_change_z"]),
                        })
            # ---- energy cell per strategy, exactly as q3_transfer_fix pools it
            real = ctx["Z_target"]
            for strategy in strategies:
                good = [entry for entry in point_records[strategy] if not entry["fallback"]]
                gen = np.stack([entry["z"] for entry in good])
                terms = L.energy_distance_terms(gen, real)
                cells.append({
                    "repeat": int(repeat), "fold": int(fold), "strategy": strategy,
                    "m": int(terms["m"]), "n": int(terms["n"]), "d_target": float(ctx["d_target"]),
                    "V": float(terms["V"]), "U": float(terms["U"]),
                    "V_normalized": float(terms["V"]) / float(ctx["d_target"]),
                    "max_violation": max(entry["max_violation"] for entry in point_records[strategy]),
                    "n_points_with_violation": int(sum(1 for entry in point_records[strategy]
                                                       if entry["max_violation"] > 1e-9)),
                    "n_points_with_delivered_violation": int(sum(
                        1 for entry in point_records[strategy] if entry["n_constraint_violations"] > 0)),
                    "n_fallback": int(sum(1 for entry in point_records[strategy] if entry["fallback"])),
                })

    # ---- pooled per strategy (the delivered pooling: cells weighted by m; V_normalized is V/D_target per cell)
    pooled = {}
    for strategy in strategies:
        block = [cell for cell in cells if cell["strategy"] == strategy]
        pooled[strategy] = {
            "V": weighted_mean([cell["V"] for cell in block], [cell["m"] for cell in block]),
            "U": weighted_mean([cell["U"] for cell in block], [cell["m"] for cell in block]),
            "V_normalized": weighted_mean([cell["V_normalized"] for cell in block],
                                          [cell["m"] for cell in block]),
            "nPoints": int(sum(cell["m"] for cell in block)),
            "nCells": len(block),
            "perFold": [{"repeat": cell["repeat"], "fold": cell["fold"], "V": cell["V"], "U": cell["U"],
                         "V_normalized": cell["V_normalized"], "m": cell["m"], "n": cell["n"],
                         "d_target": cell["d_target"]} for cell in block],
        }

    # ---- control cross-check against the frozen EXP-0110 artifact
    artifact = json.load(open(EXP0110 / "transfer_outputs.json", encoding="utf-8"))["q3_transfer"]
    artifact_energy = artifact["energy_by_strategy"]
    max_control_diff = 0.0
    for strategy in TR.STRATEGIES:
        delivered = artifact_energy[strategy]
        max_control_diff = max(max_control_diff,
                               abs(pooled[strategy]["V"] - delivered["V"]),
                               abs(pooled[strategy]["U"] - delivered["U"]),
                               abs(pooled[strategy]["V_normalized"] - delivered["V_normalized"]))
        for cell, reference in zip(pooled[strategy]["perFold"], delivered["perFold"]):
            if (cell["repeat"], cell["fold"]) != (reference["repeat"], reference["fold"]):
                raise RuntimeError("per-fold order differs from the EXP-0110 artifact for %r" % strategy)
            max_control_diff = max(max_control_diff, abs(cell["V"] - reference["V"]),
                                   abs(cell["U"] - reference["U"]),
                                   abs(cell["V_normalized"] - reference["V_norm"]))
    record("controls_match_EXP0110_artifact", 0.0, max_control_diff, max_control_diff <= 1e-9,
           note="max abs diff over V, U, V_normalized pooled and 9 per-fold cells x 5 strategies")
    for strategy, expected in CONTROL_EXPECTED.items():
        check_close("control_%s_V" % strategy, expected, pooled[strategy]["V"])
        check_close("control_%s_U" % strategy, CONTROL_EXPECTED_U[strategy], pooled[strategy]["U"])
    for strategy in ("target-mean-projection", "target-mean-projection-full"):
        check_close("control_%s_V_normalized" % strategy,
                    artifact_energy[strategy]["V_normalized"], pooled[strategy]["V_normalized"])

    # ---- the ablation's own assertions
    direct = pooled[ANCHOR_DIRECT]
    qp = pooled["qp-quantile-anchor"]
    n_points = len(point_rows)
    n_bad = int(sum(1 for row in point_rows if row["max_violation"] > 1e-9))
    max_violation = float(max([row["max_violation"] for row in point_rows] + [max_chemistry_residual]))
    record("anchorDirect_n_points", 99, n_points, n_points == 99)
    record("anchorDirect_n_points_with_violation", 0, n_bad, n_bad == 0)
    record("anchorDirect_max_constraint_violation", 0.0, max_violation, max_violation <= 1e-9,
           note="max over the 99 points of max(box lower, box upper, stale half-space, chemistry non-increase)")
    record("anchorDirect_chemistry_nonincrease_residual_max", 0.0, max_chemistry_residual,
           max_chemistry_residual <= 1e-12, note="physical c_new - c_source; must be <= 0 (fp tolerance)")
    record("anchorDirect_delivered_constraint_violations_total", 0,
           int(sum(row["n_constraint_violations"] for row in point_rows)),
           sum(row["n_constraint_violations"] for row in point_rows) == 0,
           note="delivered_metrics: four chemistry non-increase checks + stale proxy row per point")
    check_rounded("anchorDirect_V", 2.0903, direct["V"], 4)
    record("anchorDirect_V_near_2.0903", 2.0903, direct["V"],
           abs(direct["V"] - 2.0903) <= 1e-4,
           note="the full-precision value is stored in this dict; the review quotes 2.0903")

    refinement_abs = direct["V"] - qp["V"]
    refinement_pct = 100.0 * refinement_abs / direct["V"]
    check_rounded("refinement_relative_percent", 0.50, refinement_pct, 2)

    # ---- L1 control: the QP's explicit L1 term vs the plain projection, over the same 99 points
    qp_l1 = np.asarray(point_l1["qp-quantile-anchor"], dtype=float)
    direct_l1 = np.asarray(point_l1[ANCHOR_DIRECT], dtype=float)
    qp_ma = np.asarray(point_mean_abs["qp-quantile-anchor"], dtype=float)
    direct_ma = np.asarray(point_mean_abs[ANCHOR_DIRECT], dtype=float)
    l1_reduction_pct = 100.0 * (float(direct_l1.mean()) - float(qp_l1.mean())) / float(direct_l1.mean())
    record("qp_has_smaller_mean_L1_than_direct_projection", "qp mean L1 < direct mean L1",
           [float(qp_l1.mean()), float(direct_l1.mean())],
           bool(qp_l1.mean() < direct_l1.mean()),
           note="the QP's eta*sum|z-z_source| term is its explicit L1 control")
    l1_comparison = {
        "definition": ("l1_change_z = sum_i |z_i - z_source,i| in the fold-standardised space; mean_abs_change_z "
                       "is the same divided by 231. Both are evaluated on the DELIVERED point (99 points each: "
                       "11 sources x 3 repeats x 3 folds)."),
        "qp_quantile": {"meanL1ChangeZ": float(qp_l1.mean()), "medianL1ChangeZ": float(np.median(qp_l1)),
                        "meanMeanAbsChangeZ": float(qp_ma.mean())},
        "anchor_direct": {"meanL1ChangeZ": float(direct_l1.mean()), "medianL1ChangeZ": float(np.median(direct_l1)),
                          "meanMeanAbsChangeZ": float(direct_ma.mean())},
        "relative_l1_reduction_percent_of_anchor_direct": l1_reduction_pct,
        "interpretation": ("the plain projection has the larger mean L1 move; the QP trades ~0.50%% of distance "
                           "refinement for ~%.2f%% smaller L1 displacement, which is its declared explicit control "
                           "on how far a source beer may move" % l1_reduction_pct),
    }

    # ---- exported anchor values: independent reconstruction + honest feasibility
    record("representative_source_beer", 28,
           representative["source_beer"] if representative else None,
           representative is not None and representative["source_beer"] == 28,
           note="fixed rule: repeat=0, outer fold=0, smallest Pils/Lager source beer id")
    record("representative_anchor_reconstruction_max_abs_error", 0.0,
           representative_reconstruction_error,
           representative_reconstruction_error is not None
           and representative_reconstruction_error <= 1e-12,
           note="independent route: source empirical CDF -> target style marginal inverse -> storage vector; "
                "compared with centre + scale*z_anchor from build_problem; tolerance 1e-12")
    record("anchor_stored_equals_build_problem_anchor_input_max_abs", 0.0,
           anchor_stored_vs_quantile_max, anchor_stored_vs_quantile_max <= 1e-12,
           note="centre + scale*z_anchor vs the quantile_anchor_storage vector actually passed to build_problem")
    record("all_anchor_box_violations_only_on_declared_chemistry_caps", True,
           sorted(anchor_feasibility["boxViolationColumnCounts"]),
           set(anchor_feasibility["boxViolationColumnCounts"]) <= set(TR.CAPPED_CHEMISTRY),
           note=("honest feasibility: %d/%d raw quantile anchors lie outside the capped box; every violating "
                 "coordinate is a declared source-capped chemistry column (c_new<=c_source), which the QP / "
                 "projection enforces" % (anchor_feasibility["nPoints"] - anchor_feasibility["nInsideBox"],
                                          anchor_feasibility["nPoints"])))
    record("representative_anchor_box_violations_only_on_declared_chemistry_caps", True,
           representative["feasibility"]["boxViolationColumns"] if representative else None,
           representative is not None
           and set(representative["feasibility"]["boxViolationColumns"]) <= set(TR.CAPPED_CHEMISTRY))
    record("representative_anchor_stale_halfspace_residual_reported",
           "reported honestly (anchor not required to satisfy the proxy row)",
           representative["staleHopsProxy"]["halfspace_residual_at_anchor"] if representative else None,
           representative is not None,
           note="the raw anchor is not forced onto the stale_hops proxy row a'z<=b; the QP enforces it. "
                "Residual reported for transparency")

    return {
        "label": "MAIN-DERIVED DIAGNOSTIC: the delivered Q3 transfer remains qp-quantile-anchor "
                 "(V = 2.0798861351916886); this ablation is not a replacement",
        "definition": {
            "ablation": ("keep the main scheme's quantile anchor z_anchor and project it DIRECTLY onto the declared "
                         "feasible set with _project_box_halfspace(z_anchor, low, up, arow, b): no PCA quadratic "
                         "term and no L1 term"),
            "feasibleSet": ("low <= z <= up (declared training support, 33 LINEAR_CALIBRATED columns >= 0, four "
                            "per-coordinate chemistry caps c_new <= c_source) and the single corrected stale_hops "
                            "half-space a'z <= b with b = a'z_source + 1e-9; identical low/up/arow/b to "
                            "qp-quantile-anchor"),
            "energy": ("V = 2*mean d(G,R) - sum d(G,G)/m^2 - sum d(R,R)/n^2 against the fold's target-style "
                       "training reference Z_target; pooled over cells weighting by m (the delivered pooling)"),
            "protocol": "11 Pils/Lager source beers x 3 repeats x 3 outer folds = 99 projected points",
        },
        "perFold": [{key: cell[key] for key in ("repeat", "fold", "m", "n", "d_target", "V", "U",
                                                "V_normalized", "max_violation", "n_points_with_violation",
                                                "n_points_with_delivered_violation", "n_fallback")}
                    for cell in cells if cell["strategy"] == ANCHOR_DIRECT],
        "pooled": {key: direct[key] for key in ("V", "U", "V_normalized", "nPoints", "nCells")},
        "residuals": {
            "box_lower_violation_max": float(max(row["box_lower_violation"] for row in point_rows)),
            "box_upper_violation_max": float(max(row["box_upper_violation"] for row in point_rows)),
            "stale_halfspace_residual_max": float(max(row["stale_halfspace_residual"] for row in point_rows)),
            "stale_halfspace_violation_max": float(max(row["stale_halfspace_violation"] for row in point_rows)),
            "chemistry_physical_nonincrease_residual_max": float(max_chemistry_residual),
            "max_constraint_violation": float(max_violation),
            "delivered_constraint_violations_total": int(sum(row["n_constraint_violations"]
                                                             for row in point_rows)),
            "note": ("box/half-space residuals are the projection's own feasibility residuals; the delivered "
                     "constraint violations are the physical chemistry non-increase checks plus the proxy row"),
        },
        "exportedAnchorValues": {
            "file": "outputs/q3/v62_tables/transfer_anchor_values.csv",
            "nRows": int(len(anchor_rows)), "nPoints": int(anchor_feasibility["nPoints"]),
            "nColumns": int(len(L.FEATURE_COLS)),
            "columnNaming": "column = q3.csv storage name including the chem__ prefix",
            "src_stored": "the raw stored source cell from data/clean/q3.csv (blank when the source cell is NaN)",
            "anchor_stored": "centre + scale * z_anchor = the quantile_anchor_storage vector used by build_problem",
            "anchor_physical": ("10**anchor_stored for calibrated_log10, anchor_stored for calibrated_linear, "
                                "NaN for uncalibrated columns (src/q3_v62_answer_tables.to_physical)"),
            "note": ("the raw quantile anchor is not projected; the QP / anchor-direct-projection start from it. "
                     "This file lets the paper quote the actual anchor values instead of 'not persisted'."),
        },
        "representativeAnchor": representative,
        "rawAnchorFeasibility": {
            "label": "honest feasibility of the RAW quantile anchor (before projection / QP)",
            "nPoints": int(anchor_feasibility["nPoints"]),
            "nInsideBox": int(anchor_feasibility["nInsideBox"]),
            "nOutsideBox": int(anchor_feasibility["nPoints"] - anchor_feasibility["nInsideBox"]),
            "nStaleHalfspaceSatisfied": int(anchor_feasibility["nStaleSatisfied"]),
            "maxBoxViolation": float(anchor_feasibility["maxBoxViolation"]),
            "maxStaleHalfspaceResidual": float(anchor_feasibility["maxStaleResidual"]),
            "boxViolationColumnCounts": dict(sorted(anchor_feasibility["boxViolationColumnCounts"].items())),
            "note": ("reported honestly: the raw quantile anchor is not a feasible point of the declared set. All "
                     "box violations sit on the four source-capped chemistry columns; the stale proxy row is "
                     "violated part of the time. This is exactly why the delivered pipeline projects / optimises "
                     "the anchor, and it is not a defect of the anchor export."),
        },
        "pointRows": point_rows,
        "controls": {strategy: {"V": pooled[strategy]["V"], "U": pooled[strategy]["U"],
                                "V_normalized": pooled[strategy]["V_normalized"],
                                "nPoints": pooled[strategy]["nPoints"],
                                "perFold": pooled[strategy]["perFold"]}
                     for strategy in TR.STRATEGIES},
        "refinement": {
            "V_anchor_direct": direct["V"], "V_qp_quantile": qp["V"],
            "absolute_improvement": refinement_abs,
            "relative_percent_of_anchor_direct": refinement_pct,
            "formula": "(V_anchor_direct - V_qp_quantile) / V_anchor_direct * 100",
            "interpretation": ("the quantile anchor provides nearly all of the distance gain; the QP adds ~%.2f%% "
                               "distance refinement on top of it, plus the explicit L1 control"
                               % refinement_pct),
        },
        "l1Comparison": l1_comparison,
        "qpStatus": qp_status,
    }, anchor_rows


# ================================================================================================== TASK B
def task_b_beer156(data, splits, samples) -> dict:
    X_raw, styles, beers, index_of = data["X_raw"], data["styles"], data["beers"], data["index_of"]
    all_beers = np.asarray(beers, dtype=int)
    if COORD_COLUMN not in L.CHEM_COLS:
        raise RuntimeError("coordinate %r is not one of the frozen 231 chem__ columns" % COORD_COLUMN)
    j = L.CHEM_COLS.index(COORD_COLUMN)
    stored = np.asarray(X_raw[:, j], dtype=float)
    finite = np.isfinite(stored)
    row156 = index_of[156]
    value156 = float(stored[row156])
    order = np.argsort(-np.where(finite, stored, -np.inf))
    rank = int(np.nonzero(order == row156)[0][0]) + 1
    second_row = int(order[1])
    second_value = float(stored[second_row])
    if styles[row156] != "Kriek":
        raise RuntimeError("beer 156 is %r, expected Kriek" % styles[row156])
    check_close("coordinate_beer156_stored_value", 12596.4329, value156, tol=1e-4)
    check_close("coordinate_second_largest_value", 76.8328, second_value, tol=1e-4)
    record("coordinate_second_largest_beer", 177, int(beers[second_row]), int(beers[second_row]) == 177)
    record("coordinate_beer156_rank", 1, rank, rank == 1)
    coordinate = {
        "storedColumn": COORD_COLUMN,
        "featureColumn": COORD_FEATURE,
        "featureIndex": int(j),
        "storageTier": ("LINEAR_CALIBRATED (stored as the concentration; non-negativity applies)"
                        if COORD_FEATURE in L.LINEAR_SET else "not in the 33 LINEAR_CALIBRATED columns"),
        "declaredDefectThreshold": False,
        "beer": 156, "style": "Kriek",
        "storedValue": value156,
        "secondLargestValue": second_value,
        "secondLargestBeer": int(beers[second_row]),
        "maxOverSecondRatio": value156 / second_value,
        "rankOfBeer156": rank,
        "nRows": int(finite.sum()),
        "nMissing": int((~finite).sum()),
        "minimum": float(np.nanmin(stored)),
        "q25": float(np.nanquantile(stored, 0.25)),
        "median": float(np.nanmedian(stored)),
        "mean": float(np.nanmean(stored)),
        "q75": float(np.nanquantile(stored, 0.75)),
        "q90": float(np.nanquantile(stored, 0.90)),
        "q99": float(np.nanquantile(stored, 0.99)),
        "std": float(np.nanstd(stored)),
        "mad": float(np.nanmedian(np.abs(stored - np.nanmedian(stored)))),
        "top5": [float(value) for value in np.sort(stored[np.isfinite(stored)])[::-1][:5]],
        "note": ("this column has no declared defect threshold; the outlier is a real stored value, not a missing/"
                 "floor code (0 missing, no repeated detection-limit atom)"),
    }

    # ---- per-fold standardisation of beer156 + per-cell design energy (EXP-0109 design stage, copula-selected)
    cells = []
    coordinate_by_fold = []
    held_out_folds = set()
    for repeat in range(3):
        for fold in range(3):
            train_idx, test_idx = fold_indices(splits, index_of, repeat, fold)
            medians, X_train, centre, scale = fold_standardizer(X_raw, train_idx)
            Z_std_train = L.standardize(X_train, centre, scale)
            styles_train = styles[train_idx]
            beer156_held_out = bool(156 in set(all_beers[test_idx].tolist()))
            if beer156_held_out:
                held_out_folds.add((repeat, fold))
                z156 = (value156 - float(centre[j])) / float(scale[j])
                coordinate_by_fold.append({
                    "repeat": int(repeat), "fold": int(fold),
                    "seed": int(V6.SEEDS[repeat]),
                    "beer156InOuterTest": True,
                    "trainFoldCentre": float(centre[j]), "trainFoldScale": float(scale[j]),
                    "trainFoldNRows": int(train_idx.size),
                    "standardizedCoordinate": float(z156),
                })
            for style in sorted(set(styles[test_idx].tolist())):
                test_rows = test_idx[styles[test_idx] == style]
                real_z = L.standardize(L.apply_median(np.asarray(X_raw[test_rows], dtype=float), medians),
                                      centre, scale)
                gen = samples[(samples["repeat"] == repeat) & (samples["fold"] == fold)
                              & (samples["style"] == style)]
                if gen.shape[0] != test_rows.size:
                    raise RuntimeError("sample count mismatch at R%d-F%d %s: %d generated vs %d real"
                                       % (repeat, fold, style, gen.shape[0], test_rows.size))
                gen_z = L.standardize(gen[L.CHEM_COLS].to_numpy(dtype=float), centre, scale)
                m, n = int(gen_z.shape[0]), int(real_z.shape[0])
                estimable = bool(m >= 2 and n >= 2)
                d_train = L.style_dtrain(Z_std_train, styles_train, style)
                if estimable:
                    terms = L.energy_distance_terms(gen_z, real_z)
                    V_raw = float(terms["V"])
                    U_raw = float(terms["U"])
                    keep = np.ones(gen_z.shape[1], dtype=bool)
                    keep[j] = False
                    dropped = L.energy_distance_terms(gen_z[:, keep], real_z[:, keep])
                    d_train_dropped = L.style_dtrain(Z_std_train[:, keep], styles_train, style)
                    V_raw_dropped = float(dropped["V"])
                else:
                    V_raw = U_raw = V_raw_dropped = d_train_dropped = None
                cells.append({
                    "repeat": int(repeat), "fold": int(fold), "style": style,
                    "seed": int(V6.SEEDS[repeat]), "n_real": n, "n_gen": m,
                    "estimable": estimable,
                    "beer156_held_out": beer156_held_out,
                    "d_train": float(d_train),
                    "V_raw": V_raw, "U_raw": U_raw,
                    "V_normalized": (V_raw / d_train) if (estimable and d_train > 1e-12) else None,
                    "d_train_dropped": (float(d_train_dropped) if estimable else None),
                    "V_raw_dropped": V_raw_dropped,
                    "V_normalized_dropped": ((V_raw_dropped / d_train_dropped)
                                             if (estimable and d_train_dropped > 1e-12) else None),
                })

    def scope(rows) -> dict:
        usable = [row for row in rows if row["estimable"]]
        return {
            "nCells": len(usable),
            "nSamples": int(sum(row["n_gen"] for row in usable)),
            "V_raw": weighted_mean([row["V_raw"] for row in usable], [row["n_gen"] for row in usable]),
            "V_normalized": weighted_mean([row["V_normalized"] for row in usable],
                                          [row["n_gen"] for row in usable]),
            "V_raw_dropped": weighted_mean([row["V_raw_dropped"] for row in usable],
                                           [row["n_gen"] for row in usable]),
            "V_normalized_dropped": weighted_mean([row["V_normalized_dropped"] for row in usable],
                                                  [row["n_gen"] for row in usable]),
        }

    all_scope = scope(cells)
    kriek_scope = scope([row for row in cells if row["style"] == "Kriek"])
    subset_scope = scope([row for row in cells if row["style"] in SUBSET_STYLES])
    scopes = {"allStyles": all_scope, "Kriek": kriek_scope, "TripelKriekLambicSubset": subset_scope}

    # ---- "before" values must reproduce energy_summary.csv; "after" values are the review's sensitivity numbers
    summary = pd.read_csv(EXP0109 / "energy_summary.csv").set_index("scope")
    check_close("sensitivity_before_allStyles", SENSITIVITY_BEFORE["allStyles"],
                all_scope["V_normalized"])
    check_close("sensitivity_before_allStyles_matches_energy_summary",
                float(summary.loc["allStyles", "V_normalized"]), all_scope["V_normalized"])
    check_close("sensitivity_before_Kriek", SENSITIVITY_BEFORE["Kriek"], kriek_scope["V_normalized"])
    check_close("sensitivity_before_Kriek_matches_energy_summary",
                float(summary.loc["style:Kriek", "V_normalized"]), kriek_scope["V_normalized"])
    check_close("sensitivity_before_subset", SENSITIVITY_BEFORE["TripelKriekLambicSubset"],
                subset_scope["V_normalized"])
    check_close("sensitivity_before_subset_matches_energy_summary",
                float(summary.loc["excludedStylesSubset", "V_normalized"]),
                subset_scope["V_normalized"])
    check_close("sensitivity_Kriek_raw_V_matches_energy_summary",
                float(summary.loc["style:Kriek", "V"]), kriek_scope["V_raw"])
    for key in SENSITIVITY_AFTER_ROUNDED:
        check_rounded("sensitivity_after_%s" % key, SENSITIVITY_AFTER_ROUNDED[key],
                      scopes[key]["V_normalized_dropped"], 4)

    # ---- per-fold Kriek table: bad folds are exactly the beer156 held-out cells
    kriek_cells = [row for row in cells if row["style"] == "Kriek"]
    bad = [row for row in kriek_cells if row["beer156_held_out"]]
    good = [row for row in kriek_cells if not row["beer156_held_out"]]
    record("kriek_bad_folds_count", 3, len(bad), len(bad) == 3)
    record("kriek_good_folds_count", 6, len(good), len(good) == 6)
    bad_min = min(row["V_normalized"] for row in bad)
    bad_max = max(row["V_normalized"] for row in bad)
    good_min = min(row["V_normalized"] for row in good)
    good_max = max(row["V_normalized"] for row in good)
    record("kriek_bad_folds_V_normalized_range", [22.61, 23.93],
           [min(row["V_normalized"] for row in bad), max(row["V_normalized"] for row in bad)],
           round(bad_min, 2) == 22.61 and round(bad_max, 2) == 23.93,
           note="single-cell V/D_train; the three beer156 held-out folds")
    record("kriek_good_folds_V_normalized_range", [0.58, 0.77],
           [min(row["V_normalized"] for row in good), max(row["V_normalized"] for row in good)],
           round(good_min, 2) == 0.58 and round(good_max, 2) == 0.77,
           note="single-cell V/D_train; the six other Kriek folds")
    z_values = [row["standardizedCoordinate"] for row in coordinate_by_fold]
    record("coordinate_standardized_by_held_out_fold", "~1900", z_values,
           all(1800.0 < value < 2000.0 for value in z_values),
           note="(beer156 stored value - fold train centre) / fold train scale")
    record("beer156_held_out_folds", [[0, 2], [1, 0], [2, 1]],
           [[row["repeat"], row["fold"]] for row in coordinate_by_fold],
           [[row["repeat"], row["fold"]] for row in coordinate_by_fold] == [[0, 2], [1, 0], [2, 1]])

    # ---- the primary metric must be untouched: read the delivered artifacts and assert they still hold
    metrics = json.load(open(EXP0110 / "transfer_metrics.json", encoding="utf-8"))
    primary_untouched = {
        "delivered_artifact": "experiments/EXP-0110/transfer_metrics.json",
        "EXP0110_transfer_energy_qp_quantile_anchor": float(metrics["transfer-energy"]),
        "EXP0109_allStyles_V_normalized": float(summary.loc["allStyles", "V_normalized"]),
        "statement": ("all 231 coordinates are kept in every delivered artifact; the coordinate-dropped numbers "
                      "are a SENSITIVITY DIAGNOSTIC ONLY and never replace the primary metric"),
    }
    check_close("primary_metric_EXP0110_unchanged", 2.0798861351916886,
                primary_untouched["EXP0110_transfer_energy_qp_quantile_anchor"])
    check_close("primary_metric_EXP0109_unchanged", SENSITIVITY_BEFORE["allStyles"],
                primary_untouched["EXP0109_allStyles_V_normalized"])

    fold_rows = []
    for row in kriek_cells:
        fold_rows.append({
            "repeat": row["repeat"], "fold": row["fold"], "seed": row["seed"],
            "n_real": row["n_real"], "n_gen": row["n_gen"],
            "beer156HeldOut": row["beer156_held_out"],
            "dTrain": row["d_train"], "dTrainDropped": row["d_train_dropped"],
            "V": row["V_raw"], "VNormalized": row["V_normalized"],
            "VDropped": row["V_raw_dropped"], "VNormalizedDropped": row["V_normalized_dropped"],
        })

    return {
        "label": "SENSITIVITY DIAGNOSTIC: the delivered primary metric keeps all 231 coordinates",
        "coordinate": coordinate,
        "standardizedCoordinateByHeldOutFold": coordinate_by_fold,
        "foldEnergyKriek": {
            "denominatorRule": ("each cell value is V/D_train for that fold and style, D_train = mean pairwise "
                                "distance of the Kriek TRAIN rows in that fold's standardised space"),
            "rows": fold_rows,
            "badFolds": [row for row in fold_rows if row["beer156HeldOut"]],
            "goodFolds": [row for row in fold_rows if not row["beer156HeldOut"]],
        },
        "beforeAfter": {
            "method": ("distance evaluation only: drop the ONE coordinate chem__X2.methyltetrahydrofuran.3.one "
                       "simultaneously from the generated block, the real block and the D_train denominator; the "
                       "generated samples, the fold contexts and every delivered artifact are unchanged"),
            "scopes": {key: {
                "nCells": scopes[key]["nCells"], "nSamples": scopes[key]["nSamples"],
                "V_raw_before": scopes[key]["V_raw"], "V_raw_after": scopes[key]["V_raw_dropped"],
                "V_normalized_before": scopes[key]["V_normalized"],
                "V_normalized_after": scopes[key]["V_normalized_dropped"],
                "V_normalized_absolute_change": (scopes[key]["V_normalized"]
                                                 - scopes[key]["V_normalized_dropped"]),
                "V_normalized_relative_change_percent": (100.0 * (scopes[key]["V_normalized"]
                                                                  - scopes[key]["V_normalized_dropped"])
                                                         / scopes[key]["V_normalized"]),
            } for key in scopes},
        },
        "numberDefinitions": {
            "allStyles_V_normalized_0.8727": ("n_gen-weighted mean over the 177 estimable (repeat,fold,style) "
                                              "design cells of V_cell/D_train_cell; denominator = 729 generated "
                                              "spectra; raw pooled V = %.6f" % all_scope["V_raw"]),
            "Kriek_V_normalized_7.4079": ("n_gen-weighted mean over the 9 Kriek design cells (30 generated Kriek "
                                          "spectra) of V_cell/D_train_cell. It is a NORMALISED POOLED per-cell "
                                          "statistic, NOT a raw per-style V: raw pooled Kriek V = %.6f"
                                          % kriek_scope["V_raw"]),
            "TripelKriekLambic_subset_V_normalized_1.8079": ("n_gen-weighted mean over the 27 estimable Tripel/"
                                                             "Kriek/Lambic cells; denominator = 147 generated "
                                                             "spectra; raw pooled V = %.6f"
                                                             % subset_scope["V_raw"]),
            "per_fold_Kriek_values": ("the values 22.61-23.93 (beer156 held out) and 0.58-0.77 (other folds) are "
                                      "single-cell V/D_train values; their n_gen-weighted mean is the pooled "
                                      "7.4079 value, so per-fold and pooled numbers have DIFFERENT denominators "
                                      "and must not be averaged together as if they were the same statistic"),
            "denominators": ("every pooled value uses n_gen as the cell weight (the delivered EXP-0109 pooling "
                             "rule); V_normalized always divides by the fold/style D_train, never by a variance or "
                             "by the number of samples"),
        },
        "scopeRecompute": {key: scopes[key] for key in scopes},
        "cells": cells,
        "primaryMetricUntouched": primary_untouched,
    }


# ================================================================================================== CSV tables
# ================================================================================================== TASK C
def task_c_crossset(data, splits, samples) -> dict:
    """Cross-set proximity of the delivered design spectra against each fold's own training rows."""
    X_raw = np.asarray(data["X_raw"], dtype=float)
    per_fold, all_distances = [], []
    total_rows = exact_total = 0
    for repeat in range(3):
        for fold in range(3):
            train_idx, _test_idx = fold_indices(splits, data["index_of"], repeat, fold)
            _medians, X_train, centre, scale = fold_standardizer(X_raw, train_idx)
            Z_train = L.standardize(X_train, centre, scale)
            block = samples[(samples["repeat"] == repeat) & (samples["fold"] == fold)]
            gen = block[L.CHEM_COLS].to_numpy(dtype=float)
            if gen.shape[0] == 0:
                raise RuntimeError("no generated sample for repeat=%d fold=%d" % (repeat, fold))
            Z_gen = L.standardize(gen, centre, scale)
            exact = int(sum(bool(np.isclose(X_train, row, rtol=0.0, atol=1e-12).all(axis=1).any())
                            for row in gen))
            distances = cdist(Z_gen, Z_train).min(axis=1)
            per_fold.append({
                "repeat": int(repeat), "fold": int(fold),
                "nGenerated": int(gen.shape[0]), "nTrain": int(X_train.shape[0]),
                "exactRowMatches": exact, "exactRowMatchRate": float(exact) / float(gen.shape[0]),
                "nearestDistanceMean": float(distances.mean()),
                "nearestDistanceMedian": float(np.median(distances)),
                "nearestDistanceP10": float(np.percentile(distances, 10)),
                "nearestDistanceP90": float(np.percentile(distances, 90)),
            })
            total_rows += int(gen.shape[0])
            exact_total += exact
            all_distances.extend(float(value) for value in distances)

    if total_rows != 750:
        raise RuntimeError("cross-set diagnostic covered %d generated rows, expected 750" % total_rows)
    distances = np.asarray(all_distances, dtype=float)
    pooled = {
        "nGenerated": int(total_rows),
        "nFolds": len(per_fold),
        "exactRowMatches": int(exact_total),
        "exactRowMatchRate": float(exact_total) / float(total_rows),
        "nearestDistanceMean": float(distances.mean()),
        "nearestDistanceMedian": float(np.median(distances)),
        "nearestDistanceP10": float(np.percentile(distances, 10)),
        "nearestDistanceP90": float(np.percentile(distances, 90)),
    }
    record("crossset_rows", 750, total_rows, total_rows == 750,
           "cross-set diagnostic covers all 750 delivered design spectra")
    record("crossset_exact_row_matches", 0, exact_total, exact_total == 0,
           "no design spectrum duplicates a same-fold training row on all 231 chem__ cells (atol 1e-12)")
    check_close("crossset_nearest_mean_consistency", float(distances.mean()),
                float(np.average([row["nearestDistanceMean"] for row in per_fold],
                                 weights=[row["nGenerated"] for row in per_fold])), tol=1e-10)
    record("crossset_nearest_mean_finite", True, bool(np.isfinite(pooled["nearestDistanceMean"])),
           "mean nearest-training distance is finite (fold-standardised 231-dim space)")
    return {
        "definition": {
            "referenceSet": "the SAME outer fold's training rows (X_train): fold median imputation, then the "
                            "EXP-0109 fold standardiser (mean/std of the imputed training rows)",
            "generatedSet": "the delivered EXP-0109 copula-selected design spectra (3 repeats x 3 outer folds, 750 rows)",
            "exactRowMatch": "a generated row matches a training row when all 231 chem__ cells differ by <= 1e-12; "
                             "the rate is matches / 750",
            "nearestDistance": "per generated row, the minimum standardised Euclidean distance to any training row of "
                               "the same fold; the pooled value is the unweighted mean over all 750 generated rows",
            "relationToWithinBatch": "the within-batch duplicate share (table q3-quality, 0.0000) measures repeats "
                                     "inside the generated batch; this diagnostic measures copying of TRAINING rows. "
                                     "The two are different statements and neither substitutes for the other",
        },
        "perFold": per_fold,
        "pooled": pooled,
    }


def write_tables(task_a: dict, task_b: dict) -> None:
    # ---- anchor_direct_projection.csv
    rows = []
    for strategy in list(TR.STRATEGIES) + [ANCHOR_DIRECT]:
        control = task_a["controls"].get(strategy)
        if control is None:
            direct = task_a["pooled"]
            rows.append({"level": "pooled", "strategy": strategy, "repeat": None, "fold": None,
                         "source_beer": None, "m_sources": direct["nPoints"],
                         "n_target_reference": None, "d_target": None, "V": direct["V"],
                         "V_normalized": direct["V_normalized"], "U": direct["U"],
                         "max_constraint_violation": task_a["residuals"]["max_constraint_violation"],
                         "stale_halfspace_residual": None, "l1_change_z": None,
                         "mean_abs_change_z": None, "n_constraint_violations": 0,
                         "note": "new ablation (review §4.1); same anchor, same box + corrected stale half-space, "
                                 "no PCA quadratic, no L1"})
            for cell in task_a["perFold"]:
                rows.append({"level": "fold", "strategy": strategy, "repeat": cell["repeat"],
                             "fold": cell["fold"], "source_beer": None, "m_sources": cell["m"],
                             "n_target_reference": cell["n"], "d_target": cell["d_target"],
                             "V": cell["V"], "V_normalized": cell["V_normalized"], "U": cell["U"],
                             "max_constraint_violation": cell["max_violation"],
                             "stale_halfspace_residual": None, "l1_change_z": None,
                             "mean_abs_change_z": None,
                             "n_constraint_violations": cell["n_points_with_delivered_violation"],
                             "note": "new ablation (review §4.1)"})
            for entry in task_a["pointRows"]:
                rows.append({"level": "point", "strategy": strategy, "repeat": entry["repeat"],
                             "fold": entry["fold"], "source_beer": entry["source_beer"],
                             "m_sources": None, "n_target_reference": None, "d_target": None,
                             "V": None, "V_normalized": None, "U": None,
                             "max_constraint_violation": entry["max_violation"],
                             "stale_halfspace_residual": entry["stale_halfspace_residual"],
                             "l1_change_z": entry["l1_change_z"],
                             "mean_abs_change_z": entry["mean_abs_change_z"],
                             "n_constraint_violations": entry["n_constraint_violations"],
                             "note": "projected quantile anchor, delivered point"})
            continue
        rows.append({"level": "pooled", "strategy": strategy, "repeat": None, "fold": None,
                     "source_beer": None, "m_sources": control["nPoints"],
                     "n_target_reference": None, "d_target": None, "V": control["V"],
                     "V_normalized": control["V_normalized"], "U": control["U"],
                     "max_constraint_violation": None, "stale_halfspace_residual": None,
                     "l1_change_z": None, "mean_abs_change_z": None, "n_constraint_violations": None,
                     "note": "reproduced control (EXP-0110 artifact)"})
        for cell in control["perFold"]:
            rows.append({"level": "fold", "strategy": strategy, "repeat": cell["repeat"],
                         "fold": cell["fold"], "source_beer": None, "m_sources": cell["m"],
                         "n_target_reference": cell["n"], "d_target": cell["d_target"],
                         "V": cell["V"], "V_normalized": cell["V_normalized"], "U": cell["U"],
                         "max_constraint_violation": None, "stale_halfspace_residual": None,
                         "l1_change_z": None, "mean_abs_change_z": None,
                         "n_constraint_violations": None,
                         "note": "reproduced control (EXP-0110 artifact)"})
    columns = ["level", "strategy", "repeat", "fold", "source_beer", "m_sources", "n_target_reference",
               "d_target", "V", "V_normalized", "U", "max_constraint_violation",
               "stale_halfspace_residual", "l1_change_z", "mean_abs_change_z",
               "n_constraint_violations", "note"]
    anchor_frame = pd.DataFrame(rows, columns=columns)
    for column in ("repeat", "fold", "source_beer", "m_sources", "n_target_reference",
                   "n_constraint_violations"):
        anchor_frame[column] = anchor_frame[column].astype("Int64")
    anchor_frame.to_csv(TABLE_DIR / "anchor_direct_projection.csv", index=False, lineterminator="\n")

    # ---- beer156_sensitivity.csv (long/tidy: block, entity, ..., metric, value, value_before, value_after)
    rows = []

    def add(block, entity, metric, value=None, before=None, after=None, repeat=None, fold=None,
            n_cells=None, n_samples=None, denominator=None, note=""):
        rows.append({"block": block, "entity": entity, "repeat": repeat, "fold": fold,
                     "n_cells": n_cells, "n_samples": n_samples, "denominator": denominator,
                     "metric": metric, "value": value, "value_before": before, "value_after": after,
                     "note": note})

    coordinate = task_b["coordinate"]
    entity = "beer156 (Kriek) / %s" % coordinate["storedColumn"]
    for key, metric in (("storedValue", "stored_value"),
                        ("secondLargestValue", "second_largest_value"),
                        ("maxOverSecondRatio", "max_over_second_ratio"),
                        ("rankOfBeer156", "rank_of_beer156"),
                        ("nRows", "n_rows"),
                        ("nMissing", "n_missing"),
                        ("minimum", "minimum"),
                        ("q25", "q25"),
                        ("median", "median"),
                        ("q75", "q75"),
                        ("q90", "q90"),
                        ("q99", "q99"),
                        ("mean", "mean"),
                        ("std", "std"),
                        ("mad", "mad")):
        add("coordinate", entity, metric, value=coordinate[key],
            note=("linear concentration column, no declared defect threshold; second-largest row is beer %d"
                  % coordinate["secondLargestBeer"]) if key == "secondLargestValue" else "")
    for entry in task_b["standardizedCoordinateByHeldOutFold"]:
        add("standardized_coordinate", "beer156 (Kriek)", "z_coordinate",
            value=entry["standardizedCoordinate"], repeat=entry["repeat"], fold=entry["fold"],
            denominator="centre=%.6f scale=%.6f (fold train rows, n=%d)"
                        % (entry["trainFoldCentre"], entry["trainFoldScale"], entry["trainFoldNRows"]),
            note="beer156 is held out in this outer fold")
    for row in task_b["foldEnergyKriek"]["rows"]:
        for metric, before_key, after_key in (("V_raw", "V", "VDropped"),
                                              ("V_normalized", "VNormalized", "VNormalizedDropped"),
                                              ("D_train_denominator", "dTrain", "dTrainDropped")):
            add("kriek_fold_energy", "Kriek", metric, repeat=row["repeat"], fold=row["fold"],
                n_cells=1, n_samples=row["n_gen"], before=row[before_key], after=row[after_key],
                denominator="single-cell V / D_train; D_train from Kriek training rows",
                note=("beer156 held out -> bad fold" if row["beer156HeldOut"] else "beer156 in training"))
    for key, label in (("allStyles", "all styles"),
                       ("Kriek", "Kriek"),
                       ("TripelKriekLambicSubset", "Tripel + Kriek + Lambic")):
        block = task_b["beforeAfter"]["scopes"][key]
        for metric in ("V_normalized", "V_raw"):
            add("scope_before_after", label, metric,
                n_cells=block["nCells"], n_samples=block["nSamples"],
                before=block["%s_before" % metric], after=block["%s_after" % metric],
                denominator=("n_gen-weighted over %d estimable cells (%d generated spectra); V_normalized "
                             "divides by each cell's D_train" % (block["nCells"], block["nSamples"])),
                note="distance-evaluation-only coordinate drop; delivered primary metric unchanged")
    sensitivity_frame = pd.DataFrame(rows, columns=["block", "entity", "repeat", "fold", "n_cells",
                                                    "n_samples", "denominator", "metric", "value",
                                                    "value_before", "value_after", "note"])
    for column in ("repeat", "fold", "n_cells", "n_samples"):
        sensitivity_frame[column] = sensitivity_frame[column].astype("Int64")
    sensitivity_frame.to_csv(TABLE_DIR / "beer156_sensitivity.csv", index=False, lineterminator="\n")


def write_crossset_table(task_c: dict) -> None:
    header = ["level", "repeat", "fold", "n_generated", "n_train", "exact_row_matches",
              "exact_row_match_rate", "nearest_distance_mean", "nearest_distance_median",
              "nearest_distance_p10", "nearest_distance_p90"]
    rows = []
    for entry in task_c["perFold"]:
        rows.append(["fold", entry["repeat"], entry["fold"], entry["nGenerated"], entry["nTrain"],
                     entry["exactRowMatches"], "%.6f" % entry["exactRowMatchRate"],
                     "%.6f" % entry["nearestDistanceMean"], "%.6f" % entry["nearestDistanceMedian"],
                     "%.6f" % entry["nearestDistanceP10"], "%.6f" % entry["nearestDistanceP90"]])
    pooled = task_c["pooled"]
    rows.append(["pooled", "", "", pooled["nGenerated"], "", pooled["exactRowMatches"],
                 "%.6f" % pooled["exactRowMatchRate"], "%.6f" % pooled["nearestDistanceMean"],
                 "%.6f" % pooled["nearestDistanceMedian"], "%.6f" % pooled["nearestDistanceP10"],
                 "%.6f" % pooled["nearestDistanceP90"]])
    with open(TABLE_DIR / "q3_crossset_diagnostic.csv", "w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(header)
        for row in rows:
            csv.writer(handle, lineterminator="\n").writerow(row)


def write_anchor_values(anchor_rows) -> None:
    """One row per (repeat, fold, source_beer, chem column) for the 99 delivered points: the REAL quantile anchor."""
    columns = ["repeat", "fold", "source_beer", "column", "src_stored", "anchor_stored",
               "anchor_physical", "storage_scale", "unit", "unit_declared", "note"]
    frame = pd.DataFrame(anchor_rows, columns=columns)
    for column in ("repeat", "fold", "source_beer"):
        frame[column] = frame[column].astype("Int64")
    frame.to_csv(TABLE_DIR / "transfer_anchor_values.csv", index=False, lineterminator="\n")


# ================================================================================================== main
def main() -> int:
    started = time.time()
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    data = load_data()
    splits = V6.load_splits()
    samples = load_samples()

    # ---- Task A -------------------------------------------------------------------------------------------
    task_a, anchor_rows = task_a_anchor_direct(data, splits)
    critical_a = [name for name in ASSERTIONS
                  if name.startswith("control_") or name.startswith("controls_match")]
    if not all(ASSERTIONS[name]["passed"] for name in critical_a):
        print("[STOP] the qp-quantile-anchor control was NOT reproduced; refusing to publish the ablation.")
        for name in critical_a:
            if not ASSERTIONS[name]["passed"]:
                print("  FAILED %s expected=%r actual=%r" % (name, ASSERTIONS[name]["expected"],
                                                              ASSERTIONS[name]["actual"]))
        return 2

    # ---- Task B -------------------------------------------------------------------------------------------
    task_b = task_b_beer156(data, splits, samples)

    # ---- Task C -------------------------------------------------------------------------------------------
    task_c = task_c_crossset(data, splits, samples)
    critical_b = [name for name in ASSERTIONS if name.startswith("sensitivity_before_")]
    if not all(ASSERTIONS[name]["passed"] for name in critical_b):
        print("[STOP] the EXP-0109 before-state was NOT reproduced by the recomputation; refusing to publish.")
        for name in critical_b:
            if not ASSERTIONS[name]["passed"]:
                print("  FAILED %s expected=%r actual=%r" % (name, ASSERTIONS[name]["expected"],
                                                              ASSERTIONS[name]["actual"]))
        return 2

    protocol = {
        "script": "src/q3_v62_diagnostics.py",
        "purpose": "v6.2 review-response diagnostics for Q3 (anchor-direct-projection ablation; beer156 sensitivity)",
        "deterministic": True,
        "seeds": [int(seed) for seed in V6.SEEDS],
        "inputsReadOnly": {
            "data/clean/q3.csv": sha256_file(DATA_Q3),
            "data/splits/NESTED-CV-1/splits.csv": sha256_file(SPLITS_CSV),
            "experiments/EXP-0109/samples.csv": sha256_file(EXP0109 / "samples.csv"),
            "experiments/EXP-0109/samples-repeat-0.csv": sha256_file(EXP0109 / "samples-repeat-0.csv"),
            "experiments/EXP-0109/samples-repeat-1.csv": sha256_file(EXP0109 / "samples-repeat-1.csv"),
            "experiments/EXP-0109/samples-repeat-2.csv": sha256_file(EXP0109 / "samples-repeat-2.csv"),
            "experiments/EXP-0109/q3_metrics.csv": sha256_file(EXP0109 / "q3_metrics.csv"),
            "experiments/EXP-0109/energy_summary.csv": sha256_file(EXP0109 / "energy_summary.csv"),
            "experiments/EXP-0110/transfer_outputs.json": sha256_file(EXP0110 / "transfer_outputs.json"),
            "experiments/EXP-0110/transfer_metrics.json": sha256_file(EXP0110 / "transfer_metrics.json"),
            "src/q3_transfer_fix.py": sha256_file(SRC / "q3_transfer_fix.py"),
            "src/q3_lib.py": sha256_file(SRC / "q3_lib.py"),
            "src/q3_fix.py": sha256_file(SRC / "q3_fix.py"),
            "src/v6_common.py": sha256_file(SRC / "v6_common.py"),
            "src/q3_v62_answer_tables.py": sha256_file(SRC / "q3_v62_answer_tables.py"),
            "data/processed/v6_feature_dictionary.csv": sha256_file(FEATURE_DICTIONARY),
        },
        "writes": {
            "json": "outputs/q3/v62_diagnostics/v62_diagnostics.json",
            "tables": ["outputs/q3/v62_tables/anchor_direct_projection.csv",
                       "outputs/q3/v62_tables/beer156_sensitivity.csv",
                       "outputs/q3/v62_tables/transfer_anchor_values.csv"],
            "deliveryCopies": [str(FINAL_DIR / name) for name in
                               ("v62_diagnostics.json", "anchor_direct_projection.csv",
                                            "beer156_sensitivity.csv", "transfer_anchor_values.csv",
                       "q3_crossset_diagnostic.csv")],
        },
        "noRetraining": ("both diagnostics are post-processing of frozen artifacts: no generator, projection model, "
                         "marginal or QP hyper-parameter is refitted other than recomputing the frozen EXP-0109 "
                         "fold standardisers and the deterministic EXP-0110 transfer QP solves"),
    }

    payload = {
        "protocol": protocol,
        "anchorDirectProjection": task_a,
        "beer156Sensitivity": task_b,
        "crossSetDiagnostic": task_c,
        "assertions": ASSERTIONS,
        "summary": {
            "anchorDirectProjection": {
                "V": task_a["pooled"]["V"], "V_normalized": task_a["pooled"]["V_normalized"],
                "nPoints": task_a["pooled"]["nPoints"],
                "maxConstraintViolation": task_a["residuals"]["max_constraint_violation"],
                "control_qp_quantile_V": task_a["controls"]["qp-quantile-anchor"]["V"],
                "refinement_relative_percent": task_a["refinement"]["relative_percent_of_anchor_direct"],
            },
            "beer156Sensitivity": {
                "allStyles_V_normalized_before": task_b["beforeAfter"]["scopes"]["allStyles"]["V_normalized_before"],
                "allStyles_V_normalized_after": task_b["beforeAfter"]["scopes"]["allStyles"]["V_normalized_after"],
                "Kriek_V_normalized_before": task_b["beforeAfter"]["scopes"]["Kriek"]["V_normalized_before"],
                "Kriek_V_normalized_after": task_b["beforeAfter"]["scopes"]["Kriek"]["V_normalized_after"],
                "subset_V_normalized_before": task_b["beforeAfter"]["scopes"]["TripelKriekLambicSubset"]["V_normalized_before"],
                "subset_V_normalized_after": task_b["beforeAfter"]["scopes"]["TripelKriekLambicSubset"]["V_normalized_after"],
            },
        },
    }

    json_path = DIAG_DIR / "v62_diagnostics.json"
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(json_safe(payload), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_tables(task_a, task_b)
    write_crossset_table(task_c)
    write_anchor_values(anchor_rows)
    copies = {"v62_diagnostics.json": json_path,
              "anchor_direct_projection.csv": TABLE_DIR / "anchor_direct_projection.csv",
              "beer156_sensitivity.csv": TABLE_DIR / "beer156_sensitivity.csv",
              "transfer_anchor_values.csv": TABLE_DIR / "transfer_anchor_values.csv",
              "q3_crossset_diagnostic.csv": TABLE_DIR / "q3_crossset_diagnostic.csv"}
    for name, source in copies.items():
        shutil.copyfile(source, FINAL_DIR / name)

    failed = [name for name, entry in ASSERTIONS.items() if not entry["passed"]]
    elapsed = time.time() - started

    # ---- compact report -----------------------------------------------------------------------------------
    direct = task_a["pooled"]
    qp = task_a["controls"]["qp-quantile-anchor"]
    l1 = task_a["l1Comparison"]
    print("[q3_v62_diagnostics] elapsed=%.1fs  assertions=%d/%d passed"
          % (elapsed, len(ASSERTIONS) - len(failed), len(ASSERTIONS)))
    print("TASK C cross-set proximity of the delivered design spectra")
    cross = task_c["pooled"]
    print("  rows=%d  exact training-row copies=%d (rate=%.6f)  nearest-training distance mean=%.6f "
          "(median=%.6f, P10=%.6f, P90=%.6f)"
          % (cross["nGenerated"], cross["exactRowMatches"], cross["exactRowMatchRate"],
             cross["nearestDistanceMean"], cross["nearestDistanceMedian"],
             cross["nearestDistanceP10"], cross["nearestDistanceP90"]))
    print("TASK A anchor-direct-projection (review §4.1)")
    print("  points=%d  max constraint violation=%g  chemistry residual max=%g  delivered violations=%d"
          % (direct["nPoints"], task_a["residuals"]["max_constraint_violation"],
             task_a["residuals"]["chemistry_physical_nonincrease_residual_max"],
             task_a["residuals"]["delivered_constraint_violations_total"]))
    print("  V(anchor-direct-projection) = %.12f  (expected 2.0903)   V_normalized = %.6f"
          % (direct["V"], direct["V_normalized"]))
    for strategy in TR.STRATEGIES:
        print("  control %-26s V=%.12f  U=%.12f  V_norm=%.12f"
              % (strategy, task_a["controls"][strategy]["V"],
                 task_a["controls"][strategy]["U"],
                 task_a["controls"][strategy]["V_normalized"]))
    representative = task_a["representativeAnchor"]
    print("  exported anchor values: outputs/q3/v62_tables/transfer_anchor_values.csv (%d rows = %d points x %d columns)"
          % (task_a["exportedAnchorValues"]["nRows"], task_a["exportedAnchorValues"]["nPoints"],
             task_a["exportedAnchorValues"]["nColumns"]))
    print("  representative anchor: R%d-F%d beer %d; reconstruction max|err|=%.3e (tol 1e-12); "
          "inside declared box=%s; stale proxy satisfied=%s (residual %+.6f)"
          % (representative["repeat"], representative["fold"], representative["source_beer"],
             representative["reconstruction"]["maxAbsError"],
             representative["feasibility"]["insideDeclaredBox"],
             representative["feasibility"]["staleHalfspaceSatisfied"],
             representative["feasibility"]["staleHalfspaceResidual"]))
    for item in representative["items"]:
        physical = item["anchor_physical"]
        physical_text = ("%.10g" % physical) if np.isfinite(physical) else "NaN (uncalibrated)"
        print("    %-20s %-18s anchor_stored=%14.8f anchor_physical=%s"
              % (item["name"], item["storage_scale"], item["anchor_stored"], physical_text))
    proxy = representative["staleHopsProxy"]
    print("    %-20s %-18s proxy(anchor)=%.10g  proxy(source)=%.10g  b=%.10g  residual=%+.6g"
          % ("stale_hops", "sensory label proxy", proxy["proxy_score_at_anchor"],
             proxy["proxy_score_at_source"], proxy["halfspace_b"],
             proxy["halfspace_residual_at_anchor"]))
    print("  refinement = %.6f (%.3f%% of anchor-direct V);  L1 mean QP=%.4f vs direct=%.4f (QP %.3f%% smaller)"
          % (task_a["refinement"]["absolute_improvement"],
             task_a["refinement"]["relative_percent_of_anchor_direct"],
             l1["qp_quantile"]["meanL1ChangeZ"], l1["anchor_direct"]["meanL1ChangeZ"],
             l1["relative_l1_reduction_percent_of_anchor_direct"]))
    print("TASK B beer156 sensitivity (review §4.2)")
    print("  %s = %.8f  vs second-largest %.8f (beer %d); rank %d/%d; ratio %.3f"
          % (task_b["coordinate"]["storedColumn"], task_b["coordinate"]["storedValue"],
             task_b["coordinate"]["secondLargestValue"], task_b["coordinate"]["secondLargestBeer"],
             task_b["coordinate"]["rankOfBeer156"], task_b["coordinate"]["nRows"],
             task_b["coordinate"]["maxOverSecondRatio"]))
    print("  standardized coordinate on held-out folds: %s"
          % ", ".join("R%d-F%d=%.2f" % (entry["repeat"], entry["fold"], entry["standardizedCoordinate"])
                      for entry in task_b["standardizedCoordinateByHeldOutFold"]))
    for row in task_b["foldEnergyKriek"]["rows"]:
        print("  Kriek R%d-F%d n=%d/%d beer156_held_out=%-5s V=%.4f V_norm=%.4f (drop: V=%.4f V_norm=%.4f)"
              % (row["repeat"], row["fold"], row["n_gen"], row["n_real"], row["beer156HeldOut"],
                 row["V"], row["VNormalized"], row["VDropped"], row["VNormalizedDropped"]))
    scopes = task_b["beforeAfter"]["scopes"]
    print("  all styles    V_norm %.6f -> %.6f   raw V %.6f -> %.6f"
          % (scopes["allStyles"]["V_normalized_before"], scopes["allStyles"]["V_normalized_after"],
             scopes["allStyles"]["V_raw_before"], scopes["allStyles"]["V_raw_after"]))
    print("  Kriek         V_norm %.6f -> %.6f   raw V %.6f -> %.6f"
          % (scopes["Kriek"]["V_normalized_before"], scopes["Kriek"]["V_normalized_after"],
             scopes["Kriek"]["V_raw_before"], scopes["Kriek"]["V_raw_after"]))
    print("  Tripel/Kriek/Lambic V_norm %.6f -> %.6f   raw V %.6f -> %.6f"
          % (scopes["TripelKriekLambicSubset"]["V_normalized_before"],
             scopes["TripelKriekLambicSubset"]["V_normalized_after"],
             scopes["TripelKriekLambicSubset"]["V_raw_before"],
             scopes["TripelKriekLambicSubset"]["V_raw_after"]))
    print("  primary metric untouched: EXP-0110 qp-quantile V=%.12f (all 231 coordinates kept)"
          % task_b["primaryMetricUntouched"]["EXP0110_transfer_energy_qp_quantile_anchor"])
    print("wrote %s and the three CSVs (copied into the delivery tree)" % json_path)
    if failed:
        print("[FAIL] %d assertion(s) failed: %s" % (len(failed), ", ".join(failed)))
        for name in failed:
            print("  %-45s expected=%r actual=%r" % (name, ASSERTIONS[name]["expected"],
                                                      ASSERTIONS[name]["actual"]))
        return 3
    print("[OK] all assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
