# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q1_lib.py — shared Q1 machinery (fold-safe preprocessing, graph-regularised low-rank multi-output
regression, train-only cross-validation, 0-6 grading and reporting helpers).

Design notes
------------
* Every preprocessing rule (median imputer, z-score / Rank-Gauss, target centre/scale, feature graph) is
  fitted on the TRAIN part of a fold only; an evaluation block is transformed with the stored rule.
* The design matrix is ``[231 chem features | 9 missing-indicator columns]`` (240 columns).  The graph
  Laplacian is blockdiag(L_231, 0_9) so the indicators are not smoothed over the chemistry graph.
* ``L`` starts as ``D_{|W|} - W`` with ``W_jk = rho_jk * 1{|rho_jk| >= tau}`` (Spearman on the train rows,
  symmetric, zero diagonal) and is then projected to the PSD cone by clipping its eigenvalues at 0.  That
  projection is a numerical-stabilisation step, reported as such in the paper.
* The low-rank fit is ALS on ``B = A C^T`` with 25 sweeps and a per-sweep intercept update.  All linear
  solves are deterministic (Cholesky for the PSD normal matrix, LAPACK solve for the small r x r system).
* Grading is derived from ``data/processed/q1_grade_params.json`` (its ``trainValues`` are the sorted
  SPLIT-0001 train labels; SPLIT-0001 and SPLIT-0002 share the same assignment, so this is the train fold).

