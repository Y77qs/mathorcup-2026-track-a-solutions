"""q3_lib.py — Q3 helpers: per-column scale recovery, defect constraints, style-conditional sampling.

THE DATA FACTS THIS MODULE IS BUILT ON (all read from the registered project files, never assumed):
  * `data/processed/data_quality.json#perColumnCheck[<column>]["transform"]` declares, per compound, whether the
    1.csv/dataset value is `log10` of the concentration (196 columns), `raw` concentration (33), or a `zeroFloor`
    code (2: CS2, X4VG). The floor code itself is stored in
    `perColumnCheck[<column>]["calibrated"]["floorValueUsedForCalibratedZeros"]`.
  * `thr__<column>` in DATA-0003 carries 8.xlsx `threshold_mean` in ORIGINAL concentration units.
  * a defect is exceeded when `excess = concentration / threshold - 1 > 0`.
  * trans-2-nonenal (X.E..2.nonenal) and "Stale hops" have NO numeric threshold in 8.xlsx: they are reported as
    "not assessable", never given an invented threshold.

Everything is deterministic (one np.random.default_rng(seed) stream, fixed draw order).
"""

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.stats import rankdata
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

import q_common as C

DEFECT_COLUMNS = (
    "DMS", "X2.3.butanedione", "X4VG", "acetaldehyde", "DES", "H2S", "SO2.mg.L.",
)
UNASSESSABLE_DEFECTS = ("X.E..2.nonenal", "3-methyl-2-butenal")
HOLDOUT_STYLES = ("Tripel", "Kriek", "Lambic")
SOURCE_STYLE = "Pils/Lager"

# A-priori style relatedness used to condition generation on a style that is NOT in the training styles.
# It is registered BEFORE the run (params.priorStyleMapping) and is domain knowledge about beer styles, not a
# quantity estimated from the held-out rows.
PRIOR_STYLE_MAPPING = {
    "Tripel": ["Strong ale", "Dubbel"],                       # Belgian strong ale family
    "Kriek": ["Fruitbeer"],                                   # Belgian fruit beer
    "Lambic": ["Faro", "Flanders old brown", "West Flanders ale", "Brett/cofermented"],  # sour/wild family
}
# One explicit deviation from the zero-shot rule is pre-registered and disclosed in the outputs:
# READY -- no held-out row is used for fitting; only the prior mapping above conditions the generator.

ALPHA_GRID = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)
EPS = 1e-9


# ----------------------------------------------------------------------------------------------------------------
# data / scale recovery
# ----------------------------------------------------------------------------------------------------------------
def load_q3() -> dict:
    data = C.load_dataset()
    chem = C.chem_columns(data)
    thresholds = C.threshold_columns(data)
    style_column = "style" if "style" in data.columns else "tasting_category_fine"
    holdout_column = "style_holdout"
    if holdout_column not in data.columns:
        raise RuntimeError("DATA-0003 has no style_holdout column; the style holdout discipline cannot be applied")
    if style_column not in data.columns:
        raise RuntimeError("DATA-0003 has no style column")
    return {"data": data, "chem": chem, "thresholds": thresholds,
            "style": style_column, "holdout": holdout_column}


def load_scale_audit() -> dict:
    """perColumnCheck from data_quality.json: transform + zero-floor code per compound (no-prefix column name)."""
    quality, basis = C.read_json_dependency("data/processed/data_quality.json")
    checks = quality.get("perColumnCheck") or {}
    if not isinstance(checks, dict) or not checks:
        raise RuntimeError("data_quality.json has no perColumnCheck map; the per-column scale recovery cannot be "
                           "performed and thresholds must not be compared on a guessed scale")
    audit = {}
    for column, record in checks.items():
        transform = str(record.get("transform", "")).strip()
        if transform not in ("log10", "raw", "zeroFloor"):
            raise RuntimeError("unknown transform %r for column %r in data_quality.json" % (transform, column))
        calibrated = record.get("calibrated") or {}
        floor = calibrated.get("floorValueUsedForCalibratedZeros")
        if floor is None:
            recurring = record.get("recurringValues") or []
            if len(recurring) == 1 and int(recurring[0][1]) > 0:
                floor = recurring[0][0]
        if transform == "zeroFloor" and floor is None:
            raise RuntimeError("column %r is zeroFloor-coded but data_quality.json records no floor value" % column)
        audit[column] = {"transform": transform,
                         "floor": float(floor) if floor is not None else None}
    return {"columns": audit, "basis": basis,
            "rule": "log10 -> 10**v ; raw -> v ; zeroFloor -> 0 if v equals the recorded floor code else 10**v"}


