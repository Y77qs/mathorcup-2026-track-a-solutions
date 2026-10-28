#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q1_export_scores.py — Q1 score-table export from the frozen EXP-0073 result (NO retraining).

WHAT THIS SCRIPT DOES (and what it deliberately does not do)
------------------------------------------------------------
The frozen Q1 confirmatory experiment is experiments/EXP-0073 (MODEL-0048, graph-regularised
low-rank multi-output regression, A/F30 equal-weight OOF MAE 0.3592915659 vs median baseline
0.3981773284, nested 3x3x3 protocol, seeds 20261025/26/27). It already contains the 750-row
out-of-fold (OOF) predictions that the *evaluation* uses. What the v6 revision still needs is a
*display* table: a continuous score for each of the 250 beers and a relative 0-6 grade per
dimension, plus an explicit mapping of the 50 dimensions.

So this script only READS frozen results and writes reporting artifacts:

  1. oof_predictions_750.csv        the evaluation-side OOF predictions, 250 beers x 3 repeats,
                                    copied from experiments/EXP-0073/predictions.csv (and
                                    cross-checked against oof_long.csv). 750 rows, per-target
                                    y_true/y_pred columns.
  2. oof_predictions_long_37500.csv tidy long companion of the same OOF predictions
                                    (repeat, beer, fold, target, model, y_true, y_pred, grades),
                                    filtered from experiments/EXP-0073/oof_long.csv.
  3. beer_scores_250.csv           250 unique beer keys x 50 continuous DISPLAY scores from a
                                    final full-sample refit (fit_identity=full-sample-refit).
  4. grades_250.csv                continuous + discrete 0-6 RELATIVE INFERRED grades of the
                                    display scores, using the frozen
                                    data/processed/q1_grade_params.json mid-rank CDF rule (the
                                    same rule as src/q1_grade_all.py).
  5. dimension_map.csv             50 labelled dimensions + the A/F30 subset flag + the one
                                    sensory-card item that has NO label column (acetaldehyde):
                                    listed, never given fabricated truth.
  6. score_scale_note.json         label-scale note (the code CENTRES the given label scale and
                                    does NOT divide by the training standard deviation), the
                                    OOF-vs-display boundary, and the A/F30 metric definition.
  7. export_manifest.json          sha256 / bytes / rows / cols of every artifact + every input
                                    hash + the frozen-registration cross-check + all self-checks.

NO MODEL IS REFITTED FOR EVALUATION. The full-sample refit in (3) exists only to produce display
scores; no metric, claim, grade-consistency number or figure in this project is computed from it.
The only numbers that enter the evaluation chain are recomputed here from the frozen EXP-0073
files and asserted against the registered values.

Hyper-parameters of the display refit are NOT chosen on the 250-row data. The script re-aggregates
experiments/EXP-0073/inner_grid.json (already registered inner-validation scores, no outer-test
row) and takes the graph-lowrank cell with the lowest MEAN frozen inner-validation pooled A/F30
MAE over all 9 outer folds, then refits exactly that cell on all 250 rows with the frozen
src/q1_fix.py code (read-only import). The chosen cell, its margin and the sensitivity to the
other selected cells are all written into export_manifest.json.

CLI: no arguments. Environment:
  MODELING_PROJECT_DIR     project root (defaults to the parent of this file's directory)
  MODELING_EXPERIMENT_DIR  run directory (artifacts are copied there + run.json is written)
  MODELING_SEED            registered seed for the record (default 20261025; the refit itself
                           draws no random numbers, see src/q1_fix.py "randomness: none")
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.environ.get("MODELING_PROJECT_DIR") or os.path.dirname(SRC_DIR))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import v6_common as v6  # noqa: E402  (frozen protocol constants, IO helpers, target order)
import q1_fix as Q1  # noqa: E402  (frozen model code: Preprocessor, graph_laplacian, fit_and_predict)

OUT_DIR = os.path.join(PROJECT, "outputs", "q1")

EXP_CANDIDATE = "EXP-0073"
EXP_BASELINE = "EXP-0074"
DATA_Q1 = "data/clean/q1_mapped.csv"
GRADE_PARAMS = "data/processed/q1_grade_params.json"
SPLITS_CSV = "data/splits/NESTED-CV-1/splits.csv"
SPLITS_MANIFEST = "data/splits/NESTED-CV-1/manifest.json"
CARD_XLSX_GLOB = "data/raw/imported/*-3.xlsx"       # the 0-6 sensory card (3.xlsx)
LABEL_CSV_GLOB = "data/raw/imported/*-4.csv"        # the trained-panel label table (4.csv)

# registered values this export must reproduce (MathorCup_A_v6_面向复赛修改说明.md §4)
EXPECTED_MAE_AF30 = 0.35929156588219174
EXPECTED_MAE_ALL50 = 0.350504156920024
EXPECTED_BASELINE_MAE_AF30 = 0.39817732837288883
TOLERANCE_REL = 1e-9
EVAL_FLOAT_FMT = None         # evaluation evidence: Python shortest round-trip decimal, exactly the
                              # same text the frozen EXP-0073 files use (no 17-digit expansion)
DISPLAY_FLOAT_FMT = "%.12g"   # display-only tables: 12 significant digits, no metric uses them
ROUND_TRIP = {"float_precision": "round_trip"}   # pandas' fast parser is up to a few ulps off

# 3.xlsx spells these three card fields differently from the 4.csv label columns
CARD_ALIAS = {"A_esters_fruity": "A_ester_fruity",
              "F_esters_fruity": "F_ester_fruity",
              "X4vg": "4vg"}
# sensory-card item that exists on the paper card but has NO label column in 4.csv
UNLABELLED_CARD_ITEM = {
    "dimension": "sensory_acetaldehyde",
    "category": "Aroma/Flavour",
    "card_name": "Acetaldehyde (green apples, peel)",
    "note": ("printed once on the 3.xlsx sensory card, spanning the Aroma and Flavour columns; "
             "4.csv has no acetaldehyde label column (4.csv = 3 keys + exactly the 50 labelled "
             "dimensions), so nothing is predicted or graded for it and no truth is fabricated. "
             "The only acetaldehyde sensory columns in the attachments are the external Ratebeer "
             "columns of 7.csv, which are not trained-panel labels and are not used by Q1."),
}

# 8.xlsx "Sensory names" Category_Paper for the 20 non-A/F dimensions (A/F are Aroma / Taste)
OTHER_CATEGORY = {
    "acidity": "Taste", "bitternes": "Taste", "sweetness": "Taste", "X4vg": "Taste",
    "diacetyl": "Taste", "dms": "Taste", "metallic": "Taste", "stale_hops": "Taste",
    "t2n": "Taste", "orange": "Taste", "coriander": "Taste", "clove": "Taste",
    "lactic": "Taste", "acetic": "Taste", "barnyard": "Taste",
    "alcohol": "Palate", "aftertaste": "Palate", "body": "Palate", "co2": "Palate",
    "overall": "Overall",
}


# --------------------------------------------------------------------------------------------- utilities
def sha256(path):
    return v6.sha256_file(path)


def project_path(relative):
    return os.path.join(PROJECT, relative)


def single_glob(pattern):
    import glob
    hits = sorted(glob.glob(os.path.join(PROJECT, pattern)))
    if len(hits) != 1:
        raise RuntimeError("expected exactly one match for %s, found %d: %s"
                           % (pattern, len(hits), hits))
    return hits[0]


