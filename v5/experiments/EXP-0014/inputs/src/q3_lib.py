"""q3_lib.py — Q3 toolkit: storage scale, hybrid marginals, Gaussian copula, defect constraints,
energy distance and cross-style transfer.

WHY THIS FILE EXISTS. The Q3 question asks for a generator over the 231-dim chemical space that (a) reproduces a
style's chemical profile, (b) can be pushed below sensory defect thresholds, and (c) can transfer a foreign beer
towards a target style without worsening its defects. Every one of those pieces must be reproducible from a seed and
the frozen data, so the numerics live here and the two experiment scripts (`q3_baseline.py`, `q3_generate.py`) only
orchestrate and call `modeling_contract`.

CONVENTIONS THAT MATTER
  · Storage scale. `chem__*` columns are *as stored in 1.csv*: LOG10_CALIBRATED columns store log10(concentration),
    LINEAR_CALIBRATED store the concentration, the rest are unverified and kept as stored. Physical concentration is
    therefore 10**x for the log10 tier and x otherwise. A "floor" cell is a non-detect code and maps to 0.
  · Floor codes. The 142 declared FLOOR_COLUMNS cells use the global FLOOR_VALUE (-1.81781854). Five more log10
    columns (X4VG, CS2, octyl_acetate, ethyl_2.methyl_butyrate, ethyl_isovalerate) and CO2 show a repeated minimum
    that is their detection limit; treating that repeated minimum as an atom is the same right-censoring logic and is
    documented in the outputs. X4VG's code is -2.013157381, *not* FLOOR_VALUE (the thresholds file only lists the
    global code); both readings put the floor concentration at or below the 4VG threshold.
  · Determinism. No hidden RNG: every sampler takes an explicit numpy Generator; every pair of runs with the same
    seed therefore reproduces the same numbers.
"""

import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial.distance import cdist
from scipy.special import ndtr, ndtri
from scipy.stats import spearmanr

import q_common
from target_columns import (
    DEFECT_COLUMNS,
    DEFECT_DISPLAY,
    FEATURE_COLS,
    FLOOR_COLUMNS,
    FLOOR_VALUE,
    LINEAR_CALIBRATED,
    LOG10_CALIBRATED,
    MISSING_COLUMNS,
    N_FEATURES,
    STYLE_COLUMN,
    TARGET_COLS,
    UNCALIBRATED,
)

CHEM_PREFIX = "chem__"
CHEM_COLS = [CHEM_PREFIX + name for name in FEATURE_COLS]
LABEL_COLS = list(TARGET_COLS)
LOG10_SET = set(LOG10_CALIBRATED)
LINEAR_SET = set(LINEAR_CALIBRATED)
FLOOR_SET = set(FLOOR_COLUMNS)

# thresholds from data/clean/q3_thresholds.json (mean and median sensory threshold per defect, physical units)
THRESHOLD_MEAN = {"DMS": 17.25, "X2.3.butanedione": 0.29925, "X4VG": 0.206333333}
THRESHOLD_MEDIAN = {"DMS": 19.0, "X2.3.butanedione": 0.09, "X4VG": 0.2}
DEFECT_KEYS = ("DMS", "X2.3.butanedione", "X4VG")
T2N = "t2n"
STALE = "stale_hops"
PROXY_TARGETS = (T2N, STALE)

# floor-code detection: a repeated column minimum is a detection limit
FLOOR_MIN_REPEATS = 20
# numerical safety margin for proxy-imposed bounds; a CSV round-trip must not flip a satisfied constraint
PROXY_MARGIN = 1e-6


# ------------------------------------------------------------------------------------------------ inputs
def load_thresholds():
    """Thresholds + storage rules, straight from the registered dependency (never re-typed by hand)."""
    return q_common.read_dependency_json("data/clean/q3_thresholds.json")


def load_protocol():
    return q_common.read_dependency_json("data/clean/q3_style_protocol.json")


def load_frame():
    frame = q_common.load_dataset()
    missing = [c for c in CHEM_COLS + LABEL_COLS if c not in frame.columns]
    if missing:
        raise RuntimeError("dataset is missing columns: %s" % missing[:5])
    return frame


def prepare(frame: pd.DataFrame) -> dict:
    """Storage-scale matrix + style labels + row ids + sensory labels. NaNs are kept here on purpose."""
    X = frame[CHEM_COLS].to_numpy(dtype=float)
    return {
        "X": X,
        "styles": frame[STYLE_COLUMN].astype(str).to_numpy(),
        "rows": frame["row"].to_numpy(dtype=int),
        "Y": frame[LABEL_COLS].to_numpy(dtype=float),
        "n": X.shape[0],
    }


def fold_of_row(protocol: dict, rows) -> np.ndarray:
    """The registered within-style 3-fold assignment, keyed by the real (0-based) row id."""
    mapping = {int(k): int(v) for k, v in protocol["foldByRow"].items()}
    return np.array([mapping[int(r)] for r in np.asarray(rows)], dtype=int)


# ------------------------------------------------------------------------------------------------ imputation / scaling
def column_medians(X: np.ndarray) -> np.ndarray:
    med = np.nanmedian(X, axis=0)
    return np.where(np.isfinite(med), med, 0.0)


def apply_median(X: np.ndarray, med: np.ndarray) -> np.ndarray:
    out = np.array(X, dtype=float, copy=True)
    bad = ~np.isfinite(out)
    if bad.any():
        rows, cols = np.nonzero(bad)
        out[rows, cols] = med[cols]
    return out


def fit_standardizer(X: np.ndarray) -> tuple:
    centre = X.mean(axis=0)
    scale = X.std(axis=0)
    scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1.0)
    return centre, scale