The module is imported by ``q1_candidate.py`` and ``q1_fusion.py``; the median baseline is owned by the Lead
(``q1_baseline.py``) and is not touched here.
"""

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
from scipy.special import ndtri

from q_common import (
    chem_columns,
    target_columns,
    fit_median_imputer,
    apply_median_imputer,
    fit_standardizer,
    apply_standardizer,
    fit_rank_gauss,
    apply_rank_gauss,
    spearman_matrix,
    r2_per_target,
    rng_for,
)
from target_columns import FEATURE_COLS, TARGET_COLS, MISSING_COLUMNS

CHEM_COLS = ["chem__" + name for name in FEATURE_COLS]
MISSING_CHEM_COLS = ["chem__" + name for name in MISSING_COLUMNS]
N_FEATURES = len(FEATURE_COLS)
N_TARGETS = len(TARGET_COLS)
N_INDICATORS = len(MISSING_COLUMNS)
TAU = 0.5
N_ITER = 25

GROUPS = {
    "Aroma": [t for t in TARGET_COLS if t.startswith("A_")],
    "Flavour": [t for t in TARGET_COLS if t.startswith("F_")],
    "other": [t for t in TARGET_COLS if not t.startswith(("A_", "F_"))],
}


# --------------------------------------------------------------------------------------------- data loading
def check_targets(frame: pd.DataFrame, n_expected: int = N_TARGETS) -> list:
    present = [t for t in TARGET_COLS if t in frame.columns]
    if len(present) != n_expected:
        raise RuntimeError("expected %d target columns, found %d" % (n_expected, len(present)))
    return present


def frame_columns(frame: pd.DataFrame) -> list:
    missing = [c for c in CHEM_COLS if c not in frame.columns]
    if missing:
        raise RuntimeError("chem columns missing from the table: %s" % missing[:5])
    return list(CHEM_COLS)


def raw_chem_matrix(frame: pd.DataFrame) -> np.ndarray:
    return frame[list(CHEM_COLS)].to_numpy(dtype=float)


def raw_target_matrix(frame: pd.DataFrame) -> np.ndarray:
    return frame[list(TARGET_COLS)].to_numpy(dtype=float)


# --------------------------------------------------------------------------------------------- preprocessing
def imputed_blocks(fit_frame: pd.DataFrame, blocks: dict) -> dict:
    """Fit the median imputer on ``fit_frame`` and apply it to every block (n x 240 each).

    The layout is ``[231 imputed chem features | 9 missing-indicator columns]`` exactly as q_common builds it.
    """
    medians = fit_median_imputer(fit_frame, CHEM_COLS)
    out = {}
    for key, frame in blocks.items():
        out[key] = apply_median_imputer(frame, CHEM_COLS, medians, MISSING_CHEM_COLS)
    return out


def feature_view(matrix: np.ndarray) -> pd.DataFrame:
    """A named frame of the 231 imputed chem columns (needed by q_common's Rank-Gauss helpers)."""
    return pd.DataFrame(matrix[:, :N_FEATURES], columns=list(CHEM_COLS))


def representation(fit_matrix: np.ndarray, blocks: dict, rep: str, n_train: int) -> dict:
    """Fit z-score or Rank-Gauss on ``fit_matrix`` (231 columns) and transform every block.

    The 9 indicator columns are appended unchanged in both representations.
    """
    fit_frame = feature_view(fit_matrix)
    out = {}
    if rep == "zscore":
        rule = fit_standardizer(fit_matrix[:, :N_FEATURES])
        for key, matrix in blocks.items():
            transformed = apply_standardizer(matrix[:, :N_FEATURES], rule)
            out[key] = np.concatenate([transformed, matrix[:, N_FEATURES:]], axis=1)
    elif rep == "rankgauss":
        rule = fit_rank_gauss(fit_frame, list(CHEM_COLS), n_train)
        for key, matrix in blocks.items():
            transformed = apply_rank_gauss(feature_view(matrix), list(CHEM_COLS), rule)
            out[key] = np.concatenate([transformed, matrix[:, N_FEATURES:]], axis=1)
    else:
        raise ValueError("unknown representation %r (expected zscore|rankgauss)" % (rep,))
    return out


def target_scaling(fit_targets: np.ndarray) -> dict:
    centre = fit_targets.mean(axis=0)
    scale = fit_targets.std(axis=0)
    scale = np.where(np.isfinite(scale) & (scale > 1e-8), scale, 1.0)
    return {"centre": centre, "scale": scale}


# --------------------------------------------------------------------------------------------- graph
def adjacency(rho: np.ndarray, tau: float = TAU) -> np.ndarray:
    weight = np.where(np.abs(rho) >= tau, rho, 0.0)
    weight = 0.5 * (weight + weight.T)
    np.fill_diagonal(weight, 0.0)
    return weight


def build_graph(train_matrix: np.ndarray, tau: float = TAU) -> dict:
    """W (231x231), L_231 = D_{|W|} - W projected to PSD, and the 240x240 blockdiag(L_231, 0_9)."""
    features = train_matrix[:, :N_FEATURES]
    rho = spearman_matrix(features, features)
    weight = adjacency(rho, tau)
    lap231 = np.diag(np.abs(weight).sum(axis=1)) - weight
    lap231 = 0.5 * (lap231 + lap231.T)
    values, vectors = np.linalg.eigh(lap231)
    min_eigen = float(values.min())
    values = np.clip(values, 0.0, None)
    lap231 = (vectors * values) @ vectors.T
    lap231 = 0.5 * (lap231 + lap231.T)
    laplacian = np.zeros((N_FEATURES + N_INDICATORS, N_FEATURES + N_INDICATORS), dtype=float)
    laplacian[:N_FEATURES, :N_FEATURES] = lap231
    return {"rho": rho, "weight": weight, "laplacian231": lap231, "laplacian": laplacian,
            "tau": float(tau), "minEigenvalue": min_eigen,
            "edges": int(np.count_nonzero(np.triu(weight, 1))),
            "components": connected_components(weight)}


def connected_components(weight: np.ndarray) -> dict:
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components as cc
    matrix = csr_matrix((np.abs(weight) > 0).astype(np.int8))
    count, labels = cc(matrix, directed=False)
    return {"count": int(count), "labels": labels.astype(int).tolist()}


# --------------------------------------------------------------------------------------------- models
class NormalSystem:
    """The penalised normal matrix ``Z^T Z / n + lambda I + gamma L`` for one fold and one (lambda, gamma)."""

    def __init__(self, design: np.ndarray, laplacian: np.ndarray, lam: float, gamma: float):
        n = design.shape[0]
        self.design = design
        self.lam = float(lam)
        self.gamma = float(gamma)
        self.gram = design.T @ design / float(n)
        matrix = self.gram + self.lam * np.eye(design.shape[1]) + self.gamma * laplacian
        self.matrix = 0.5 * (matrix + matrix.T)
        self.factor = cho_factor(self.matrix, lower=True, check_finite=False)

    def solve(self, rhs: np.ndarray) -> np.ndarray:
        return cho_solve(self.factor, rhs, check_finite=False)


def ridge_graph_fit(design: np.ndarray, targets: np.ndarray, laplacian: np.ndarray,
                    lam: float, gamma: float) -> dict:
    """Ridge + graph penalty with an unrestricted coefficient matrix (ablation reference)."""
    system = NormalSystem(design, laplacian, lam, gamma)
    n = design.shape[0]
    intercept = targets.mean(axis=0)
    beta = system.solve(design.T @ (targets - intercept) / float(n))
    return {"beta": beta, "intercept": intercept, "system": system}


def _small_solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(matrix, rhs, rcond=None)[0]


def lowrank_fit(design: np.ndarray, targets: np.ndarray, laplacian: np.ndarray, rank: int,
                lam: float, gamma: float, n_iter: int = N_ITER) -> dict:
    """Graph-regularised low-rank multi-output regression: min ||Y - ZB - 1 b^T||^2/n + lam||B||^2 + gamma tr(B^T L B)
    with B = A C^T of rank <= r; ALS sweeps with a per-sweep intercept update."""
    n, d = design.shape
    q = targets.shape[1]
    system = NormalSystem(design, laplacian, lam, gamma)
    intercept = targets.mean(axis=0)
    beta0 = system.solve(design.T @ (targets - intercept) / float(n))
    u, s, vt = np.linalg.svd(beta0, full_matrices=False)
    rank_eff = int(min(rank, s.size))
    a = u[:, :rank_eff] * np.sqrt(s[:rank_eff])
    c = vt[:rank_eff].T * np.sqrt(s[:rank_eff])
    for _ in range(int(n_iter)):
        residual = targets - intercept
        ctc = c.T @ c
        rhs = design.T @ residual @ c / float(n)
        a = system.solve(rhs)
        a = _small_solve(ctc, a.T).T
        za = design @ a
        gram = za.T @ za / float(n) + lam * (a.T @ a) + gamma * (a.T @ laplacian @ a)
        gram = 0.5 * (gram + gram.T)
        c = _small_solve(gram, za.T @ residual / float(n)).T
        intercept = (targets - za @ c.T).mean(axis=0)
    beta = a @ c.T
    return {"beta": beta, "intercept": intercept, "a": a, "c": c, "system": system, "rank": rank_eff}


def predict(design: np.ndarray, model: dict) -> np.ndarray:
    return design @ model["beta"] + model["intercept"]


# --------------------------------------------------------------------------------------------- fold plumbing
def fold_indices(n_rows: int, n_folds: int, seed: int, salt: int = 11) -> list:
    order = rng_for(seed, salt).permutation(n_rows)
    return [np.sort(part.astype(int)) for part in np.array_split(order, n_folds)]


def fold_blocks(frame: pd.DataFrame, train_idx: np.ndarray, eval_idx: np.ndarray,
                rep: str) -> dict:
    """Fit every rule on ``train_idx`` rows only and transform train/eval blocks.

    Returns a dict with Z/Y for the train rows, Z for the eval rows and the unstandardised eval targets.
    """
    train_frame = frame.iloc[train_idx]
    eval_frame = frame.iloc[eval_idx]
    blocks = imputed_blocks(train_frame, {"train": train_frame, "eval": eval_frame})
    transformed = representation(blocks["train"], blocks, rep, n_train=len(train_idx))
    targets = raw_target_matrix(train_frame)
    scaling = target_scaling(targets)
    return {
        "rep": rep,
        "train_index": np.asarray(train_idx),
        "eval_index": np.asarray(eval_idx),
        "z_train": transformed["train"],
        "z_eval": transformed["eval"],
        "y_train": targets,
        "y_train_std": (targets - scaling["centre"]) / scaling["scale"],
        "y_eval": raw_target_matrix(eval_frame),
        "target_centre": scaling["centre"],
        "target_scale": scaling["scale"],
        "graph": build_graph(blocks["train"]),
        "imputed_train": blocks["train"],
    }


def evaluate(model: dict, block: dict) -> dict:
    prediction = predict(block["z_eval"], model) * block["target_scale"] + block["target_centre"]
    truth = block["y_eval"]
    return {"prediction": prediction, "truth": truth,
            "mae": float(np.mean(np.abs(truth - prediction))),
            "mae_per_target": np.mean(np.abs(truth - prediction), axis=0)}


# --------------------------------------------------------------------------------------------- CV search
def cv_mae_for(blocks: list, rank, lam, gamma, model_kind: str = "lowrank",
               n_iter: int = N_ITER) -> dict:
    """Mean and per-fold pooled MAE over the given fold blocks."""
    fold_maes = []
    predictions = []
    for block in blocks:
        laplacian = block["graph"]["laplacian"]
        if model_kind == "lowrank":
            model = lowrank_fit(block["z_train"], block["y_train_std"], laplacian, rank, lam, gamma, n_iter)
        elif model_kind == "ridge":
            model = ridge_graph_fit(block["z_train"], block["y_train_std"], laplacian, lam, gamma)
        else:
            raise ValueError("unknown model kind %r" % (model_kind,))
        scored = evaluate(model, block)
        fold_maes.append(scored["mae"])
        predictions.append(scored["prediction"])
    return {"fold_maes": [float(v) for v in fold_maes],
            "mean": float(np.mean(fold_maes)), "sd": float(np.std(fold_maes, ddof=0)),
            "predictions": predictions}


def build_blocks(frame: pd.DataFrame, folds: list, rep: str) -> list:
    blocks = []
    n_rows = len(frame)
    all_index = np.arange(n_rows)
    for held_out in folds:
        train_index = np.setdiff1d(all_index, held_out, assume_unique=False)
        blocks.append(fold_blocks(frame, train_index, held_out, rep))
    return blocks


def search_grid(frame: pd.DataFrame, seed: int, ranks, lambdas, gammas, reps=("zscore", "rankgauss"),
                n_folds: int = 5, n_iter: int = N_ITER) -> dict:
    """Train-only 5-fold CV over (representation, rank, lambda, gamma); returns every cell with fold detail."""
    folds = fold_indices(len(frame), n_folds, seed, salt=13)
    blocks = {rep: build_blocks(frame, folds, rep) for rep in reps}
    cells = []
    for rep in reps:
        for rank in ranks:
            for lam in lambdas:
                for gamma in gammas:
                    scoring = cv_mae_for(blocks[rep], rank, lam, gamma, "lowrank", n_iter)
                    cells.append({"representation": rep, "rank": int(rank), "lambda": float(lam),
                                  "gamma": float(gamma), "cv_mae": scoring["mean"],
                                  "cv_mae_sd": scoring["sd"], "fold_maes": scoring["fold_maes"]})
    return {"cells": cells, "blocks": blocks, "folds": folds}


def best_cell(cells: list, representation: str = "zscore") -> dict:
    subset = [c for c in cells if c["representation"] == representation]
    best = min(subset, key=lambda c: (c["cv_mae"], c["rank"], c["lambda"], c["gamma"]))
    return best


def ridge_cv(blocks: list, lambdas, gammas) -> list:
    out = []
    for lam in lambdas:
        for gamma in gammas:
            scoring = cv_mae_for(blocks, None, lam, gamma, "ridge")
            out.append({"lambda": float(lam), "gamma": float(gamma), "cv_mae": scoring["mean"],
                        "cv_mae_sd": scoring["sd"], "fold_maes": scoring["fold_maes"]})
    return out


# --------------------------------------------------------------------------------------------- final fit
class FittedModel:
    """A full-train fit plus the exact rules needed to transform any later table."""

    def __init__(self, fit_frame: pd.DataFrame, rep: str, rank, lam, gamma, n_iter: int = N_ITER,
                 tau: float = TAU):
        self.rep = rep
        self.medians = fit_median_imputer(fit_frame, CHEM_COLS)
        matrix = apply_median_imputer(fit_frame, CHEM_COLS, self.medians, MISSING_CHEM_COLS)
        self.zscore_rule = fit_standardizer(matrix[:, :N_FEATURES])
        self.rankgauss_rule = fit_rank_gauss(feature_view(matrix), list(CHEM_COLS), len(fit_frame))
        transformed = representation(matrix, {"train": matrix}, rep, len(fit_frame))["train"]
        targets = raw_target_matrix(fit_frame)
        scaling = target_scaling(targets)
        self.target_centre = scaling["centre"]
        self.target_scale = scaling["scale"]
        self.graph = build_graph(matrix, tau=tau)
        self.rank = int(rank)
        self.lam = float(lam)
        self.gamma = float(gamma)
        self.model = lowrank_fit(transformed, (targets - self.target_centre) / self.target_scale,
                                 self.graph["laplacian"], rank, lam, gamma, n_iter)

    def design(self, frame: pd.DataFrame) -> np.ndarray:
        matrix = apply_median_imputer(frame, CHEM_COLS, self.medians, MISSING_CHEM_COLS)
        if self.rep == "zscore":
            transformed = apply_standardizer(matrix[:, :N_FEATURES], self.zscore_rule)
        else:
            transformed = apply_rank_gauss(feature_view(matrix), list(CHEM_COLS), self.rankgauss_rule)
        return np.concatenate([transformed, matrix[:, N_FEATURES:]], axis=1)

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        standardised = predict(self.design(frame), self.model)
        return standardised * self.target_scale + self.target_centre


# --------------------------------------------------------------------------------------------- misc utilities
def transform_pair(fit_frame: pd.DataFrame, eval_frame: pd.DataFrame, rep: str) -> dict:
    """Train-fold rules from ``fit_frame`` applied to both tables (design matrices only)."""
    blocks = imputed_blocks(fit_frame, {"fit": fit_frame, "eval": eval_frame})
    transformed = representation(blocks["fit"], blocks, rep, n_train=len(fit_frame))
    return {"fit": transformed["fit"], "eval": transformed["eval"]}


def simplex_projection(values: np.ndarray) -> np.ndarray:
    """Euclidean projection of a vector onto the probability simplex {w >= 0, sum w = 1} (Duchi et al.)."""
    vector = np.asarray(values, dtype=float).ravel()
    n = vector.size
    ordered = np.sort(vector)[::-1]
    cumulative = np.cumsum(ordered) - 1.0
    indices = np.arange(1, n + 1, dtype=float)
    candidate = np.nonzero(ordered - cumulative / indices > 0)[0]
    rho = int(candidate[-1])
    theta = cumulative[rho] / float(rho + 1)
    return np.clip(vector - theta, 0.0, None)


# --------------------------------------------------------------------------------------------- metrics
def pooled_mae(truth: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(truth, dtype=float) - np.asarray(prediction, dtype=float))))


