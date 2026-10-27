"""q3_fix.py — Q3 generator, corrected for the six defects of MathorCup_A_v5.1 §三.

WHY THIS FILE EXISTS. The v5 Q3 generator (`src/q3_baseline.py` / `src/q3_generate.py`) was rejected by the
independent recheck on six points that are all visible in its own outputs:

  D1 state/scale      generated LINEAR_CALIBRATED cells went negative (142 cells / 40 rows), because the t2n
                      projection shifted the whole vector and nothing kept the physical concentrations non-negative;
                      log10 cells were clipped at zero as if they were concentrations.
  D2 raw/design       only the post-projection spectrum was stored, so the size of the projection was unknowable.
  D3 tuning           one (kappa, kappa_R) was picked by averaging the per-fold selection tables and then written
                      back into every fold ("cross-fold pooled tuning"); a fold's own held-out information ended up
                      in its own hyper-parameter.
  D4 constraints      t2n (a sensory label) was used as a constraint through a ridge proxy; trans-2-nonenal is a
                      *measured chemical column* and must carry the "do not increase" statement instead. Defect caps
                      were applied without recording whether the source value is verifiable.
  D5 statistics       the signed energy statistic U was reported as if it were a distance (clipped at 0 / square
                      rooted); diversity, duplication and edge saturation were not measured at all.
  D6 comparisons      no copy reference, no dependence-free reference, no stratified shrinkage ladder.

WHAT THIS FILE DOES INSTEAD
  * per-column state (tier / unit / observed support / floor code / reported zeros / missing cells) is recorded;
    only the 33 LINEAR_CALIBRATED columns get a physical non-negativity bound, the 37 log10 columns are NOT clipped
    at zero, and UNCALIBRATED columns are only kept inside their declared observed support;
  * `samples_raw.csv` is the conditional generation draw and `samples.csv` the constrained design; the change is
    reported per column;
  * every outer fold selects (kappa, kappa_R) with its own three inner folds only — no table is pooled across folds;
  * constraints: 3 threshold defects (hard caps), trans-2-nonenal chemical non-increase bound (NOT the t2n sensory
    proxy), stale_hops as a training-internal linear proxy (labelled as a proxy), 33 linear non-negativity;
  * V = 2 mean d(G,R) - sum d(G,G)/m^2 - sum d(R,R)/n^2 (empirical energy distance, non-negative by construction)
    and U = 2 mean d(G,R) - mean d(G,G) - mean d(R,R) (signed diagnostic: it CAN be negative; it is never clipped
    or square-rooted); marginals / dependence / diversity / nearest-neighbour / duplicate / edge statistics too;
  * comparisons on the same training rows, transform, sample count and seed: same-style training resample (copy),
    dependence-free independent marginals, and three copula shrinkage levels;
  * the sensory profile uses one declared predictor (training-internal ridge 231 -> 50), validated on the REAL
    outer-fold beers first; the profile of generated spectra is a diagnostic, never an independent validation.

Everything is deterministic: every draw comes from a numpy Generator derived from
SeedSequence([seed, tag, repeat, fold, ...]) with the frozen seeds of `src/v6_common.py`.

USAGE
    python src/q3_fix.py --repeat all      # repeats 0,1,2 in one process (default)
    python src/q3_fix.py --repeat 0        # one repeat only (samples.csv is then exactly 250 rows)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.special import ndtri

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# ------------------------------------------------------------------------------------------------- contract shim
def _contract_shim():
    """Minimal stand-in for the runner module so the FROZEN libraries import unchanged outside the runner.

    `q3_lib` imports `q_common`, which imports `modeling_contract`. Locally that module does not exist; the shim
    only satisfies the import and never writes into the ledger. When the runner provides the real module it wins.
    """
    module = types.ModuleType("modeling_contract")

    def _noop(*_args, **_kwargs):
        return None

    for name in ("seed", "emit_metrics", "emit_predictions", "emit_output", "save_figure"):
        setattr(module, name, _noop)
    module.experiment_dir = lambda: _ROOT / "state/devrun/v6/q3"
    module.project_dir = lambda: _ROOT
    module.dataset_path = lambda: _ROOT / "data/clean/q3.csv"
    module.split_paths = lambda: {}
    module.dependency_path = lambda rel: _ROOT / rel
    return module


try:  # the runner's own module wins when it is importable
    import modeling_contract as _CONTRACT

    _HAS_CONTRACT = True
except Exception:  # noqa: BLE001 - any import failure means "not inside the runner"
    _CONTRACT = _contract_shim()
    sys.modules["modeling_contract"] = _CONTRACT
    _HAS_CONTRACT = False

import v6_common as V6  # noqa: E402  (frozen protocol: seeds, splits, IO)
import q3_lib as L  # noqa: E402  (frozen numerics: marginals, copula, proxy, storage scale)
import target_columns as T  # noqa: E402  (frozen column constants)


# ------------------------------------------------------------------------------------------------- protocol
NONENAL = "X.E..2.nonenal"
KAPPAS = (0.0, 5.0, 15.0)
KAPPA_RS = (20.0, 50.0, 100.0)
THRESHOLDS = dict(L.THRESHOLD_MEAN)          # declared mean sensory thresholds (physical units)
REFERENCE_DRAWS = 20
DIVERSITY_DRAWS = 100
PROXY_EXCLUDED = tuple(L.DEFECT_KEYS) + (NONENAL,)  # a proxy shift must never undo a chemistry cap
COVERAGE_TOL = 1e-9
STALE_PROXY_MARGIN = 1e-9

LINEAR_MASK = np.array([name in L.LINEAR_SET for name in L.FEATURE_COLS])
LOG10_MASK = np.array([name in L.LOG10_SET for name in L.FEATURE_COLS])


def run_dir() -> Path:
    value = os.environ.get("MODELING_EXPERIMENT_DIR")
    path = Path(value) if value else _ROOT / "state/devrun/v6/q3"
    path.mkdir(parents=True, exist_ok=True)
    return path


_RUN_DIR = run_dir()
_OUTPUTS = {}


def emit_metrics(payload: dict) -> None:
    V6.write_json(_RUN_DIR / "metrics.json", payload)
    if _HAS_CONTRACT:
        try:
            _CONTRACT.emit_metrics(payload)
        except Exception as exc:  # noqa: BLE001 - the file above is the local record
            print("[warn] runner emit_metrics failed: %r" % (exc,))


def emit_output(name: str, value) -> None:
    _OUTPUTS[name] = value
    if _HAS_CONTRACT:
        try:
            _CONTRACT.emit_output(name, value)
        except Exception as exc:  # noqa: BLE001
            print("[warn] runner emit_output(%s) failed: %r" % (name, exc))


def flush_outputs() -> None:
    V6.write_json(_RUN_DIR / "outputs.json", {"q3": _OUTPUTS})


def finite(value, what: str) -> float:
    """A metric is a real measurement: refuse a non-finite value by name instead of shipping a silent NaN."""
    out = float(value)
    if not np.isfinite(out):
        raise ValueError("metric %r is not finite (%r): this is a defect, not a measurement" % (what, value))
    return out


def _finite_or_none(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def weighted(values, weights) -> float | None:
    total = 0.0
    num = 0.0
    for value, weight in zip(values, weights):
        if value is None or weight is None:
            continue
        value = float(value)
        weight = float(weight)
        if not np.isfinite(value) or not np.isfinite(weight) or weight <= 0:
            continue
        num += value * weight
        total += weight
    return num / total if total > 0 else None


def seed_rng(*entropy) -> np.random.Generator:
    """Deterministic Generator from an explicit entropy tuple (no hidden global RNG)."""
    return np.random.default_rng(np.random.SeedSequence([int(e) for e in entropy]))


# ------------------------------------------------------------------------------------------------- data
def load_data():
    frame = pd.read_csv(V6.DATA_Q3)
    for column in ("beer", "tasting_category_fine", "row"):
        if column not in frame.columns:
            raise RuntimeError("data/clean/q3.csv lacks the %r column" % column)
    if not frame["beer"].is_unique:
        raise RuntimeError("'beer' is not unique: row identity would be a guess")
    chem = [c for c in frame.columns if c.startswith(V6.CHEM_PREFIX)]
    if chem != L.CHEM_COLS:
        raise RuntimeError("the chem__* column order of data/clean/q3.csv differs from the frozen FEATURE_COLS")
    X = frame[L.CHEM_COLS].to_numpy(dtype=float)
    Y = frame[L.LABEL_COLS].to_numpy(dtype=float)
    if np.isnan(Y).any():
        raise RuntimeError("the 50 sensory labels contain NaN: the profile proxy would silently propagate them")
    styles = frame["tasting_category_fine"].astype(str).to_numpy()
    beers = frame["beer"].to_numpy(dtype=int)
    return frame, X, Y, styles, beers


def column_state_table(X: np.ndarray, codes: dict) -> list:
    """Per-column scale / unit / support / branch state. Nothing here is inferred beyond the declared files."""
    thresholds = json.load(open(_ROOT / "data/clean/q3_thresholds.json", encoding="utf-8"))["defects"]
    rows = []
    for j, name in enumerate(L.FEATURE_COLS):
        values = X[:, j]
        finite = values[np.isfinite(values)]
        lo = float(finite.min()) if finite.size else None
        hi = float(finite.max()) if finite.size else None
        n_missing = int((~np.isfinite(values)).sum())
        n_floor = int(np.isclose(values, codes[name], rtol=1e-6, atol=0.0).sum()) if name in codes else 0
        n_zero = int((finite == 0.0).sum()) if finite.size else 0
        if name in L.LOG10_SET:
            tier = "calibrated_log10"
            physical = [float(10.0 ** lo), float(10.0 ** hi)] if lo is not None else None
        elif name in L.LINEAR_SET:
            tier = "calibrated_linear"
            physical = [lo, hi] if lo is not None else None
        else:
            tier = "uncalibrated"
            physical = None
        unit = thresholds[name]["unit"] if name in thresholds else "not_declared"
        if name in codes and n_floor > 0:
            branch = "floor_code_atom"
        elif n_zero > 0:
            branch = "reported_zero_present"
        elif n_missing > 0:
            branch = "partially_missing"
        else:
            branch = "observed_continuous"
        rows.append({
            "column": V6.CHEM_PREFIX + name,
            "tier": tier,
            "unit": unit,
            "storage": "log10(concentration)" if name in L.LOG10_SET else
                       ("concentration" if name in L.LINEAR_SET else "as_stored_unverified"),
            "observed_storage_min": lo,
            "observed_storage_max": hi,
            "physical_range": physical,
            "n_missing_cells": n_missing,
            "n_floor_cells": n_floor,
            "n_reported_zero_cells": n_zero,
            "floor_code": float(codes[name]) if name in codes else None,
            "branch_state": branch,
            "nonnegativity_imposed": bool(name in L.LINEAR_SET),
            "support_imposed": bool(name not in L.LINEAR_SET),
            "declared_unit_source": ("data/clean/q3_thresholds.json" if name in thresholds else "not_declared"),
        })
    return rows


# ------------------------------------------------------------------------------------------------- fold context
def fit_fold_context(X_raw, Y, styles, train_idx, repeat, fold, kappa, kappa_R, with_copulas=True):
    medians = L.column_medians(X_raw[train_idx])
    X_train = L.apply_median(X_raw[train_idx], medians)
    centre, scale = L.fit_standardizer(X_train)
    codes = L.floor_code_map(X_train)
    styles_train = styles[train_idx]
    marginals = L.StyleMarginals(kappa, codes).fit(X_train, styles_train)
    proxy = L.LabelProxy(centre, scale).fit(X_train, Y[train_idx])
    # rank-gauss transform of the training rows, shared by every copula fit of this fold
    Z = np.empty_like(X_train)
    for style in sorted(set(styles_train.tolist())):
        rows = np.nonzero(styles_train == style)[0]
        U = marginals.forward(style, X_train[rows])
        Z[rows] = np.clip(ndtri(np.clip(U, 1e-9, 1.0 - 1e-9)), -8.0, 8.0)
    copulas = {}
    if with_copulas:
        for label, value in (("selected", float(kappa_R)), ("shared-only", 1e9), ("style-empirical", 0.0)):
            copulas[label] = L.GaussianCopula(value).fit(Z, styles_train)
    predicted_stale = proxy.predict_storage(X_train, L.STALE)
    predicted_t2n = proxy.predict_storage(X_train, L.T2N)
    stale_bounds, t2n_bounds, nonenal_bounds = {}, {}, {}
    nonenal_index = L.FEATURE_COLS.index(NONENAL)
    for style in sorted(set(styles_train.tolist())):
        rows = np.nonzero(styles_train == style)[0]
        stale_bounds[style] = float(np.quantile(predicted_stale[rows], 0.90))
        t2n_bounds[style] = float(np.quantile(predicted_t2n[rows], 0.90))
        nonenal_bounds[style] = float(np.quantile(X_train[rows, nonenal_index], 0.90))
    pooled = {
        "stale": float(np.quantile(predicted_stale, 0.90)),
        "t2n": float(np.quantile(predicted_t2n, 0.90)),
        "nonenal": float(np.quantile(X_train[:, nonenal_index], 0.90)),
    }
    train_lo = np.nanmin(X_train, axis=0)
    train_hi = np.nanmax(X_train, axis=0)
    for j in np.nonzero(LINEAR_MASK)[0]:
        train_lo[j] = max(train_lo[j], 0.0)
    return {
        "repeat": int(repeat), "fold": int(fold), "train_idx": np.asarray(train_idx, dtype=int),
        "medians": medians, "X_train": X_train, "centre": centre, "scale": scale, "codes": codes,
        "styles_train": styles_train, "marginals": marginals, "proxy": proxy, "Z_train": Z,
        "Z_std_train": L.standardize(X_train, centre, scale),
        "copulas": copulas, "kappa": float(kappa), "kappa_R": float(kappa_R),
        "stale_bounds": stale_bounds, "t2n_bounds": t2n_bounds, "nonenal_bounds": nonenal_bounds,
        "global_stale": pooled["stale"], "global_t2n": pooled["t2n"], "global_nonenal": pooled["nonenal"],
        "train_lo": train_lo, "train_hi": train_hi,
    }


def style_stale_bound(ctx, style: str) -> float:
    return float(ctx["stale_bounds"].get(style, ctx["global_stale"]))


def style_t2n_bound(ctx, style: str) -> float:
    return float(ctx["t2n_bounds"].get(style, ctx["global_t2n"]))


def style_nonenal_bound(ctx, style: str) -> float:
    return float(ctx["nonenal_bounds"].get(style, ctx["global_nonenal"]))


# ------------------------------------------------------------------------------------------------- generation
def generation_draws(ctx, style: str, n: int, rng: np.random.Generator) -> dict:
    """One conditional draw per generation model, all driven by the SAME standard-normal array (paired)."""
    z0 = rng.standard_normal((n, len(L.FEATURE_COLS)))
    out = {}
    for label, copula in (("copula-selected", ctx["copulas"]["selected"]),
                          ("copula-shared-only", ctx["copulas"]["shared-only"]),
                          ("copula-style-empirical", ctx["copulas"]["style-empirical"])):
        uniforms = copula.uniforms_from_normal(style, z0)
        out[label] = L.sample_from_uniforms(ctx["marginals"], style, uniforms)
    uniforms = rng.random((n, len(L.FEATURE_COLS)))  # no dependence structure at all
    out["independent-marginals"] = L.sample_from_uniforms(ctx["marginals"], style, uniforms)
    train_rows = np.nonzero(ctx["styles_train"] == style)[0]
    if train_rows.size:
        pick = rng.choice(train_rows, size=n, replace=n > train_rows.size)
        out["source-resample"] = np.array(ctx["X_train"][pick], dtype=float, copy=True)
    else:
        pick = rng.choice(ctx["X_train"].shape[0], size=n, replace=True)
        out["source-resample"] = np.array(ctx["X_train"][pick], dtype=float, copy=True)
    return out


def project_design(raw: np.ndarray, ctx: dict, style: str, max_rounds: int = 12) -> dict:
    """Constrained design spectrum: hard caps, chemical non-increase, stale proxy bound, linear non-negativity.

    The 33 LINEAR_CALIBRATED columns are capped from below at 0 (they store a concentration). The 37 log10 columns
    are never floored: a negative log10 cell is a legitimate concentration. UNCALIBRATED columns are only kept
    inside the declared observed support (not part of this projection: the marginals already live inside it).
    """
    X = np.array(raw, dtype=float, copy=True)
    defect_caps = []
    for name in L.DEFECT_KEYS:
        j = L.FEATURE_COLS.index(name)
        cap = float(np.asarray(L.storage_bound(name, THRESHOLDS[name])))
        defect_caps.append((j, cap))
    nonenal_cap = style_nonenal_bound(ctx, style)
    nonenal_index = L.FEATURE_COLS.index(NONENAL)
    raw_nonenal = np.array(X[:, nonenal_index], dtype=float, copy=True)
    stale_cap = style_stale_bound(ctx, style)
    l2 = LINEAR_MASK
    rounds = 0
    for rounds in range(1, int(max_rounds) + 1):
        for j, cap in defect_caps:
            X[:, j] = np.minimum(X[:, j], cap)
        X[:, nonenal_index] = np.minimum(np.minimum(X[:, nonenal_index], nonenal_cap), raw_nonenal)
        if ctx["proxy"] is not None:
            X = L.project_proxy_bound(X, ctx["proxy"], L.STALE, np.full(X.shape[0], stale_cap),
                                      ctx["centre"], ctx["scale"], excluded_columns=PROXY_EXCLUDED,
                                      max_rounds=1)
        X[:, l2] = np.maximum(X[:, l2], 0.0)
        violations = constraint_violations(X, ctx, style)
        if violations["max"] <= COVERAGE_TOL:
            break
    return {"design": X, "rounds": int(rounds), "violations": constraint_violations(X, ctx, style)}


def constraint_violations(X: np.ndarray, ctx: dict, style: str) -> dict:
    """Numeric violations of every declared constraint, in storage units (physical cap converted back)."""
    out = {}
    worst = 0.0
    for name in L.DEFECT_KEYS:
        j = L.FEATURE_COLS.index(name)
        cap = float(np.asarray(L.storage_bound(name, THRESHOLDS[name])))
        violation = np.maximum(X[:, j] - cap, 0.0)
        out[name] = float(violation.max()) if violation.size else 0.0
        worst = max(worst, out[name])
    j = L.FEATURE_COLS.index(NONENAL)
    violation = np.maximum(X[:, j] - style_nonenal_bound(ctx, style), 0.0)
    out[NONENAL] = float(violation.max()) if violation.size else 0.0
    worst = max(worst, out[NONENAL])
    predicted = ctx["proxy"].predict_storage(X, L.STALE)
    violation = np.maximum(predicted - style_stale_bound(ctx, style), 0.0)
    out[L.STALE] = float(violation.max()) if violation.size else 0.0
    worst = max(worst, out[L.STALE])
    negative = np.maximum(-X[:, LINEAR_MASK], 0.0)
    out["linear-nonneg"] = float(negative.max()) if negative.size else 0.0
    worst = max(worst, out["linear-nonneg"])
    out["max"] = float(worst)
    return out


def violated_rows(X: np.ndarray, ctx: dict, style: str) -> np.ndarray:
    """Boolean per row: does this row violate any declared numeric constraint (storage units)?"""
    flags = np.zeros(X.shape[0], dtype=bool)
    for name in L.DEFECT_KEYS:
        j = L.FEATURE_COLS.index(name)
        cap = float(np.asarray(L.storage_bound(name, THRESHOLDS[name])))
        flags |= X[:, j] > cap + COVERAGE_TOL
    j = L.FEATURE_COLS.index(NONENAL)
    flags |= X[:, j] > style_nonenal_bound(ctx, style) + COVERAGE_TOL
    flags |= ctx["proxy"].predict_storage(X, L.STALE) > style_stale_bound(ctx, style) + COVERAGE_TOL
    flags |= (X[:, LINEAR_MASK] < -1e-12).any(axis=1)
    return flags


def cell_satisfaction(X: np.ndarray, ctx: dict, style: str) -> float:
    """Fraction of rows of one generation cell that satisfy every declared numeric constraint."""
    return float(1.0 - np.mean(violated_rows(X, ctx, style)))


# ------------------------------------------------------------------------------------------------- statistics
def energy_statistics(gen_z: np.ndarray, real_z: np.ndarray, dref: float) -> dict:
    """V (empirical energy distance, squared) and U (signed diagnostic, NOT clipped, NOT square-rooted)."""
    m, n = int(gen_z.shape[0]), int(real_z.shape[0])
    if m == 0 or n == 0:
        return {"V": None, "U": None, "dref": float(dref), "cross": None}
    within_gen = cdist(gen_z, gen_z, metric="euclidean")
    within_real = cdist(real_z, real_z, metric="euclidean")
    cross = float(cdist(gen_z, real_z, metric="euclidean").mean())
    aa = float(within_gen.sum())
    bb = float(within_real.sum())
    V = 2.0 * cross - aa / (m * m) - bb / (n * n)
    gen_pair = aa / (m * (m - 1)) if m > 1 else float(dref)
    real_pair = bb / (n * (n - 1)) if n > 1 else float(dref)
    U = 2.0 * cross - gen_pair - real_pair
    return {"V": float(V), "U": float(U), "dref": float(dref), "cross": cross,
            "within_gen": float(gen_pair), "within_real": float(real_pair), "m": m, "n": n}


def marginal_error(gen_z: np.ndarray, real_z: np.ndarray) -> float | None:
    """Mean absolute difference of the 9 deciles, averaged over the 231 columns (standardised space)."""
    if gen_z.shape[0] == 0 or real_z.shape[0] == 0:
        return None
    grid = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    qg = np.quantile(gen_z, grid, axis=0)
    qr = np.quantile(real_z, grid, axis=0)
    return float(np.mean(np.abs(qg - qr)))


def dependence_error(gen_z: np.ndarray, real_z: np.ndarray) -> float | None:
    """Mean absolute off-diagonal difference of the two correlation matrices (standardised space)."""
    if gen_z.shape[0] < 3 or real_z.shape[0] < 3:
        return None
    cg = np.corrcoef(gen_z, rowvar=False)
    cr = np.corrcoef(real_z, rowvar=False)
    mask = ~np.eye(cg.shape[0], dtype=bool)
    value = np.abs(cg - cr)[mask].mean()
    return float(value) if np.isfinite(value) else None


def diversity_statistics(gen_z: np.ndarray, rng: np.random.Generator) -> dict:
    m = gen_z.shape[0]
    if m < 2:
        return {"diversity": None, "nearest_neighbor": None}
    take = np.arange(m) if m <= DIVERSITY_DRAWS else np.sort(rng.choice(m, size=DIVERSITY_DRAWS, replace=False))
    block = gen_z[take]
    distance = cdist(block, block, metric="euclidean")
    size = block.shape[0]
    diversity = float(distance.sum() / (size * (size - 1)))
    np.fill_diagonal(distance, np.inf)
    nearest = float(distance.min(axis=1).mean())
    return {"diversity": diversity, "nearest_neighbor": nearest}


def duplicate_share(block: np.ndarray) -> float:
    """Fraction of rows that are an exact duplicate of an earlier row (bitwise equality on all 231 stored values)."""
    if block.shape[0] < 2:
        return 0.0
    unique = np.unique(block, axis=0)
    return float(1.0 - unique.shape[0] / block.shape[0])


def edge_fraction(block: np.ndarray, ctx: dict) -> float:
    """Fraction of stored cells sitting on a declared edge: floor code, observed support min/max, or 0 (linear)."""
    hits = np.zeros(block.shape, dtype=bool)
    for j, name in enumerate(L.FEATURE_COLS):
        if name in ctx["codes"]:
            hits[:, j] |= np.isclose(block[:, j], ctx["codes"][name], rtol=1e-9, atol=0.0)
        hits[:, j] |= np.isclose(block[:, j], ctx["train_lo"][j], rtol=1e-9, atol=1e-12)
        hits[:, j] |= np.isclose(block[:, j], ctx["train_hi"][j], rtol=1e-9, atol=1e-12)
        if LINEAR_MASK[j]:
            hits[:, j] |= np.isclose(block[:, j], 0.0, rtol=0.0, atol=1e-12)
    return float(hits.mean())


def profile_metrics(proxy, gen_storage: np.ndarray, real_labels: np.ndarray) -> dict:
    gen_profile = proxy.predict_storage(gen_storage).mean(axis=0)
    real_profile = np.nanmean(real_labels, axis=0)
    rho, mae = L.profile_scores(gen_profile, real_profile)
    return {"profile_spearman": float(rho), "profile_mae": float(mae),
            "_gen_profile": gen_profile, "_real_profile": real_profile}


def spectrum_mae(gen_z: np.ndarray, real_z: np.ndarray, components: int = 20) -> float | None:
    """Mean |difference| of the top-20 normalised correlation eigenvalues (dependence fidelity, size-matched)."""
    if gen_z.shape[0] < 4 or real_z.shape[0] < 4:
        return None
    cg = np.corrcoef(gen_z, rowvar=False)
    cr = np.corrcoef(real_z, rowvar=False)
    k = int(min(components, cg.shape[0]))
    eg = np.linalg.eigvalsh(cg)[::-1][:k] / float(np.trace(cg))
    er = np.linalg.eigvalsh(cr)[::-1][:k] / float(np.trace(cr))
    value = float(np.mean(np.abs(eg - er)))
    return value if np.isfinite(value) else None


def _median_trace_ratio(rows) -> float | None:
    """Median over cells of trace(cov(gen))/trace(cov(real)); the mean is dominated by one held-out outlier."""
    ratios = [row["cov_trace_gen"] / row["cov_trace_real"] for row in rows
              if row.get("cov_trace_gen") and row.get("cov_trace_real")
              and np.isfinite(row["cov_trace_real"]) and row["cov_trace_real"] > 1e-12]
    return float(np.median(ratios)) if ratios else None


def _pooled_profile_mae(rows, weight: str = "n_gen") -> float | None:
    gen_sum = None
    real_sum = None
    total = 0.0
    for row in rows:
        w = row.get(weight)
        gen = row.get("_gen_profile")
        real = row.get("_real_profile")
        if w is None or gen is None or real is None or not np.isfinite(w) or w <= 0:
            continue
        gen_sum = w * gen if gen_sum is None else gen_sum + w * gen
        real_sum = w * real if real_sum is None else real_sum + w * real
        total += w
    if gen_sum is None or total <= 0:
        return None
    return float(np.mean(np.abs(gen_sum / total - real_sum / total)))


def pooled_profile_spearman(rows, weight: str = "n_gen") -> float | None:
    """Old-style pooled statistic: weight-average the 50-label mean profiles, then one Spearman."""
    gen_sum = None
    real_sum = None
    total = 0.0
    for row in rows:
        w = row.get(weight)
        gen = row.get("_gen_profile")
        real = row.get("_real_profile")
        if w is None or gen is None or real is None or not np.isfinite(w) or w <= 0:
            continue
        gen_sum = w * gen if gen_sum is None else gen_sum + w * gen
        real_sum = w * real if real_sum is None else real_sum + w * real
        total += w
    if gen_sum is None or total <= 0:
        return None
    rho, _ = L.profile_scores(gen_sum / total, real_sum / total)
    return float(rho)


def pooled_spectrum_mae(entries) -> float | None:
    """Pool the style blocks inside each fold's own standardised space, then weight the folds by sample count."""
    values, weights = [], []
    for key in sorted({(entry["repeat"], entry["fold"]) for entry in entries}):
        subset = [entry for entry in entries if (entry["repeat"], entry["fold"]) == key]
        gen = np.vstack([entry["gen_z"] for entry in subset])
        real = np.vstack([entry["real_z"] for entry in subset])
        value = spectrum_mae(gen, real)
        if value is not None:
            values.append(value)
            weights.append(gen.shape[0])
    return weighted(values, weights)