def standardize(X: np.ndarray, centre: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (np.asarray(X, dtype=float) - centre) / scale


# ------------------------------------------------------------------------------------------------ storage scale
def floor_code_map(X: np.ndarray, min_repeats: int = FLOOR_MIN_REPEATS) -> dict:
    """column name -> non-detect code. Declared floor columns use FLOOR_VALUE; detected repeated minima are added."""
    X = np.asarray(X, dtype=float)
    codes = {}
    for j, name in enumerate(FEATURE_COLS):
        values = X[:, j]
        values = values[np.isfinite(values)]
        if values.size == 0:
            continue
        if name in FLOOR_SET:
            codes[name] = float(FLOOR_VALUE)
            continue
        if name in LOG10_SET:
            low = float(values.min())
            repeats = int(np.sum(np.isclose(values, low, rtol=1e-6, atol=0.0)))
            if repeats >= int(min_repeats):
                codes[name] = low
    return codes


def floor_mask(X: np.ndarray, codes: dict) -> np.ndarray:
    """Boolean (n, 231) mask of non-detect cells."""
    mask = np.zeros(np.shape(X), dtype=bool)
    for j, name in enumerate(FEATURE_COLS):
        if name in codes:
            mask[:, j] = np.isclose(X[:, j], codes[name], rtol=1e-6, atol=0.0)
    return mask


def physical_conc(column: str, storage, codes: dict = None):
    """Physical concentration of a stored value; a non-detect cell counts as 0."""
    values = np.asarray(storage, dtype=float)
    if column in LOG10_SET:
        out = np.power(10.0, values)
    elif column in LINEAR_SET:
        out = values.copy()
    else:
        out = values.copy()
    if codes and column in codes:
        out = np.where(np.isclose(values, codes[column], rtol=1e-6, atol=0.0), 0.0, out)
    return out


def storage_bound(column: str, physical_bound):
    """Inverse of physical_conc for a cap (no floor handling: a cap is never inside the non-detect region here)."""
    if column in LOG10_SET:
        return np.log10(np.maximum(np.asarray(physical_bound, dtype=float), 1e-300))
    return np.asarray(physical_bound, dtype=float)


# ------------------------------------------------------------------------------------------------ constraints
def constraint_arrays(X: np.ndarray, t2n_bound, proxy, codes: dict, thresholds: dict) -> dict:
    """The four declared constraints on a storage-scale sample matrix.

    excess__<defect> = max(c / T - 1, 0) with c the physical concentration (non-detect -> 0);
    t2n_margin       = upper bound - predicted t2n (a real value close to 1 means "at the bound").
    """
    X = np.asarray(X, dtype=float)
    out = {}
    for name in DEFECT_KEYS:
        j = FEATURE_COLS.index(name)
        conc = physical_conc(name, X[:, j], codes)
        bound = float(thresholds[name])
        out["excess__" + name] = np.maximum(conc / bound - 1.0, 0.0)
    pred = proxy.predict_storage(X, T2N)
    out["t2n_margin"] = np.asarray(t2n_bound, dtype=float) - pred
    return out


def constraint_satisfied(parts: dict) -> np.ndarray:
    ok = np.ones(np.asarray(parts["t2n_margin"]).shape[0], dtype=bool)
    for name in DEFECT_KEYS:
        ok &= np.asarray(parts["excess__" + name]) <= 0.0
    ok &= np.asarray(parts["t2n_margin"]) >= 0.0
    return ok


def defect_exceeded(parts: dict) -> np.ndarray:
    bad = np.zeros(np.asarray(parts["t2n_margin"]).shape[0], dtype=bool)
    for name in DEFECT_KEYS:
        bad |= np.asarray(parts["excess__" + name]) > 0.0
    return bad


def project_thresholds(X: np.ndarray, physical_caps: dict, codes: dict) -> np.ndarray:
    """Hard projection of the three threshold defects: cap the *stored* value at the physical cap."""
    out = np.array(X, dtype=float, copy=True)
    for name, cap in physical_caps.items():
        j = FEATURE_COLS.index(name)
        out[:, j] = np.minimum(out[:, j], float(np.asarray(storage_bound(name, cap))))
    return out


def project_proxy_bound(X: np.ndarray, proxy, target: str, bounds, centre, scale,
                        excluded_columns=(), max_rounds: int = 4) -> np.ndarray:
    """Minimal-norm (in standardised space) row-wise shift that puts a linear label proxy at/below its bound.

    `excluded_columns` are held fixed (the three threshold defects), so pushing t2n down can never push a chemical
    defect back over its cap. The proxy is linear, so the shift lands exactly on the bound.
    """
    X = np.array(X, dtype=float, copy=True)
    bounds = np.broadcast_to(np.asarray(bounds, dtype=float), (X.shape[0],)).copy() - PROXY_MARGIN
    weight = np.array(proxy.coef_for(target), dtype=float)
    intercept = float(proxy.intercept_for(target))
    excl = np.zeros(len(FEATURE_COLS), dtype=bool)
    for name in excluded_columns:
        excl[FEATURE_COLS.index(name)] = True
    direction = np.where(excl, 0.0, weight)
    norm_sq = float(np.sum(direction * direction))
    if norm_sq <= 1e-18:
        return X
    for _ in range(int(max_rounds)):
        Z = standardize(X, centre, scale)
        pred = Z @ weight + intercept
        gap = pred - bounds
        active = gap > 1e-12
        if not active.any():
            break
        delta = gap[active] / norm_sq
        X[active, :] -= delta[:, None] * (scale * direction)[None, :]
    return X


def project_transfer_feasible(problem, v: np.ndarray, t2n_caps: np.ndarray, stale_caps: np.ndarray,
                              rounds: int = 6) -> np.ndarray:
    """Feasibility projection in the [0,1] transfer coordinates: box caps for chemistry, linear shifts for proxies."""
    out = np.clip(np.array(v, dtype=float, copy=True), 0.0, 1.0)
    for _ in range(int(rounds)):
        out = np.clip(out, 0.0, problem.v_upper)
        out = problem.shift_along_proxy(out, STALE, stale_caps)
        out = problem.shift_along_proxy(out, T2N, t2n_caps)
        out = np.clip(out, 0.0, problem.v_upper)
        if problem.proxy_ok(out, t2n_caps, stale_caps):
            break
    return out


# ------------------------------------------------------------------------------------------------ label proxy
class LabelProxy:
    """Ridge map 231 chemical features -> 50 sensory labels, used only as a *proxy* for constraints / profiles.

    Alpha per target is selected by 5-fold CV inside the training rows (rows are visited in their given order, so the
    folds are deterministic). The closed form is solved once per alpha group; no stochastic solver is involved.
    """

    def __init__(self, centre, scale, alphas=(0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0), folds: int = 5):
        self.centre = np.asarray(centre, dtype=float)
        self.scale = np.asarray(scale, dtype=float)
        self.alphas = tuple(float(a) for a in alphas)
        self.folds = int(folds)
        self.alpha = {}
        self.coef = None
        self.intercept = None
        self.cv_r2 = {}

    # -- internals
    def _design(self, X):
        return standardize(np.asarray(X, dtype=float), self.centre, self.scale)

    @staticmethod
    def _ridge_fit(Z, y, alpha):
        zm = Z.mean(axis=0)
        ym = float(np.mean(y))
        Zc = Z - zm
        gram = Zc.T @ Zc
        rhs = Zc.T @ (y - ym)
        coef = np.linalg.solve(gram + float(alpha) * np.eye(gram.shape[0]), rhs)
        intercept = ym - float(zm @ coef)
        return coef, intercept

    def fit(self, X, Y):
        Z = self._design(X)
        Y = np.asarray(Y, dtype=float)
        n = Z.shape[0]
        order = np.arange(n)
        blocks = np.array_split(order, self.folds)
        # per-fold gram matrices are shared by every alpha and every target
        grams, rhss, means = [], [], []
        for block in blocks:
            keep = np.ones(n, dtype=bool)
            keep[block] = False
            Zt = Z[keep]
            Yt = Y[keep]
            zm = Zt.mean(axis=0)
            ym = Yt.mean(axis=0)
            Zc = Zt - zm
            grams.append(Zc.T @ Zc)
            rhss.append(Zc.T @ (Yt - ym))
            means.append((zm, ym))
        identity = np.eye(Z.shape[1])
        best = np.full(Y.shape[1], -np.inf)
        chosen = np.ones(Y.shape[1], dtype=float) * self.alphas[0]
        for alpha in self.alphas:
            pred = np.zeros_like(Y)
            for k, block in enumerate(blocks):
                zm, ym = means[k]
                coefs = np.linalg.solve(grams[k] + alpha * identity, rhss[k])  # (231, 50)
                pred[block] = (Z[block] - zm) @ coefs + ym
            resid = np.sum((Y - pred) ** 2, axis=0)
            total = np.sum((Y - Y.mean(axis=0)) ** 2, axis=0)
            with np.errstate(divide="ignore", invalid="ignore"):
                r2 = 1.0 - resid / np.where(total > 1e-12, total, np.inf)
            better = r2 > best
            best = np.where(better, r2, best)
            chosen = np.where(better, alpha, chosen)
        self.alpha = {name: float(chosen[j]) for j, name in enumerate(LABEL_COLS)}
        self.cv_r2 = {name: float(best[j]) for j, name in enumerate(LABEL_COLS)}
        coef = np.zeros((Y.shape[1], Z.shape[1]), dtype=float)
        intercept = np.zeros(Y.shape[1], dtype=float)
        for alpha in sorted(set(float(a) for a in chosen)):
            targets = [j for j in range(Y.shape[1]) if float(chosen[j]) == alpha]
            zm = Z.mean(axis=0)
            Zc = Z - zm
            ym = Y[:, targets].mean(axis=0)
            gram = Zc.T @ Zc
            rhs = Zc.T @ (Y[:, targets] - ym)
            block = np.linalg.solve(gram + alpha * identity, rhs)
            coef[targets, :] = block.T
            intercept[targets] = ym - zm @ block
        self.coef = coef
        self.intercept = intercept
        return self

    # -- prediction
    def predict_z(self, Z):
        return np.asarray(Z, dtype=float) @ self.coef.T + self.intercept

    def predict_storage(self, X, target: str = None):
        pred = self.predict_z(self._design(X))
        if target is None:
            return pred
        return pred[:, LABEL_COLS.index(target)]

    def coef_for(self, target: str):
        return self.coef[LABEL_COLS.index(target)]

    def intercept_for(self, target: str):
        return float(self.intercept[LABEL_COLS.index(target)])

    def refit_with_alphas(self, X, Y):
        """Refit with the already selected alphas (bootstrap resampling keeps the selected penalty)."""
        Z = self._design(X)
        Y = np.asarray(Y, dtype=float)
        identity = np.eye(Z.shape[1])
        coef = np.zeros((Y.shape[1], Z.shape[1]), dtype=float)
        intercept = np.zeros(Y.shape[1], dtype=float)
        zm = Z.mean(axis=0)
        Zc = Z - zm
        gram = Zc.T @ Zc
        for alpha in sorted(set(self.alpha.values())):
            targets = [j for j in range(Y.shape[1]) if float(self.alpha[LABEL_COLS[j]]) == alpha]
            ym = Y[:, targets].mean(axis=0)
            rhs = Zc.T @ (Y[:, targets] - ym)
            block = np.linalg.solve(gram + alpha * identity, rhs)
            coef[targets, :] = block.T
            intercept[targets] = ym - zm @ block
        clone = LabelProxy(self.centre, self.scale, alphas=self.alphas, folds=self.folds)
        clone.alpha = dict(self.alpha)
        clone.cv_r2 = dict(self.cv_r2)
        clone.coef = coef
        clone.intercept = intercept
        return clone


# ------------------------------------------------------------------------------------------------ marginals
class Marginal:
    """A monotone mixture CDF: omega * F_style + (1 - omega) * F_pool, with a floor atom.

    `grid_x` are the pooled support points, `grid_u` the mixture CDF value *including* the floor mass. Inversion is
    piecewise-linear on the sorted support (the "sorted samples + quantile interpolation" contract), which keeps the
    map monotone and bounded by the observed training range (no extrapolation blow-up in 231 dimensions).
    """

    __slots__ = ("grid_x", "grid_u", "pi", "floor_code", "has_floor")

    def __init__(self, grid_x, grid_u, pi, floor_code):
        self.grid_x = grid_x
        self.grid_u = grid_u
        self.pi = float(pi)
        self.floor_code = None if floor_code is None else float(floor_code)
        self.has_floor = self.floor_code is not None

    def forward(self, x):
        x = np.asarray(x, dtype=float)
        u = np.interp(x, self.grid_x, self.grid_u, left=self.grid_u[0], right=self.grid_u[-1])
        if self.has_floor:
            hit = np.isclose(x, self.floor_code, rtol=1e-6, atol=0.0)
            if hit.any():
                u = np.where(hit, 0.5 * self.pi, u)
        return u

    def inverse(self, u):
        u = np.asarray(u, dtype=float)
        t = np.clip((u - self.pi) / max(1.0 - self.pi, 1e-12), 0.0, 1.0)
        base = (self.grid_u - self.pi) / max(1.0 - self.pi, 1e-12)
        x = np.interp(t, base, self.grid_x, left=self.grid_x[0], right=self.grid_x[-1])
        if self.has_floor:
            x = np.where(u <= self.pi, self.floor_code, x)
        return x


def _midrank_cdf(sorted_values, grid):
    below = np.searchsorted(sorted_values, grid, side="left")
    equal = np.searchsorted(sorted_values, grid, side="right") - below
    return (below + 0.5 * equal) / float(sorted_values.size)


def build_marginal(cont_style, cont_pool, pi_style, pi_pool, omega, floor_code, eps=1e-9):
    cont_style = np.sort(np.asarray(cont_style, dtype=float))
    cont_pool = np.sort(np.asarray(cont_pool, dtype=float))
    if cont_style.size == 0:
        cont_style = cont_pool
    if cont_pool.size == 0:
        cont_pool = cont_style
    if cont_style.size == 0:
        cont_style = np.array([0.0])
        cont_pool = np.array([0.0])
    grid = np.union1d(cont_style, cont_pool)
    u_style = _midrank_cdf(cont_style, grid)
    u_pool = _midrank_cdf(cont_pool, grid)
    u = float(omega) * u_style + (1.0 - float(omega)) * u_pool
    pi = float(np.clip(float(omega) * float(pi_style) + (1.0 - float(omega)) * float(pi_pool), 0.0, 1.0 - 1e-6))
    u = pi + (1.0 - pi) * u
    # strictly increasing: cumulative max + a negligible rank ramp to break exact ties
    u = np.maximum.accumulate(u)
    ramp = np.arange(grid.size, dtype=float) * 1e-12
    u = np.minimum(u + ramp, 1.0 - eps)
    u = np.maximum.accumulate(u)
    u = np.clip(u, pi + 1e-12, 1.0 - eps)
    return Marginal(grid, u, pi, floor_code)


class StyleMarginals:
    """Per-style hybrid marginals F_{j,s} = omega_s F_emp_{j,s} + (1 - omega_s) F_pool_j, omega_s = n_s/(n_s+kappa).

    Floor-coded variables are a two-part mixture: the atom carries mass pi_floor, the continuous part samples the
    non-floor sub-sample. Styles absent from the training rows fall back to the pooled marginal.
    """

    def __init__(self, kappa: float, codes: dict, eps: float = 1e-9, drop_floor_atoms: bool = False):
        self.kappa = float(kappa)
        self.codes = dict(codes)
        self.eps = float(eps)
        self.drop_floor_atoms = bool(drop_floor_atoms)
        self.styles = []
        self.marg = {}
        self.pool = {}

    def fit(self, X: np.ndarray, styles) -> "StyleMarginals":
        X = np.asarray(X, dtype=float)
        styles = np.asarray(styles)
        self.styles = sorted(set(str(s) for s in styles))
        mask = floor_mask(X, self.codes)
        finite = np.isfinite(X)
        # pooled pieces per column
        pool_cont = {}
        pool_pi = {}
        for j, name in enumerate(FEATURE_COLS):
            keep = finite[:, j] & ~mask[:, j]
            values = X[keep, j]
            pool_cont[name] = np.sort(values)
            n_kept = int(keep.sum())
            n_floor = 0 if self.drop_floor_atoms else int(mask[:, j].sum())
            pool_pi[name] = float(n_floor / max(n_kept + n_floor, 1))
            code = None if self.drop_floor_atoms else self.codes.get(name, None)
            self.pool[name] = build_marginal(values, values, pool_pi[name], pool_pi[name], 1.0, code, self.eps)
        for style in self.styles:
            rows = np.nonzero(styles == style)[0]
            n_s = rows.size
            omega = n_s / (n_s + self.kappa) if n_s + self.kappa > 0 else 1.0
            style_margs = []
            for j, name in enumerate(FEATURE_COLS):
                column = X[rows, j]
                ok = np.isfinite(column)
                hit = mask[rows, j]
                cont = np.sort(column[ok & ~hit])
                n_kept = int((ok & ~hit).sum())
                n_floor = 0 if self.drop_floor_atoms else int(hit.sum())
                pi_style = float(n_floor / max(n_kept + n_floor, 1))
                code = None if self.drop_floor_atoms else self.codes.get(name, None)
                style_margs.append(build_marginal(cont, pool_cont[name], pi_style, pool_pi[name],
                                                  omega, code, self.eps))
            self.marg[style] = style_margs
        return self

    def _marginals(self, style):
        return self.marg.get(str(style), None)

    def forward(self, style: str, X: np.ndarray) -> np.ndarray:
        """Storage values -> probability integral transform u in (0, 1)."""
        X = np.asarray(X, dtype=float)
        margs = self._marginals(style)
        U = np.empty_like(X)
        for j, name in enumerate(FEATURE_COLS):
            marginal = margs[j] if margs is not None else self.pool[name]
            U[:, j] = marginal.forward(X[:, j])
        return U

    def inverse(self, style: str, U: np.ndarray) -> np.ndarray:
        """Probability integral transform u -> storage values (bounded by the observed support)."""
        U = np.asarray(U, dtype=float)
        margs = self._marginals(style)
        X = np.empty_like(U)
        for j, name in enumerate(FEATURE_COLS):
            marginal = margs[j] if margs is not None else self.pool[name]
            X[:, j] = marginal.inverse(U[:, j])
        return X


class GaussianCopula:
    """Style-conditional Gaussian copula with a shared backbone.

    R_s = eta_s R_s^emp + (1 - eta_s) R_shared, eta_s = n_s/(n_s + kappa_R); eigenvalues are floored at 1e-6,
    the matrix is renormalised to unit diagonal and finally shrunk 5% towards the identity for a stable Cholesky.
    """

    def __init__(self, kappa_R: float, shrink: float = 0.05, eig_floor: float = 1e-6):
        self.kappa_R = float(kappa_R)
        self.shrink = float(shrink)
        self.eig_floor = float(eig_floor)
        self.shared = None
        self.factor = {}
        self.corr = {}

    @staticmethod
    def _correlation(Z):
        Z = np.asarray(Z, dtype=float)
        n = Z.shape[0]
        if n < 3:
            return np.eye(Z.shape[1])
        centre = Z - Z.mean(axis=0, keepdims=True)
        scale = centre.std(axis=0)
        scale = np.where(scale > 1e-12, scale, 1.0)
        W = centre / scale
        return (W.T @ W) / float(n - 1)

    def _spd(self, R):
        R = np.asarray(R, dtype=float)
        R = 0.5 * (R + R.T)
        values, vectors = np.linalg.eigh(R)
        values = np.maximum(values, self.eig_floor)
        R = (vectors * values) @ vectors.T
        diag = np.sqrt(np.clip(np.diag(R), 1e-18, None))
        R = R / np.outer(diag, diag)
        R = (1.0 - self.shrink) * R + self.shrink * np.eye(R.shape[0])
        values, vectors = np.linalg.eigh(R)
        values = np.maximum(values, self.eig_floor)
        R = (vectors * values) @ vectors.T
        diag = np.sqrt(np.clip(np.diag(R), 1e-18, None))
        return R / np.outer(diag, diag)

    @staticmethod
    def _cholesky(R):
        try:
            return np.linalg.cholesky(R)
        except np.linalg.LinAlgError:
            for jitter in (1e-10, 1e-8, 1e-6, 1e-4, 1e-2):
                try:
                    return np.linalg.cholesky(R + jitter * np.eye(R.shape[0]))
                except np.linalg.LinAlgError:
                    continue
        raise RuntimeError("copula correlation matrix is not positive definite even after jitter")

    def fit(self, Z: np.ndarray, styles) -> "GaussianCopula":
        Z = np.asarray(Z, dtype=float)
        styles = np.asarray(styles)
        shared = self._spd(self._correlation(Z))
        self.shared = shared
        self.factor = {}
        for style in sorted(set(str(s) for s in styles)):
            rows = np.nonzero(styles == style)[0]
            n_s = rows.size
            eta = n_s / (n_s + self.kappa_R) if n_s + self.kappa_R > 0 else 1.0
            empirical = self._correlation(Z[rows]) if n_s >= 4 else shared
            R = eta * empirical + (1.0 - eta) * shared
            R = self._spd(R)
            self.corr[str(style)] = R
            self.factor[str(style)] = self._cholesky(R)
        return self

    def uniforms_from_normal(self, style: str, z: np.ndarray) -> np.ndarray:
        """Correlate standard normal draws with the style factor, then map to uniforms."""
        factor = self.factor.get(str(style), self._cholesky(self.shared))
        return ndtr(np.asarray(z, dtype=float) @ factor.T)

    def uniforms(self, style: str, n: int, rng) -> np.ndarray:
        z = rng.standard_normal((int(n), self.shared.shape[0]))
        return self.uniforms_from_normal(style, z)


def sample_from_uniforms(marginals: StyleMarginals, style: str, U: np.ndarray) -> np.ndarray:
    return marginals.inverse(style, U)


# ------------------------------------------------------------------------------------------------ energy distance
def mean_pairwise_distance(A: np.ndarray) -> float:
    A = np.asarray(A, dtype=float)
    n = A.shape[0]
    if n < 2:
        return 0.0
    D = cdist(A, A, metric="euclidean")
    return float(D.sum() / (n * (n - 1)))


def energy_distance_sq(gen: np.ndarray, real: np.ndarray, within_fallback: float = None) -> float:
    """Energy distance squared; `within_fallback` replaces an unestimable within-block term.

    A style can leave a single held-out row (14 of the 22 styles have fewer than 4 rows), and one point does not
    identify its own pairwise distance. In that case the expected same-style pairwise distance D_ref is used for the
    missing within-block term, which is the natural plug-in and removes the 1-sample artefact.
    """
    gen = np.asarray(gen, dtype=float)
    real = np.asarray(real, dtype=float)
    if gen.shape[0] == 0 or real.shape[0] == 0:
        return 0.0
    cross = float(cdist(gen, real, metric="euclidean").mean())
    within_gen = mean_pairwise_distance(gen)
    within_real = mean_pairwise_distance(real)
    if within_fallback is not None:
        if gen.shape[0] < 2:
            within_gen = float(within_fallback)
        if real.shape[0] < 2:
            within_real = float(within_fallback)
    return float(2.0 * cross - within_gen - within_real)


def normalized_energy_distance(gen, real, dref) -> tuple:
    e2 = energy_distance_sq(gen, real, within_fallback=dref)
    dref = float(dref)
    if not np.isfinite(dref) or dref <= 1e-12:
        return 0.0, e2
    return float(np.sqrt(max(e2, 0.0) / dref)), e2


def reference_scale(X_style_train: np.ndarray, n_holdout: int, rng, repeats: int = 20) -> float:
    """D_ref: mean pairwise distance of same-style *real* training samples at the held-out sample size."""
    X = np.asarray(X_style_train, dtype=float)
    n_train = X.shape[0]
    if n_train < 2:
        return 0.0
    if n_holdout < 2:
        return mean_pairwise_distance(X)
    size = int(min(n_holdout, n_train))
    values = []
    for _ in range(int(repeats)):
        idx = rng.choice(n_train, size=size, replace=False)
        values.append(mean_pairwise_distance(X[idx]))
    return float(np.mean(values))


def real_reference_energy(real: np.ndarray, dref: float, rng, draws: int = 20) -> float:
    """Real-vs-real null: two independent bootstrap draws of the held-out sample size."""
    real = np.asarray(real, dtype=float)
    n = real.shape[0]
    if n == 0:
        return 0.0
    values = []
    for _ in range(int(draws)):
        a = real[rng.integers(0, n, size=n)]
        b = real[rng.integers(0, n, size=n)]
        value, _ = normalized_energy_distance(a, b, dref)
        values.append(value)
    return float(np.mean(values))


# ------------------------------------------------------------------------------------------------ profile metrics
def profile_vector(proxy: LabelProxy, X: np.ndarray) -> np.ndarray:
    """Mean sensory profile of a storage-scale sample block (ridge proxy prediction, 50 labels)."""
    return proxy.predict_storage(X).mean(axis=0)


def profile_scores(gen_profile: np.ndarray, real_profile: np.ndarray) -> tuple:
    gen_profile = np.asarray(gen_profile, dtype=float)
    real_profile = np.asarray(real_profile, dtype=float)
    rho = float(spearmanr(gen_profile, real_profile).statistic)
    if not np.isfinite(rho):
        rho = 0.0
    mae = float(np.mean(np.abs(gen_profile - real_profile)))
    return rho, mae


# ------------------------------------------------------------------------------------------------ model container
class StyleModel:
    """A fitted fold: imputer + standardiser + marginals + copula + label proxy + style bounds."""

    def __init__(self, centre, scale, medians, marginals, copula, proxy, codes, t2n_bounds, global_t2n):
        self.centre = centre
        self.scale = scale
        self.medians = medians
        self.marginals = marginals
        self.copula = copula
        self.proxy = proxy
        self.codes = codes
        self.t2n_bounds = dict(t2n_bounds)
        self.global_t2n = float(global_t2n)

    def t2n_bound(self, styles):
        styles = np.asarray(styles)
        return np.array([self.t2n_bounds.get(str(s), self.global_t2n) for s in styles], dtype=float)

    def generate(self, style: str, n: int, rng, mode: str = "copula", marginals=None, copula=None,
                 normal: np.ndarray = None):
        """Draw n storage-scale samples for one style.

        mode='copula' uses the fitted correlation; mode='independent' draws independent uniforms (the ablation);
        `normal` lets a caller reuse one standard-normal array across variants (paired comparisons).
        """
        marginals = marginals if marginals is not None else self.marginals
        copula = copula if copula is not None else self.copula
        if mode == "independent":
            U = rng.random((int(n), len(FEATURE_COLS)))
        else:
            if normal is None:
                U = copula.uniforms(style, int(n), rng)
            else:
                U = copula.uniforms_from_normal(style, normal)
        return sample_from_uniforms(marginals, style, U)


def fit_style_model(X_train, styles_train, Y_train, kappa, kappa_R, codes, t2n_bounds, global_t2n,
                    centre=None, scale=None, proxy=False, floor_aware=True):
    """Fit one fold's model; returns (model, proxy) with the proxy optional (ablations may skip it)."""
    medians = column_medians(X_train)
    X = apply_median(X_train, medians)
    if centre is None or scale is None:
        centre, scale = fit_standardizer(X)
    used_codes = dict(codes)
    marginals = StyleMarginals(kappa, used_codes, drop_floor_atoms=not floor_aware).fit(X, styles_train)
    Z = np.empty_like(X)
    for style in sorted(set(str(s) for s in styles_train)):
        rows = np.nonzero(styles_train == style)[0]
        Z[rows] = marginals.forward(style, X[rows])
    Z = np.clip(ndtri(np.clip(Z, 1e-9, 1 - 1e-9)), -8.0, 8.0)
    copula = GaussianCopula(kappa_R).fit(Z, styles_train)
    label_proxy = None
    if proxy:
        label_proxy = LabelProxy(centre, scale).fit(X, Y_train)
    model = StyleModel(centre, scale, medians, marginals, copula, label_proxy, used_codes,
                       t2n_bounds, global_t2n)
    return model, label_proxy


# ------------------------------------------------------------------------------------------------ hyper-parameter selection
def _half_split(styles):
    """Deterministic even/odd split inside each style (row order is the file order)."""
    half = np.zeros(len(styles), dtype=int)
    for style in sorted(set(str(s) for s in styles)):
        rows = np.nonzero(styles == style)[0]
        half[rows] = np.arange(rows.size) % 2
    return half


def select_hyperparameters(X, styles, kappas=(0.0, 5.0, 15.0), kappa_Rs=(20.0, 50.0, 100.0),
                           codes=None, rng_seed=0, max_cells=6):
    """Training-internal selection of (kappa, kappa_R) by style-half cross-validation energy distance.

    Both halves are used in turn (fit on one, score on the other); the score is the hold-out-size-weighted
    normalised energy distance in the fit's standardised scale. Ties break towards stronger shrinkage.
    """
    styles = np.asarray(styles)
    half = _half_split(styles)
    rng = np.random.default_rng(int(rng_seed))
    scores = {(float(k), float(r)): [] for k in kappas for r in kappa_Rs}
    for side in (0, 1):
        train = half != side
        hold = ~train
        Xtr = apply_median(X[train], column_medians(X[train]))
        Xho = apply_median(X[hold], column_medians(X[train]))
        centre, scale = fit_standardizer(Xtr)
        Ztr = standardize(Xtr, centre, scale)
        Zho = standardize(Xho, centre, scale)
        s_tr, s_ho = styles[train], styles[hold]
        used_codes = codes if codes is not None else floor_code_map(Xtr)
        for kappa in kappas:
            marginals = StyleMarginals(kappa, used_codes).fit(Xtr, s_tr)
            # the copula only depends on kappa through z, so one z-matrix serves every kappa_R
            Zc = np.empty_like(Ztr)
            for style in sorted(set(str(s) for s in s_tr)):
                rows = np.nonzero(s_tr == style)[0]
                U = marginals.forward(style, Xtr[rows])
                Zc[rows] = np.clip(ndtri(np.clip(U, 1e-9, 1 - 1e-9)), -8.0, 8.0)
            for kappa_R in kappa_Rs:
                copula = GaussianCopula(kappa_R).fit(Zc, s_tr)
                num = 0.0
                den = 0
                for style in sorted(set(str(s) for s in s_ho)):
                    rows = np.nonzero(s_ho == style)[0]
                    n = rows.size
                    U = copula.uniforms(style, n, rng)
                    gen = marginals.inverse(style, U)
                    gen_z = standardize(gen, centre, scale)
                    real_z = Zho[rows]
                    tr_rows = np.nonzero(s_tr == style)[0]
                    dref = reference_scale(Ztr[tr_rows], n, rng, repeats=max_cells)
                    value, _ = normalized_energy_distance(gen_z, real_z, dref)
                    num += value * n
                    den += n
                scores[(float(kappa), float(kappa_R))].append(num / max(den, 1))
    table = {key: float(np.mean(values)) for key, values in scores.items()}
    # ties break towards the stronger-shrinkage grid point (larger kappa, then larger kappa_R)
    best_key = min(table, key=lambda key: (table[key], -key[0], -key[1]))
    return best_key[0], best_key[1], table


def aggregate_selection(tables):
    """Average the per-fold selection score tables and pick one grid point (ties -> stronger shrinkage)."""
    keys = sorted({key for table in tables for key in table})
    mean_table = {key: float(np.mean([table[key] for table in tables if key in table])) for key in keys}
    kappa, kappa_r = min(mean_table, key=lambda key: (mean_table[key], -key[0], -key[1]))
    return float(kappa), float(kappa_r), mean_table


# ------------------------------------------------------------------------------------------------ transfer
class TransferProblem:
    """Pils/Lager -> Tripel transfer: quantile initialisation, PCA/Mahalanobis target, constrained projection.

    The optimisation variable is v in [0, 1]^231 (min-max normalised storage space). Hard chemistry caps become box
    bounds; the two label-proxy constraints (t2n, stale hops) are handled by an exact linear shift inside the
    objective ("feasibility projection"), so every objective evaluation is feasible.
    """

    def __init__(self, X_train, styles_train, Y_train, source_rows, source_style, target_style,
                 kappa, kappa_R, proxy, codes, thresholds, n_components: int = 10):
        X_train = np.asarray(X_train, dtype=float)
        styles_train = np.asarray(styles_train)
        self.codes = dict(codes)
        self.target_style = str(target_style)
        self.source_style = str(source_style)
        self.thresholds = dict(thresholds)
        self.medians = column_medians(X_train)
        self.X_train = apply_median(X_train, self.medians)
        self.centre, self.scale = fit_standardizer(self.X_train)
        lo = np.nanmin(self.X_train, axis=0)
        hi = np.nanmax(self.X_train, axis=0)
        span = hi - lo
        span = np.where(np.isfinite(span) & (span > 1e-12), span, 1e-12)
        self.lo = np.where(np.isfinite(lo), lo, 0.0)
        self.hi = self.lo + span
        self.span = span
        self.v_upper = np.ones(len(FEATURE_COLS))
        self.marginals = StyleMarginals(kappa, self.codes).fit(self.X_train, styles_train)
        source_X = apply_median(np.asarray(source_rows, dtype=float), self.medians)
        self.X_source = source_X
        source_styles = np.array([self.source_style] * source_X.shape[0])
        self.source_marginals = StyleMarginals(0.0, self.codes).fit(source_X, source_styles)
        self.x0 = self.marginals.inverse(self.target_style,
                                         self.source_marginals.forward(self.source_style, source_X))
        self.v0 = np.clip((self.x0 - self.lo) / self.span, 0.0, 1.0)
        self.proxy = proxy
        self.source_phys = {name: physical_conc(name, source_X[:, FEATURE_COLS.index(name)], self.codes)
                            for name in DEFECT_KEYS}
        self.source_pred = {name: proxy.predict_storage(source_X, name) for name in PROXY_TARGETS}
        label_sd = float(np.nanstd(Y_train[:, LABEL_COLS.index(STALE)]))
        self.stale_tolerance = 0.05 * label_sd
        self.label_sd = {name: float(np.nanstd(Y_train[:, LABEL_COLS.index(name)])) for name in PROXY_TARGETS}
        # target PCA on the standardised target-style training rows
        target_rows = np.nonzero(styles_train == self.target_style)[0]
        Zt = standardize(self.X_train[target_rows], self.centre, self.scale)
        self.z_mean = Zt.mean(axis=0)
        Zc = Zt - self.z_mean
        _, _, vt = np.linalg.svd(Zc, full_matrices=False)
        n_comp = int(min(n_components, Zc.shape[0] - 1, Zc.shape[1]))
        self.pca = vt[:n_comp]
        scores = Zc @ self.pca.T
        self.score_mean = scores.mean(axis=0)
        score_sd = scores.std(axis=0, ddof=1)
        self.score_sd = np.where(score_sd > 1e-12, score_sd, 1.0)
        corr = np.corrcoef((scores - self.score_mean) / self.score_sd, rowvar=False)
        corr = np.atleast_2d(np.nan_to_num(corr, nan=0.0))
        corr = 0.9 * corr + 0.1 * np.eye(corr.shape[0])
        self.target_cov = corr
        self.target_cov_inv = np.linalg.inv(corr)
        # gradients: z = (lo + span*v - centre)/scale, so dz/dv = span/scale
        self.dz_dv = self.span / self.scale
        self.d_score_dv = (self.pca * self.dz_dv[None, :]) / self.score_sd[:, None]
        # proxy gradients w.r.t. v (used by the exact shifts and by the L1 change penalty)
        self.proxy_grad = {}
        for name in PROXY_TARGETS:
            self.proxy_grad[name] = self.proxy.coef_for(name) * self.dz_dv
        self.source_defect_profile = self.defect_profile(source_X)

    # -- coordinate changes
    def v_to_x(self, v):
        return self.lo + self.span * np.asarray(v, dtype=float)

    def x_to_v(self, x):
        return np.clip((np.asarray(x, dtype=float) - self.lo) / self.span, 0.0, 1.0)

    def score(self, v):
        v = np.asarray(v, dtype=float)
        Z = (self.v_to_x(v) - self.centre) / self.scale
        return ((Z @ self.pca.T) - self.score_mean) / self.score_sd

    def target_mahalanobis(self, v):
        s = self.score(v)
        return float(np.sqrt(max(float(s @ self.target_cov_inv @ s), 0.0)))

    def target_objective(self, v):
        s = self.score(v)
        return float(s @ self.target_cov_inv @ s)

    def predicts(self, v, name):
        x = self.v_to_x(v)
        return float(self.proxy.predict_storage(x[None, :], name)[0])

    def defect_profile(self, x):
        """The five defect indicators of each row, scaled by its threshold (chemistry) or label sd (proxies)."""
        x = np.asarray(x, dtype=float)
        columns = []
        for name in DEFECT_KEYS:
            columns.append(physical_conc(name, x[:, FEATURE_COLS.index(name)], self.codes)
                           / float(self.thresholds[name]))
        for name in PROXY_TARGETS:
            columns.append(self.proxy.predict_storage(x, name) / self.label_sd[name])
        return np.stack(columns, axis=1)

    def defect_gradient(self, index: int) -> np.ndarray:
        """d defect_profile / d v for one source row (the log defects are linearised at that source)."""
        grad = np.zeros((5, len(FEATURE_COLS)))
        for k, name in enumerate(DEFECT_KEYS):
            j = FEATURE_COLS.index(name)
            conc = float(self.source_phys[name][index])
            factor = (np.log(10.0) * conc) if name in LOG10_SET else 1.0
            grad[k, j] = factor * self.span[j] / float(self.thresholds[name])
        for k, name in enumerate(PROXY_TARGETS):
            grad[len(DEFECT_KEYS) + k, :] = self.proxy_grad[name] / self.label_sd[name]
        return grad

    # -- exact linear shifts
    def shift_along_proxy(self, v, name, caps, excluded=tuple(DEFECT_KEYS)):
        v = np.array(v, dtype=float, copy=True)
        caps = np.broadcast_to(np.asarray(caps, dtype=float), (1,)).copy()
        grad = np.array(self.proxy_grad[name], dtype=float)
        mask = np.ones(len(FEATURE_COLS), dtype=bool)
        for column in excluded:
            mask[FEATURE_COLS.index(column)] = False
        grad = np.where(mask, grad, 0.0)
        norm_sq = float(np.sum(grad * grad))
        if norm_sq <= 1e-18:
            return v
        Z = (self.v_to_x(v) - self.centre) / self.scale
        pred = float(self.proxy.coef_for(name) @ Z + self.proxy.intercept_for(name))
        gap = pred - (float(caps[0]) - PROXY_MARGIN)
        if gap > 0.0:
            v = v - (gap / norm_sq) * grad
        return np.clip(v, 0.0, 1.0)

    def proxy_ok(self, v, t2n_caps, stale_caps, tol: float = 1e-7):
        pred_t2n = self.predicts(v, T2N)
        pred_stale = self.predicts(v, STALE)
        return (pred_t2n <= float(t2n_caps[0]) + tol) and (pred_stale <= float(stale_caps[0]) + 1e-7)

    # -- optimisation
    def solve(self, index: int, lambda_: float, eta: float, caps: dict, t2n_cap=None, stale_cap=None,
              maxiter: int = 150):
        """Solve one source beer under hard chemistry caps. Returns v, metrics and feasibility flags."""
        v0 = self.v0[index]
        if t2n_cap is None:
            t2n_cap = float(self.source_pred[T2N][index])
        if stale_cap is None:
            stale_cap = float(self.source_pred[STALE][index]) + self.stale_tolerance
        t2n_caps = np.array([t2n_cap], dtype=float)
        stale_caps = np.array([stale_cap], dtype=float)
        upper = apply_transfer_caps(self, caps)
        self.v_upper = upper
        defect_grad = self.defect_gradient(index)
        source_profile = self.source_defect_profile[index]

        def objective(v):
            v = np.clip(v, 0.0, upper)
            v = project_transfer_feasible(self, v, t2n_caps, stale_caps)
            v = np.clip(v, 0.0, upper)
            diff = v - v0
            f_quad = float(diff @ diff)
            s = self.score(v)
            grad_target = self.target_cov_inv @ s
            f_target = float(s @ grad_target)
            profile = self.defect_profile(self.v_to_x(v)[None, :])[0]
            delta = profile - source_profile
            f_l1 = float(np.sum(np.abs(delta)))
            value = f_quad + float(lambda_) * f_target + float(eta) * f_l1
            grad = 2.0 * diff
            grad = grad + float(lambda_) * (2.0 * (self.d_score_dv.T @ grad_target))
            if eta:
                signs = np.sign(delta)
                grad = grad + float(eta) * (signs @ defect_grad)
            return value, grad

        start = project_transfer_feasible(self, v0, t2n_caps, stale_caps)
        start = np.clip(start, 0.0, upper)
        result = minimize(objective, start, jac=True, method="L-BFGS-B",
                          bounds=list(zip(np.zeros_like(upper), upper)),
                          options={"maxiter": int(maxiter), "ftol": 1e-12, "gtol": 1e-8, "maxls": 30})
        v = project_transfer_feasible(self, np.clip(result.x, 0.0, upper), t2n_caps, stale_caps)
        v = np.clip(v, 0.0, upper)
        x = self.v_to_x(v)
        pred_t2n = self.predicts(v, T2N)
        pred_stale = self.predicts(v, STALE)
        nonworsen = {}
        for name in DEFECT_KEYS:
            out_conc = float(physical_conc(name, x[FEATURE_COLS.index(name)], self.codes))
            src_conc = float(self.source_phys[name][index])
            nonworsen[name] = bool(out_conc <= src_conc * (1.0 + 1e-9) + 1e-12)
        nonworsen[T2N] = bool(pred_t2n <= float(self.source_pred[T2N][index]) + 1e-9)
        nonworsen[STALE] = bool(pred_stale <= float(self.source_pred[STALE][index]) + self.stale_tolerance + 1e-9)
        return {
            "v": v,
            "x": x,
            "targetMahalanobis": self.target_mahalanobis(v),
            "targetObjective": self.target_objective(v),
            "l1Change": float(np.sum(np.abs(v - v0))),
            "meanAbsChange": float(np.mean(np.abs(v - v0))),
            "quadratic": float((v - v0) @ (v - v0)),
            "feasible": bool(self.proxy_ok(v, t2n_caps, stale_caps, tol=1e-6)),
            "nonworsen": nonworsen,
            "nonworsenAll": bool(all(nonworsen.values())),
            "iterations": int(getattr(result, "nit", 0)),
            "converged": bool(getattr(result, "success", False)),
        }


CAP_AT_MAX_SOURCE_THRESHOLD = "cap-at-max-source-threshold"   # c_new <= max(c_source, T):  "超阈不恶化"
NON_INCREASING = "non-increasing"                              # c_new <= c_source:            "绝对不增"


def transfer_caps(problem: TransferProblem, index: int, threshold_set: dict, policy: str):
    """Hard chemistry caps for one source under a policy; returns (caps, t2n_cap, stale_cap)."""
    caps = {}
    for name in DEFECT_KEYS:
        source = float(problem.source_phys[name][index])
        threshold = float(threshold_set[name])
        if policy == NON_INCREASING:
            # a non-detect source (physical 0) must stay a non-detect: cap 0 maps to the floor code below
            caps[name] = source
        elif policy in (CAP_AT_MAX_SOURCE_THRESHOLD, "threshold-capped"):
            caps[name] = max(source, threshold)
        else:
            raise ValueError("unknown transfer constraint policy: %s" % policy)
    return caps, float(problem.source_pred[T2N][index]), float(problem.source_pred[STALE][index])


def policy_bound(problem: TransferProblem, index: int, threshold_set: dict, policy: str) -> np.ndarray:
    """The per-defect bound that defines "not worse" *under that policy* (three threshold defects only)."""
    bounds = np.zeros(len(DEFECT_KEYS))
    for k, name in enumerate(DEFECT_KEYS):
        source = float(problem.source_phys[name][index])
        threshold = float(threshold_set[name])
        bounds[k] = source if policy == NON_INCREASING else max(source, threshold)
    return bounds


def apply_transfer_caps(problem: TransferProblem, caps: dict) -> np.ndarray:
    """Box upper bounds in v for the three threshold defects (hard chemistry caps)."""
    upper = np.ones(len(FEATURE_COLS))
    for name, cap in caps.items():
        j = FEATURE_COLS.index(name)
        if float(cap) <= 0.0:
            # non-detect cap: the smallest representable physical value (log10 tier: the floor code)
            storage = float(problem.lo[j]) if name in LOG10_SET else 0.0
        else:
            storage = float(np.asarray(storage_bound(name, cap)))
        upper[j] = float(np.clip((storage - problem.lo[j]) / problem.span[j], 0.0, 1.0))
    return upper


# ------------------------------------------------------------------------------------------------ bootstrap
def bootstrap_label_proxy(X, Y, centre, scale, base_proxy: LabelProxy, n_boot: int, rng):
    """Refit the ridge proxy on row bootstraps (alphas held at the CV-selected values)."""
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)
    n = X.shape[0]
    out = []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, size=n)
        clone = base_proxy.refit_with_alphas(X[idx], Y[idx])
        out.append(clone)
    return out