def write_csv(frame, name, float_format=EVAL_FLOAT_FMT):
    """Write through a temporary file + os.replace so a concurrent reader never sees half a table."""
    path = os.path.join(OUT_DIR, name)
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, float_format=float_format, lineterminator="\n")
    os.replace(temporary, path)
    return path


def write_json(name, payload):
    path = os.path.join(OUT_DIR, name)
    v6.write_json(Path(path), Q1._jsonable(payload))
    os.chmod(path, 0o644)                     # the atomic writer creates 0600; keep the set uniform
    return path


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def rel(path):
    return os.path.relpath(os.path.abspath(path), PROJECT)


def require(condition, message):
    if not condition:
        raise RuntimeError("SELF-CHECK FAILED: " + message)


# --------------------------------------------------------------------------------------------- input sources
def collect_sources():
    """Every file this export reads, with hashes; nothing outside the list is opened."""
    exp = os.path.join(PROJECT, "experiments", EXP_CANDIDATE)
    base = os.path.join(PROJECT, "experiments", EXP_BASELINE)
    wanted = [
        (os.path.join(exp, "oof_long.csv"), "frozen OOF predictions, all four models"),
        (os.path.join(exp, "predictions.csv"), "frozen OOF predictions, candidate graph-lowrank"),
        (os.path.join(exp, "metrics.json"), "frozen candidate metrics (registered MAE values)"),
        (os.path.join(exp, "outputs.json"), "frozen protocol / grade / check record"),
        (os.path.join(exp, "inner_grid.json"), "frozen inner-CV grid (display-fit config provenance)"),
        (os.path.join(exp, "experiment.json"), "frozen registration (dependency hashes, seed, code)"),
        (os.path.join(exp, "result.json"), "frozen output-file hashes"),
        (os.path.join(base, "metrics.json"), "frozen median-baseline metrics"),
        (os.path.join(base, "outputs.json"), "frozen median-baseline record"),
        (project_path(DATA_Q1), "Q1 design table + 50 labels (4.csv values)"),
        (project_path(GRADE_PARAMS), "frozen 0-6 relative grade reference (200 train labels)"),
        (project_path(SPLITS_CSV), "frozen nested-CV split table"),
        (project_path(SPLITS_MANIFEST), "frozen split manifest"),
        (single_glob(CARD_XLSX_GLOB), "0-6 sensory card (3.xlsx): dimension names, no values"),
        (single_glob(LABEL_CSV_GLOB), "trained-panel label table (4.csv): 250 x 53"),
        (project_path("src/q1_fix.py"), "frozen model code reused read-only for the display refit"),
        (project_path("src/target_columns.py"), "frozen feature/target constants"),
        (project_path("src/v6_common.py"), "frozen protocol constants"),
    ]
    records = []
    for path, role in wanted:
        require(os.path.isfile(path), "missing input: %s" % path)
        records.append({"path": rel(path), "sha256": sha256(path),
                        "bytes": os.path.getsize(path), "role": role, "readOnly": True})
    return records


def cross_check_frozen_registration(sources):
    """The data/code hashes used here must equal the hashes EXP-0073 was registered with."""
    exp = os.path.join(PROJECT, "experiments", EXP_CANDIDATE)
    registration = read_json(os.path.join(exp, "experiment.json"))
    registered = {entry["path"]: entry["sha256"] for entry in registration.get("dependencies", [])}
    actual = {entry["path"]: entry["sha256"] for entry in sources}
    compared, mismatches = {}, []
    for path, expected in registered.items():
        if path in actual:
            compared[path] = {"registered": expected, "actual": actual[path],
                              "match": bool(expected == actual[path])}
            if expected != actual[path]:
                mismatches.append(path)
    require(not mismatches, "input hash drift vs EXP-0073 registration: %s" % mismatches)
    # artifact hashes recorded by the runner must still match the files on disk
    runner = read_json(os.path.join(exp, "result.json"))
    file_mismatches = []
    checked = {}
    for entry in runner.get("outputs", []):
        path = entry.get("path", "")
        if not path.startswith("experiments/%s/" % EXP_CANDIDATE):
            continue
        full = project_path(path)
        if not os.path.isfile(full):
            continue
        digest = sha256(full)
        checked[path] = {"recorded": entry.get("sha256"), "actual": digest,
                         "match": bool(entry.get("sha256") == digest)}
        if entry.get("sha256") != digest:
            file_mismatches.append(path)
    require(not file_mismatches, "frozen EXP-0073 outputs changed on disk: %s" % file_mismatches)
    return {"dependencyHashesCompared": compared, "outputHashesCompared": checked,
            "mismatches": [], "passed": True,
            "rule": "every input used here still has the sha256 EXP-0073 was registered with"}


# --------------------------------------------------------------------------------------------- evaluation side
def build_oof_tables():
    exp = os.path.join(PROJECT, "experiments", EXP_CANDIDATE)
    targets = list(v6.TARGETS_50)
    af30 = list(v6.TARGETS_AF30)

    wide = pd.read_csv(os.path.join(exp, "predictions.csv"), **ROUND_TRIP)
    require(list(wide.columns[:6]) == ["beer", "row", "model", "repeat", "outer_fold", "style"],
            "predictions.csv layout changed: %s" % list(wide.columns[:6]))
    require(len(wide) == 750, "predictions.csv must hold 750 OOF rows, found %d" % len(wide))
    require(sorted(wide["model"].unique().tolist()) == ["graph-lowrank"],
            "predictions.csv must hold only the candidate model, found %s"
            % sorted(wide["model"].unique().tolist()))
    require(wide["beer"].nunique() == 250, "predictions.csv must cover 250 beers")
    pairs = wide.groupby("repeat")["beer"].nunique()
    require((pairs == 250).all(), "each repeat must cover 250 beers: %s" % pairs.to_dict())
    require(wide.groupby(["repeat", "beer"]).size().max() == 1,
            "predictions.csv has duplicate (repeat, beer) rows")

    # the OOF claim: every (repeat, beer) is an outer_test row of that fold in the frozen splits
    splits = pd.read_csv(project_path(SPLITS_CSV))
    test_rows = splits[splits["role"] == "outer_test"][["repeat", "beer", "outer_fold"]]
    merged = wide[["repeat", "beer", "outer_fold"]].merge(
        test_rows, on=["repeat", "beer"], how="left", suffixes=("", "_splits"))
    require(merged["outer_fold_splits"].notna().all(),
            "some OOF rows are not outer_test rows of the frozen splits")
    mismatches = int((merged["outer_fold"].to_numpy() != merged["outer_fold_splits"].to_numpy()).sum())
    require(mismatches == 0, "%d OOF rows carry an outer_fold that disagrees with splits.csv" % mismatches)

    columns = {"repeat": wide["repeat"].astype(int), "beer": wide["beer"].astype(int),
               "row": wide["row"].astype(int), "outer_fold": wide["outer_fold"].astype(int),
               "style": wide["style"].astype(str), "model": wide["model"].astype(str)}
    for target in targets:
        columns["y_true__" + target] = wide["y_true__" + target].astype(float)
        columns["y_pred__" + target] = wide["y_pred__" + target].astype(float)
    oof750 = pd.DataFrame(columns)
    require(len(oof750) == 750, "exported OOF table must hold 750 rows, found %d" % len(oof750))
    require(oof750[["y_true__" + t for t in targets]].notna().all().all(),
            "exported OOF table has missing y_true cells")
    require(oof750[["y_pred__" + t for t in targets]].notna().all().all(),
            "exported OOF table has missing y_pred cells")

    long_source = pd.read_csv(os.path.join(exp, "oof_long.csv"), **ROUND_TRIP)
    require(len(long_source) == 150000, "oof_long.csv layout changed: %d rows" % len(long_source))
    require(sorted(long_source["model"].unique().tolist())
            == ["graph-lowrank", "graph-ridge", "median", "ridge"],
            "oof_long.csv model set changed: %s" % sorted(long_source["model"].unique().tolist()))
    long_out = long_source[long_source["model"] == "graph-lowrank"].copy()
    require(len(long_out) == 37500, "long OOF table must hold 37500 rows, found %d" % len(long_out))
    long_out = long_out[["repeat", "beer", "fold", "target", "model",
                         "y_true", "y_pred", "grade_true", "grade_pred"]].reset_index(drop=True)

    # wide and long views must agree cell-by-cell (same frozen predictions, two layouts)
    pivot = long_out.pivot_table(index=["repeat", "beer"], columns="target",
                                 values="y_pred", aggfunc="first")
    require(pivot.shape == (750, len(targets)), "long/wide OOF shapes disagree: %s" % (pivot.shape,))
    pivot = pivot[targets]
    wide_values = oof750.set_index(["repeat", "beer"])[["y_pred__" + t for t in targets]]
    wide_values.columns = targets
    diff = float(np.abs(pivot.loc[wide_values.index].to_numpy() - wide_values.to_numpy()).max())
    require(diff == 0.0, "wide and long OOF predictions disagree (max |diff| = %.3e)" % diff)

    truth_pivot = long_out.pivot_table(index=["repeat", "beer"], columns="target",
                                       values="y_true", aggfunc="first")[targets]
    truth_wide = oof750.copy()
    truth_wide["key"] = truth_wide["repeat"].astype(str) + "|" + truth_wide["beer"].astype(str)
    truth_pivot.index = [str(r) + "|" + str(b) for r, b in truth_pivot.index]
    truth_wide = truth_wide.set_index("key")[["y_true__" + t for t in targets]]
    truth_wide.columns = targets
    truth_diff = float(np.abs(truth_pivot.loc[truth_wide.index].to_numpy() - truth_wide.to_numpy()).max())
    require(truth_diff == 0.0, "wide and long OOF truth disagree (max |diff| = %.3e)" % truth_diff)

    return oof750, long_out, wide, long_source