def block_row(*, stage, model, style, n_real, n_gen, seed, repeat, fold, ctx, gen_storage, gen_z,
              real_z, real_labels, rng) -> dict:
    d_train = _style_dtrain(ctx, style)
    estimable = (n_real >= 2 and n_gen >= 2)
    if estimable:
        style_rows = np.nonzero(ctx["styles_train"] == style)[0]
        reference = ctx["Z_std_train"][style_rows] if style_rows.size >= 2 else ctx["Z_std_train"]
        dref = L.reference_scale(reference, n_real, rng, repeats=REFERENCE_DRAWS)
        energy = energy_statistics(gen_z, real_z, dref)
    else:
        # one point does not identify a distribution: energy/marginal/dependence are NOT estimated here and the
        # cell is excluded from the pooled statistic (it is still written to the per-cell table with blanks)
        energy = {"V": None, "U": None}
        dref = float("nan")
    diversity = diversity_statistics(gen_z, rng)
    profile = profile_metrics(ctx["proxy"], gen_storage, real_labels)
    trace_gen = float(np.trace(np.cov(gen_z, rowvar=False))) if gen_z.shape[0] >= 2 else None
    trace_real = float(np.trace(np.cov(real_z, rowvar=False))) if real_z.shape[0] >= 2 else None
    row = {
        "stage": stage, "model": model, "style": style, "n_real": int(n_real), "n_gen": int(n_gen),
        "seed": int(seed), "repeat": int(repeat), "fold": int(fold),
        "E_V_raw": energy["V"], "E_V_norm": (energy["V"] / d_train) if (energy["V"] is not None and
                                                                       d_train > 1e-12) else None,
        "U_raw": energy["U"], "marginals": marginal_error(gen_z, real_z) if estimable else None,
        "dependence": dependence_error(gen_z, real_z) if estimable else None,
        "diversity": diversity["diversity"],
        "nearest_neighbor": diversity["nearest_neighbor"], "duplicate_share": duplicate_share(gen_storage),
        "edge_frac": edge_fraction(gen_storage, ctx), **profile,
        "cov_trace_gen": trace_gen, "cov_trace_real": trace_real,
        "d_train": d_train, "n_excluded_from_energy": int(0 if estimable else 1),
    }
    return row


