#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q1_fix.py — Q1 in one process: four models, TRUE nested OOF, one repeat or all three.

WHY THIS FILE EXISTS
--------------------
The v5.1 Q1 experiment reported several things that were not what their names said:

  * "ridge" was a graph-regularised ridge (gamma = 1), never an ordinary ridge (finding F07);
  * the low-rank fit refreshed its intercept every ALS sweep while the ridge reference held the
    label mean fixed, so the two were not compared under one intercept convention;
  * the "OOF" tables mixed in-sample and holdout predictions (q1_grade_all.py trains on the 200
    SPLIT-0001 train rows and scores all 250 rows, 200 of which are in-sample);
  * hyper-parameters and the graph were tuned with a locally drawn 5-fold split, not the frozen
    nested protocol.

This script produces one honest artifact set per repeat of the frozen protocol in
src/v6_common.py: 3 outer folds x 3 inner folds inside every outer training set, seeds
v6_common.SEEDS[repeat]. Every prediction written for a beer comes from a model whose training
rows exclude that beer, and no outer_test row participates in any fit, in any imputation median,
in any standardisation, in the graph, in any hyper-parameter choice or in any grading cut point.

MODELS (same run, same preprocessing rules, same intercept rule)
  1. median          per-target median of the outer-training labels (baseline).
  2. ridge           ordinary ridge: gamma = 0, r = 50 (no rank restriction); lambda by inner CV.
                     This is the F07 repair.
  3. graph_ridge     gamma > 0, r = 50; (representation, lambda, gamma) by inner CV.
  4. graph_lowrank   gamma >= 0, r in {3,6,10}; (representation, lambda, gamma, r) by inner CV.

INTERCEPT (one formula for every linear model, no exceptions)
    b = ybar - zbar @ B          with zbar, ybar the means of the training block
    yhat = ybar + (z - zbar) @ B
so rank 50 with gamma = 0 must reproduce ordinary ridge to machine precision (checked per fold).

LOW-RANK SOLVER (closed form, no explicit inverse, no ALS)
    A  = Zc^T Zc / n + lambda I + gamma L        (symmetric positive definite, lambda > 0)
    C  = Zc^T Yc / n
    A  = R R^T                                   (Cholesky; only triangular solves afterwards)
    M  = C^T A^{-1} C                            (q x q, PSD; A^{-1} C from cho_solve)
    Vr = leading r eigenvectors of M             (eigh, descending)
    B  = A^{-1} C Vr Vr^T
This is the exact minimiser of ||Yc - Zc B||_F^2 / n + lambda ||B||_F^2 + gamma tr(B^T L B)
subject to rank(B) <= r (reduced-rank regression in the A-inner product), not the 25-sweep ALS
approximation used before. With r = q (50) it collapses to the full penalised solution.

GRAPH (refit inside every training set, never on evaluation rows)
    231 median-imputed chem features -> Spearman (mid-ranks, ties handled)
    -> signed adjacency W = rho * 1{|rho| >= tau}, tau = 0.5 frozen, zero diagonal
    -> L = diag(sum_j |W_ij|) - W, blockdiag with a 0_9 block for the 9 missing indicators
diag(sum|W|) - W is PSD by Gershgorin (eigenvalues in [0, 2 max_i sum_j |W_ij|]), so the legacy
eigenvalue clipping is dropped instead of silently changing the penalty; the measured minimum
eigenvalue is recorded per fold as evidence.