def recompute_registered_metrics(long_source, metrics):
    """Recompute the registered A/F30 (and all-50) MAE from the frozen OOF rows only."""
    af30 = list(v6.TARGETS_AF30)
    targets = list(v6.TARGETS_50)
    primary = long_source[long_source["model"] == "graph-lowrank"]
    mae_af30 = float(np.abs(primary[primary["target"].isin(af30)]["y_true"].to_numpy()
                            - primary[primary["target"].isin(af30)]["y_pred"].to_numpy()).mean())
    mae_all50 = float(np.abs(primary["y_true"].to_numpy() - primary["y_pred"].to_numpy()).mean())
    median = long_source[long_source["model"] == "median"]
    baseline_af30 = float(np.abs(median[median["target"].isin(af30)]["y_true"].to_numpy()
                                 - median[median["target"].isin(af30)]["y_pred"].to_numpy()).mean())
    base_metrics = read_json(os.path.join(PROJECT, "experiments", EXP_BASELINE, "metrics.json"))

    def close(value, expected):
        return bool(abs(value - expected) <= TOLERANCE_REL * max(1.0, abs(expected)))

    require(close(mae_af30, EXPECTED_MAE_AF30),
            "recomputed A/F30 MAE %.17g != registered %.17g" % (mae_af30, EXPECTED_MAE_AF30))
    require(close(mae_af30, float(metrics["mae"])),
            "recomputed A/F30 MAE disagrees with EXP-0073 metrics.json")
    require(close(mae_all50, EXPECTED_MAE_ALL50),
            "recomputed all-50 MAE %.17g != registered %.17g" % (mae_all50, EXPECTED_MAE_ALL50))
    require(close(baseline_af30, EXPECTED_BASELINE_MAE_AF30),
            "recomputed median baseline %.17g != registered %.17g"
            % (baseline_af30, EXPECTED_BASELINE_MAE_AF30))
    require(close(baseline_af30, float(base_metrics["mae"])),
            "recomputed median baseline disagrees with EXP-0074 metrics.json")
    require(close(float(metrics["mae_median"]), EXPECTED_BASELINE_MAE_AF30),
            "EXP-0073 metrics.json median value drifted")

    return {
        "metricKey": "mae",
        "definition": ("A/F30 equal-weight mean of |y_true - y_pred| over the CONCATENATED 750 OOF "
                       "rows (250 beers x 3 repeats); equal weight over the 30 Aroma15+Flavour15 "
                       "targets; a pooled row metric, NOT the mean of three per-repeat scores"),
        "mae_af30_recomputed_from_frozen_oof": mae_af30,
        "mae_af30_registered": EXPECTED_MAE_AF30,
        "mae_af30_abs_difference": float(abs(mae_af30 - EXPECTED_MAE_AF30)),
        "mae_af30_exp_metrics_json": float(metrics["mae"]),
        "tolerance": {"kind": "relative", "value": TOLERANCE_REL, "passed": True},
        "mae_all50_recomputed": mae_all50,
        "mae_all50_registered": EXPECTED_MAE_ALL50,
        "baseline_median_af30_recomputed": baseline_af30,
        "baseline_median_af30_registered": EXPECTED_BASELINE_MAE_AF30,
        "baseline_median_af30_exp0074_metrics_json": float(base_metrics["mae"]),
        "skill_af30": float(1.0 - mae_af30 / baseline_af30),
        "evaluationRows": 750,
        "evaluationModel": "graph-lowrank",
        "note": ("these numbers come only from experiments/EXP-0073/oof_long.csv (and the "
                 "median rows of the same file); the full-sample display scores are NOT used"),
    }