def _style_dtrain(ctx, style: str) -> float:
    """D_train: mean pairwise distance of the style's TRAIN rows in the standardised storage space."""
    Z = ctx["Z_std_train"]
    rows = np.nonzero(ctx["styles_train"] == style)[0]
    if rows.size >= 2:
        block = Z[rows]
        return float(cdist(block, block).sum() / (rows.size * (rows.size - 1)))
    n = Z.shape[0]
    return float(cdist(Z, Z).sum() / (n * (n - 1))) if n >= 2 else 1.0


# ------------------------------------------------------------------------------------------------- audit
def _censored(block: np.ndarray, name: str, ctx: dict) -> np.ndarray:
    """Cells whose stored value is a non-detect / reported-zero code (physical value not identified)."""
    j = L.FEATURE_COLS.index(name)
    hit = np.zeros(block.shape[0], dtype=bool)
    if name in ctx["codes"]:
        hit |= np.isclose(block[:, j], ctx["codes"][name], rtol=1e-6, atol=0.0)
    if LINEAR_MASK[j]:
        hit |= np.isclose(block[:, j], 0.0, rtol=0.0, atol=1e-12)
    return hit


def audit_block(raw: np.ndarray, design: np.ndarray, ctx: dict, style: str, sample_ids, repeat, fold,
                state_by_name: dict) -> list:
    """One record per (sample, declared constraint field): verdict verified/conditional/not_identifiable/infeasible."""
    records = []
    n = raw.shape[0]
    for name in L.DEFECT_KEYS:
        j = L.FEATURE_COLS.index(name)
        cap_phys = float(THRESHOLDS[name])
        cap_stored = float(np.asarray(L.storage_bound(name, cap_phys)))
        before = raw[:, j]
        after = design[:, j]
        conc_before = L.physical_conc(name, before, ctx["codes"])
        conc_after = L.physical_conc(name, after, ctx["codes"])
        residual = np.maximum(after - cap_stored, 0.0)
        censored = _censored(design, name, ctx)
        unit = state_by_name[name]["unit"]
        partial = state_by_name[name]["n_missing_cells"] > 0
        for k in range(n):
            if residual[k] > 1e-9:
                verdict = "infeasible"
            elif censored[k]:
                verdict = "not_identifiable"
            elif partial:
                verdict = "conditional"
            else:
                verdict = "verified"
            records.append({
                "sample_id": sample_ids[k], "repeat": int(repeat), "fold": int(fold), "style": style,
                "field": V6.CHEM_PREFIX + name, "unit": unit, "bound_type": "upper_threshold",
                "bound_value": cap_phys, "stored_bound": cap_stored,
                "source_state": "declared_mean_threshold" + (";column_has_missing_cells" if partial else ""),
                "stored_before": float(before[k]), "stored_after": float(after[k]),
                "conc_before": float(conc_before[k]), "conc_after": float(conc_after[k]),
                "residual": float(residual[k]), "verdict": verdict,
            })
    # chemical non-increase of trans-2-nonenal (a real measured column, not the t2n sensory proxy)
    j = L.FEATURE_COLS.index(NONENAL)
    bound = style_nonenal_bound(ctx, style)
    residual = np.maximum(design[:, j] - bound, 0.0)
    censored = _censored(design, NONENAL, ctx)
    for k in range(n):
        verdict = ("infeasible" if residual[k] > 1e-9 else
                   ("not_identifiable" if censored[k] else "conditional"))
        records.append({
            "sample_id": sample_ids[k], "repeat": int(repeat), "fold": int(fold), "style": style,
            "field": V6.CHEM_PREFIX + NONENAL, "unit": state_by_name[NONENAL]["unit"],
            "bound_type": "upper_training_q90_chemical", "bound_value": float(bound),
            "stored_bound": float(bound),
            "source_state": ("training_q90_of_the_chemical_column (data-derived, conditional); the design is also "
                             "<= the raw draw of that sample (chemical non-increase)"),
            "stored_before": float(raw[k, j]), "stored_after": float(design[k, j]),
            "conc_before": float(raw[k, j]), "conc_after": float(design[k, j]),
            "residual": float(residual[k]), "verdict": verdict,
        })
    # stale_hops: training-internal linear ridge proxy (declared as a proxy, not a chemical measurement)
    bound = style_stale_bound(ctx, style)
    before = ctx["proxy"].predict_storage(raw, L.STALE)
    after = ctx["proxy"].predict_storage(design, L.STALE)
    residual = np.maximum(after - bound, 0.0)
    for k in range(n):
        verdict = "infeasible" if residual[k] > 1e-9 else "conditional"
        records.append({
            "sample_id": sample_ids[k], "repeat": int(repeat), "fold": int(fold), "style": style,
            "field": "stale_hops(ridge-proxy)", "unit": "ridge-proxy score (sensory label units)",
            "bound_type": "upper_training_q90_proxy", "bound_value": float(bound),
            "stored_bound": float(bound),
            "source_state": "linear-ridge-proxy trained inside this fold: PROXY, not a chemical measurement",
            "stored_before": float(before[k]), "stored_after": float(after[k]),
            "conc_before": None, "conc_after": None,
            "residual": float(residual[k]), "verdict": verdict,
        })
    # 33 LINEAR_CALIBRATED non-negativity
    for j in np.nonzero(LINEAR_MASK)[0]:
        name = L.FEATURE_COLS[j]
        residual = np.maximum(-design[:, j], 0.0)
        censored = _censored(design, name, ctx)
        partial = state_by_name[name]["n_missing_cells"] > 0
        for k in range(n):
            if residual[k] > 1e-12:
                verdict = "infeasible"
            elif censored[k]:
                verdict = "not_identifiable"
            elif partial:
                verdict = "conditional"
            else:
                verdict = "verified"
            records.append({
                "sample_id": sample_ids[k], "repeat": int(repeat), "fold": int(fold), "style": style,
                "field": V6.CHEM_PREFIX + name,
                "unit": state_by_name[name]["unit"],
                "bound_type": "lower_zero", "bound_value": 0.0, "stored_bound": 0.0,
                "source_state": ("calibrated_linear_concentration"
                                 + (";column_has_missing_cells" if partial else "")),
                "stored_before": float(raw[k, j]), "stored_after": float(design[k, j]),
                "conc_before": float(raw[k, j]), "conc_after": float(design[k, j]),
                "residual": float(residual[k]), "verdict": verdict,
            })
    return records


