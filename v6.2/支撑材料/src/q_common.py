# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q_common.py — shared plumbing for the beer 2026 MathorCup experiments.

Every experiment runs inside the modeling-contest runner:
  * cwd is the experiment directory; the runner exports MODELING_* paths for the registered data/split;
  * only registered snapshot files are readable, so auxiliary inputs go through dependency_path();
  * helpers live in src/ and are declared as dependencies, which puts this directory on PYTHONPATH.

The module deliberately avoids hidden global state: the seed is the runner's seed, and every random draw takes an
explicit numpy Generator/seed so an independent rerun reproduces the same numbers bit for bit.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy.special import ndtri

from modeling_contract import (  # noqa: F401  (re-exported for scripts)
    seed as contract_seed,
    emit_metrics,
    emit_predictions,
    emit_output,
    save_figure,
    experiment_dir,
    project_dir,
    dataset_path,
    split_paths,
    dependency_path,
)

META_COLUMNS = ("row", "beer", "beer_id", "tasting_category_fine")
CHEM_PREFIX = "chem__"
GRADE_PREFIX = "g6__"
DEFAULT_SEED = 20261024


# ----------------------------------------------------------------------------- seed / options
def run_seed(default: int = DEFAULT_SEED) -> int:
    """The runner seed (and its receipt), or the project default when run outside the runner."""
    value = contract_seed()
    return int(value) if value is not None else int(default)


def argv_options() -> dict:
    """--key value / --flag pairs, so a perturbation experiment can change a declared parameter."""
    out = {}
    args = os.sys.argv[1:]
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("--"):
            key = token[2:]
            if index + 1 < len(args) and not args[index + 1].startswith("--"):
                out[key] = args[index + 1]
                index += 2
            else:
                out[key] = "true"
                index += 1
        else:
            index += 1
    return out


def option(name: str, default=None):
    return argv_options().get(name, default)


def option_float(name: str, default: float) -> float:
    value = option(name, None)
    return float(default) if value is None else float(value)


def option_int(name: str, default: int) -> int:
    value = option(name, None)
    return int(default) if value is None else int(value)


def rng_for(seed: int, salt: int = 0) -> np.random.Generator:
    return np.random.default_rng(int(seed) + 1000003 * int(salt))


# ----------------------------------------------------------------------------- readers
def read_csv(path) -> pd.DataFrame:
    return pd.read_csv(path)


def read_dependency_csv(rel: str) -> pd.DataFrame:
    return pd.read_csv(dependency_path(rel))


def read_dependency_json(rel: str):
    with open(dependency_path(rel), "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset() -> pd.DataFrame:
    path = dataset_path()
    if path is None:
        raise RuntimeError("MODELING_DATA_FILE is not set: this script must run through modeling_experiment")
    return pd.read_csv(path)


def load_split() -> dict:
    paths = split_paths()
    if not paths.get("train"):
        raise RuntimeError("MODELING_TRAIN_FILE is not set: the experiment did not declare a split")
    out = {"train": pd.read_csv(paths["train"]), "test": pd.read_csv(paths["test"]) if paths.get("test") else None,
           "assignment": pd.read_csv(paths["assignment"]), "paths": {k: str(v) if v else None for k, v in paths.items()}}
    return out


def chem_columns(frame: pd.DataFrame) -> list:
    return [c for c in frame.columns if c.startswith(CHEM_PREFIX)]


def target_columns(frame: pd.DataFrame, targets) -> list:
    present = [t for t in targets if t in frame.columns]
    if len(present) != len(targets):
        missing = [t for t in targets if t not in frame.columns]
        raise RuntimeError("target columns missing from the table: %s" % missing[:5])
    return present


# ----------------------------------------------------------------------------- preprocessing
def matrix(frame: pd.DataFrame, columns: list) -> np.ndarray:
    """Numeric matrix of the named columns (NaN preserved); refuses a missing column by name."""
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise RuntimeError("matrix() is missing columns: %s" % missing[:5])
    return frame[columns].to_numpy(dtype=float)


def fit_median_imputer(frame: pd.DataFrame, columns: list) -> dict:
    medians = {}
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        medians[column] = float(np.median(finite)) if finite.size else 0.0
    return medians


def apply_median_imputer(frame: pd.DataFrame, columns: list, medians: dict, missing_columns: list = None):
    values = np.empty((len(frame), len(columns) + len(missing_columns or [])), dtype=float)
    for position, column in enumerate(columns):
        raw = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        filled = np.where(np.isfinite(raw), raw, medians[column])
        values[:, position] = filled
    if missing_columns:
        for offset, column in enumerate(missing_columns):
            raw = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            values[:, len(columns) + offset] = np.where(np.isfinite(raw), 0.0, 1.0)
    return values


def fit_standardizer(values: np.ndarray) -> dict:
    centre = np.nanmean(values, axis=0)
    scale = np.nanstd(values, axis=0)
    scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1.0)
    return {"centre": centre, "scale": scale}