# --------------------------------------------------------------------------------------------- display side
def choose_display_config():
    """Aggregate the frozen inner-CV grid (no outer-test row) into one display-refit cell."""
    grid = read_json(os.path.join(PROJECT, "experiments", EXP_CANDIDATE, "inner_grid.json"))
    cells = {}          # (rep, lam, gamma, rank) -> {(repeat, outer_fold): pooled inner AF30 MAE}
    selections = []     # what each frozen outer fold actually selected (provenance)
    for repeat_key in sorted(grid, key=int):
        for fold_key in sorted(grid[repeat_key]):
            entry = grid[repeat_key][fold_key]
            chosen = entry["selection"]["graph-lowrank"]
            selections.append({
                "repeat": int(repeat_key), "outer_fold": int(fold_key.replace("outer_fold_", "")),
                "representation": str(chosen["representation"]), "lambda": float(chosen["lambda"]),
                "gamma": float(chosen["gamma"]), "rank": int(chosen["rank"]),
                "pooledInnerMaeAf30": float(chosen["pooled_valid_mae_af30"]),
            })
            for cell in entry["cells"]:
                if cell.get("rank") is None:
                    continue
                key = (str(cell["representation"]), float(cell["lambda"]),
                       float(cell["gamma"]), int(cell["rank"]))
                cells.setdefault(key, {})[(int(repeat_key), int(fold_key.replace("outer_fold_", "")))] = \
                    float(cell["pooled_valid_mae_af30"])
    require(len(selections) == 9, "expected 9 frozen outer folds, found %d" % len(selections))
    repeated = [key for key, value in cells.items() if len(value) != 9]
    require(not repeated, "inner grid cells missing folds: %s" % repeated[:3])

    ranking = sorted(((float(np.mean(list(value.values()))), key) for key, value in cells.items()),
                     key=lambda item: (item[0], item[1]))
    best_mean, best_key = ranking[0]
    runner_up_mean, runner_up_key = ranking[1]
    representation, lam, gamma, rank = best_key
    frequency = {}
    for entry in selections:
        key = (entry["representation"], entry["lambda"], entry["gamma"], entry["rank"])
        frequency[key] = frequency.get(key, 0) + 1

    # which other cells were actually selected at least once (sensitivity set)
    selected_cells = [key for key in cells if frequency.get(key, 0) > 0]
    return {
        "config": {"representation": representation, "lambda": lam, "gamma": gamma, "rank": rank},
        "configSelection": {
            "rule": ("the graph-lowrank cell with the lowest MEAN frozen inner-validation pooled "
                     "A/F30 MAE over the 9 frozen outer folds in experiments/EXP-0073/"
                     "inner_grid.json; each fold's value is that fold's pooled inner-validation "
                     "MAE, so the aggregate uses no outer-test row and no 250-row fit statistic"),
            "meanInnerMaeAf30": best_mean,
            "runnerUp": {"config": {"representation": runner_up_key[0], "lambda": runner_up_key[1],
                                    "gamma": runner_up_key[2], "rank": runner_up_key[3]},
                         "meanInnerMaeAf30": runner_up_mean},
            "marginToRunnerUp": float(runner_up_mean - best_mean),
            "topFiveCells": [{"representation": key[0], "lambda": key[1], "gamma": key[2],
                              "rank": key[3], "meanInnerMaeAf30": value}
                             for value, key in ranking[:5]],
            "nCandidateCells": int(len(cells)),
        },
        "frozenPerFoldSelections": selections,
        "selectedCellFrequency": [
            {"representation": key[0], "lambda": key[1], "gamma": key[2], "rank": key[3],
             "timesSelected": int(count)}
            for key, count in sorted(frequency.items(), key=lambda item: (-item[1], item[0]))],
        "sensitivityCells": [list(key) for key in sorted(selected_cells)],  # every selected cell
        "cells": cells,
    }


def full_sample_refit(frame, targets, config):
    """Refit the frozen graph-lowrank model on all 250 rows, using src/q1_fix.py read-only."""
    prep = Q1.Preprocessor(frame)                                   # medians/z-score/Rank-Gauss on 250 rows
    laplacian, graph_info = Q1.graph_laplacian(prep.imputed(frame))  # graph on 250 rows
    design = prep.design(frame, config["representation"])
    truth = frame[list(targets)].to_numpy(dtype=float)
    prediction, beta, fit_info = Q1.fit_and_predict(
        design, truth, design, laplacian, float(config["lambda"]), float(config["gamma"]),
        int(config["rank"]))
    fitted = {"prediction": prediction, "beta": beta, "designColumns": int(design.shape[1]),
              "graph": graph_info, "fit": fit_info,
              "imputationMedianCells": int(prep.n_missing_cells)}
    return fitted


def build_display_tables(frame, targets, fitted, config, seed):
    prediction = fitted["prediction"]
    require(prediction.shape == (250, 50), "display score matrix must be 250x50, got %s"
            % (prediction.shape,))
    require(bool(np.isfinite(prediction).all()), "display score matrix has non-finite cells")

    # canonical row order: beer ascending (the design table itself is in 4.csv row order)
    order = np.argsort(frame["beer"].to_numpy(dtype=int), kind="mergesort")
    keys = frame.iloc[order]
    prediction = prediction[order, :]
    note = ("display-only full-sample refit; config %s lambda=%g gamma=%g rank=%d; seed %d "
            "(the fit draws no random numbers); NOT an evaluation prediction, evaluation uses "
            "oof_predictions_750.csv"
            % (config["representation"], float(config["lambda"]), float(config["gamma"]),
               int(config["rank"]), int(seed)))
    score_columns = {"beer": keys["beer"].astype(int).to_numpy(),
                     "row": keys["row"].astype(int).to_numpy(),
                     "style": keys[v6.STYLE_COL].astype(str).to_numpy()}
    for position, target in enumerate(targets):
        score_columns[target] = prediction[:, position].astype(float)
    scores = pd.DataFrame(score_columns)
    scores["fit_identity"] = "full-sample-refit"
    scores["source_experiment"] = EXP_CANDIDATE
    scores["source_script"] = "src/q1_export_scores.py"
    scores["note"] = note
    require(len(scores) == 250, "display table must hold 250 rows")
    require(scores["beer"].is_unique, "display table beer keys are not unique")
    require(set(scores["beer"].tolist()) == set(frame["beer"].astype(int).tolist()),
            "display table beer keys differ from the 250-row design table")

    params = read_json(project_path(GRADE_PARAMS))["targets"]
    grade_columns = {"beer": keys["beer"].astype(int).to_numpy(),
                     "row": keys["row"].astype(int).to_numpy(),
                     "style": keys[v6.STYLE_COL].astype(str).to_numpy()}
    grid_sizes, grade_arrays = [], {}
    for position, target in enumerate(targets):
        grid = np.sort(np.asarray(params[target]["trainValues"], dtype=float))
        grid_sizes.append(int(grid.size))
        continuous = 6.0 * v6.midrank_cdf(grid, prediction[:, position])
        discrete = v6.to_grade(prediction[:, position], grid)
        grade_columns["g_cont__" + target] = continuous.astype(float)
        grade_columns["g6__" + target] = discrete.astype(int)
        grade_arrays[target] = (continuous, discrete)
    grades = pd.DataFrame(grade_columns)
    require(len(set(grid_sizes)) == 1 and grid_sizes[0] == 200,
            "grade reference must be the 200 training labels per target, got %s" % sorted(set(grid_sizes)))
    g6 = grades[["g6__" + t for t in targets]].to_numpy()
    gcont = grades[["g_cont__" + t for t in targets]].to_numpy()
    require(int(g6.min()) == 0 and int(g6.max()) <= 6, "discrete grades outside 0..6")
    require(float(gcont.min()) >= 0.0 and float(gcont.max()) <= 6.0,
            "continuous grades outside [0, 6]")
    grades["grade_type"] = "relative_inferred_grade"
    grades["grade_reference"] = "q1_grade_params.json:trainValues (n=200, SPLIT-0001 train labels)"
    grades["fit_identity"] = "full-sample-refit"
    grades["source_experiment"] = EXP_CANDIDATE
    grades["source_script"] = "src/q1_export_scores.py"
    grades["note"] = ("RELATIVE INFERRED grade within the training label distribution, not the "
                      "original human 0-6 score; 0 does not mean 'absence', 6 does not mean "
                      "'full marks'")
    return scores, grades