# ------------------------------------------------------------------------------------------------- tuning
def select_hyperparameters_inner(X_raw, styles, train_idx, beer_index, splits, repeat, fold, seed):
    """(kappa, kappa_R) selected with this outer fold's OWN three inner folds; nothing is pooled across folds."""
    tables = []
    inner_sizes = []
    # the frozen helper needs the outer-train beer ids, which the caller passes in
    for inner, inner_train, inner_valid in V6.iter_inner(repeat, fold, beer_index["train_beers"], splits):
        itr = np.array([beer_index["index_of"][int(b)] for b in inner_train], dtype=int)
        iva = np.array([beer_index["index_of"][int(b)] for b in inner_valid], dtype=int)
        medians = L.column_medians(X_raw[itr])
        Xtr = L.apply_median(X_raw[itr], medians)
        Xva = L.apply_median(X_raw[iva], medians)
        centre, scale = L.fit_standardizer(Xtr)
        Zva = L.standardize(Xva, centre, scale)
        Ztr = L.standardize(Xtr, centre, scale)
        codes = L.floor_code_map(Xtr)
        s_tr, s_va = styles[itr], styles[iva]
        rng = seed_rng(seed, 3, repeat, fold, inner)
        marginals = {}
        zblocks = {}
        for kappa in KAPPAS:
            marginal = L.StyleMarginals(kappa, codes).fit(Xtr, s_tr)
            marginals[kappa] = marginal
            Zc = np.empty_like(Xtr)
            for style in sorted(set(s_tr.tolist())):
                rows = np.nonzero(s_tr == style)[0]
                U = marginal.forward(style, Xtr[rows])
                Zc[rows] = np.clip(ndtri(np.clip(U, 1e-9, 1.0 - 1e-9)), -8.0, 8.0)
            zblocks[kappa] = Zc
        scores = {}
        for kappa in KAPPAS:
            marginal = marginals[kappa]
            for kappa_R in KAPPA_RS:
                copula = L.GaussianCopula(kappa_R).fit(zblocks[kappa], s_tr)
                num, den = 0.0, 0
                for style in sorted(set(s_va.tolist())):
                    rows = np.nonzero(s_va == style)[0]
                    n = int(rows.size)
                    if n == 0:
                        continue
                    z0 = rng.standard_normal((n, len(L.FEATURE_COLS)))
                    U = copula.uniforms_from_normal(style, z0)
                    gen = L.sample_from_uniforms(marginal, style, U)
                    gen_z = L.standardize(gen, centre, scale)
                    tr_rows = np.nonzero(s_tr == style)[0]
                    dref = L.reference_scale(Ztr[tr_rows] if tr_rows.size >= 2 else Ztr, n, rng,
                                             repeats=REFERENCE_DRAWS)
                    value, _ = L.normalized_energy_distance(gen_z, Zva[rows], dref)
                    num += float(value) * n
                    den += n
                scores[(float(kappa), float(kappa_R))] = float(num / max(den, 1))
        tables.append(scores)
        inner_sizes.append(int(len(iva)))
    keys = sorted({key for table in tables for key in table})
    mean_table = {key: float(np.mean([table[key] for table in tables if key in table])) for key in keys}
    # ties break towards the stronger shrinkage, exactly like the frozen selection rule
    best = min(mean_table, key=lambda key: (mean_table[key], -key[0], -key[1]))
    return float(best[0]), float(best[1]), mean_table, tables, inner_sizes


