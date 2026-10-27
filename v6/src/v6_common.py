"""v6_common.py — frozen shared interfaces for the R00-R03 rerun (MathorCup 2026 track A).

WHY THIS FILE EXISTS. The rerun must compare candidates under ONE frozen protocol:
3 repeats x 3 outer folds, 3 inner folds inside every outer training set, seeds
20261025/20261026/20261027, stratified by tasting_category_fine. Every script that
touches the protocol imports it from here so the split, the target universe and the
metric definitions cannot drift between questions.

CONVENTIONS (fixed by the lead, do not change without a new config acceptance):
  * row identity is `beer` (1..250), never the positional row index and never `beer_id`
    (which is truncated and therefore not a join key);
  * 231 chemical features are the `chem__*` columns of data/clean/q1_mapped.csv;
  * 50 sensory targets = 15 A_* + 15 F_* + 20 remaining columns, in the frozen order of
    src/target_columns.py:TARGET_COLS; the A/F 30 are the primary task;
  * A/F 30 primary metric = uniform-average MAE over the 30 targets (`mae`);
  * grades are RELATIVE grades derived from the outer-training empirical CDF:
    g = clip(floor(6*F(y)+0.5), 0, 6); they are never called the panel's original 0-6 score.

This module never fits a model and never writes outside the experiment directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]

SEEDS = (20261025, 20261026, 20261027)
N_REPEATS = 3
N_OUTER = 3
N_INNER = 3

STYLE_COL = "tasting_category_fine"
CHEM_PREFIX = "chem__"
GRADE_PREFIX = "g6__"

DATA_Q1 = PROJECT / "data/clean/q1_mapped.csv"
DATA_Q3 = PROJECT / "data/clean/q3.csv"
SPLITS_DIR = PROJECT / "data/splits/NESTED-CV-1"
SPLITS_CSV = SPLITS_DIR / "splits.csv"
SPLITS_MANIFEST = SPLITS_DIR / "manifest.json"

# frozen order of the 50 sensory targets (must equal src/target_columns.py:TARGET_COLS)
TARGETS_50 = [
    "A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
    "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
    "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
    "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
    "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
    "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
    "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic", "stale_hops",
    "t2n", "orange", "coriander", "clove", "lactic", "acetic", "barnyard", "alcohol",
    "aftertaste", "body", "co2", "overall",
]
TARGETS_AF30 = TARGETS_50[:30]
GROUPS = {
    "Aroma15": TARGETS_50[:15],
    "Flavour15": TARGETS_50[15:30],
    "Other20": TARGETS_50[30:],
}

# physical/derived feature groups (from data/clean/q2_chem_meta.json, regenerated in R00)
NON_SINGLE_COMPOUND = {
    "physical_parameter": ["pH", "color.EBC.", "bitterness", "ethanol..v.v.", "CO2.PSI.", "GFS", "unfermentables"],
    "derived_sum": ["kcalperc", "acids_sum", "esters_sum", "aroma_hops_sum", "sulfur_sum"],
    "element_or_index": ["iron", "protein.g.L.", "betaglucan.mg.L."],
}


# ----------------------------------------------------------------------------- hashes / IO
def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def write_json(path: Path, value) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# ----------------------------------------------------------------------------- data
def load_frame(path=None):
    import pandas as pd
    path = Path(path) if path is not None else DATA_Q1
    frame = pd.read_csv(path)
    if "beer" not in frame.columns:
        raise RuntimeError(f"{path} has no 'beer' column: row identity would be a guess")
    if not frame["beer"].is_unique:
        raise RuntimeError(f"{path}: 'beer' is not unique; a duplicate key would silently merge rows")
    return frame


def chem_columns(frame) -> list:
    cols = [c for c in frame.columns if c.startswith(CHEM_PREFIX)]
    if len(cols) != 231:
        raise RuntimeError(f"expected 231 chemical features, found {len(cols)}")
    return cols


def af_targets(frame) -> list:
    present = [t for t in TARGETS_AF30 if t in frame.columns]
    if len(present) != 30:
        raise RuntimeError(f"expected the 30 A/F targets, found {len(present)}")
    return present


def all_targets(frame) -> list:
    present = [t for t in TARGETS_50 if t in frame.columns]
    if len(present) != 50:
        raise RuntimeError(f"expected the 50 targets, found {len(present)}")
    return present


def style_of(frame):
    if STYLE_COL not in frame.columns:
        raise RuntimeError(f"{STYLE_COL} missing: style stratification is impossible")
    return frame[STYLE_COL].astype(str).to_numpy()


# ----------------------------------------------------------------------------- frozen splits
def load_splits():
    """Read the immutable nested-CV manifest written by src/r00_build_splits.py."""
    import pandas as pd
    if not SPLITS_CSV.exists():
        raise RuntimeError(f"frozen splits missing at {SPLITS_CSV}; run src/r00_build_splits.py first")
    table = pd.read_csv(SPLITS_CSV)
    need = {"beer", "repeat", "outer_fold", "inner_fold", "role", "style"}
    if not need.issubset(table.columns):
        raise RuntimeError(f"frozen splits lack columns {sorted(need - set(table.columns))}")
    return table


def iter_outer(splits=None):
    """Yield (repeat, outer_fold, train_beers, test_beers)."""
    splits = load_splits() if splits is None else splits
    for repeat in range(N_REPEATS):
        for fold in range(N_OUTER):
            part = splits[(splits["repeat"] == repeat) & (splits["outer_fold"] == fold)]
            train = np.sort(part.loc[part["role"] == "inner", "beer"].to_numpy())
            test = np.sort(part.loc[part["role"] == "outer_test", "beer"].to_numpy())
            if not len(train) or not len(test):
                raise RuntimeError(f"empty outer fold repeat={repeat} fold={fold}")
            if set(train) & set(test):
                raise RuntimeError(f"outer train/test overlap at repeat={repeat} fold={fold}")
            yield repeat, fold, train, test


def iter_inner(repeat, outer_fold, outer_train_beers, splits=None):
    """Yield (inner_fold, inner_train_beers, inner_valid_beers) inside one outer training set."""
    splits = load_splits() if splits is None else splits
    part = splits[(splits["repeat"] == repeat) & (splits["outer_fold"] == outer_fold)]
    part = part[part["role"] == "inner"]
    part = part[np.isin(part["beer"].to_numpy(), outer_train_beers)]
    for inner in range(N_INNER):
        valid = np.sort(part.loc[part["inner_fold"] == inner, "beer"].to_numpy())
        train = np.sort(part.loc[part["inner_fold"] != inner, "beer"].to_numpy())
        if not len(valid) or not len(train):
            raise RuntimeError(f"empty inner fold repeat={repeat} outer={outer_fold} inner={inner}")
        yield inner, train, valid


# ----------------------------------------------------------------------------- grades / metrics
def midrank_cdf(reference, values):
    """Empirical CDF of `reference` evaluated at `values`, with mid-ranks for ties."""
    reference = np.sort(np.asarray(reference, dtype=float))
    values = np.asarray(values, dtype=float)
    n = reference.size
    if n == 0:
        raise RuntimeError("empty reference distribution")
    below = np.searchsorted(reference, values, side="left")
    equal = np.searchsorted(reference, values, side="right") - below
    return (below + 0.5 * equal) / n


def to_grade(values, reference, lo=0, hi=6):
    """Relative grade g = clip(floor(6F(y)+0.5), 0, 6) using the TRAINING empirical CDF."""
    f = midrank_cdf(reference, values)
    return np.clip(np.floor(6.0 * f + 0.5), lo, hi).astype(int)


def quadratic_weighted_kappa(y_true, y_pred, lo=0, hi=6):
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    k = hi - lo + 1
    observed = np.zeros((k, k), dtype=float)
    for t, p in zip(y_true - lo, y_pred - lo):
        observed[t, p] += 1
    total = observed.sum()
    if total == 0:
        return float("nan")
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / total
    weights = np.zeros((k, k), dtype=float)
    for i in range(k):
        for j in range(k):
            weights[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)
    num = (weights * observed).sum()
    den = (weights * expected).sum()
    if den == 0:
        return 1.0 if num == 0 else float("nan")
    return float(1.0 - num / den)


def _r2(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(((y_true - y_pred) ** 2).sum())
    ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
    if ss_tot == 0.0:
        return None  # undefined: reported as NA, never forced to 0
    return 1.0 - ss_res / ss_tot


def mae_columns(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape:
        raise RuntimeError(f"shape mismatch {y_true.shape} vs {y_pred.shape}")
    return np.abs(y_true - y_pred).mean(axis=0)


def regression_block(y_true, y_pred, targets, styles=None, baseline_mae=None):
    """Uniform-average MAE block. Keys are stable and safe for the ledger (finite floats only)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    targets = list(targets)
    if y_true.shape != y_pred.shape:
        raise RuntimeError("y_true/y_pred shape mismatch")
    if y_true.shape[1] != len(targets):
        raise RuntimeError("target count disagrees with the matrix width")
    per_target_mae = mae_columns(y_true, y_pred)
    idx = {t: i for i, t in enumerate(targets)}
    block = {
        "mae": float(per_target_mae.mean()),
        "n_rows": int(y_true.shape[0]),
        "n_targets": int(len(targets)),
        "per_target": {t: {"mae": float(per_target_mae[i])} for t, i in idx.items()},
    }
    r2 = {}
    for t, i in idx.items():
        value = _r2(y_true[:, i], y_pred[:, i])
        if value is not None:
            r2[t] = float(value)
    block["r2"] = r2
    block["r2_na"] = int(len(targets) - len(r2))
    if r2:
        block["macro_r2"] = float(np.mean(list(r2.values())))
    # groups, only where every column of the group is present
    groups = {}
    for name, members in GROUPS.items():
        present = [m for m in members if m in idx]
        if len(present) == len(members):
            groups[name] = {
                "mae": float(np.mean([per_target_mae[idx[m]] for m in members])),
                "n": int(len(members)),
            }
    block["groups"] = groups
    if styles is not None:
        styles = np.asarray(styles)
        per_style = {}
        for style in sorted(set(styles.tolist())):
            mask = styles == style
            per_style[str(style)] = {
                "n": int(mask.sum()),
                "mae": float(np.abs(y_true[mask] - y_pred[mask]).mean()),
            }
        block["per_style"] = per_style
    if baseline_mae is not None and baseline_mae > 0:
        block["skill"] = float(1.0 - block["mae"] / baseline_mae)
    return block


# ----------------------------------------------------------------------------- output channel
def out_dir(script_name: str) -> Path:
    """The experiment directory when started by the runner; a local scratch dir otherwise."""
    value = os.environ.get("MODELING_EXPERIMENT_DIR")
    if value:
        return Path(value)
    fallback = PROJECT / "state/devrun/v6" / Path(script_name).stem
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def save_csv(frame, name: str, directory: Path = None) -> Path:
    directory = directory or out_dir(__file__)
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def save_json(name: str, value, directory: Path = None) -> Path:
    directory = directory or out_dir(__file__)
    path = Path(directory) / name
    write_json(path, value)
    return path


def emit_metrics(metrics: dict) -> None:
    from modeling_contract import emit_metrics as _emit
    _emit(metrics)


def emit_output(name: str, value) -> None:
    from modeling_contract import emit_output as _emit
    _emit(name, value)


def emit_predictions(frame) -> None:
    from modeling_contract import emit_predictions as _emit
    _emit(frame)
