"""q_common.py — shared deterministic helpers for the Q1/Q2/Q3 model scripts (modeler).

RULES THIS MODULE ENFORCES (so a run is evidence, not a story):
  * no project file is read at runtime: inputs come from the runner's frozen environment
    (MODELING_DATA_FILE / MODELING_TRAIN_FILE / MODELING_TEST_FILE) or from a DECLARED dependency
    (data/raw/2.csv, data/processed/q1_mapped.csv) resolved through MODELING_DEPENDENCIES;
  * every random draw uses np.random.default_rng(seed) with the registered seed, and the reduction order is
    pinned by single-threaded BLAS/OMP so a rerun with the same seed is bit-reproducible;
  * every number is emitted through modeling_contract.emit_metrics (finite floats only), every table through
    emit_predictions, every figure through save_figure (they land in the experiment directory and are hashed
    by the runner as registered outputs).
"""

import os

# Determinism first: a fixed reduction order is what makes the 1e-9 / 1e-6 reproduction tolerance meaningful.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ.setdefault("PYTHONHASHSEED", "0")

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from modeling_contract import (  # noqa: E402,F401
    dataset_path,
    project_dir,
    split_paths,
    seed,
    emit_metrics,
    emit_predictions,
    save_figure,
    emit_output,
    dependency_path,
)

META_COLUMNS = (
    "row", "row_index", "beer", "beer_id", "tasting_category_fine", "style", "style_holdout", "split_role",
)
CHEM_PREFIX = "chem__"
THR_PREFIX = "thr__"
EXCESS_PREFIX = "excess__"

DEFAULT_SEED = 20261024


# ----------------------------------------------------------------------------------------------------------------
# environment / IO
# ----------------------------------------------------------------------------------------------------------------
def run_seed(default: int = DEFAULT_SEED) -> int:
    """The registered seed, or the project-wide split seed when the runner did not pin one."""
    value = seed()
    return int(value) if value is not None else int(default)


def read_csv(path) -> pd.DataFrame:
    if path is None:
        raise RuntimeError("a required input file path is unset; run this script through modeling_experiment")
    frame = pd.read_csv(Path(path), encoding="utf-8-sig")
    frame.columns = [str(c) for c in frame.columns]
    return frame


def read_dependency(rel_path: str) -> pd.DataFrame:
    """Read a DECLARED dependency (the runner snapshots it and maps the original path to the snapshot copy)."""
    try:
        return read_csv(dependency_path(rel_path))
    except (ValueError, RuntimeError, FileNotFoundError):
        # Local debugging path only (never used inside a sealed runner snapshot for a registered dependency).
        return read_csv(project_dir() / rel_path)


def row_id_column(frame: pd.DataFrame) -> str:
    for candidate in ("row", "row_index", "id"):
        if candidate in frame.columns:
            return candidate
    raise RuntimeError("the registered table has no stable sample-id column (row/row_index/id)")


def id_values(frame: pd.DataFrame) -> np.ndarray:
    column = row_id_column(frame)
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        raise RuntimeError("the sample-id column %r contains missing/non-numeric values" % column)
    return values.to_numpy(dtype=float)


def chem_columns(frame: pd.DataFrame) -> list:
    return [c for c in frame.columns if c.startswith(CHEM_PREFIX)]


def threshold_columns(frame: pd.DataFrame) -> list:
    return [c for c in frame.columns if c.startswith(THR_PREFIX)]


def sensory_target_columns(frame: pd.DataFrame) -> list:
    """The 50 sensory target columns of a Q1/Q2 table: every column that is neither metadata nor a chem/thr block."""
    out = []
    for column in frame.columns:
        if column in META_COLUMNS:
            continue
        if column.startswith(CHEM_PREFIX) or column.startswith(THR_PREFIX) or column.startswith(EXCESS_PREFIX):
            continue
        out.append(column)
    return out


def load_split() -> dict:
    """The registered random holdout: train/test frames, their ids and the shared feature/target columns."""
    paths = split_paths()
    if paths.get("train") is None or paths.get("test") is None:
        raise RuntimeError("this script needs a registered split with both train and test files"
                           " (modeling_data {action:'register-split'})")
    train = read_csv(paths["train"])
    test = read_csv(paths["test"])
    data_path = dataset_path()
    data = read_csv(data_path) if data_path is not None else None
    reference = data if data is not None else train
    return {
        "train": train,
        "test": test,
        "data": data,
        "train_ids": id_values(train),
        "test_ids": id_values(test),
        "chem": chem_columns(reference),
        "targets": sensory_target_columns(reference),
    }