def raw_concentration(column: str, values: np.ndarray, audit: dict) -> np.ndarray:
    record = audit["columns"].get(column)
    if record is None:
        raise RuntimeError("column %r is missing from the registered perColumnCheck audit" % column)
    values = np.asarray(values, dtype=float)
    if record["transform"] == "raw":
        return values.copy()
    if record["transform"] == "log10":
        return np.power(10.0, values)
    # zeroFloor: the floor code means "raw concentration 0", NOT 10**floor
    floor = record["floor"]
    return np.where(np.isclose(values, floor, rtol=0.0, atol=1e-12), 0.0, np.power(10.0, values))


def defect_table(frame: pd.DataFrame, thresholds: dict, audit: dict) -> pd.DataFrame:
    """excess__<compound> = concentration / threshold - 1 for the seven thresholded defect compounds."""
    out = pd.DataFrame(index=frame.index)
    for column in DEFECT_COLUMNS:
        chem_name = C.CHEM_PREFIX + column
        if chem_name not in frame.columns:
            raise RuntimeError("the dataset has no %r column" % chem_name)
        threshold = thresholds[column]
        raw = raw_concentration(column, frame[chem_name].to_numpy(dtype=float), audit)
        out["excess__" + column] = raw / threshold - 1.0
    return out


def threshold_map(frame: pd.DataFrame) -> dict:
    """The constant thr__<compound> value in ORIGINAL concentration units; refuses a non-constant column."""
    values, missing = {}, []
    for column in DEFECT_COLUMNS:
        name = C.THR_PREFIX + column
        if name not in frame.columns:
            missing.append(column)
            continue
        unique = np.unique(frame[name].to_numpy(dtype=float))
        if len(unique) != 1:
            raise RuntimeError("threshold column %r is not constant (%d distinct values)" % (name, len(unique)))
        values[column] = float(unique[0])
    if missing:
        raise RuntimeError("the dataset is missing threshold columns for the registered defect set: %s"
                           % ", ".join(missing))
    return values


def constraint_satisfaction(excess: pd.DataFrame) -> float:
    """Fraction of rows whose SEVEN excess values are all <= 0 (the registered native definition)."""
    if len(excess) == 0:
        raise RuntimeError("no generated row to evaluate")
    satisfied = np.ones(len(excess), dtype=bool)
    for column in excess.columns:
        satisfied &= excess[column].to_numpy(dtype=float) <= 0.0
    return float(np.mean(satisfied))


def exceedance_counts(excess: pd.DataFrame) -> dict:
    return {column: int(np.sum(excess[column].to_numpy(dtype=float) > 0.0)) for column in excess.columns}


# ----------------------------------------------------------------------------------------------------------------
# generative model
# ----------------------------------------------------------------------------------------------------------------
def standardised_training(frame: pd.DataFrame, chem: list, train_mask: np.ndarray):
    values = C.matrix(frame, chem)
    values = np.where(np.isfinite(values), values, 0.0)
    train_values = values[train_mask]
    mean = train_values.mean(axis=0)
    scale = train_values.std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)
    return (values - mean) / scale, mean, scale, train_values


def shrunk_covariance(z_train: np.ndarray, lam: float = 0.5) -> np.ndarray:
    """Covariance shrunk toward its diagonal: n (201) < p (231) makes the sample covariance singular."""
    covariance = np.cov(z_train, rowvar=False)
    diagonal = np.diag(np.diag(covariance))
    shrunk = (1.0 - lam) * covariance + lam * diagonal
    shrunk = (shrunk + shrunk.T) / 2.0
    return shrunk + 1e-8 * np.eye(shrunk.shape[0])


def sample_style(rng, mean: np.ndarray, covariance: np.ndarray, size: int) -> np.ndarray:
    return rng.multivariate_normal(mean, covariance, size=size, method="eigh")


def project_defects(frame: pd.DataFrame, thresholds: dict, audit: dict, margin: float = EPS):
    """Clip only the SEVEN defect compounds to their threshold when (and only when) they exceed it.

    The clip is applied in the column's own scale (log10 -> log10(threshold) - margin, raw -> threshold*(1-margin))
    with a tiny margin so the inequality `concentration/threshold - 1 <= 0` is numerically robust. Nothing else
    about the generated spectrum is modified.
    """
    out = frame.copy()
    clipped = {}
    for column in DEFECT_COLUMNS:
        name = C.CHEM_PREFIX + column
        threshold = thresholds[column]
        values = out[name].to_numpy(dtype=float).copy()
        raw = raw_concentration(column, values, audit)
        over = raw > threshold
        clipped[column] = int(np.sum(over))
        if not np.any(over):
            continue
        if audit["columns"][column]["transform"] == "raw":
            values[over] = threshold * (1.0 - margin)
        else:
            values[over] = np.log10(threshold) - margin
        out[name] = values
    return out, clipped