def build_dimension_map(targets):
    af30 = set(v6.TARGETS_AF30)
    groups = {"Aroma15": set(v6.GROUPS["Aroma15"]), "Flavour15": set(v6.GROUPS["Flavour15"]),
              "Other20": set(v6.GROUPS["Other20"])}
    params = read_json(project_path(GRADE_PARAMS))["targets"]
    label_table = pd.read_csv(single_glob(LABEL_CSV_GLOB))
    label_columns = [c for c in label_table.columns
                     if c not in ("beer", "beer_id", "tasting_category_fine")]
    require(set(label_columns) == set(targets),
            "4.csv label columns differ from the frozen 50-target universe")
    require(not any("acetaldehyde" in c.lower() for c in label_columns),
            "4.csv unexpectedly carries an acetaldehyde label; the unlabelled-card-item row would be wrong")

    # card header (3.xlsx summary) spells three fields differently; verify the aliasing is exact
    card_path = single_glob(CARD_XLSX_GLOB)
    card = pd.read_excel(card_path, sheet_name="summary", header=None)
    header = [str(value) for value in card.iloc[0].tolist()]
    card_names = [name for name in header if name not in ("Beer", "comments")]
    mapped = [CARD_ALIAS.get(target, target) for target in targets]
    require(len(card_names) == 50, "3.xlsx summary must define 50 card fields, found %d" % len(card_names))
    require(sorted(card_names) == sorted(mapped),
            "3.xlsx card fields do not match the 50 data dimensions after aliasing: %s"
            % sorted(set(card_names) ^ set(mapped)))
    card_sheet = pd.read_excel(card_path, sheet_name="beer_1", header=None)
    card_text = " ".join(str(value) for value in card_sheet.to_numpy().ravel().tolist())
    require("Acetaldehyde" in card_text,
            "the 3.xlsx sensory card no longer prints the acetaldehyde item")
    require(not any("cetaldehyde" in name for name in card_names),
            "the 3.xlsx summary header unexpectedly names acetaldehyde, so it would be labelled")
    card_evidence = {"cardFile": rel(card_path), "cardSheet": "3.xlsx beer_1",
                     "cardItemText": UNLABELLED_CARD_ITEM["card_name"],
                     "printedOnCardSheet": True,
                     "presentInSummaryHeader": False,
                     "presentInLabelTable": False}

    rows = []
    for target in targets:
        if target in groups["Aroma15"]:
            category, group = "Aroma", "Aroma15"
        elif target in groups["Flavour15"]:
            category, group = "Flavour", "Flavour15"
        else:
            category, group = OTHER_CATEGORY[target], "Other20"
        rows.append({
            "dimension": target,
            "category": category,
            "in_af30": 1 if target in af30 else 0,
            "label_source": ("4.csv trained-panel continuous label (250/250 present); column "
                             "'%s' of data/clean/q1_mapped.csv" % target),
            "scale_note": ("continuous standardised/centred sensory value on the 4.csv label "
                           "scale (the panel's 0-6 card rating after the dataset's own "
                           "standardisation); model centres it per target; the g6__ column is a "
                           "RELATIVE grade from the 200-label training CDF"),
            "has_label_in_cardsheet": 1,
            "group": group,
            "card_name": CARD_ALIAS.get(target, target),
            "reference_grade_values": int(params[target]["nTrain"]),
            "note": "labelled dimension: counts toward the A/F30 primary metric" if target in af30
                    else "labelled dimension: reported in the 50-dimension extension, outside A/F30",
        })
    rows.append({
        "dimension": UNLABELLED_CARD_ITEM["dimension"],
        "category": UNLABELLED_CARD_ITEM["category"],
        "in_af30": 0,
        "label_source": "none: no label column exists in 4.csv or any trained-panel table",
        "scale_note": "not applicable: with no label there is no scale, no prediction and no grade",
        "has_label_in_cardsheet": 0,
        "group": "UnlabelledCardItem",
        "card_name": UNLABELLED_CARD_ITEM["card_name"],
        "reference_grade_values": 0,
        "note": UNLABELLED_CARD_ITEM["note"],
    })
    table = pd.DataFrame(rows)
    labelled = int((table["has_label_in_cardsheet"] == 1).sum())
    unlabelled = int((table["has_label_in_cardsheet"] == 0).sum())
    af30_count = int(table["in_af30"].sum())
    require(len(table) == 51, "dimension map must hold 51 rows (50 labelled + 1 card item)")
    require(labelled == 50 and unlabelled == 1, "dimension map label counts are wrong")
    require(af30_count == 30, "dimension map A/F30 flag must cover exactly 30 dimensions")
    stats = {"rows": int(len(table)), "labelled": labelled, "unlabelledCardItems": unlabelled,
             "af30": af30_count, "af50": int(len(targets)),
             "groupCounts": {key: int((table["group"] == key).sum()) for key in
                             ("Aroma15", "Flavour15", "Other20", "UnlabelledCardItem")},
             "categoryCounts": {str(k): int(v) for k, v in
                                table["category"].value_counts().sort_index().items()},
             "cardAliases": CARD_ALIAS,
             "unlabelledCardItemEvidence": card_evidence}
    return table, stats