def median_reference(train_targets: np.ndarray, eval_targets: np.ndarray) -> dict:
    """Per-target train median reference; also used to normalise the skill score."""
    medians = np.median(train_targets, axis=0)
    prediction = np.broadcast_to(medians, eval_targets.shape)
    return {"prediction": prediction, "mae": pooled_mae(eval_targets, prediction)}


def r2_mean(truth: np.ndarray, prediction: np.ndarray) -> float:
    values = r2_per_target(truth, prediction)
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else 0.0


def skill_score(mae: float, reference_mae: float) -> float:
    if not np.isfinite(reference_mae) or reference_mae <= 0.0:
        return 0.0
    return float(1.0 - mae / reference_mae)


def group_macro_arrays(values: np.ndarray) -> dict:
    out = {}
    for group, members in GROUPS.items():
        index = [TARGET_COLS.index(t) for t in members]
        out[group] = float(np.mean(values[index]))
    return out


# --------------------------------------------------------------------------------------------- grading
def midpoint_cdf(grid: np.ndarray, values: np.ndarray) -> np.ndarray:
    below = np.searchsorted(grid, values, side="left")
    equal = np.searchsorted(grid, values, side="right") - below
    return (below + 0.5 * equal) / float(grid.size)


def continuous_grade(grade_params: dict, prediction: np.ndarray) -> dict:
    """a = train midrank CDF of the prediction; the delivered grade is floor(6a + 0.5) clipped to 0..6."""
    n_targets = prediction.shape[1]
    a = np.zeros_like(prediction, dtype=float)
    for position, target in enumerate(TARGET_COLS[:n_targets]):
        grid = np.asarray(grade_params[target]["trainValues"], dtype=float)
        a[:, position] = midpoint_cdf(grid, prediction[:, position])
    continuous = 6.0 * a
    discrete = np.clip(np.floor(continuous + 0.5), 0, 6).astype(int)
    # linear sensitivity variant: the declared [low, high] reference endpoints map to 0 and 1
    a_linear = np.zeros_like(prediction, dtype=float)
    for position, target in enumerate(TARGET_COLS[:n_targets]):
        entry = grade_params[target]
        low = float(entry["linearReferenceLow"])
        high = float(entry["linearReferenceHigh"])
        span = high - low if high - low > 1e-12 else 1.0
        a_linear[:, position] = np.clip((prediction[:, position] - low) / span, 0.0, 1.0)
    discrete_linear = np.clip(np.floor(6.0 * a_linear + 0.5), 0, 6).astype(int)
    return {"a": a, "continuous": continuous, "discrete": discrete,
            "a_linear": a_linear, "discrete_linear": discrete_linear}