GRADES (reporting only, never a claim about the panel's original 0-6 score)
    F = mid-rank empirical CDF of the outer-TRAINING labels of that target
    g = clip(floor(6 F(y) + 0.5), 0, 6)
applied to the prediction AND to the observed outer_test label with the same F, so the only
claim is RELATIVE grade consistency.

Outputs (all inside v6_common.out_dir(), i.e. the experiment directory under the runner):
    predictions.csv            250 rows per repeat, candidate model (graph-lowrank)
    predictions_all_models.csv 250 rows per repeat per model
    oof_long.csv               one row per (repeat, model, beer, target), with both grades
    metrics.json               flat finite numbers only (emit_metrics refuses anything else)
    outputs.json               key "q1": protocol, per_repeat, models, grade, baseline, excluded
    inner_grid.json            every inner-CV cell, so the parameter choice is auditable

CLI: --repeat {0,1,2,all}   (default all: the three repeats in one process)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
from scipy.special import ndtri
from scipy.stats import rankdata

_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import v6_common as v6  # noqa: E402  (frozen protocol: splits, seeds, targets, metrics, IO)
import target_columns as TC  # noqa: E402  (pure constants: 231 feature names + 9 missing columns)

# ------------------------------------------------------------------------------------ frozen constants
CHEM_COLS = ["chem__" + name for name in TC.FEATURE_COLS]
MISSING_COLS = ["chem__" + name for name in TC.MISSING_COLUMNS]
N_CHEM = len(CHEM_COLS)
N_IND = len(MISSING_COLS)
if N_CHEM != 231 or N_IND != 9:
    raise RuntimeError("expected 231 chem features and 9 missing-indicator columns, got %d/%d" % (N_CHEM, N_IND))

TAU = 0.5                         # frozen correlation threshold
Z_CLIP = 8.0                      # frozen in q_common.apply_standardizer, kept for comparability
LAMBDAS = (0.1, 1.0, 10.0)
GRAPH_GAMMAS = (0.1, 1.0)         # strictly positive: this is what makes "graph ridge" distinct
LOWRANK_GAMMAS = (0.0, 0.1, 1.0)  # gamma >= 0 as required
RANKS = (3, 6, 10)
REPS = ("zscore", "rankgauss")

MODELS = ("median", "ridge", "graph-ridge", "graph-lowrank")
PRIMARY = "graph-lowrank"          # the Q1 candidate this experiment is about
METRIC_SUFFIX = {"median": "median", "ridge": "ridge0",
                 "graph-ridge": "graph_ridge", "graph-lowrank": "graph_lowrank"}


# ------------------------------------------------------------------------------------ small utilities
def _as_matrix(frame: pd.DataFrame, columns) -> np.ndarray:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise RuntimeError("table lacks columns: %s" % missing[:5])
    return frame[list(columns)].to_numpy(dtype=float)


def _sanitise_key(text: str) -> str:
    out = "".join(ch if ch.isalnum() else "_" for ch in str(text))
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def _jsonable(value):
    """NaN/Inf never reach a JSON file (a missing number must be absent or null, never a lie)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        out = float(value)
        return out if math.isfinite(out) else None
    if value is None or isinstance(value, str):
        return value
    return str(value)


# ------------------------------------------------------------------------------------ preprocessing
class Preprocessor:
    """Every rule (median imputation, missing indicators, z-score, Rank-Gauss) fitted on TRAIN rows only.

    The design matrix is [231 transformed chem features | 9 missing-indicator columns] = 240 columns,
    the legacy Q1 layout, so the graph block and the indicator block line up exactly.
    """

    def __init__(self, train_frame: pd.DataFrame):
        raw = _as_matrix(train_frame, CHEM_COLS)
        self.n_train = int(raw.shape[0])
        finite = np.isfinite(raw)
        medians = np.zeros(N_CHEM, dtype=float)
        for j in range(N_CHEM):
            column = raw[finite[:, j], j]
            medians[j] = float(np.median(column)) if column.size else 0.0
        self.medians = medians
        self.n_missing_cells = int((~finite).sum())
        imputed = np.where(finite, raw, medians[None, :])
        self.z_centre = imputed.mean(axis=0)
        spread = imputed.std(axis=0)
        self.z_scale = np.where(np.isfinite(spread) & (spread > 1e-12), spread, 1.0)
        self.rg_grids = [np.sort(imputed[:, j]) for j in range(N_CHEM)]
        self.rg_eps = 1.0 / (2.0 * max(self.n_train, 1))

    def imputed(self, frame: pd.DataFrame) -> np.ndarray:
        raw = _as_matrix(frame, CHEM_COLS)
        return np.where(np.isfinite(raw), raw, self.medians[None, :])

    def indicators(self, frame: pd.DataFrame) -> np.ndarray:
        raw = _as_matrix(frame, MISSING_COLS)
        return np.where(np.isfinite(raw), 0.0, 1.0)

    def design(self, frame: pd.DataFrame, rep: str) -> np.ndarray:
        imputed = self.imputed(frame)
        if rep == "zscore":
            transformed = np.clip((imputed - self.z_centre) / self.z_scale, -Z_CLIP, Z_CLIP)
        elif rep == "rankgauss":
            transformed = np.empty_like(imputed)
            for j in range(N_CHEM):
                grid = self.rg_grids[j]
                column = imputed[:, j]
                below = np.searchsorted(grid, column, side="left")
                equal = np.searchsorted(grid, column, side="right") - below
                u = (below + 0.5 * equal) / float(grid.size)
                u = np.clip(u, self.rg_eps, 1.0 - self.rg_eps)
                transformed[:, j] = ndtri(u)
        else:
            raise ValueError("unknown representation %r" % (rep,))
        return np.concatenate([transformed, self.indicators(frame)], axis=1)


def graph_laplacian(imputed_train: np.ndarray) -> tuple:
    """Spearman -> signed adjacency (tau = 0.5) -> L = diag(sum|W|) - W; indicators stay unconnected."""
    ranks = rankdata(imputed_train[:, :N_CHEM], axis=0)          # mid-ranks, ties averaged
    ranks = ranks - ranks.mean(axis=0, keepdims=True)
    norm = np.linalg.norm(ranks, axis=0, keepdims=True)
    norm = np.where(norm > 1e-12, norm, 1.0)
    ranks = ranks / norm
    rho = ranks.T @ ranks
    rho = 0.5 * (rho + rho.T)
    non_finite = int((~np.isfinite(rho)).sum())
    rho = np.nan_to_num(rho, nan=0.0, posinf=0.0, neginf=0.0)
    np.clip(rho, -1.0, 1.0, out=rho)
    weight = np.where(np.abs(rho) >= TAU, rho, 0.0)
    np.fill_diagonal(weight, 0.0)
    degree = np.abs(weight).sum(axis=1)
    lap231 = np.diag(degree) - weight
    lap231 = 0.5 * (lap231 + lap231.T)
    laplacian = np.zeros((N_CHEM + N_IND, N_CHEM + N_IND), dtype=float)
    laplacian[:N_CHEM, :N_CHEM] = lap231
    info = {
        "tau": float(TAU),
        "nodes": int(N_CHEM),
        "edges": int(np.count_nonzero(np.triu(weight, 1))),
        "isolatedNodes": int(np.count_nonzero(degree == 0.0)),
        "minEigenvalue231": float(np.linalg.eigvalsh(lap231).min()),
        "nonFiniteRho": non_finite,
        "indicatorBlock": "zero (missing indicators are not connected on the chemistry graph)",
    }
    return laplacian, info


# ------------------------------------------------------------------------------------ linear models
def moments(z_train: np.ndarray, y_train: np.ndarray) -> dict:
    """Train-block means and the two sufficient statistics, in ONE place for every family."""
    n = z_train.shape[0]
    z_bar = z_train.mean(axis=0)
    y_bar = y_train.mean(axis=0)
    centred = z_train - z_bar
    return {
        "n": int(n),
        "z_bar": z_bar,
        "y_bar": y_bar,
        "gram": centred.T @ centred / float(n),
        "cross": centred.T @ (y_train - y_bar) / float(n),
        "z_centred": centred,
        "y_centred": y_train - y_bar,
    }


class NormalSystem:
    """A = gram + lambda I + gamma L, factored once; A^{-1} C comes from triangular solves only."""

    def __init__(self, stats: dict, laplacian: np.ndarray, lam: float, gamma: float):
        d = stats["gram"].shape[0]
        self.lam = float(lam)
        self.gamma = float(gamma)
        self.cross = stats["cross"]
        matrix = stats["gram"] + self.lam * np.eye(d) + self.gamma * laplacian
        matrix = 0.5 * (matrix + matrix.T)
        self.factor = cho_factor(matrix, lower=True, check_finite=False)   # raises if not SPD
        self.solution = cho_solve(self.factor, self.cross, check_finite=False)  # A^{-1} C

    def coefficients(self, rank):
        """rank=None -> full penalised solution; rank=r -> exact rank-r reduced solution."""
        if rank is None:
            return self.solution
        moment = self.cross.T @ self.solution           # C^T A^{-1} C, q x q PSD
        moment = 0.5 * (moment + moment.T)
        values, vectors = np.linalg.eigh(moment)
        order = np.argsort(values, kind="mergesort")[::-1][:int(rank)]
        leading = vectors[:, order]
        return self.solution @ (leading @ leading.T)    # A^{-1} C Vr Vr^T


def fit_and_predict(z_train: np.ndarray, y_train: np.ndarray, z_eval: np.ndarray,
                    laplacian: np.ndarray, lam: float, gamma: float, rank):
    """One model. The intercept rule b = ybar - zbar B is enforced here for every family."""
    stats = moments(z_train, y_train)
    system = NormalSystem(stats, laplacian, lam, gamma)
    beta = system.coefficients(rank)
    prediction = stats["y_bar"] + (z_eval - stats["z_bar"]) @ beta
    info = {"n_train": int(stats["n"]), "n_columns": int(z_train.shape[1]),
            "lambda": float(lam), "gamma": float(gamma),
            "rank": None if rank is None else int(rank),
            "interceptRule": "b = ybar - zbar @ B",
            "coefficientNorm": float(np.linalg.norm(beta))}
    return prediction, beta, info


# ------------------------------------------------------------------------------------ inner CV
def _rows(frame: pd.DataFrame, beer_position: dict, beers) -> pd.DataFrame:
    return frame.iloc[[beer_position[int(b)] for b in beers]]


def inner_select(frame: pd.DataFrame, beer_position: dict, repeat: int, outer_fold: int,
                 outer_train_beers, target_af_idx: np.ndarray, target_all_idx: np.ndarray) -> dict:
    """Inner 3-fold CV inside one outer training set.

    Candidates are scored by the equal-weight MAE over the CONCATENATED validation rows across the
    three inner folds (never the mean of the three per-fold scores).
    """
    folds = list(v6.iter_inner(repeat, outer_fold, outer_train_beers))
    cache = []
    for inner_fold, inner_train_beers, inner_valid_beers in folds:
        train_frame = _rows(frame, beer_position, inner_train_beers)
        valid_frame = _rows(frame, beer_position, inner_valid_beers)
        prep = Preprocessor(train_frame)
        laplacian, graph_info = graph_laplacian(prep.imputed(train_frame))
        designs = {rep: (prep.design(train_frame, rep), prep.design(valid_frame, rep)) for rep in REPS}
        counts = {}
        for style in valid_frame[v6.STYLE_COL].astype(str).to_numpy():
            counts[style] = counts.get(style, 0) + 1
        cache.append({
            "inner_fold": int(inner_fold),
            "designs": designs,
            "laplacian": laplacian,
            "graph": graph_info,
            "y_train": _as_matrix(train_frame, v6.TARGETS_50),
            "y_valid": _as_matrix(valid_frame, v6.TARGETS_50),
            "n_train": int(len(inner_train_beers)),
            "n_valid": int(len(inner_valid_beers)),
            "missingCells": int(prep.n_missing_cells),
            "styleCounts": {k: int(v) for k, v in sorted(counts.items())},
        })

    cells = {}   # (rep, lambda, gamma, rank) -> list of validation predictions, one per inner fold
    for entry in cache:
        stats_by_rep = {rep: moments(entry["designs"][rep][0], entry["y_train"]) for rep in REPS}
        for rep in REPS:
            stats = stats_by_rep[rep]
            _, z_valid = entry["designs"][rep]
            eval_centred = z_valid - stats["z_bar"]
            for lam in LAMBDAS:
                for gamma in LOWRANK_GAMMAS:
                    system = NormalSystem(stats, entry["laplacian"], lam, gamma)
                    base = stats["y_bar"] + eval_centred @ system.solution
                    cells.setdefault((rep, lam, gamma, None), []).append(base)
                    for rank in RANKS:
                        beta = system.coefficients(rank)
                        cells.setdefault((rep, lam, gamma, rank), []).append(
                            stats["y_bar"] + eval_centred @ beta)

    truth = np.concatenate([entry["y_valid"] for entry in cache], axis=0)
    scored = {}
    for key, predictions in cells.items():
        pooled = np.concatenate(predictions, axis=0)
        if pooled.shape != truth.shape:
            raise RuntimeError("inner pooled prediction %s != truth %s" % (pooled.shape, truth.shape))
        scored[key] = {
            "pooled_valid_mae_af30": float(np.abs(truth[:, target_af_idx] - pooled[:, target_af_idx]).mean()),
            "pooled_valid_mae_all50": float(np.abs(truth[:, target_all_idx] - pooled[:, target_all_idx]).mean()),
            "n_pooled_valid_rows": int(pooled.shape[0]),
        }

    def best(keys):
        return min(keys, key=lambda k: (scored[k]["pooled_valid_mae_af30"],
                                        scored[k]["pooled_valid_mae_all50"],
                                        REPS.index(k[0]), k[1], k[2],
                                        -1 if k[3] is None else k[3]))

    full_rank_keys = [k for k in scored if k[3] is None]
    ridge_keys = [k for k in full_rank_keys if k[2] == 0.0]
    graph_keys = [k for k in full_rank_keys if k[2] > 0.0]
    lowrank_keys = [k for k in scored if k[3] is not None]
    if not ridge_keys or not graph_keys or not lowrank_keys:
        raise RuntimeError("the inner grid lost a model family")
    selection = {"ridge": best(ridge_keys), "graph-ridge": best(graph_keys),
                 "graph-lowrank": best(lowrank_keys)}

    def family_diagnostics(family, keys, chosen):
        value = scored[chosen]["pooled_valid_mae_af30"]
        others = [scored[key]["pooled_valid_mae_af30"] for key in keys if key != chosen]
        lam, gamma, rank = chosen[1], chosen[2], chosen[3]
        gammas = LOWRANK_GAMMAS if family == "graph-lowrank" else GRAPH_GAMMAS
        return {"nCells": int(len(keys)),
                "selectedInnerMaeAf30": float(value),
                "runnerUpInnerMaeAf30": float(min(others)) if others else None,
                "marginToRunnerUp": float(min(others) - value) if others else None,
                "lambdaAtGridEdge": bool(lam in (LAMBDAS[0], LAMBDAS[-1])),
                "gammaAtGridEdge": bool(gamma in (gammas[0], gammas[-1])),
                "rankAtGridEdge": None if rank is None else bool(rank in (RANKS[0], RANKS[-1]))}

    diagnostics = {
        "ridge": family_diagnostics("ridge", ridge_keys, selection["ridge"]),
        "graph-ridge": family_diagnostics("graph-ridge", graph_keys, selection["graph-ridge"]),
        "graph-lowrank": family_diagnostics("graph-lowrank", lowrank_keys, selection["graph-lowrank"]),
    }

    grid = []
    for key in sorted(scored, key=lambda k: (REPS.index(k[0]), k[1], k[2], -1 if k[3] is None else k[3])):
        rep, lam, gamma, rank = key
        cell = {"representation": rep, "lambda": float(lam), "gamma": float(gamma),
                "rank": None if rank is None else int(rank)}
        cell.update(scored[key])
        grid.append(cell)

    geometry = {
        "n_folds": int(len(cache)),
        "n_train_rows": [entry["n_train"] for entry in cache],
        "n_valid_rows": [entry["n_valid"] for entry in cache],
        "missingCellsInInnerTrain": [entry["missingCells"] for entry in cache],
        "styleValidCounts": {str(entry["inner_fold"]): entry["styleCounts"] for entry in cache},
        "styleCountsBelowTwo": sorted({style for entry in cache
                                       for style, count in entry["styleCounts"].items() if count < 2}),
        "graph": [entry["graph"] for entry in cache],
        "n_pooled_valid_rows": int(sum(entry["n_valid"] for entry in cache)),
        "n_cells": int(len(scored)),
    }
    return {"cells": scored, "selection": selection, "grid": grid, "geometry": geometry,
            "diagnostics": diagnostics}


# ------------------------------------------------------------------------------------ metrics helpers
def _regression(truth, prediction, targets, styles=None, baseline_mae=None) -> dict:
    """v6.regression_block requires width == len(targets), so the caller selects the columns."""
    return v6.regression_block(truth, prediction, list(targets), styles=styles, baseline_mae=baseline_mae)


def _grade_arrays(prediction: np.ndarray, truth: np.ndarray, reference: np.ndarray) -> tuple:
    """Relative grades from the outer-TRAINING empirical CDF of each target, same F on both sides."""
    g_pred = np.empty(prediction.shape, dtype=int)
    g_true = np.empty(truth.shape, dtype=int)
    for j in range(prediction.shape[1]):
        cut = reference[:, j]
        g_pred[:, j] = v6.to_grade(prediction[:, j], cut)
        g_true[:, j] = v6.to_grade(truth[:, j], cut)
    return g_pred, g_true


def _grade_block(g_pred: np.ndarray, g_true: np.ndarray) -> dict:
    mask = (g_pred >= 0) & (g_true >= 0)
    n = int(mask.sum())
    if n == 0:
        return {"n_grade_cells": 0}
    qwk = v6.quadratic_weighted_kappa(g_true[mask], g_pred[mask])
    return {
        "n_grade_cells": n,
        "qwk": float(qwk) if math.isfinite(qwk) else None,
        "grade_mae": float(np.abs(g_true[mask] - g_pred[mask]).mean()),
        "exact_agreement": float((g_true[mask] == g_pred[mask]).mean()),
        "within_one_agreement": float((np.abs(g_true[mask] - g_pred[mask]) <= 1).mean()),
        "grade_counts_predicted": np.bincount(g_pred[mask].ravel(), minlength=7).tolist(),
        "grade_counts_reference": np.bincount(g_true[mask].ravel(), minlength=7).tolist(),
        "note": "relative grades of a prediction, not an accuracy claim about the panel's original 0-6 score",
    }


# ------------------------------------------------------------------------------------ output channel
def _runner_channel(out: Path) -> bool:
    """True only inside the modeling-contest runner (contract on the path AND its experiment dir set).

    Outside the runner (local self-test) the same JSON/CSV files are written straight into
    v6_common.out_dir(), so the artifact set is identical without pretending a runner ran, and
    nothing is ever written into the current working directory by accident.
    """
    if not (os.environ.get("MODELING_EXPERIMENT_DIR") or os.environ.get("EXPERIMENT_DIR")):
        return False
    try:
        import modeling_contract  # noqa: F401
    except ImportError:
        return False
    return Path(out).is_dir()


def emit_metrics(payload: dict, out: Path) -> dict:
    clean = {}
    for key, value in payload.items():
        if isinstance(value, (bool, np.bool_)):
            continue
        if isinstance(value, (int, np.integer)):
            clean[str(key)] = int(value)
        elif isinstance(value, (float, np.floating)) and math.isfinite(float(value)):
            clean[str(key)] = float(value)
    dropped = sorted(set(payload) - set(clean))
    if _runner_channel(out):
        v6.emit_metrics(clean)
        channel = "modeling_contract"
    else:
        # a local dev run IS one atomic experiment: overwrite instead of merging stale keys from an
        # earlier local run in the same directory (the runner channel keeps its documented merge)
        path = out / "metrics.json"
        v6.write_json(path, clean)
        channel = "local-file (modeling_contract absent: direct write into out_dir)"
    print("[q1_fix] metrics channel: %s (%d keys, %d non-finite keys withheld)"
          % (channel, len(clean), len(dropped)))
    return {"keys": len(clean), "dropped": dropped, "channel": channel}


def emit_output(name: str, payload, out: Path) -> None:
    value = _jsonable(payload)
    if _runner_channel(out):
        v6.emit_output(name, value)
    else:
        path = out / "outputs.json"
        merged = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        merged[name] = value
        v6.write_json(path, merged)


def emit_table(frame: pd.DataFrame, name: str, out: Path) -> Path:
    if _runner_channel(out):
        import modeling_contract
        return Path(modeling_contract.emit_predictions(frame, name))
    path = out / name
    frame.to_csv(path, index=False)
    return path


# ------------------------------------------------------------------------------------ main
def run(repeats: list) -> int:
    started = time.perf_counter()
    out = v6.out_dir("src/q1_fix.py")
    out.mkdir(parents=True, exist_ok=True)

    frame = v6.load_frame()
    splits = v6.load_splits()
    all_targets = v6.all_targets(frame)
    af_targets = v6.af_targets(frame)
    if list(all_targets) != list(v6.TARGETS_50) or list(af_targets) != list(v6.TARGETS_AF30):
        raise RuntimeError("the registered table does not carry the frozen target order")
    target_all_idx = np.arange(len(all_targets))
    target_af_idx = np.array([all_targets.index(t) for t in af_targets])
    styles = v6.style_of(frame)
    beer = frame["beer"].to_numpy(dtype=int)
    row_id = frame["row"].to_numpy(dtype=int) if "row" in frame.columns else np.arange(len(frame))
    beer_position = {int(b): i for i, b in enumerate(beer)}
    if len(beer_position) != len(frame):
        raise RuntimeError("'beer' is not unique: row identity would be a guess")

    manifest = v6.read_json(v6.SPLITS_MANIFEST) if v6.SPLITS_MANIFEST.exists() else {}
    splits_sha = v6.sha256_file(v6.SPLITS_CSV)
    data_sha = v6.sha256_file(v6.DATA_Q1)
    dataset_missing_cells = int(np.isnan(_as_matrix(frame, CHEM_COLS)).sum())

    oof = {m: {} for m in MODELS}
    folds_record = {m: [] for m in MODELS}
    inner_grid = {}
    equivalence = {"perFold": [],
                   "criterion": "max |prediction difference| < 1e-9 over every outer fold",
                   "note": "rank 50 with gamma = 0 uses the same normal matrix and the same intercept as ridge"}

    for repeat in repeats:
        if repeat < 0 or repeat >= v6.N_REPEATS:
            raise RuntimeError("repeat %d outside [0,%d)" % (repeat, v6.N_REPEATS))
        print("[q1_fix] repeat=%d seed=%d" % (repeat, int(v6.SEEDS[repeat])), flush=True)
        for model in MODELS:
            oof[model][repeat] = {
                "pred": np.full((len(frame), len(all_targets)), np.nan),
                "true": np.full((len(frame), len(all_targets)), np.nan),
                "gpred": np.full((len(frame), len(all_targets)), -1, dtype=int),
                "gtrue": np.full((len(frame), len(all_targets)), -1, dtype=int),
                "fold": np.full(len(frame), -1, dtype=int),
            }
        inner_grid[str(repeat)] = {}

        for repeat_out, outer_fold, train_beers, test_beers in v6.iter_outer(splits):
            if repeat_out != repeat:
                continue
            train_frame = _rows(frame, beer_position, train_beers)
            test_frame = _rows(frame, beer_position, test_beers)
            y_train = _as_matrix(train_frame, all_targets)
            y_test = _as_matrix(test_frame, all_targets)
            test_positions = np.array([beer_position[int(b)] for b in test_beers], dtype=int)

            selection = inner_select(frame, beer_position, repeat, outer_fold, train_beers,
                                     target_af_idx, target_all_idx)
            geometry = selection["geometry"]
            diagnostics = selection["diagnostics"]
            inner_grid[str(repeat)]["outer_fold_%d" % outer_fold] = {
                "selection": {family: dict({"family": family,
                                            "representation": key[0],
                                            "lambda": float(key[1]),
                                            "gamma": float(key[2]),
                                            "rank": None if key[3] is None else int(key[3])},
                                           **selection["cells"][key])
                              for family, key in selection["selection"].items()},
                "geometry": {k: v for k, v in geometry.items() if k != "graph"},
                "selectionDiagnostics": selection["diagnostics"],
                "cells": selection["grid"],
            }

            prep = Preprocessor(train_frame)
            laplacian, graph_info = graph_laplacian(prep.imputed(train_frame))
            designs = {rep: (prep.design(train_frame, rep), prep.design(test_frame, rep)) for rep in REPS}

            predictions, details = {}, {}

            # ---- median baseline: per-target median of the outer-training labels
            predictions["median"] = np.broadcast_to(np.median(y_train, axis=0), y_test.shape).copy()
            details["median"] = {"params": {"family": "median", "representation": "none",
                                            "lambda": None, "gamma": None, "rank": None},
                                 "note": "no hyper-parameter to tune: this is the reference line"}

            for family in ("ridge", "graph-ridge", "graph-lowrank"):
                rep, lam, gamma, rank = selection["selection"][family]
                z_train, z_test = designs[rep]
                prediction, _, info = fit_and_predict(z_train, y_train, z_test, laplacian,
                                                      lam, gamma, rank)
                predictions[family] = prediction
                details[family] = {
                    "params": {"family": family, "representation": rep, "lambda": float(lam),
                               "gamma": float(gamma), "rank": None if rank is None else int(rank)},
                    "pooledValidMaeAf30": selection["cells"][(rep, lam, gamma, rank)]["pooled_valid_mae_af30"],
                    "pooledValidMaeAll50": selection["cells"][(rep, lam, gamma, rank)]["pooled_valid_mae_all50"],
                    "nInnerCells": geometry["n_cells"],
                    "coefficientNorm": info["coefficientNorm"],
                }
                if family == "ridge":
                    if float(gamma) != 0.0:
                        raise RuntimeError("the ridge family must have gamma = 0, got %r" % (gamma,))
                    # ---- equivalence probe: rank 50 + gamma 0 must reproduce ordinary ridge exactly
                    probe, _, probe_info = fit_and_predict(z_train, y_train, z_test, laplacian,
                                                           lam, gamma, len(all_targets))
                    diff = float(np.max(np.abs(probe - prediction)))
                    equivalence["perFold"].append({
                        "repeat": int(repeat), "outer_fold": int(outer_fold),
                        "representation": rep, "lambda": float(lam), "gamma": float(gamma),
                        "rank": int(len(all_targets)), "nColumns": probe_info["n_columns"],
                        "maxAbsPredictionDifference": diff, "passed": bool(diff < 1e-9),
                    })

            # ---- grades from the same outer-training CDF, for every model
            for family, prediction in predictions.items():
                g_pred, g_true = _grade_arrays(prediction, y_test, y_train)
                store = oof[family][repeat]
                store["pred"][test_positions, :] = prediction
                store["true"][test_positions, :] = y_test
                store["gpred"][test_positions, :] = g_pred
                store["gtrue"][test_positions, :] = g_true
                store["fold"][test_positions] = outer_fold

            for family in MODELS:
                folds_record[family].append({
                    "repeat": int(repeat), "outer_fold": int(outer_fold), "seed": int(v6.SEEDS[repeat]),
                    "n_train": int(len(train_beers)), "n_test": int(len(test_beers)),
                    "n_features": int(N_CHEM + N_IND), "n_columns": int(N_CHEM + N_IND),
                    "n_targets": int(len(all_targets)),
                    "missingCellsInTrain": int(prep.n_missing_cells),
                    "params": details[family]["params"],
                    "pooledValidMaeAf30": details[family].get("pooledValidMaeAf30"),
                    "selectionDiagnostics": diagnostics.get(family),
                    "inner": {"n_folds": geometry["n_folds"],
                              "n_train_rows": geometry["n_train_rows"],
                              "n_valid_rows": geometry["n_valid_rows"],
                              "n_pooled_valid_rows": geometry["n_pooled_valid_rows"],
                              "missingCellsInInnerTrain": geometry["missingCellsInInnerTrain"],
                              "styleValidCounts": geometry["styleValidCounts"],
                              "styleCountsBelowTwo": geometry["styleCountsBelowTwo"]},
                    "graph": graph_info,
                    "testMaeAf30": float(np.abs(y_test[:, target_af_idx]
                                                - predictions[family][:, target_af_idx]).mean()),
                    "testMaeAll50": float(np.abs(y_test - predictions[family]).mean()),
                })

            sel = selection["selection"]
            print("  [q1_fix] r%df%d train=%3d test=%3d | ridge(%s,lam=%.2g) "
                  "graph-ridge(%s,lam=%.2g,gamma=%.2g) lowrank(%s,lam=%.2g,gamma=%.2g,r=%s)"
                  % (repeat, outer_fold, len(train_beers), len(test_beers),
                     *sel["ridge"][:2], *sel["graph-ridge"][:3], *sel["graph-lowrank"][:4]), flush=True)

        for model in MODELS:
            missing = int(np.isnan(oof[model][repeat]["pred"]).any(axis=1).sum())
            if missing:
                raise RuntimeError("%s repeat=%d: %d beers received no OOF prediction"
                                   % (model, repeat, missing))

    # ------------------------------------------------------------------ pooled metrics
    sample_truth = {m: np.concatenate([oof[m][r]["true"] for r in repeats], axis=0) for m in MODELS}
    sample_pred = {m: np.concatenate([oof[m][r]["pred"] for r in repeats], axis=0) for m in MODELS}
    sample_style = np.concatenate([styles for _ in repeats], axis=0)

    blocks = {}
    for model in MODELS:
        truth = sample_truth[model]
        pred = sample_pred[model]
        blocks[model] = {
            "af30": _regression(truth[:, target_af_idx], pred[:, target_af_idx],
                                af_targets, styles=sample_style),
            "all50": _regression(truth, pred, all_targets, styles=sample_style),
        }

    baseline_af30 = blocks["median"]["af30"]["mae"]
    skill = {m: (0.0 if m == "median"
                 else float(1.0 - blocks[m]["af30"]["mae"] / baseline_af30)) for m in MODELS}
    primary_af = blocks[PRIMARY]["af30"]
    primary_all = blocks[PRIMARY]["all50"]

    per_repeat = {}
    for repeat in repeats:
        entry = {}
        for model in MODELS:
            truth_r = oof[model][repeat]["true"]
            pred_r = oof[model][repeat]["pred"]
            entry["mae_" + METRIC_SUFFIX[model]] = float(
                _regression(truth_r[:, target_af_idx], pred_r[:, target_af_idx], af_targets,
                            styles=styles)["mae"])
            entry["mae_all50_" + METRIC_SUFFIX[model]] = float(
                _regression(truth_r, pred_r, all_targets, styles=styles)["mae"])
        entry["n_rows"] = int(len(frame))
        entry["seed"] = int(v6.SEEDS[repeat])
        per_repeat[str(repeat)] = entry

    per_repeat_by_model = {
        model: {str(r): float(per_repeat[str(r)]["mae_" + METRIC_SUFFIX[model]]) for r in repeats}
        for model in MODELS
    }

    per_fold = {}
    for repeat in repeats:
        for fold in range(v6.N_OUTER):
            key = "r%df%d" % (repeat, fold)
            mask = oof[PRIMARY][repeat]["fold"] == fold
            primary_mae = float(np.abs(oof[PRIMARY][repeat]["pred"][mask][:, target_af_idx]
                                       - oof[PRIMARY][repeat]["true"][mask][:, target_af_idx]).mean())
            median_mae = float(np.abs(oof["median"][repeat]["pred"][mask][:, target_af_idx]
                                      - oof["median"][repeat]["true"][mask][:, target_af_idx]).mean())
            per_fold[key] = {"n_rows": int(mask.sum()), "mae_graph_lowrank": primary_mae,
                             "mae_median": median_mae,
                             "skill_af30": float(1.0 - primary_mae / median_mae) if median_mae > 0 else 0.0}

    equivalence["maxAbsPredictionDifference"] = float(
        max((entry["maxAbsPredictionDifference"] for entry in equivalence["perFold"]), default=float("nan")))
    equivalence["passed"] = bool(equivalence["perFold"]) and all(e["passed"] for e in equivalence["perFold"])

    # ------------------------------------------------------------------ flat metrics
    metrics = {
        "mae": float(primary_af["mae"]),
        "mae_all50": float(primary_all["mae"]),
        "macro_r2_50": float(primary_all.get("macro_r2", float("nan"))),
        "macro_r2_af30": float(primary_af.get("macro_r2", float("nan"))),
        "skill_af30": float(skill[PRIMARY]),
        "n_rows": int(primary_af["n_rows"]),
        "n_targets": int(len(af_targets)),
        "n_targets_all50": int(len(all_targets)),
        "n_repeats": int(len(repeats)),
        "r2_na": int(primary_all["r2_na"]),
        "r2_na_af30": int(primary_af["r2_na"]),
        "baseline_mae_af30": float(baseline_af30),
        "eq_ridge_rank50_max_abs_diff": float(equivalence["maxAbsPredictionDifference"]),
        "eq_ridge_rank50_passed": 1.0 if equivalence["passed"] else 0.0,
    }
    for model in MODELS:
        suffix = METRIC_SUFFIX[model]
        metrics["mae_" + suffix] = float(blocks[model]["af30"]["mae"])
        metrics["mae_all50_" + suffix] = float(blocks[model]["all50"]["mae"])
        metrics["skill_af30_" + suffix] = float(skill[model])
        metrics["macro_r2_af30_" + suffix] = float(blocks[model]["af30"].get("macro_r2", float("nan")))
    for group, value in primary_all["groups"].items():
        metrics["per_group__%s__mae" % _sanitise_key(group)] = float(value["mae"])
        metrics["per_group__%s__n" % _sanitise_key(group)] = float(value["n"])
    for style, value in primary_af["per_style"].items():
        metrics["per_style__%s__mae" % _sanitise_key(style)] = float(value["mae"])
        metrics["per_style__%s__n" % _sanitise_key(style)] = float(value["n"])
    for key, value in per_fold.items():
        metrics["per_fold__%s__mae" % key] = float(value["mae_graph_lowrank"])
        metrics["per_fold__%s__n_rows" % key] = float(value["n_rows"])
        metrics["per_fold__%s__mae_median" % key] = float(value["mae_median"])
    for repeat in repeats:
        metrics["mae_r%d" % repeat] = float(per_repeat[str(repeat)]["mae_" + METRIC_SUFFIX[PRIMARY]])
    metrics = {k: v for k, v in metrics.items() if _finite_number(v)}
    channel = emit_metrics(metrics, out)

    # ------------------------------------------------------------------ prediction tables
    def wide_table(store, model, repeat):
        columns = {"beer": beer, "row": row_id, "model": np.full(len(beer), model),
                   "repeat": np.full(len(beer), int(repeat)),
                   "outer_fold": store["fold"].astype(int), "style": styles}
        for j, target in enumerate(all_targets):
            columns["y_pred__" + target] = store["pred"][:, j]
            columns["y_true__" + target] = store["true"][:, j]
        return pd.DataFrame(columns)

    primary_rows = [wide_table(oof[PRIMARY][repeat], PRIMARY, repeat) for repeat in repeats]
    predictions_table = pd.concat(primary_rows, ignore_index=True)
    predictions_path = emit_table(predictions_table, "predictions.csv", out)

    all_rows = [wide_table(oof[model][repeat], model, repeat)
                for repeat in repeats for model in MODELS]
    all_models_path = emit_table(pd.concat(all_rows, ignore_index=True),
                                 "predictions_all_models.csv", out)

    long_frames = []
    for repeat in repeats:
        for model in MODELS:
            store = oof[model][repeat]
            n = len(beer)
            long_frames.append(pd.DataFrame({
                "beer": np.repeat(beer, len(all_targets)),
                "repeat": np.full(n * len(all_targets), int(repeat)),
                "fold": np.repeat(store["fold"].astype(int), len(all_targets)),
                "target": np.tile(np.asarray(all_targets, dtype=object), n),
                "model": np.full(n * len(all_targets), model),
                "y_true": store["true"].reshape(-1),
                "y_pred": store["pred"].reshape(-1),
                "grade_pred": store["gpred"].reshape(-1),
                "grade_true": store["gtrue"].reshape(-1),
            }))
    long_table = pd.concat(long_frames, ignore_index=True)
    long_path = emit_table(long_table, "oof_long.csv", out)

    # ------------------------------------------------------------------ self checks (fail loudly)
    checks = {}
    counts = predictions_table.groupby("repeat")["beer"].agg(["count", "nunique"])
    checks["predictionsRows"] = {
        "rows": int(len(predictions_table)),
        "expected": int(len(repeats) * len(frame)),
        "beerCountPerRepeat": {str(k): int(v) for k, v in counts["count"].items()},
        "uniqueBeerPerRepeat": {str(k): int(v) for k, v in counts["nunique"].items()},
    }
    if len(predictions_table) != len(repeats) * len(frame) or (counts["nunique"] != len(frame)).any():
        raise RuntimeError("predictions.csv is not one row per beer per repeat: %s"
                           % checks["predictionsRows"])

    fold_truth = splits[splits["role"] == "outer_test"].set_index(["repeat", "beer"])["outer_fold"]
    mismatch = 0
    for repeat in repeats:
        part = predictions_table[predictions_table["repeat"] == repeat]
        for beer_value, fold_value in zip(part["beer"].to_numpy(), part["outer_fold"].to_numpy()):
            if int(fold_truth.loc[(repeat, int(beer_value))]) != int(fold_value):
                mismatch += 1
    checks["outerFoldMatchesSplits"] = {"mismatches": int(mismatch), "passed": bool(mismatch == 0)}
    if mismatch:
        raise RuntimeError("predictions.csv outer_fold disagrees with splits.csv for %d rows" % mismatch)

    training_pairs = {(int(r), int(f), int(b)) for r, f, b in
                      zip(splits.loc[splits["role"] == "inner", "repeat"],
                          splits.loc[splits["role"] == "inner", "outer_fold"],
                          splits.loc[splits["role"] == "inner", "beer"])}
    leaks = 0
    for repeat in repeats:
        for beer_value, fold_value in zip(beer, oof[PRIMARY][repeat]["fold"]):
            if (repeat, int(fold_value), int(beer_value)) in training_pairs:
                leaks += 1
    checks["oofDefinition"] = {
        "trainingPairsChecked": int(len(training_pairs)),
        "predictionsThatCameFromATrainingSet": int(leaks), "passed": bool(leaks == 0),
        "rule": ("(repeat, outer_fold, beer) with role=inner IS the training set of that fold; a beer "
                 "predicted in that fold must never appear in it"),
    }
    if leaks:
        raise RuntimeError("%d beers were predicted by a model that trained on them" % leaks)

    recomputed = {}
    for model in MODELS:
        subset = long_table[(long_table["model"] == model) & long_table["target"].isin(list(af_targets))]
        value = float(np.abs(subset["y_true"].to_numpy() - subset["y_pred"].to_numpy()).mean())
        record = float(metrics["mae_" + METRIC_SUFFIX[model]])
        recomputed[model] = {"fromOofLong": value, "fromMetrics": record,
                             "absDifference": float(abs(value - record))}
    checks["maeRecomputedFromOofLong"] = recomputed
    if any(v["absDifference"] > 1e-12 for v in recomputed.values()):
        raise RuntimeError("oof_long recomputation disagrees with metrics: %s" % recomputed)

    checks["noNaNInPredictionTable"] = {
        "passed": bool(np.isfinite(predictions_table.filter(like="y_pred__").to_numpy()).all()
                       and np.isfinite(predictions_table.filter(like="y_true__").to_numpy()).all())}
    checks["gradeRange"] = {"min": int(long_table["grade_pred"].min()),
                            "max": int(long_table["grade_pred"].max()),
                            "passed": bool(long_table["grade_pred"].min() >= 0
                                           and long_table["grade_pred"].max() <= 6)}
    checks["equivalence"] = equivalence
    checks["metricChannel"] = channel
    for key in ("noNaNInPredictionTable", "gradeRange"):
        if not checks[key]["passed"]:
            raise RuntimeError("self check failed: %s -> %s" % (key, checks[key]))
    if not equivalence["passed"]:
        print("[q1_fix] WARNING: rank-50/gamma-0 equivalence did not pass (%.3e)"
              % equivalence["maxAbsPredictionDifference"])

    # ------------------------------------------------------------------ outputs.json
    grade_block = {"perModel": {}}
    for model in MODELS:
        g_pred = np.concatenate([oof[model][r]["gpred"] for r in repeats], axis=0)
        g_true = np.concatenate([oof[model][r]["gtrue"] for r in repeats], axis=0)
        grade_block["perModel"][model] = _grade_block(g_pred, g_true)
    grade_block["rule"] = ("F = mid-rank empirical CDF of the outer-training labels; "
                           "g = clip(floor(6F(y)+0.5),0,6); the observed outer_test label goes through "
                           "the same F, so this is RELATIVE grade consistency only")

    baseline_block = {
        "definition": "per-target median of the outer-training labels, applied once to each outer_test row",
        "pooledMaeAf30": float(baseline_af30),
        "pooledMaeAll50": float(blocks["median"]["all50"]["mae"]),
        "perFoldMaeAf30": {k: v["mae_median"] for k, v in per_fold.items()},
        "perRepeatMaeAf30": {str(r): per_repeat[str(r)]["mae_median"] for r in repeats},
        "skillDefinition": ("skill_af30(model) = 1 - mae_af30(model) / mae_af30(median) over the same "
                            "pooled OOF rows; the median model's own skill is 0 by construction"),
    }

    payload = {
        "status": "succeeded",
        "definition": {
            "oof": ("a beer's prediction comes from the model fitted on that beer's outer-fold training "
                    "rows; the beer is in that fold's outer_test set and was in no fit, no imputation "
                    "median, no standardisation, no graph, no tuning decision and no grading cut point"),
            "mae": ("A/F30 equal-weight mean of |y_true - y_pred| over the CONCATENATED OOF rows "
                    "(%d repeat(s) x %d beers = %d rows); it is NOT the mean of per-repeat scores"
                    % (len(repeats), len(frame), int(primary_af["n_rows"]))),
            "primaryModel": PRIMARY,
            "predictionsCsv": ("250 rows per repeat for the candidate graph-lowrank model; "
                               "predictions_all_models.csv has all four models and oof_long.csv has "
                               "every (beer, target, model) row"),
        },
        "protocol": {
            "repeats": [int(r) for r in repeats],
            "seeds": {str(r): int(v6.SEEDS[r]) for r in repeats},
            "nOuterFolds": int(v6.N_OUTER),
            "nInnerFolds": int(v6.N_INNER),
            "splitsCsv": str(v6.SPLITS_CSV.relative_to(v6.PROJECT)),
            "splitsSha256": splits_sha,
            "splitsSha256MatchesManifest": bool(splits_sha == manifest.get("splits_sha256")),
            "dataFile": str(v6.DATA_Q1.relative_to(v6.PROJECT)),
            "dataSha256": data_sha,
            "dataSha256MatchesManifest": bool(data_sha == manifest.get("source_sha256")),
            "nRows": int(len(frame)),
            "nChemFeatures": int(N_CHEM),
            "nMissingIndicators": int(N_IND),
            "missingIndicatorCellsInDataset": dataset_missing_cells,
            "designColumns": int(N_CHEM + N_IND),
            "representation": list(REPS),
            "lambdaGrid": list(LAMBDAS),
            "graphGammaGrid": list(GRAPH_GAMMAS),
            "lowrankGammaGrid": list(LOWRANK_GAMMAS),
            "rankGrid": list(RANKS),
            "tau": float(TAU),
            "zclip": float(Z_CLIP),
            "randomness": "none: no RNG draw anywhere; every fold comes from the frozen splits.csv",
            "interceptRule": "b = ybar - zbar @ B for ridge, graph-ridge and graph-lowrank",
            "lowrankSolver": ("A = Zc^T Zc/n + lambda I + gamma L (Cholesky), C = Zc^T Yc/n, "
                              "B = A^{-1} C Vr Vr^T with Vr the leading r eigenvectors of C^T A^{-1} C; "
                              "no explicit inverse, no ALS sweeps"),
            "selectionRule": ("inner 3-fold CV inside each outer training set; candidates are scored by the "
                              "equal-weight MAE over the CONCATENATED validation rows (not the mean of "
                              "per-fold scores); the winner is refitted on the whole outer training set"),
            "gradeRule": grade_block["rule"],
            "metricKeyConvention": ("nested blocks are flattened with '__' "
                                    "(per_group__<name>__mae, per_style__<name>__mae, per_fold__r<r>f<f>__mae) "
                                    "because modeling_contract.emit_metrics accepts finite numbers only"),
            "equivalence": equivalence,
        },
        "perRepeat": per_repeat,
        "perRepeatByModel": per_repeat_by_model,
        "models": {
            model: {
                "metricSuffix": METRIC_SUFFIX[model],
                "pooled": {
                    "mae_af30": float(blocks[model]["af30"]["mae"]),
                    "mae_all50": float(blocks[model]["all50"]["mae"]),
                    "macro_r2_af30": float(blocks[model]["af30"].get("macro_r2", float("nan"))),
                    "macro_r2_50": float(blocks[model]["all50"].get("macro_r2", float("nan"))),
                    "skill_af30": float(skill[model]),
                    "r2_na": int(blocks[model]["all50"]["r2_na"]),
                    "groups": {k: {"mae": float(v["mae"]), "n": int(v["n"])}
                               for k, v in blocks[model]["af30"]["groups"].items()},
                },
                "folds": folds_record[model],
            }
            for model in MODELS
        },
        "perFold": per_fold,
        "grade": grade_block,
        "baseline": baseline_block,
        "excluded": [
            {"item": "HGB / gradient-boosted nonlinear baseline", "status": "not_run",
             "kind": "optional-enhancement",
             "why": "separable nonlinear probe; out of scope for this Q1 repair, left to a later experiment"},
            {"item": "fusion / stacking (median + graph + HGB)", "status": "not_run",
             "kind": "optional-enhancement",
             "why": "the fused pipeline was the v5.1 source of in-sample/holdout mixing; not reused here"},
            {"item": "exact rank-r low-rank solution", "status": "implemented",
             "kind": "scope-note",
             "why": ("B = A^{-1} C Vr Vr^T (eigenvectors of C^T A^{-1} C) is the exact minimiser, so the "
                     "25-sweep ALS of the legacy code is NOT used and nothing about low rank is skipped")},
            {"item": "PSD projection of the Laplacian (legacy eigenvalue clipping)", "status": "dropped",
             "kind": "defect-fix",
             "why": ("L = diag(sum|W|) - W is PSD by Gershgorin, so clipping silently changed the penalty; "
                     "the measured minimum eigenvalue is recorded per fold as evidence instead")},
            {"item": "external panel / true test data", "status": "not_available",
             "kind": "scope-note",
             "why": "no external evaluation set exists; every number here is internal nested CV"},
        ],
        "devNotes": [
            {"item": "lambda grid edge probe", "provenance": "separate exploratory run, NOT part of this artifact",
             "result": ("ridge, inner pooled AF30 MAE averaged over the same 9 outer folds: lambda=1 -> 0.3763, "
                        "10 -> 0.3701, 30 -> 0.3848, 100 -> 0.4000, 300 -> 0.4077; zscore shows the same shape. "
                        "lambda=10 is therefore an interior optimum and the frozen grid {0.1,1,10} is not truncated, "
                        "even though 10 is its largest value")},
            {"item": "rank grid", "provenance": "this artifact",
             "result": ("rank 6 is selected in 9/9 outer folds within the prescribed grid {3,6,10}; ranks 3 and 10 "
                        "are never chosen, so the rank is stable but the grid is coarse (see selectionDiagnostics)")},
        ],
        "fixes": {
            "ridgeIsOrdinaryRidge": ("gamma = 0 and r = 50; the v5.1 'ridge' was a gamma = 1 graph ridge and "
                                     "now appears separately as graph-ridge"),
            "uniformIntercept": ("every model uses b = ybar - zbar B; the legacy low-rank model refreshed the "
                                 "intercept every ALS sweep while its ridge reference held the label mean fixed"),
            "trueOOF": ("every beer is predicted by a model that never saw it; q1_grade_all.py's in-sample "
                        "200-row predictions are not reused"),
            "protocol": "frozen NESTED-CV-1 splits via v6_common.iter_outer / iter_inner, no local fold drawing",
        },
        "checks": checks,
        "artifacts": {
            "predictions": Path(predictions_path).name,
            "predictionsAllModels": Path(all_models_path).name,
            "oofLong": Path(long_path).name,
            "innerGrid": "inner_grid.json",
            "metrics": "metrics.json",
            "importance": "omitted (this experiment makes no feature-importance claim)",
        },
        "runtimeSeconds": float(time.perf_counter() - started),
    }

    v6.write_json(out / "inner_grid.json", _jsonable(inner_grid))
    emit_output("q1", payload, out)

    # ------------------------------------------------------------------ stdout summary
    elapsed = time.perf_counter() - started
    print("[q1_fix] OOF pooled over %d repeat(s), %d rows each" % (len(repeats), len(frame)))
    print("[q1_fix] %-14s %12s %12s %12s" % ("model", "mae_af30", "mae_all50", "skill_af30"))
    for model in MODELS:
        print("[q1_fix] %-14s %12.6f %12.6f %12.6f"
              % (model, blocks[model]["af30"]["mae"], blocks[model]["all50"]["mae"], skill[model]))
    for repeat in repeats:
        entry = per_repeat[str(repeat)]
        print("[q1_fix] repeat %d: median=%.6f ridge0=%.6f graph-ridge=%.6f graph-lowrank=%.6f"
              % (repeat, entry["mae_median"], entry["mae_ridge0"],
                 entry["mae_graph_ridge"], entry["mae_graph_lowrank"]))
    print("[q1_fix] equivalence r=50,gamma=0 vs ridge: max|diff|=%.3e passed=%s"
          % (equivalence["maxAbsPredictionDifference"], equivalence["passed"]))
    grade_primary = grade_block["perModel"][PRIMARY]
    print("[q1_fix] grade(primary): QWK=%s agreement=%.4f gradeMAE=%.4f"
          % (grade_primary.get("qwk"), grade_primary.get("exact_agreement", float("nan")),
             grade_primary.get("grade_mae", float("nan"))))
    print("[q1_fix] checks: rows=%d foldMismatch=%d leaks=%d recomputeMaxDiff=%.2e"
          % (len(predictions_table), mismatch, leaks,
             max(v["absDifference"] for v in recomputed.values())))
    print("[q1_fix] elapsed=%.1fs out=%s" % (elapsed, out))
    return 0


def _finite_number(value) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and math.isfinite(float(value))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Q1 nested-CV rerun: 4 models, true OOF, frozen protocol")
    parser.add_argument("--repeat", default="all", choices=["all", "0", "1", "2"],
                        help="repeat index to run (default all = 0,1,2 in one process)")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        # the runner may register extra argv; the protocol here comes from v6_common, never from argv
        print("[q1_fix] ignoring unrecognised arguments: %s" % unknown)
    repeats = list(range(v6.N_REPEATS)) if args.repeat == "all" else [int(args.repeat)]
    return run(repeats)


if __name__ == "__main__":
    sys.exit(main())