# ------------------------------------------------------------------------------------------------ convenience
def low_defect_samples(model: StyleModel, X: np.ndarray, styles, thresholds: dict,
                       extra_caps: dict = None) -> np.ndarray:
    """Project a generated block onto the four constraints: 3 threshold defects (hard caps) + t2n (proxy bound).

    The chemistry caps are applied directly on the stored value; the t2n shift excludes the three defect columns, so
    it can never undo a chemistry cap. `extra_caps` lets the transfer delivery variant tighten a chemistry cap.
    """
    caps = {name: float(thresholds[name]) for name in DEFECT_KEYS}
    if extra_caps:
        caps = {name: min(caps[name], float(extra_caps[name])) for name in DEFECT_KEYS}
    out = project_thresholds(X, caps, model.codes)
    if model.proxy is not None:
        bounds = model.t2n_bound(styles)
        out = project_proxy_bound(out, model.proxy, T2N, bounds, model.centre, model.scale,
                                  excluded_columns=DEFECT_KEYS)
        out = project_thresholds(out, caps, model.codes)
    return out


def min_caps(a: dict, b: dict) -> dict:
    return {name: min(float(a[name]), float(b[name])) for name in a}


def bootstrap_energy_interval(gen: np.ndarray, real: np.ndarray, dref: float, rng, draws: int = 200) -> dict:
    """Bootstrap 95% interval of the normalised energy distance by resampling both blocks."""
    gen = np.asarray(gen, dtype=float)
    real = np.asarray(real, dtype=float)
    n_gen, n_real = gen.shape[0], real.shape[0]
    if n_gen == 0 or n_real == 0:
        return {"low": 0.0, "mid": 0.0, "high": 0.0, "draws": 0}
    values = []
    for _ in range(int(draws)):
        gi = gen[rng.integers(0, n_gen, size=n_gen)]
        ri = real[rng.integers(0, n_real, size=n_real)]
        value, _ = normalized_energy_distance(gi, ri, dref)
        values.append(value)
    values = np.sort(np.asarray(values, dtype=float))
    return {
        "low": float(np.quantile(values, 0.025)),
        "mid": float(np.median(values)),
        "high": float(np.quantile(values, 0.975)),
        "draws": int(draws),
    }


def weighted(values, weights) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    total = float(weights.sum())
    if total <= 0:
        return 0.0
    return float(np.sum(values * weights) / total)