def reference_grades(frame: pd.DataFrame) -> np.ndarray:
    columns = ["g6__" + t for t in TARGET_COLS]
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise RuntimeError("reference grade columns missing: %s" % missing[:3])
    continuous = frame[columns].to_numpy(dtype=float)
    return np.clip(np.floor(continuous + 0.5), 0, 6).astype(int)


def quadratic_weighted_kappa(truth: np.ndarray, prediction: np.ndarray, n_labels: int = 7) -> float:
    truth = np.asarray(truth, dtype=int).ravel()
    prediction = np.asarray(prediction, dtype=int).ravel()
    observed = np.zeros((n_labels, n_labels), dtype=float)
    for t, p in zip(truth, prediction):
        if 0 <= t < n_labels and 0 <= p < n_labels:
            observed[t, p] += 1.0
    total = observed.sum()
    if total <= 0:
        return 0.0
    observed = observed / total
    hist_truth = observed.sum(axis=1)
    hist_pred = observed.sum(axis=0)
    expected = np.outer(hist_truth, hist_pred)
    weights = np.zeros((n_labels, n_labels), dtype=float)
    for i in range(n_labels):
        for j in range(n_labels):
            weights[i, j] = (i - j) ** 2 / float((n_labels - 1) ** 2)
    denominator = float((weights * expected).sum())
    if denominator <= 1e-12:
        return 0.0
    return float(1.0 - (weights * observed).sum() / denominator)