# ------------------------------------------------------------------------------------------------- main
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Q3 corrected generator (v5.1 §三)")
    parser.add_argument("--repeat", default="all", help="0, 1, 2 or 'all' (default)")
    return parser.parse_args(argv)


def resolve_repeats(token: str) -> list:
    token = str(token).strip().lower()
    if token in ("all", ""):
        return [0, 1, 2]
    value = int(token)
    if value not in (0, 1, 2):
        raise SystemExit("--repeat must be 0, 1, 2 or 'all', got %r" % token)
    return [value]


def main(argv=None):
    args = parse_args(argv)
    repeats = resolve_repeats(args.repeat)
    started = time.time()
    _OUTPUTS.clear()

    frame, X_raw, Y, styles, beers = load_data()
    splits = V6.load_splits()
    index_of = {int(beer): i for i, beer in enumerate(beers)}
    all_beers = np.asarray(beers, dtype=int)
    codes_all = L.floor_code_map(L.apply_median(X_raw, L.column_medians(X_raw)))
    state_rows = column_state_table(X_raw, codes_all)
    state_by_name = {row["column"].replace(V6.CHEM_PREFIX, ""): row for row in state_rows}

    fingerprints = {
        "data_q3_sha256": V6.sha256_file(V6.DATA_Q3),
        "splits_sha256": V6.sha256_file(V6.SPLITS_CSV),
        "splits_manifest_sha256": V6.sha256_file(V6.SPLITS_MANIFEST) if V6.SPLITS_MANIFEST.exists() else None,
        "style_protocol_sha256": V6.sha256_file(_ROOT / "data/clean/q3_style_protocol.json"),
        "thresholds_sha256": V6.sha256_file(_ROOT / "data/clean/q3_thresholds.json"),
        "q3_lib_sha256": V6.sha256_file(_HERE / "q3_lib.py"),
        "v6_common_sha256": V6.sha256_file(_HERE / "v6_common.py"),
        "target_columns_sha256": V6.sha256_file(_HERE / "target_columns.py"),
    }

    floor_code_stability = []
    for name in list(L.DEFECT_KEYS) + [NONENAL]:
        j = L.FEATURE_COLS.index(name)
        present = []
        for repeat in repeats:
            for fold in range(V6.N_OUTER):
                for rep, f, train_beers, test_beers in V6.iter_outer(splits):
                    if rep == repeat and f == fold:
                        break
                train_idx = np.array([index_of[int(b)] for b in train_beers], dtype=int)
                codes = L.floor_code_map(L.apply_median(X_raw[train_idx], L.column_medians(X_raw[train_idx])))
                present.append(float(codes[name]) if name in codes else None)
        unique = sorted({value for value in present if value is not None})
        floor_code_stability.append({
            "column": V6.CHEM_PREFIX + name,
            "codesPerFoldAndRepeat": present,
            "detectedInEveryFold": bool(all(value is not None for value in present)),
            "detectedInNoFold": bool(all(value is None for value in present)),
            "distinctCodes": unique,
            "stable": bool(len(unique) <= 1),
        })

    tuning_rows = []
    metric_rows = []
    sample_records = []
    raw_records = []
    audit_records = []
    per_repeat = []
    contexts = {}
    problem_notes = []
    raw_design_change = []
    profile_validation = []
    cell_energy = []          # (repeat, stage, model, n_gen, energy dict, style) for pooling
    projection_rounds = []    # how many cap/shift passes the design projection needed per cell
    repeat_t2n_increases = {}  # per repeat: rows whose t2n proxy moved up through the design projection
    ceiling_rows = []         # predictor-on-real-rows profile cells (the honest ceiling for the same statistic)
    block_store = []          # per (repeat, fold, stage, model, style) blocks for pooled dependence/profile
    constraint_counts = {"verified": 0, "conditional": 0, "not_identifiable": 0, "infeasible": 0}
    linear_index = np.nonzero(LINEAR_MASK)[0]
    nonenal_index = L.FEATURE_COLS.index(NONENAL)

    for repeat in repeats:
        seed = int(V6.SEEDS[repeat])
        repeat_rows = []
        repeat_energy = []
        n_neg_raw = n_neg_design = t2n_increases = 0
        repeat_t2n_increases[int(repeat)] = 0
        t2n_delta_sum = 0.0
        t2n_delta_max = 0.0
        t2n_delta_positive = 0
        n_samples_repeat = 0
        for fold in range(V6.N_OUTER):
            train_beers, test_beers = None, None
            for rep, f, train_beers, test_beers in V6.iter_outer(splits):
                if rep == repeat and f == fold:
                    break
            train_idx = np.array([index_of[int(b)] for b in train_beers], dtype=int)
            test_idx = np.array([index_of[int(b)] for b in test_beers], dtype=int)
            beer_index = {"index_of": index_of, "train_beers": train_beers}
            kappa, kappa_R, mean_table, inner_tables, inner_sizes = select_hyperparameters_inner(
                X_raw, styles, train_idx, beer_index, splits, repeat, fold, seed)
            tuning_rows.append({
                "repeat": int(repeat), "fold": int(fold), "kappa": float(kappa), "kappa_R": float(kappa_R),
                "innerFolds": int(len(inner_tables)), "innerSizes": inner_sizes,
                "rule": ("this outer fold's three inner folds averaged into one 3x3 table, argmin, "
                         "ties -> stronger shrinkage; no cross-fold pooling"),
                "gridScores": {"kappa=%.6g|kappa_R=%.6g" % key: value for key, value in mean_table.items()},
                "innerTables": [{"kappa=%.6g|kappa_R=%.6g" % key: value for key, value in table.items()}
                                for table in inner_tables],
            })
            ctx = fit_fold_context(X_raw, Y, styles, train_idx, repeat, fold, kappa, kappa_R)
            contexts[(repeat, fold)] = ctx
            # ---- profile predictor validated on the REAL outer-fold beers first
            X_test = L.apply_median(X_raw[test_idx], ctx["medians"])
            predicted = ctx["proxy"].predict_storage(X_test)
            truth = Y[test_idx]
            abs_error = np.abs(predicted - truth)
            per_target = {name: float(np.nanmean(abs_error[:, t])) for t, name in enumerate(L.LABEL_COLS)}
            gen_prof = predicted.mean(axis=0)
            real_prof = np.nanmean(truth, axis=0)
            rho_all, mae_all = L.profile_scores(gen_prof, real_prof)
            profile_validation.append({
                "repeat": int(repeat), "fold": int(fold), "rows": int(len(test_idx)),
                "mae50": float(np.nanmean(abs_error)), "maeAF30": float(np.nanmean(abs_error[:, :30])),
                "meanProfileSpearman": float(rho_all), "meanProfileMAE": float(mae_all),
                "worstTargets": sorted(per_target.items(), key=lambda item: -item[1])[:5],
                "proxyCvR2": {"t2n": float(ctx["proxy"].cv_r2[L.T2N]),
                              "stale_hops": float(ctx["proxy"].cv_r2[L.STALE])},
            })
            X_test_predicted = predicted  # proxy prediction on the REAL held-out rows (fold level, kept for pooling)
            # ---- per-style generation cells
            style_order = sorted(set(styles[test_idx].tolist()))
            for style_slot, style in enumerate(style_order):
                rows = np.nonzero(styles[test_idx] == style)[0]
                n = int(rows.size)
                if n == 0:
                    continue
                test_rows = test_idx[rows]
                real_labels = Y[test_rows]
                test_row_positions = np.nonzero(np.isin(test_idx, test_rows))[0]
                ceiling_rows.append({"n_gen": n, "_gen_profile": X_test_predicted[test_row_positions].mean(axis=0),
                                     "_real_profile": np.nanmean(real_labels, axis=0)})
                real_z = L.standardize(L.apply_median(X_raw[test_rows], ctx["medians"]),
                                       ctx["centre"], ctx["scale"])
                rng = seed_rng(seed, 21, repeat, fold, style_slot)
                raw_blocks = generation_draws(ctx, style, n, rng)
                audit_raw = raw_blocks["copula-selected"]
                sample_ids = ["R%d-F%d-N%04d" % (repeat, fold, n_samples_repeat + k) for k in range(n)]
                n_samples_repeat += n
                # raw linear negatives / design linear negatives / t2n increases (base model only)
                n_neg_raw += int(np.sum(raw_blocks["copula-selected"][:, linear_index] < -1e-12))
                raw_t2n = ctx["proxy"].predict_storage(raw_blocks["copula-selected"], L.T2N)
                for model_index, (model, raw) in enumerate(raw_blocks.items()):
                    projection = project_design(raw, ctx, style)
                    if model == "copula-selected":
                        projection_rounds.append(int(projection["rounds"]))
                    design = projection["design"]
                    design_t2n = ctx["proxy"].predict_storage(design, L.T2N)
                    if model == "copula-selected":
                        n_neg_design += int(np.sum(design[:, linear_index] < -1e-12))
                        delta_t2n = design_t2n - raw_t2n
                        positive = delta_t2n > 1e-9
                        n_t2n_increase = int(np.sum(positive))
                        t2n_increases += n_t2n_increase
                        repeat_t2n_increases[int(repeat)] += n_t2n_increase
                        t2n_delta_positive += int(np.sum(positive))
                        if positive.any():
                            t2n_delta_sum += float(np.sum(delta_t2n[positive]))
                            t2n_delta_max = max(t2n_delta_max, float(np.max(delta_t2n[positive])))
                    for stage_index, (stage, block) in enumerate((("raw", raw), ("design", design))):
                        gen_z = L.standardize(block, ctx["centre"], ctx["scale"])
                        row = block_row(stage=stage, model=model, style=style, n_real=n, n_gen=n, seed=seed,
                                        repeat=repeat, fold=fold, ctx=ctx, gen_storage=block, gen_z=gen_z,
                                        real_z=real_z, real_labels=real_labels,
                                        rng=seed_rng(seed, 31, repeat, fold, style_slot, model_index * 2 + stage_index))
                        row["_satisfied"] = cell_satisfaction(block, ctx, style)
                        row["t2n_increase_count"] = (n_t2n_increase if (model == "copula-selected"
                                                                        and stage == "design") else None)
                        metric_rows.append(row)
                        block_store.append({"repeat": int(repeat), "fold": int(fold), "stage": stage,
                                            "model": model, "style": style, "n": int(n),
                                            "gen_z": gen_z, "real_z": real_z,
                                            "gen_profile": row["_gen_profile"],
                                            "real_profile": row["_real_profile"]})
                        if model == "copula-selected":
                            cell_energy.append({"repeat": repeat, "stage": stage, "style": style,
                                                "n": n, "row": row})
                    if model == "copula-selected":
                        audit_records.extend(audit_block(audit_raw, design, ctx, style, sample_ids, repeat,
                                                         fold, state_by_name))
                        for k in range(n):
                            base = {"sample_id": sample_ids[k], "style": style, "seed": seed,
                                    "repeat": int(repeat), "model_id": "copula-selected", "fold": int(fold)}
                            sample_records.append({**base, **{col: float(design[k, j])
                                                              for j, col in enumerate(L.CHEM_COLS)}})
                            raw_records.append({**base, **{col: float(audit_raw[k, j])
                                                           for j, col in enumerate(L.CHEM_COLS)}})
                        # change report, per column, for the raw -> design move
                        delta = design - audit_raw
                        for j, name in enumerate(L.FEATURE_COLS):
                            raw_design_change.append({
                                "repeat": int(repeat), "fold": int(fold), "style": style,
                                "column": V6.CHEM_PREFIX + name,
                                "mean_abs_change_storage": float(np.mean(np.abs(delta[:, j]))),
                                "mean_abs_change_std": float(np.mean(np.abs(delta[:, j])) / ctx["scale"][j]),
                                "max_abs_change_storage": float(np.max(np.abs(delta[:, j]))),
                                "n_changed": int(np.sum(np.abs(delta[:, j]) > 1e-12)),
                            })
        per_repeat.append({"repeat": int(repeat), "seed": seed, "n_samples": n_samples_repeat})

    # --------------------------------------------------------------------------------- pooled metrics
    design_rows = [row for row in metric_rows if row["stage"] == "design"]
    raw_rows = [row for row in metric_rows if row["stage"] == "raw"]
    base_design = [row for row in design_rows if row["model"] == "copula-selected"]
    base_raw = [row for row in raw_rows if row["model"] == "copula-selected"]

    def pool(rows, key, weight="n_gen"):
        return weighted([row.get(key) for row in rows], [row.get(weight) for row in rows])

    per_repeat_metrics = []
    for repeat in repeats:
        records = [cell for cell in cell_energy if cell["repeat"] == repeat]
        design_rec = [cell["row"] for cell in records if cell["stage"] == "design"]
        raw_rec = [cell["row"] for cell in records if cell["stage"] == "raw"]
        entry = {
            "repeat": int(repeat), "seed": int(V6.SEEDS[repeat]),
            "n_samples": int(per_repeat[[p["repeat"] for p in per_repeat].index(repeat)]["n_samples"]),
            "constraint-satisfaction": pool(design_rec, "_satisfied"),
            "energy-distance": pool(design_rec, "E_V_norm"),
            "energy-V-raw": pool(design_rec, "E_V_raw"),
            "energy-U": pool(design_rec, "U_raw"),
            "energy-distance-raw": pool(raw_rec, "E_V_norm"),
            "diversity": pool(design_rec, "diversity"),
            "duplicate-share": pool(design_rec, "duplicate_share"),
            "profile-mae": pool(design_rec, "profile_mae"),
            "profile-spearman": pool(design_rec, "profile_spearman"),
            "t2n-increases": int(repeat_t2n_increases.get(repeat, 0)),
            "profile-pooled-spearman": pooled_profile_spearman(design_rec),
            "dependence-spectrum-mae": pooled_spectrum_mae(
                [entry for entry in block_store if entry["repeat"] == repeat
                 and entry["model"] == "copula-selected" and entry["stage"] == "design"]),
        }
        per_repeat_metrics.append(entry)

    # --------------------------------------------------------------------------------- write sample tables
    sample_frame = pd.DataFrame(sample_records)
    order = ["sample_id", "style", "seed", "repeat", "model_id", "fold"]
    sample_frame = sample_frame[[c for c in order if c in sample_frame.columns] +
                                [c for c in L.CHEM_COLS]].copy()
    raw_frame = pd.DataFrame(raw_records)[["sample_id", "style", "seed", "repeat", "model_id", "fold"] +
                                          list(L.CHEM_COLS)]
    sample_csv = _RUN_DIR / "samples.csv"
    raw_csv = _RUN_DIR / "samples_raw.csv"
    sample_frame.to_csv(sample_csv, index=False, lineterminator="\n")
    raw_frame.to_csv(raw_csv, index=False, lineterminator="\n")
    # with --repeat all the pooled files hold 250 * n_repeats rows; the per-repeat view is written too so the
    # declared "250 design spectra per repeat" is directly checkable
    for repeat in repeats:
        sample_frame[sample_frame["repeat"] == repeat].to_csv(
            _RUN_DIR / ("samples-repeat-%d.csv" % repeat), index=False, lineterminator="\n")
        raw_frame[raw_frame["repeat"] == repeat].to_csv(
            _RUN_DIR / ("samples_raw-repeat-%d.csv" % repeat), index=False, lineterminator="\n")

    # recount constraints from the WRITTEN csv (no trust in memory)
    written = pd.read_csv(sample_csv)
    written_raw = pd.read_csv(raw_csv)
    if written.shape[0] != sample_frame.shape[0]:
        raise RuntimeError("samples.csv round-trip changed the row count")
    design_matrix = written[L.CHEM_COLS].to_numpy(dtype=float)
    raw_matrix = written_raw[L.CHEM_COLS].to_numpy(dtype=float)
    # per-row recount from the WRITTEN csv, grouped by (repeat, fold, style)
    row_ok = np.zeros(written.shape[0], dtype=bool)
    grouped = written.groupby(["repeat", "fold", "style"], sort=True).indices
    for (repeat, fold, style), positions in grouped.items():
        ctx = contexts[(int(repeat), int(fold))]
        block = design_matrix[np.asarray(positions, dtype=int)]
        row_ok[np.asarray(positions, dtype=int)] = violated_rows(block, ctx, str(style)) == 0
    satisfaction_from_csv = float(row_ok.mean())
    raw_negatives = int(np.sum(raw_matrix[:, LINEAR_MASK] < -1e-12))
    design_negatives = int(np.sum(design_matrix[:, LINEAR_MASK] < -1e-12))
    # the per-repeat figure comes from the written csv (single source of truth); the in-memory value is kept
    # alongside so a disagreement between memory and disk is visible instead of silent
    for entry in per_repeat_metrics:
        mask = written["repeat"].to_numpy() == entry["repeat"]
        entry["constraint-satisfaction-from-memory"] = entry["constraint-satisfaction"]
        entry["constraint-satisfaction"] = float(row_ok[mask].mean())
        if abs(entry["constraint-satisfaction"] - entry["constraint-satisfaction-from-memory"]) > 1e-9:
            raise RuntimeError("per-repeat constraint satisfaction disagrees between memory and samples.csv")

    # the raw stage is unconstrained by construction: its satisfaction is reported, never hidden
    raw_ok = np.zeros(written_raw.shape[0], dtype=bool)
    grouped_raw = written_raw.groupby(["repeat", "fold", "style"], sort=True).indices
    for (repeat, fold, style), positions in grouped_raw.items():
        ctx = contexts[(int(repeat), int(fold))]
        block = raw_matrix[np.asarray(positions, dtype=int)]
        raw_ok[np.asarray(positions, dtype=int)] = violated_rows(block, ctx, str(style)) == 0
    satisfaction_raw = float(raw_ok.mean())

    for record in audit_records:
        constraint_counts[record["verdict"]] += 1

    # t2n increases (design vs raw, base model), from the written files
    t2n_increases = 0
    t2n_above_bound = 0
    for (repeat, fold, style), positions in grouped.items():
        ctx = contexts[(int(repeat), int(fold))]
        block_d = design_matrix[np.asarray(positions, dtype=int)]
        block_r = raw_matrix[np.asarray(positions, dtype=int)]
        t2n_d = ctx["proxy"].predict_storage(block_d, L.T2N)
        t2n_r = ctx["proxy"].predict_storage(block_r, L.T2N)
        t2n_increases += int(np.sum(t2n_d > t2n_r + 1e-9))
        t2n_above_bound += int(np.sum(t2n_d > style_t2n_bound(ctx, str(style)) + 1e-9))

    metrics = {
        "constraint-satisfaction": finite(satisfaction_from_csv, "constraint-satisfaction"),
        "constraint-satisfaction-raw": finite(satisfaction_raw, "constraint-satisfaction-raw"),
        "constraint-records-verified-share": finite(
            constraint_counts["verified"] / max(sum(constraint_counts.values()), 1),
            "constraint-records-verified-share"),
        "energy-distance": finite(pool(base_design, "E_V_norm"), "energy-distance"),
        "energy-distance-raw": finite(pool(base_raw, "E_V_norm"), "energy-distance-raw"),
        "energy-V-raw": finite(pool(base_design, "E_V_raw"), "energy-V-raw"),
        "energy-U-signed": finite(pool(base_design, "U_raw"), "energy-U-signed"),
        "diversity": finite(pool(base_design, "diversity"), "diversity"),
        "duplicate-share": finite(pool(base_design, "duplicate_share"), "duplicate-share"),
        "nearest-neighbor": finite(pool(base_design, "nearest_neighbor"), "nearest-neighbor"),
        "edge-fraction": finite(pool(base_design, "edge_frac"), "edge-fraction"),
        "marginal-error": finite(pool(base_design, "marginals"), "marginal-error"),
        "dependence-error": finite(pool(base_design, "dependence"), "dependence-error"),
        "dependence-spectrum-mae": finite(pooled_spectrum_mae(
            [entry for entry in block_store if entry["model"] == "copula-selected"
             and entry["stage"] == "design"]), "dependence-spectrum-mae"),
        "covariance-trace-ratio": finite(_median_trace_ratio(base_design), "covariance-trace-ratio"),
        "profile-pooled-spearman": finite(pooled_profile_spearman(base_design), "profile-pooled-spearman"),
        "t2n-increase-mean": finite(t2n_delta_sum / max(t2n_delta_positive, 1), "t2n-increase-mean"),
        "t2n-increase-max": finite(t2n_delta_max, "t2n-increase-max"),
        "n-cells-excluded-from-energy": int(sum(row.get("n_excluded_from_energy", 0) for row in base_design)),
        "n-cells": int(len(base_design)),
        "profile-mae": finite(pool(base_design, "profile_mae"), "profile-mae"),
        "profile-spearman": finite(pool(base_design, "profile_spearman"), "profile-spearman"),
        "n-linear-negative-raw": int(raw_negatives),
        "n-linear-negative-design": int(design_negatives),
        "t2n-increases": int(t2n_increases),
        "t2n-above-style-bound": int(t2n_above_bound),
        "constraints-verified": int(constraint_counts["verified"]),
        "constraints-conditional": int(constraint_counts["conditional"]),
        "constraints-not-identifiable": int(constraint_counts["not_identifiable"]),
        "constraints-infeasible": int(constraint_counts["infeasible"]),
        "n-samples": int(written.shape[0]),
        "n-repeats": int(len(repeats)),
        "duplicate_share": float(pool(base_design, "duplicate_share")),
        "constraints_verified": int(constraint_counts["verified"]),
        "constraints_conditional": int(constraint_counts["conditional"]),
        "constraints_not_identifiable": int(constraint_counts["not_identifiable"]),
        "constraints_infeasible": int(constraint_counts["infeasible"]),
        "n-linear-negative_raw": int(raw_negatives),
        "n-linear-negative_design": int(design_negatives),
        "t2n_increases": int(t2n_increases),
    }
    # per-repeat as independent keys too (never a pooled number pretending to be a single run)
    for entry in per_repeat_metrics:
        for key in ("constraint-satisfaction", "energy-distance", "diversity", "duplicate-share"):
            value = entry.get(key)
            if value is not None:
                metrics["%s-repeat%d" % (key, entry["repeat"])] = finite(value, key)

    # --------------------------------------------------------------------------------- tables on disk
    metric_frame = pd.DataFrame(metric_rows, columns=[
        "stage", "model", "style", "n_real", "n_gen", "seed", "E_V_raw", "E_V_norm", "U_raw", "marginals",
        "dependence", "diversity", "nearest_neighbor", "duplicate_share", "edge_frac", "profile_mae",
        "profile_spearman", "repeat", "fold", "cov_trace_gen", "cov_trace_real", "d_train",
        "n_excluded_from_energy", "t2n_increase_count"])
    metric_frame.to_csv(_RUN_DIR / "q3_metrics.csv", index=False, lineterminator="\n")
    audit_frame = pd.DataFrame(audit_records)
    audit_columns = ["sample_id", "field", "unit", "bound_type", "bound_value", "source_state",
                     "stored_before", "stored_after", "residual", "verdict",
                     "repeat", "fold", "style", "stored_bound", "conc_before", "conc_after"]
    audit_frame = audit_frame[audit_columns]
    audit_frame.to_csv(_RUN_DIR / "constraints.csv", index=False, lineterminator="\n")

    # --------------------------------------------------------------------------------- comparisons
    comparison_models = ["copula-selected", "copula-shared-only", "copula-style-empirical",
                         "independent-marginals", "source-resample"]
    comparisons = {}
    for model in comparison_models:
        rows_d = [row for row in design_rows if row["model"] == model]
        rows_r = [row for row in raw_rows if row["model"] == model]
        comparisons[model] = {
            "nCells": int(len(rows_d)),
            "design": {
                "energy-distance": pool(rows_d, "E_V_norm"),
                "energy-V": pool(rows_d, "E_V_raw"),
                "energy-U": pool(rows_d, "U_raw"),
                "marginal-error": pool(rows_d, "marginals"),
                "dependence-error": pool(rows_d, "dependence"),
                "diversity": pool(rows_d, "diversity"),
                "duplicate-share": pool(rows_d, "duplicate_share"),
                "nearest-neighbor": pool(rows_d, "nearest_neighbor"),
                "edge-fraction": pool(rows_d, "edge_frac"),
                "profile-mae": pool(rows_d, "profile_mae"),
                "profile-spearman": pool(rows_d, "profile_spearman"),
            },
            "pooled": {
                "dependence-spectrum-mae": pooled_spectrum_mae(
                    [entry for entry in block_store if entry["model"] == model and entry["stage"] == "design"]),
                "profile-pooled-spearman": pooled_profile_spearman(rows_d),
            },
            "raw": {
                "energy-distance": pool(rows_r, "E_V_norm"),
                "energy-V": pool(rows_r, "E_V_raw"),
                "energy-U": pool(rows_r, "U_raw"),
                "dependence-error": pool(rows_r, "dependence"),
                "duplicate-share": pool(rows_r, "duplicate_share"),
            },
        }

    # change magnitude raw -> design
    change_frame = pd.DataFrame(raw_design_change)
    change_summary = {
        "mean_abs_change_std_all_columns": float(change_frame["mean_abs_change_std"].mean()),
        "top_changed_columns": (change_frame.groupby("column")["mean_abs_change_std"].mean()
                                .sort_values(ascending=False).head(10).to_dict()),
    }

    # --------------------------------------------------------------------------------- outputs
    emit_output("protocol", {
        "seeds": [int(V6.SEEDS[r]) for r in repeats],
        "allSeeds": [int(s) for s in V6.SEEDS],
        "repeats": [int(r) for r in repeats],
        "nOuterFolds": int(V6.N_OUTER),
        "nInnerFolds": int(V6.N_INNER),
        "splits": str(V6.SPLITS_CSV),
        "splitFingerprints": fingerprints,
        "kappaGrid": [float(k) for k in KAPPAS],
        "kappaRGrid": [float(k) for k in KAPPA_RS],
        "storageScale": {"log10_calibrated": int(LOG10_MASK.sum()), "linear_calibrated": int(LINEAR_MASK.sum()),
                         "uncalibrated": int(len(L.FEATURE_COLS) - LOG10_MASK.sum() - LINEAR_MASK.sum())},
        "floorCodeStability": floor_code_stability,
        "designColumns": 231,
        "derivedFeatures": ("NOT rebuilt: this run uses the 231 stored chemical columns only; the 226+5 "
                            "derived-column identities are explicitly unverified in this run"),
    })
    emit_output("per_fold_tuning", tuning_rows)
    emit_output("per_repeat", per_repeat_metrics)
    emit_output("model_contract_bounds", [
        {"column": V6.CHEM_PREFIX + name, "min": 0.0} for name in L.FEATURE_COLS if name in L.LINEAR_SET
    ])
    emit_output("comparisons", comparisons)
    emit_output("column_state", state_rows)
    emit_output("raw_design_change", change_summary)
    emit_output("design_projection", {
        "method": ("fast exact projection, not an optimiser: hard storage caps for the three threshold defects, the "
                   "chemical q90 cap plus the raw-draw non-increase for trans-2-nonenal, the minimal-norm linear "
                   "stale_hops proxy shift (chemistry columns excluded so a proxy shift cannot undo a cap), and the "
                   "linear non-negativity clamp; iterated until the maximum residual is <= 1e-9"),
        "why": ("per column the projection is closed form and the only coupled row is the stale_hops proxy, so the "
                "declared constraint set admits an exact projection; the residual is then recounted from the written "
                "samples.csv instead of being trusted from memory"),
        "maxRoundsAllowed": 12,
        "maxResidualFromAudit": float(audit_frame.residual.max()),
        "constraintSatisfactionFromCsv": satisfaction_from_csv,
        "infeasibleRecords": int(constraint_counts["infeasible"]),
    })
    emit_output("projection_rounds", {
        "cells": int(len(projection_rounds)),
        "max": int(max(projection_rounds)) if projection_rounds else 0,
        "mean": float(np.mean(projection_rounds)) if projection_rounds else 0.0,
        "convergedWithin12": bool(all(r < 12 for r in projection_rounds)),
    })
    profile_validation.append({
        "repeat": None, "fold": None, "rows": None,
        "note": ("pooled predictor ceiling for the SAME statistic used on generated cells: the proxy is applied to "
                 "the REAL held-out rows of each (fold, style) cell, then the 50-label mean profiles are "
                 "weight-averaged and correlated"),
        "meanProfileSpearman": pooled_profile_spearman(ceiling_rows),
        "meanProfileMAE": _pooled_profile_mae(ceiling_rows),
    })
    emit_output("profile_predictor_validation", profile_validation)
    emit_output("constraint_definitions", {
        "thresholdSet": "mean (data/clean/q3_thresholds.json)",
        "defects": {name: float(THRESHOLDS[name]) for name in L.DEFECT_KEYS},
        "chemicalNonIncrease": {"column": V6.CHEM_PREFIX + NONENAL,
                                "bound": "q90 of the chemical column on this fold's TRAIN rows of the style",
                                "why": ("trans-2-nonenal is the measured oxidation compound behind t2n; the t2n "
                                        "sensory label is NOT used as a constraint (it is a model proxy)")},
        "staleHops": {"bound": "q90 of the linear ridge proxy on TRAIN rows of the style",
                      "state": "PROXY constraint, not a chemical measurement"},
        "t2n": {"use": "signed diagnostic only", "bound": "q90 of the proxy on TRAIN rows of the style"},
        "linearNonNegativity": {"columns": int(LINEAR_MASK.sum()), "bound": 0.0},
        "uncalibratedColumns": ("kept inside the observed training support only; no physical assumption imposed"),
        "floorHandling": ("declared floor codes and reported zeros are censored values: the audit marks them "
                          "not_identifiable instead of a physical pass"),
        "energyDistanceV": ("V = 2*mean d(G,R) - sum d(G,G)/m^2 - sum d(R,R)/n^2 on the fold-standardised "
                            "storage matrix; E_V_norm = V / D_train with D_train the mean pairwise distance of "
                            "the style's TRAIN rows"),
        "energyDistanceU": ("U = 2*mean d(G,R) - mean d(G,G) - mean d(R,R): a SIGNED diagnostic, can be "
                            "negative, never clipped and never square-rooted"),
        "duplicateShare": "fraction of rows that are exact duplicates of an earlier row of the same block",
        "edgeFraction": "fraction of cells on a declared edge (floor code / observed support min or max / 0)",
        "density": "the 231 columns are the stored chemical table; no GAN or diffusion model is used",
    })
    emit_output("notes", [
        "D1 fixed: only the 33 LINEAR_CALIBRATED columns are floored at 0; the 37 log10 columns are not clipped.",
        "D2 fixed: samples_raw.csv (conditional draw) and samples.csv (constrained design) are both written.",
        "D3 fixed: each outer fold selects (kappa, kappa_R) with its own inner folds; see per_fold_tuning.",
        "D4 fixed: t2n is no longer a constraint; trans-2-nonenal (chemical) carries the non-increase statement.",
        "D5 fixed: U is reported signed; diversity / duplicates / edges / marginals / dependence are measured.",
        "D6 fixed: copy reference, dependence-free reference and a three-level copula shrinkage ladder are compared.",
        "The sensory profile is a ridge-proxy diagnostic validated on REAL outer-fold beers; the profile of "
        "generated spectra is never an independent sensory validation.",
        "Floor-coded and reported-zero cells are censored values; the audit reports them as not_identifiable.",
        "This run uses the 231 stored columns; the 226+5 derived-feature identities are NOT verified here.",
    ])
    emit_output("metrics_omitted", {})
    emit_output("run_timing", {"seconds": float(time.time() - started), "repeatToken": str(args.repeat)})
    flush_outputs()

    # per-seed run receipts (declared by the lead)
    for entry in per_repeat_metrics:
        payload = {
            "seed": entry["seed"], "repeat": entry["repeat"], "n_samples": entry["n_samples"],
            "constraint-satisfaction": entry["constraint-satisfaction"],
            "energy-distance": entry["energy-distance"],
            "energy-V-raw": entry["energy-V-raw"], "energy-U": entry["energy-U"],
            "diversity": entry["diversity"], "duplicate-share": entry["duplicate-share"],
            "profile-mae": entry["profile-mae"], "profile-spearman": entry["profile-spearman"],
            "t2n-increases": entry.get("t2n-increases"),
            "n-linear-negative-design": metrics.get("n-linear-negative-design"),
        }
        V6.write_json(_RUN_DIR / ("run-seed-%d.json" % entry["seed"]), payload)

    emit_metrics(metrics)
    elapsed = time.time() - started
    print("[q3_fix] repeats=%s rows=%d elapsed=%.1fs" % (repeats, written.shape[0], elapsed))
    for key in ("constraint-satisfaction", "constraint-satisfaction-raw", "energy-distance", "energy-V-raw",
                "energy-U-signed", "diversity", "duplicate-share", "n-linear-negative-raw",
                "n-linear-negative-design", "t2n-increases", "profile-mae", "profile-spearman"):
        print("  %-28s %s" % (key, metrics.get(key)))
    print("  constraints verified/conditional/not_identifiable/infeasible: %d/%d/%d/%d" % (
        metrics["constraints-verified"], metrics["constraints-conditional"],
        metrics["constraints-not-identifiable"], metrics["constraints-infeasible"]))
    return metrics


if __name__ == "__main__":
    main()