def energy_distance(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    value = 2.0 * cdist(a, b, "euclidean").mean() - cdist(a, a, "euclidean").mean() \
        - cdist(b, b, "euclidean").mean()
    return float(np.sqrt(max(value, 0.0)))


def profile_spearman(generated: np.ndarray, reference: np.ndarray) -> float:
    """Spearman between the mean generated profile and the mean real profile over the 231 compounds."""
    a = rankdata(generated.mean(axis=0))
    b = rankdata(reference.mean(axis=0))
    a = a - a.mean()
    b = b - b.mean()
    denominator = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    return float((a * b).sum() / denominator) if denominator > 0 else 0.0


# ----------------------------------------------------------------------------------------------------------------
# sensory-profile proxy (Q1 train rows only; explicitly NOT the Q1 final model, NOT measured ratings)
# ----------------------------------------------------------------------------------------------------------------
def fit_sensory_proxy(seed: int) -> dict:
    """Ridge compound -> 50 mapped sensory dimensions, fitted ONLY on the registered Q1 training rows."""
    mapped, basis_data = C.read_dependency("data/processed/q1_mapped.csv")
    train, basis_split = C.read_dependency("data/splits/SPLIT-0001/train.csv")
    features = C.chem_columns(mapped)
    targets = C.sensory_target_columns(mapped)
    train_features = C.chem_columns(train)
    features = [f for f in features if f in train_features]
    if not features or not targets:
        raise RuntimeError("the Q1 mapping table/split train file did not provide the proxy features/targets")
    missing_ids = [c for c in (("row",) if "row" in train.columns else ()) if c not in mapped.columns]
    if missing_ids:
        raise RuntimeError("the Q1 mapping table has no row id; the registered training rows cannot be selected")
    merged = mapped.merge(train[["row"]], on="row", how="inner", suffixes=("", "_train"))
    if len(merged) < 50:
        raise RuntimeError("the registered Q1 training rows do not overlap the Q1 mapping table (%d rows)" % len(merged))
    X_raw = C.matrix(merged, features)
    medians = np.nanmedian(X_raw, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    X = np.where(np.isfinite(X_raw), X_raw, medians[None, :])
    Y = C.matrix(merged, targets)
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)
    Xz = (X - mean) / scale
    folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    table = {}
    for alpha in ALPHA_GRID:
        errors = []
        for fit_index, score_index in folds.split(Xz):
            model = Ridge(alpha=alpha)
            model.fit(Xz[fit_index], Y[fit_index])
            errors.append(np.abs(Y[score_index] - model.predict(Xz[score_index])).reshape(-1))
        table[alpha] = float(np.mean(np.concatenate(errors)))
    alpha = min(ALPHA_GRID, key=lambda value: (table[value], value))
    model = Ridge(alpha=alpha)
    model.fit(Xz, Y)
    return {"model": model, "features": features, "targets": targets, "mean": mean, "scale": scale,
            "alpha": float(alpha), "cv": table, "nRows": int(len(merged)),
            "basis": {"q1Mapped": basis_data, "splitTrain": basis_split},
            "label": "Ridge proxy fitted on registered Q1 TRAIN rows; NOT the Q1 final model; NOT measured ratings"}


def predict_sensory_proxy(proxy: dict, frame: pd.DataFrame) -> np.ndarray:
    X = C.matrix(frame, proxy["features"])
    X = np.where(np.isfinite(X), X, proxy["mean"][None, :])
    return proxy["model"].predict((X - proxy["mean"]) / proxy["scale"])


def style_sensory_profiles(proxy: dict, frame: pd.DataFrame, style_values, audit: dict, thresholds: dict) -> dict:
    """Per-style constraint-satisfied mean profile (projected), for the figure only."""
    profiles = {}
    for style in HOLDOUT_STYLES:
        block = frame[frame["style"] == style]
        if len(block) == 0:
            continue
        predicted = predict_sensory_proxy(proxy, block)
        profiles[style] = predicted.mean(axis=0)
    return profiles