def grade_summary(discrete: np.ndarray, reference: np.ndarray, linear: np.ndarray,
                  continuous: np.ndarray) -> dict:
    counts = np.bincount(discrete.ravel(), minlength=7).tolist()
    reference_counts = np.bincount(reference.ravel(), minlength=7).tolist()
    agreement = float(np.mean(discrete == reference))
    linear_agreement = float(np.mean(linear == reference))
    return {
        "qwk": quadratic_weighted_kappa(reference, discrete),
        "qwkLinearSensitivity": quadratic_weighted_kappa(reference, linear),
        "agreement": agreement,
        "agreementLinearSensitivity": linear_agreement,
        "meanGrade": float(np.mean(discrete)),
        "referenceMeanGrade": float(np.mean(reference)),
        "gradeCounts": counts,
        "referenceGradeCounts": reference_counts,
        "continuousMean": float(np.mean(continuous)),
        "linearVsMainAgreement": float(np.mean(linear == discrete)),
    }


def confusion_matrix(discrete: np.ndarray, reference: np.ndarray, n_labels: int = 7) -> list:
    matrix = np.zeros((n_labels, n_labels), dtype=float)
    for t, p in zip(np.asarray(reference).ravel(), np.asarray(discrete).ravel()):
        matrix[int(t), int(p)] += 1.0
    return matrix.tolist()