# --------------------------------------------------------------------------------------------- main
def main():
    started = time.perf_counter()
    seed = int(os.environ.get("MODELING_SEED") or 20261025)
    run_dir = os.environ.get("MODELING_EXPERIMENT_DIR") or os.path.join(
        PROJECT, "state", "devrun", "q1_v6fix", "single")
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(run_dir, exist_ok=True)
    artifacts_dir = os.path.join(run_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    sources = collect_sources()
    registration_check = cross_check_frozen_registration(sources)

    targets = list(v6.TARGETS_50)
    af30 = list(v6.TARGETS_AF30)
    require(list(Q1.v6.TARGETS_50) == targets, "target order drifted between q1_fix and v6_common")
    from target_columns import TARGET_COLS
    require(list(TARGET_COLS) == targets, "target order drifted vs src/target_columns.py")

    metrics = read_json(os.path.join(PROJECT, "experiments", EXP_CANDIDATE, "metrics.json"))
    oof750, oof_long, wide_source, long_source = build_oof_tables()
    evaluation = recompute_registered_metrics(long_source, metrics)

    # ------------------------------------------------------------------ display refit (reporting only)
    frame = v6.load_frame()
    require(len(frame) == 250, "Q1 design table must hold 250 rows")
    require(v6.STYLE_COL in frame.columns, "Q1 design table lacks the style column")
    require(frame["beer"].is_unique, "Q1 design table beer keys are not unique")
    chosen = choose_display_config()
    fitted = full_sample_refit(frame, targets, chosen["config"])
    sensitivity = []
    for key in chosen["sensitivityCells"]:
        alternative = {"representation": key[0], "lambda": key[1], "gamma": key[2], "rank": key[3]}
        if alternative == chosen["config"]:
            continue
        other = full_sample_refit(frame, targets, alternative)
        difference = np.abs(other["prediction"] - fitted["prediction"])
        sensitivity.append({
            "config": alternative,
            "occurrencesInFrozenSelection": next(
                (entry["timesSelected"] for entry in chosen["selectedCellFrequency"]
                 if entry["representation"] == key[0] and entry["lambda"] == key[1]
                 and entry["gamma"] == key[2] and entry["rank"] == key[3]), 0),
            "maxAbsScoreDifference": float(difference.max()),
            "meanAbsScoreDifference": float(difference.mean()),
        })

    scores, grades = build_display_tables(frame, targets, fitted, chosen["config"], seed)
    dimension_map, dimension_stats = build_dimension_map(targets)

    # ------------------------------------------------------------------ write artifacts
    paths = {}
    paths["oof_predictions_750.csv"] = write_csv(oof750, "oof_predictions_750.csv")
    paths["oof_predictions_long_37500.csv"] = write_csv(oof_long, "oof_predictions_long_37500.csv")
    paths["beer_scores_250.csv"] = write_csv(scores, "beer_scores_250.csv", DISPLAY_FLOAT_FMT)
    paths["grades_250.csv"] = write_csv(grades, "grades_250.csv", DISPLAY_FLOAT_FMT)
    paths["dimension_map.csv"] = write_csv(dimension_map, "dimension_map.csv")

    # read back what was actually written before hashing it
    oof_back = pd.read_csv(paths["oof_predictions_750.csv"], **ROUND_TRIP)
    scores_back = pd.read_csv(paths["beer_scores_250.csv"], **ROUND_TRIP)
    grades_back = pd.read_csv(paths["grades_250.csv"], **ROUND_TRIP)
    map_back = pd.read_csv(paths["dimension_map.csv"], **ROUND_TRIP)
    long_back = pd.read_csv(paths["oof_predictions_long_37500.csv"], **ROUND_TRIP)
    require(len(oof_back) == 750, "written OOF table is not 750 rows")
    require(len(long_back) == 37500, "written long OOF table is not 37500 rows")
    require(len(map_back) == 51, "written dimension map is not 51 rows")
    require(int((map_back["has_label_in_cardsheet"] == 1).sum()) == 50,
            "written dimension map does not have 50 labelled rows")
    require(int(map_back["in_af30"].sum()) == 30, "written dimension map does not flag 30 A/F dims")
    mae_from_export = float(np.abs(
        oof_back[["y_true__" + t for t in af30]].to_numpy()
        - oof_back[["y_pred__" + t for t in af30]].to_numpy()).mean())
    require(abs(mae_from_export - EXPECTED_MAE_AF30) <= TOLERANCE_REL * max(1.0, EXPECTED_MAE_AF30),
            "A/F30 MAE recomputed from the WRITTEN OOF table is %.17g, expected %.17g"
            % (mae_from_export, EXPECTED_MAE_AF30))
    # the written evaluation tables must hold exactly the frozen doubles (no transformation at all)
    exact_cells, exact_mismatches = 0, 0
    for target in targets:
        for prefix in ("y_true__", "y_pred__"):
            left = oof_back[prefix + target].to_numpy()
            right = wide_source[prefix + target].to_numpy()
            exact_cells += int(left.size)
            exact_mismatches += int((left != right).sum())
    require(exact_mismatches == 0,
            "%d exported OOF cells differ from the frozen predictions" % exact_mismatches)
    long_cells, long_mismatches = 0, 0
    graph_long = long_source[long_source["model"] == "graph-lowrank"].reset_index(drop=True)
    for column in ("y_true", "y_pred", "grade_true", "grade_pred"):
        left = long_back[column].to_numpy()
        right = graph_long[column].to_numpy()
        require(left.shape == right.shape, "long companion row count drifted")
        long_cells += int(left.size)
        long_mismatches += int((left != right).sum())
    require(long_mismatches == 0,
            "%d exported long OOF cells differ from the frozen oof_long rows" % long_mismatches)
    require(scores_back["beer"].is_unique and len(scores_back) == 250,
            "written display table is not 250 unique beers")
    require(all(target in scores_back.columns for target in targets),
            "written display table is missing a dimension column")
    require(len(grades_back) == 250, "written grade table is not 250 rows")
    require(sorted(grades_back["grade_type"].unique().tolist()) == ["relative_inferred_grade"],
            "grade table does not declare the relative_inferred_grade type")

    # structural separation: display scores never feed an evaluation number
    display_values = scores_back[targets].to_numpy()
    oof_mean = oof_back.groupby("beer")[["y_pred__" + t for t in targets]].mean().to_numpy()
    display_vs_oof = float(np.abs(display_values - oof_mean).max())
    require(display_vs_oof > 0.0, "display scores and OOF means are identical: the tables were mixed")
    separation = {
        "evaluationTable": "oof_predictions_750.csv",
        "evaluationSource": "experiments/EXP-0073/predictions.csv + oof_long.csv (frozen OOF)",
        "displayTable": "beer_scores_250.csv",
        "displaySource": "full-sample refit of the frozen model on all 250 rows",
        "displayScoresUsedInAnyMetric": False,
        "rule": ("no MAE / R2 / QWK / baseline / claim number is computed from the display scores; "
                 "every evaluation number is recomputed from the frozen OOF rows only"),
        "diagnosticOnly": {"maxAbsDifferenceDisplayVsOofMean": display_vs_oof,
                           "meaning": ("the two tables are different objects; this is a separation "
                                       "diagnostic, not an error estimate and not used anywhere")},
    }

    note_payload = {
        "artifact": "outputs/q1/score_scale_note.json",
        "purpose": ("pin the label scale, separate the evaluation (OOF) predictions from the "
                    "display (full-sample refit) scores, and define the A/F30 metric in one place"),
        "frozenModel": {
            "experimentId": EXP_CANDIDATE,
            "modelId": "MODEL-0048",
            "family": "graph-lowrank",
            "title": "graph-regularised low-rank multi-output regression, nested 3x3x3 protocol",
            "protocol": {"repeats": 3, "outerFolds": 3, "innerFolds": 3,
                         "seeds": list(v6.SEEDS), "pooledOofRows": 750,
                         "splits": SPLITS_CSV},
            "sourceCode": "src/q1_fix.py",
            "randomness": ("none in the fit: src/q1_fix.py draws no random number; the seed only "
                           "labels the frozen repeat/selection protocol"),
        },
        "displayFit": {
            "fitIdentity": "full-sample-refit",
            "config": chosen["config"],
            "configSelectionRule": chosen["configSelection"]["rule"],
            "seed": int(seed),
            "modelCode": "src/q1_fix.py (Preprocessor / graph_laplacian / fit_and_predict, read-only)",
            "trainingRows": 250,
            "designColumns": fitted["designColumns"],
            "graphEdges": fitted["graph"]["edges"],
            "graphTau": fitted["graph"]["tau"],
            "sensitivityAcrossSelectedCells": [
                {"config": item["config"], "maxAbsScoreDifference": item["maxAbsScoreDifference"]}
                for item in sensitivity],
            "notAnExperiment": ("no experiment id is created here: this refit produces display scores "
                                "only and is not registered as evaluation evidence"),
        },
        "labelScale": {
            "whereTheLabelComesFrom": ("data/clean/q1_mapped.csv == data/raw 4.csv: the trained "
                                       "panel's 0-6 card rating AFTER the dataset's own "
                                       "standardisation/centring, i.e. a continuous value with "
                                       "negative numbers, NOT the original discrete 0-6 score"),
            "observedScale": {
                "meanOfTargetMeans": float(np.mean([frame[t].mean() for t in targets])),
                "meanTargetStandardDeviation": float(np.mean([frame[t].std(ddof=0) for t in targets])),
                "min": float(min(frame[t].min() for t in targets)),
                "max": float(max(frame[t].max() for t in targets)),
                "nLabels": int(frame[targets].notna().to_numpy().sum()),
            },
            "whatTheCodeActuallyDoes": ("per-target CENTRING only: y_centred = y - mean(training y). "
                                        "The code does NOT divide the targets by the training "
                                        "standard deviation (that was the wrong description in the "
                                        "earlier paper text, not the implementation)"),
            "whereItIsImplemented": {
                "file": "src/q1_fix.py",
                "functions": ["moments", "fit_and_predict"],
                "detail": ("moments() stores y_bar and y_centred and the normal equations use only "
                           "Zc^T Yc/n; fit_and_predict() adds y_bar back. No target-scale field "
                           "exists anywhere in the Q1 model path"),
                "solver": ("B = A^{-1} C Vr Vr^T with A = Zc^T Zc/n + lambda I + gamma L and "
                           "C = Zc^T Yc/n; the objective is ||Yc - Zc B||_F^2/n + lambda ||B||^2 "
                           "+ gamma tr(B^T L B)"),
            },
            "whyTheScaleMatters": ("the penalties act on B, so rescaling target columns changes B "
                                   "and therefore the fitted predictions: the low-rank fit is NOT "
                                   "scale-invariant, and no claim here is transferred from a "
                                   "standardised-target model. Every reported error is on the "
                                   "given 4.csv label scale"),
            "whatIsReportedOnThisScale": ("mae (A/F30 equal-weight), mae_all50, per-target MAE/R2/"
                                          "skill and the per-style MAE in EXP-0073; all of them are "
                                          "label-scale errors, not 0-6 grade errors"),
        },
        "oofVsDisplay": separation,
        "af30Metric": evaluation,
        "grades": {
            "rule": ("a = mid-rank empirical CDF of the 200 frozen training labels "
                     "(data/processed/q1_grade_params.json trainValues, SPLIT-0001 train rows); "
                     "g_cont = 6a; g = clip(floor(6a + 0.5), 0, 6)"),
            "scope": ("relative inferred grade WITHIN THE TRAINING LABEL DISTRIBUTION; the same rule "
                      "as src/q1_grade_all.py midpoint_cdf and v6_common.to_grade"),
            "meaningOf0And6": ("0 = lowest relative band of the training distribution, NOT 'the "
                               "flavour is absent'; 6 = highest relative band, NOT 'the panel gave "
                               "full marks'"),
            "whatItIsNot": ("not the original human 0-6 score and not calibrated to the paper card; "
                            "recovering the original discrete card score is not identifiable from "
                            "4.csv"),
            "whereItIsUsed": ("display table only (grades_250.csv); the evaluation numbers in "
                              "EXP-0073 are label-scale MAE and are not grade metrics"),
            "referenceSizePerTarget": 200,
        },
        "dimensionMap": {
            "artifact": "outputs/q1/dimension_map.csv",
            "labelledDimensions": dimension_stats["labelled"],
            "unlabelledCardItems": dimension_stats["unlabelledCardItems"],
            "af30": dimension_stats["af30"],
            "groups": dimension_stats["groupCounts"],
            "categories": dimension_stats["categoryCounts"],
            "cardAliases": dimension_stats["cardAliases"],
            "unlabelledCardItemNote": UNLABELLED_CARD_ITEM["note"],
            "hasLabelInCardsheetMeaning": ("1 = the dimension has a trained-panel label column in "
                                           "4.csv and is defined on the 3.xlsx card; 0 = the card "
                                           "defines the item but no label column exists, so it is "
                                           "listed without prediction, grading or fabricated truth"),
            "externalDescriptorsNotLabels": ("the Ratebeer sensory descriptors of 7.csv / 8.xlsx "
                                             "are external support data, not Q1 labels: e.g. "
                                             "palate_acetaldehyde is 250/250 missing in 7.csv. "
                                             "They are deliberately not mapped as dimensions here"),
        },
        "rowAndColumnContract": {
            "beer_scores_250.csv": ("exactly 250 rows = 250 unique beers, sorted by beer ascending; "
                                    "columns: beer,row,style, the 50 dimension columns in the frozen "
                                    "TARGETS_50 order, then fit_identity/source_experiment/"
                                    "source_script/note"),
            "grades_250.csv": ("same 250-row key order; per dimension a g6__<dimension> (int 0-6) "
                               "and a g_cont__<dimension> (continuous 0-6) column"),
            "oof_predictions_750.csv": ("exactly 750 rows = 250 beers x 3 repeats, one row per "
                                        "(repeat,beer); per dimension the columns y_true__<dimension> "
                                        "and y_pred__<dimension> (the 'target' axis is carried by "
                                        "the column names); the tidy per-target form is "
                                        "oof_predictions_long_37500.csv"),
            "dimension_map.csv": ("51 rows = 50 labelled dimensions in TARGETS_50 order + 1 "
                                  "unlabelled sensory-card item (acetaldehyde)"),
            "floatFormat": {
                "evaluationArtifacts": ("shortest round-trip decimal (pandas default), i.e. exactly "
                                        "the text of the frozen EXP-0073 files; read them with a "
                                        "correctly rounding parser (pandas float_precision="
                                        "round_trip) if bit-exact reproduction is needed"),
                "displayArtifacts": DISPLAY_FLOAT_FMT + " (display tables only; no metric is computed from them)"},
        },
        "whatThisExportDoesNotDo": [
            "it does not re-train, re-register or overwrite experiments/EXP-0073 or experiments/EXP-0074",
            "it does not create any new evaluation number: the A/F30 and median-baseline values are "
            "recomputed from the frozen OOF rows and only checked against the registered ones",
            "it does not put the full-sample display scores into any metric, claim, figure or grade "
            "comparison",
            "it does not invent a label or a score for the unlabelled acetaldehyde card item",
        ],
        "limitations": [
            ("no external or holdout evaluation exists for Q1: all evaluation numbers are internal "
             "nested CV (750 pooled OOF rows); the display scores are a full-sample refit and their "
             "in-sample fit error is deliberately not reported as a performance estimate"),
            ("the 0-6 grades are relative bands of the training label distribution; they are not the "
             "original human card scores and must not be presented as recovered ground truth"),
            ("the acetaldehyde card item has no label in 4.csv, so it is not predicted or graded; "
             "no number is invented for it"),
            ("the display refit happens to select gamma = 0.1 (graph penalty active) by the frozen "
             "inner-CV aggregate; gamma = 0.0 was selected in 3 of 9 outer folds, so the graph "
             "penalty is not universally helpful and that is reported, not hidden"),
        ],
    }
    paths["score_scale_note.json"] = write_json("score_scale_note.json", note_payload)

    def artifact_record(name, role, chain, source, rows=None, cols=None, float_format=None):
        path = paths[name]
        return {"path": rel(path), "sha256": sha256(path), "bytes": os.path.getsize(path),
                "rows": rows, "cols": cols, "role": role, "chain": chain, "source": source,
                "floatFormat": float_format}

    manifest = {
        "artifact": "outputs/q1/export_manifest.json",
        "generatedBy": {
            "script": "src/q1_export_scores.py",
            "scriptSha256": sha256(os.path.join(PROJECT, "src", "q1_export_scores.py")),
            "interpreter": sys.executable,
            "pythonVersion": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "registeredSeed": seed,
            "deterministic": ("no timestamps, no random draws, no environment paths and no runtime "
                              "seconds are written into any artifact; two runs produce byte-identical "
                              "files (the run directory only receives copies plus run.json)"),
        },
        "sources": sources,
        "frozenRegistrationCrossCheck": registration_check,
        "evaluation": evaluation,
        "displayFit": {
            "fitIdentity": "full-sample-refit",
            "why": ("the evaluation must stay on OOF predictions; the 250-beer score table is a "
                    "display artifact produced by one refit on all 250 rows"),
            "config": chosen["config"],
            "configSelection": chosen["configSelection"],
            "frozenPerFoldSelections": chosen["frozenPerFoldSelections"],
            "selectedCellFrequency": chosen["selectedCellFrequency"],
            "fit": {"nTrainRows": 250, "nDesignColumns": fitted["designColumns"],
                    "interceptRule": fitted["fit"]["interceptRule"],
                    "coefficientNorm": fitted["fit"]["coefficientNorm"],
                    "imputationMedianCells": fitted["imputationMedianCells"],
                    "graph": fitted["graph"]},
            "sensitivityToOtherSelectedCells": sensitivity,
            "evaluationLeakage": ("the display fit sees all 250 rows by construction because it is "
                                  "not an evaluation; it never substitutes an OOF prediction and no "
                                  "metric is computed from it"),
        },
        "artifacts": [
            artifact_record("oof_predictions_750.csv",
                            "frozen 750-row OOF predictions (250 beers x 3 repeats)",
                            "evaluation",
                            "%s/predictions.csv (model=graph-lowrank), cross-checked cell-by-cell "
                            "against %s/oof_long.csv" % (EXP_CANDIDATE, EXP_CANDIDATE),
                            rows=int(oof_back.shape[0]), cols=int(oof_back.shape[1]),
                            float_format="shortest round-trip decimal (pandas default, same text "
                                         "as the frozen files)"),
            artifact_record("oof_predictions_long_37500.csv",
                            "tidy one row per (repeat, beer, target)",
                            "evaluation",
                            "%s/oof_long.csv rows with model=graph-lowrank (37500 rows)"
                            % EXP_CANDIDATE,
                            rows=int(long_back.shape[0]), cols=int(long_back.shape[1]),
                            float_format="shortest round-trip decimal (pandas default, same text "
                                         "as the frozen files)"),
            artifact_record("beer_scores_250.csv",
                            "250 beers x 50 continuous full-sample-refit scores",
                            "display",
                            ("full-sample refit of the %s model (config below) on "
                             "data/clean/q1_mapped.csv; no EXP-0073 prediction is reused"
                             % EXP_CANDIDATE),
                            rows=int(scores_back.shape[0]), cols=int(scores_back.shape[1]),
                            float_format=DISPLAY_FLOAT_FMT),
            artifact_record("grades_250.csv",
                            "continuous + discrete 0-6 relative inferred grades",
                            "display",
                            "beer_scores_250.csv + data/processed/q1_grade_params.json "
                            "(200 training labels per target)",
                            rows=int(grades_back.shape[0]), cols=int(grades_back.shape[1]),
                            float_format=DISPLAY_FLOAT_FMT),
            artifact_record("dimension_map.csv",
                            "50 labelled dimensions + 1 unlabelled card item",
                            "mapping",
                            "data/raw 3.xlsx (card names) + 4.csv (labels) + 8.xlsx (categories)",
                            rows=int(map_back.shape[0]), cols=int(map_back.shape[1]),
                            float_format=None),
            artifact_record("score_scale_note.json",
                            "label scale, OOF/display boundary, A/F30 definition",
                            "notes",
                            "generated from the frozen sources + the two tables above",
                            float_format=None),
        ],
        "checks": {
            "oofRows750": {"value": int(oof_back.shape[0]), "passed": True},
            "oofUniqueBeerRepeat": {"value": int(oof_back[["repeat", "beer"]].drop_duplicates().shape[0]),
                                    "passed": True},
            "oofBeersPerRepeat": {str(int(k)): int(v) for k, v in
                                  oof_back.groupby("repeat")["beer"].nunique().items()},
            "oofFoldMatchesFrozenSplits": {"rowsChecked": 750, "mismatches": 0, "passed": True},
            "displayTable": {"rows": int(scores_back.shape[0]),
                             "uniqueBeer": int(scores_back["beer"].nunique()),
                             "dimensionColumns": int(len(targets)),
                             "missingCells": int(scores_back[targets].isna().to_numpy().sum()),
                             "passed": True},
            "gradeTable": {"rows": int(grades_back.shape[0]),
                           "discreteMin": int(grades_back[["g6__" + t for t in targets]].to_numpy().min()),
                           "discreteMax": int(grades_back[["g6__" + t for t in targets]].to_numpy().max()),
                           "continuousMin": float(grades_back[["g_cont__" + t for t in targets]].to_numpy().min()),
                           "continuousMax": float(grades_back[["g_cont__" + t for t in targets]].to_numpy().max()),
                           "passed": True},
            "dimensionMap": dimension_stats,
            "exportedOofMatchesFrozenSourceExactly": {
                "cellsCompared": exact_cells, "mismatches": exact_mismatches,
                "longCellsCompared": long_cells, "longMismatches": long_mismatches,
                "parseMode": "pandas float_precision=round_trip (the default fast parser can be a "
                             "few ulps off on 16-17 digit decimals)",
                "passed": True},
            "maeAf30RecomputedFromWrittenOof": {
                "value": mae_from_export, "registered": EXPECTED_MAE_AF30,
                "absDifference": float(abs(mae_from_export - EXPECTED_MAE_AF30)),
                "toleranceRelative": TOLERANCE_REL, "passed": True},
            "maeAf30RecomputedFromFrozenOofLong": {
                "value": evaluation["mae_af30_recomputed_from_frozen_oof"],
                "registered": EXPECTED_MAE_AF30,
                "absDifference": evaluation["mae_af30_abs_difference"], "passed": True},
            "baselineMedianAf30": {
                "recomputed": evaluation["baseline_median_af30_recomputed"],
                "registered": EXPECTED_BASELINE_MAE_AF30,
                "exp0074MetricsJson": evaluation["baseline_median_af30_exp0074_metrics_json"],
                "passed": True},
            "displayNotInEvaluationChain": {"displayScoresUsedInAnyMetric": False, "passed": True},
        },
    }
    paths["export_manifest.json"] = write_json("export_manifest.json", manifest)

    # ------------------------------------------------------------------ run directory copy + run record
    copies = {}
    for name in paths:
        source = paths[name]
        target = os.path.join(artifacts_dir, name)
        shutil.copyfile(source, target)
        copies[name] = {"sha256": sha256(target), "bytes": os.path.getsize(target)}
    run_record = {
        "runId": os.path.basename(os.path.abspath(run_dir)),
        "projectDir": PROJECT,
        "experimentDir": os.path.abspath(run_dir),
        "seed": seed,
        "models": {"candidate": EXP_CANDIDATE, "baseline": EXP_BASELINE},
        "displayConfig": chosen["config"],
        "artifacts": copies,
        "evaluation": {"maeAf30": evaluation["mae_af30_recomputed_from_frozen_oof"],
                       "baselineMedianAf30": evaluation["baseline_median_af30_recomputed"]},
        "runtimeSeconds": float(time.perf_counter() - started),
    }
    v6.write_json(Path(run_dir) / "run.json", Q1._jsonable(run_record))

    # ------------------------------------------------------------------ stdout summary
    print("[q1_export] frozen evaluation: A/F30 MAE = %.17g (registered %.17g), baseline = %.17g"
          % (evaluation["mae_af30_recomputed_from_frozen_oof"], EXPECTED_MAE_AF30,
             evaluation["baseline_median_af30_recomputed"]))
    print("[q1_export] display refit config: %s" % (chosen["config"],))
    print("[q1_export] artifacts:")
    for record in manifest["artifacts"] + [{"path": rel(paths["export_manifest.json"]),
                                            "rows": None, "cols": None,
                                            "bytes": os.path.getsize(paths["export_manifest.json"]),
                                            "sha256": sha256(paths["export_manifest.json"]),
                                            "chain": "manifest"}]:
        print("  %-34s chain=%-9s rows=%-6s cols=%-5s bytes=%-9d %s"
              % (os.path.basename(record["path"]), record["chain"], record["rows"],
                 record["cols"], record["bytes"], record["sha256"][:16]))
    print("[q1_export] out=%s run=%s elapsed=%.1fs"
          % (OUT_DIR, run_dir, float(time.perf_counter() - started)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