def load_dataset() -> pd.DataFrame:
    path = dataset_path()
    if path is None:
        raise RuntimeError("MODELING_DATA_FILE is unset; register the dataset and run through modeling_experiment")
    return read_csv(path)


def matrix(frame: pd.DataFrame, columns: list) -> np.ndarray:
    return frame[columns].to_numpy(dtype=float)


def impute_train(frame: pd.DataFrame, columns: list) -> tuple:
    """Median imputation fitted on TRAIN rows only; returns (values, medians)."""
    values = matrix(frame, columns)
    medians = np.nanmedian(values, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    return np.where(np.isfinite(values), values, medians[None, :]), medians


def apply_impute(frame: pd.DataFrame, columns: list, medians: np.ndarray) -> np.ndarray:
    values = matrix(frame, columns)
    return np.where(np.isfinite(values), values, medians[None, :])


# ----------------------------------------------------------------------------------------------------------------
# metrics / tables
# ----------------------------------------------------------------------------------------------------------------
def finite(value, what: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("%s is not finite (%r); a metric must be a real measurement" % (what, number))
    return number


def mean_absolute_error(truth: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    return np.mean(np.abs(truth - prediction), axis=0)


def per_target_scores(truth: np.ndarray, prediction: np.ndarray, targets: list) -> dict:
    mae = mean_absolute_error(truth, prediction)
    rmse = np.sqrt(np.mean((truth - prediction) ** 2, axis=0))
    out = {}
    for index, target in enumerate(targets):
        t = truth[:, index]
        p = prediction[:, index]
        total = float(np.sum((t - t.mean()) ** 2))
        residual = float(np.sum((t - p) ** 2))
        r2 = (1.0 - residual / total) if total > 0 else (1.0 if residual == 0 else 0.0)
        out[target] = {"mae": finite(mae[index], "mae[%s]" % target),
                       "rmse": finite(rmse[index], "rmse[%s]" % target),
                       "r2": finite(r2, "r2[%s]" % target)}
    return out


def emit_prediction_tables(ids: np.ndarray, truth: np.ndarray, prediction: np.ndarray, targets: list,
                           wide_name: str = "predictions.csv") -> dict:
    """Write the WIDE table the native evaluator recomputes from, plus the long pair table.

    Wide:  row, y_true__<target>*, y_pred__<target>*   (embedded truth is a consistency copy, not the truth source)
    Long:  pair_id, row, target, y_true, y_pred        (pair_id = row*100 + target index, unique)
    """
    ids = np.asarray(ids)
    integer_ids = np.all(np.abs(ids - np.round(ids)) < 1e-9)
    columns = {"row": [int(v) if integer_ids else float(v) for v in ids]}
    for index, target in enumerate(targets):
        columns["y_true__" + target] = truth[:, index].tolist()
    for index, target in enumerate(targets):
        columns["y_pred__" + target] = prediction[:, index].tolist()
    wide = pd.DataFrame(columns)
    wide_path = emit_predictions(wide, wide_name)

    long_rows = {"pair_id": [], "row": [], "target": [], "y_true": [], "y_pred": []}
    for index, target in enumerate(targets):
        for position, value in enumerate(ids):
            key = (int(round(float(value))) if integer_ids else int(position))
            long_rows["pair_id"].append(key * 100 + index)
            long_rows["row"].append(int(round(float(value))) if integer_ids else position)
            long_rows["target"].append(target)
            long_rows["y_true"].append(float(truth[position, index]))
            long_rows["y_pred"].append(float(prediction[position, index]))
    long = pd.DataFrame(long_rows)
    long_path = emit_predictions(long, "predictions_long.csv")
    return {"wide": wide_path, "long": long_path, "nRows": int(wide.shape[0]), "nTargets": int(len(targets))}


def figure(width: float = 7.0, height: float = 4.5) -> Figure:
    return Figure(figsize=(width, height), dpi=150)


def save_fig(fig: Figure, name: str) -> dict:
    record = save_figure(fig, name)
    return {"name": record["name"], "path": record["path"], "sha256": record["sha256"]}


def json_safe(value):
    """Recursively convert numpy scalars/arrays so emit_output never sees an unserializable object."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def emit_report(name: str, payload: dict) -> dict:
    return emit_output(name, json_safe(payload))


def figure_manifest(records: list) -> str:
    """One small JSON so the writer/reviewer can enumerate the figures without reading figures.json."""
    return json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True)