def apply_standardizer(values: np.ndarray, rule: dict) -> np.ndarray:
    out = (values - rule["centre"]) / rule["scale"]
    return np.clip(out, -8.0, 8.0)


def fit_rank_gauss(frame: pd.DataFrame, columns: list, n_train: int) -> dict:
    """Empirical CDF per column with mid-ranks; the transform clips at eps = 1/(2 n_train)."""
    grids = {}
    for column in columns:
        raw = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        finite = np.sort(raw[np.isfinite(raw)])
        grids[column] = finite
    return {"grids": grids, "eps": 1.0 / (2.0 * max(int(n_train), 1))}


def apply_rank_gauss(frame: pd.DataFrame, columns: list, rule: dict) -> np.ndarray:
    n = len(frame)
    out = np.empty((n, len(columns)), dtype=float)
    eps = float(rule["eps"])
    for position, column in enumerate(columns):
        raw = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        grid = rule["grids"][column]
        # mid-rank empirical CDF: (# values below + half of # values equal) / n_train, then clip and prograde
        u = np.empty(n, dtype=float)
        if grid.size == 0:
            u[:] = 0.5
        else:
            below = np.searchsorted(grid, raw, side="left")
            equal = np.searchsorted(grid, raw, side="right") - below
            u = (below + 0.5 * equal) / float(grid.size)
        u = np.clip(u, eps, 1.0 - eps)
        out[:, position] = ndtri(u)
    return out


# ----------------------------------------------------------------------------- metrics
def mae_per_target(truth: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    return np.nanmean(np.abs(truth - prediction), axis=0)


def r2_per_target(truth: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    truth = np.asarray(truth, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    residual = np.nansum((truth - prediction) ** 2, axis=0)
    total = np.nansum((truth - np.nanmean(truth, axis=0)) ** 2, axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        values = 1.0 - residual / total
    return np.where(total > 1e-12, values, np.nan)


def spearman_matrix(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Spearman rho between every column of X and every column of Y (rank, then Pearson)."""
    def ranked(matrix):
        order = np.argsort(matrix, axis=0, kind="mergesort")
        ranks = np.empty_like(matrix, dtype=float)
        for j in range(matrix.shape[1]):
            column = matrix[:, j]
            idx = order[:, j]
            sorted_values = column[idx]
            positions = np.arange(len(column), dtype=float)
            # mid-ranks for ties, done vectorised per column
            uniq, inverse, counts = np.unique(sorted_values, return_inverse=True, return_counts=True)
            mid = np.cumsum(counts) - (counts - 1) / 2.0
            ranks[idx, j] = mid[inverse]
        return ranks - ranks.mean(axis=0, keepdims=True)

    Xr = ranked(np.asarray(X, dtype=float))
    Yr = ranked(np.asarray(Y, dtype=float))
    Xn = Xr / np.maximum(np.linalg.norm(Xr, axis=0, keepdims=True), 1e-12)
    Yn = Yr / np.maximum(np.linalg.norm(Yr, axis=0, keepdims=True), 1e-12)
    return Xn.T @ Yn


def percentile_rank(values: np.ndarray) -> np.ndarray:
    """Uniform percentile of each value within its column (larger value -> larger percentile)."""
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, axis=0, kind="mergesort")
    ranks = np.empty_like(values)
    for j in range(values.shape[1]):
        ranks[order[:, j], j] = np.arange(values.shape[0], dtype=float)
    return ranks / max(values.shape[0] - 1, 1)


# ----------------------------------------------------------------------------- outputs
def prediction_table(ids, truth: np.ndarray, prediction: np.ndarray, targets: list, prefix: str = "y_pred__") -> pd.DataFrame:
    frame = pd.DataFrame({"row": np.asarray(ids)})
    for position, target in enumerate(targets):
        frame[prefix + target] = np.asarray(prediction[:, position], dtype=float)
        frame["y_true__" + target] = np.asarray(truth[:, position], dtype=float)
    return frame


def long_table(ids, truth: np.ndarray, prediction: np.ndarray, targets: list) -> pd.DataFrame:
    rows = []
    for i, sample in enumerate(ids):
        for position, target in enumerate(targets):
            rows.append({"row": sample, "target": target,
                         "y_true": float(truth[i, position]), "y_pred": float(prediction[i, position])})
    return pd.DataFrame(rows)


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def report(name: str, payload: dict) -> dict:
    return emit_output(name, json_safe(payload))


def figure(width: float = 7.6, height: float = 4.6) -> Figure:
    fig = Figure(figsize=(width, height))
    fig.patch.set_facecolor("white")
    return fig


def save_fig(fig: Figure, name: str) -> dict:
    return save_figure(fig, name)


def figure_manifest(records: list) -> str:
    emit_output("figure_manifest", [r.get("path") if isinstance(r, dict) else r for r in records])
    return "figures.json"
