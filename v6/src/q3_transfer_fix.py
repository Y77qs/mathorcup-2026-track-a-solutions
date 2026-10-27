"""q3_transfer_fix.py — Pils/Lager -> Tripel transfer with a CERTIFIED convex QP.

WHY THIS FILE EXISTS. The v5 transfer (`q3_lib.TransferProblem`) was rejected on four counts:
  * the PCA score was computed without subtracting the target mean it was fitted around, so the target mean was
    0.604 away from *itself* (independent recheck `target_mean_distance_old`);
  * "not worse" was asserted through an L-BFGS-B run whose objective contained an inner feasibility projection, so
    the gradient returned to the optimiser was not the gradient of the function it evaluated (no certificate);
  * the t2n constraint used the sensory ridge proxy instead of the measured trans-2-nonenal column;
  * nothing said whether a returned point actually satisfied the declared constraints, and a failed solve was not
    distinguishable from a successful one.

WHAT THIS FILE DOES
  * one declared target reference per outer fold: only that fold's TRAINING rows of the target style define the
    target mean / PCA / correlation and the label proxy. The source beers are QUERY INPUTS only (the source style is
    excluded from every fit);
  * the QP is the declared convex program
        min_z  (z - z_ref)' Q_t (z - z_ref) + lambda ||z - z_anchor||^2 + eta * sum(t)
        s.t.   -t <= z - z_source <= t,  t >= 0,  l <= z <= u,  A z <= b
    with Q_t = P' diag(1/sd)^2 Sigma_corr^{-1} diag(1/sd)^2 P (rank 10, P = target PCA loadings), z in the
    fold-standardised storage space, t eliminated at the optimum (eta > 0 implies t = |z - z_source|);
  * l/u carry the declared support and the four per-coordinate chemistry caps c' <= c_source (DMS, diacetyl, 4VG,
    trans-2-nonenal); A z <= b is the single stale_hops linear proxy row (declared as a PROXY, not a measurement);
  * the QP is solved by an exact ADMM (primal-dual, box + one half-space projection by bisection, Woodbury solve on
    the rank-10 quadratic). scipy's SLSQP was benchmarked on this problem and rejected: 27 s/solve with
    status=8 and residuals ~1e-4 at 462 variables. Every solve writes a certificate (problem hash, status,
    objective, primal/dual residual, iterations, feasibility, KKT stationarity check);
  * the objective gradient is cross-validated against central finite differences; the only permitted discrepancy is
    the L1 kink at |z - z_source| = 0, which is reported and explained;
  * strategies, all on the same fold reference: source-fixed, target-mean projection, and two QPs (the declared
    literal source anchor and the quantile-preserving anchor);
  * a solve that does not meet the tolerance is reported (status) and the delivered point falls back to the source
    point, which is called "migration not completed" and is never counted as a success.

USAGE
    python src/q3_transfer_fix.py --repeat all     # repeats 0,1,2 (default)
    python src/q3_transfer_fix.py --repeat 0       # one repeat
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from scipy.spatial.distance import cdist
from scipy.special import ndtri

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _contract_shim():
    module = types.ModuleType("modeling_contract")

    def _noop(*_args, **_kwargs):
        return None

    for name in ("seed", "emit_metrics", "emit_predictions", "emit_output", "save_figure"):
        setattr(module, name, _noop)
    module.experiment_dir = lambda: _ROOT / "state/devrun/v6/q3/transfer"
    module.project_dir = lambda: _ROOT
    module.dataset_path = lambda: _ROOT / "data/clean/q3.csv"
    module.split_paths = lambda: {}
    module.dependency_path = lambda rel: _ROOT / rel
    return module


try:
    import modeling_contract as _CONTRACT

    _HAS_CONTRACT = True
except Exception:  # noqa: BLE001
    _CONTRACT = _contract_shim()
    sys.modules["modeling_contract"] = _CONTRACT
    _HAS_CONTRACT = False

import v6_common as V6  # noqa: E402
import q3_lib as L  # noqa: E402
import target_columns as T  # noqa: E402


# ------------------------------------------------------------------------------------------------- protocol
SOURCE_STYLE = "Pils/Lager"
TARGET_STYLE = "Tripel"
KAPPA = 5.0                 # marginal shrinkage for the quantile anchor (declared, not tuned)
N_COMPONENTS = 10
LAMBDA = 1.0
ETA = 0.01
ADMM_RHO = 1.0
ADMM_TOL = 1e-8
ADMM_MAX_ITER = 40000
STALE_TOL = 1e-9            # "not worse" tolerance on the stale_hops PROXY (numerical only)
COVERAGE_TOL = 1e-9
NONENAL = "X.E..2.nonenal"
CAPPED_CHEMISTRY = tuple(L.DEFECT_KEYS) + (NONENAL,)
LINEAR_MASK = np.array([name in L.LINEAR_SET for name in L.FEATURE_COLS])
LOG10_MASK = np.array([name in L.LOG10_SET for name in L.FEATURE_COLS])
THRESHOLDS = dict(L.THRESHOLD_MEAN)


def run_dir() -> Path:
    value = os.environ.get("MODELING_EXPERIMENT_DIR")
    path = Path(value) if value else _ROOT / "state/devrun/v6/q3/transfer"
    path.mkdir(parents=True, exist_ok=True)
    return path


_RUN_DIR = run_dir()
_OUTPUTS = {}


def emit_metrics(payload: dict) -> None:
    V6.write_json(_RUN_DIR / "transfer_metrics.json", payload)
    if _HAS_CONTRACT:
        try:
            _CONTRACT.emit_metrics(payload)
        except Exception as exc:  # noqa: BLE001
            print("[warn] runner emit_metrics failed: %r" % (exc,))


def emit_output(name: str, value) -> None:
    _OUTPUTS[name] = value
    if _HAS_CONTRACT:
        try:
            _CONTRACT.emit_output(name, value)
        except Exception as exc:  # noqa: BLE001
            print("[warn] runner emit_output(%s) failed: %r" % (name, exc))


def flush_outputs() -> None:
    V6.write_json(_RUN_DIR / "transfer_outputs.json", {"q3_transfer": _OUTPUTS})


def finite(value, what: str) -> float:
    out = float(value)
    if not np.isfinite(out):
        raise ValueError("metric %r is not finite (%r): this is a defect, not a measurement" % (what, value))
    return out


def seed_rng(*entropy) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([int(e) for e in entropy]))


def weighted(values, weights) -> float | None:
    total = num = 0.0
    for value, weight in zip(values, weights):
        if value is None or weight is None:
            continue
        value, weight = float(value), float(weight)
        if not np.isfinite(value) or not np.isfinite(weight) or weight <= 0:
            continue
        num += value * weight
        total += weight
    return num / total if total > 0 else None


# ------------------------------------------------------------------------------------------------- data / context
def load_data():
    frame = pd.read_csv(V6.DATA_Q3)
    chem = [c for c in frame.columns if c.startswith(V6.CHEM_PREFIX)]
    if chem != L.CHEM_COLS:
        raise RuntimeError("the chem__* column order of data/clean/q3.csv differs from the frozen FEATURE_COLS")
    X = frame[L.CHEM_COLS].to_numpy(dtype=float)
    Y = frame[L.LABEL_COLS].to_numpy(dtype=float)
    styles = frame["tasting_category_fine"].astype(str).to_numpy()
    beers = frame["beer"].to_numpy(dtype=int)
    return frame, X, Y, styles, beers


def fit_transfer_context(X_raw, Y, styles, context_idx, repeat, fold):
    """Everything the transfer is allowed to learn comes from these rows (source style excluded by the caller)."""
    medians = L.column_medians(X_raw[context_idx])
    X = L.apply_median(X_raw[context_idx], medians)
    centre, scale = L.fit_standardizer(X)
    codes = L.floor_code_map(X)
    style_context = styles[context_idx]
    marginals = L.StyleMarginals(KAPPA, codes).fit(X, style_context)
    proxy = L.LabelProxy(centre, scale).fit(X, Y[context_idx])
    target_rows = np.nonzero(style_context == TARGET_STYLE)[0]
    if target_rows.size < 3:
        raise RuntimeError("fold %d/%d has %d target-style training rows: the reference is not identifiable"
                           % (repeat, fold, target_rows.size))
    Z_t = L.standardize(X[target_rows], centre, scale)
    z_mean = Z_t.mean(axis=0)
    _, _, vt = np.linalg.svd(Z_t - z_mean, full_matrices=False)
    n_comp = int(min(N_COMPONENTS, Z_t.shape[0] - 1, Z_t.shape[1]))
    pca = np.array(vt[:n_comp], dtype=float, copy=True)
    scores = (Z_t - z_mean) @ pca.T
    score_mean = scores.mean(axis=0)
    score_sd = scores.std(axis=0, ddof=1)
    score_sd = np.where(score_sd > 1e-12, score_sd, 1.0)
    correlation = np.corrcoef((scores - score_mean) / score_sd, rowvar=False)
    correlation = np.atleast_2d(np.nan_to_num(correlation, nan=0.0))
    correlation = 0.9 * correlation + 0.1 * np.eye(correlation.shape[0])
    correlation_inv = np.linalg.inv(correlation)
    lo = np.nanmin(X, axis=0)
    hi = np.nanmax(X, axis=0)
    lo = np.where(np.isfinite(lo), lo, 0.0)
    hi = np.where(np.isfinite(hi), hi, lo + 1.0)
    lo = np.where(LINEAR_MASK, np.maximum(lo, 0.0), lo)   # physical concentration non-negativity
    hi = np.maximum(hi, lo)
    pm = pca / score_sd[:, None]                          # (10, 231)
    return {
        "repeat": int(repeat), "fold": int(fold), "context_idx": np.asarray(context_idx, dtype=int),
        "medians": medians, "X": X, "styles": style_context, "centre": centre, "scale": scale, "codes": codes,
        "marginals": marginals, "proxy": proxy, "target_rows": target_rows, "Z_target": Z_t,
        "z_mean": z_mean, "pca": pca, "score_mean": score_mean, "score_sd": score_sd,
        "correlation_inv": correlation_inv, "pm": pm,
        "lowrank_U": pm.T, "lowrank_C": correlation_inv, "lowrank_C2": 2.0 * correlation_inv,
        "mref": pm @ z_mean, "lo": lo, "hi": hi,
        "low_z": (lo - centre) / scale, "up_z": (hi - centre) / scale,
        "d_target": float(cdist(Z_t, Z_t).sum() / (Z_t.shape[0] * (Z_t.shape[0] - 1))),
    }


def score(ctx, z):
    """Fixed PCA centring: the same z_mean is used by the fit and by the score (this is the old defect)."""
    z = np.atleast_2d(np.asarray(z, dtype=float))
    s = ((z - ctx["z_mean"]) @ ctx["pca"].T - ctx["score_mean"]) / ctx["score_sd"]
    return s


def score_legacy(ctx, z):
    """The v5 formula (no z_mean subtraction) — computed only to show how big the old error was."""
    z = np.atleast_2d(np.asarray(z, dtype=float))
    s = (z @ ctx["pca"].T - ctx["score_mean"]) / ctx["score_sd"]
    return s


def mahalanobis(ctx, z, legacy: bool = False):
    s = score_legacy(ctx, z) if legacy else score(ctx, z)
    value = float((s @ ctx["correlation_inv"] @ s.T)[0, 0])
    return float(np.sqrt(max(value, 0.0)))


def target_objective(ctx, z):
    s = score(ctx, z)
    return float((s @ ctx["correlation_inv"] @ s.T)[0, 0])


# ------------------------------------------------------------------------------------------------- the QP
def _project_box_halfspace(point, low, up, arow, b):
    """Exact projection of `point` onto {low <= w <= up} ∩ {arow . w <= b}, by bisection on the multiplier."""
    w = np.clip(point, low, up)
    if arow is None or float(arow @ w) <= b:
        return w
    lo_mu, hi_mu = 0.0, 1.0
    for _ in range(80):
        if float(arow @ np.clip(point - hi_mu * arow, low, up)) <= b:
            break
        hi_mu *= 2.0
    else:
        raise RuntimeError("half-space projection failed: the feasible set may be empty")
    for _ in range(120):
        mid = 0.5 * (lo_mu + hi_mu)
        if float(arow @ np.clip(point - mid * arow, low, up)) > b:
            lo_mu = mid
        else:
            hi_mu = mid
    return np.clip(point - hi_mu * arow, low, up)


def admm_qp(ctx, zref, anchor, z_source, low, up, arow, b, lam, eta,
            tol=ADMM_TOL, max_iter=ADMM_MAX_ITER, rho=ADMM_RHO):
    """Exact convex QP solve. Returns the feasible primal point w, iterations and the two residuals.

    The slack vector t is eliminated at the optimum: because eta > 0, t_i = |z_i - z_source,i|, so the objective is
    the declared one evaluated at that t. The w-update is the exact prox of the L1 term composed with the box and
    the single half-space row (bisection gives the exact projection, no approximation).
    """
    U = ctx["lowrank_U"]
    C = ctx["lowrank_C"]
    C2 = ctx["lowrank_C2"]
    mref = ctx["mref"]
    n = zref.size
    C2_inv = np.linalg.inv(C2)

    def refresh(rho_value):
        a0 = rho_value + 2.0 * lam
        S = np.linalg.inv(C2_inv + (1.0 / a0) * (U.T @ U))
        return a0, S

    a0, S = refresh(rho)
    rhs_const = 2.0 * (U @ (C @ mref)) + 2.0 * lam * anchor

    def apply_minv(rhs):
        return (1.0 / a0) * rhs - (1.0 / (a0 * a0)) * (U @ (S @ (U.T @ rhs)))

    def prox(v):
        threshold = eta / rho
        shifted = v - z_source
        point = np.sign(shifted) * np.maximum(np.abs(shifted) - threshold, 0.0) + z_source
        w = np.clip(point, low, up)
        if arow is None or float(arow @ w) <= b:
            return w
        # exact constrained prox: bisection on the half-space multiplier
        lo_mu, hi_mu = 0.0, 1.0

        def candidate(mu):
            shifted_mu = v - mu * arow - z_source
            point_mu = np.sign(shifted_mu) * np.maximum(np.abs(shifted_mu) - threshold, 0.0) + z_source
            return np.clip(point_mu, low, up)

        for _ in range(80):
            if float(arow @ candidate(hi_mu)) <= b:
                break
            hi_mu *= 2.0
        for _ in range(120):
            mid = 0.5 * (lo_mu + hi_mu)
            if float(arow @ candidate(mid)) > b:
                lo_mu = mid
            else:
                hi_mu = mid
        return candidate(hi_mu)

    z = np.clip(anchor, low, up)
    w = prox(z)
    u = z - w
    w_prev = np.array(w, dtype=float, copy=True)
    primal = dual = np.inf
    iterations = 0
    for iterations in range(1, int(max_iter) + 1):
        z = apply_minv(rhs_const + rho * (w - u))
        w_prev = w
        w = prox(z + u)
        u = u + z - w
        primal = float(np.max(np.abs(z - w)))
        dual = float(rho * np.max(np.abs(w - w_prev)))
        if primal < tol and dual < tol:
            break
        if iterations % 50 == 0:  # residual balancing; the scaled dual variable is rescaled with rho
            if primal > 10.0 * dual:
                u = u * 0.5
                rho *= 2.0
            elif dual > 10.0 * primal:
                u = u * 2.0
                rho *= 0.5
            else:
                continue
            a0, S = refresh(rho)
            rhs_const = 2.0 * (U @ (C @ mref)) + 2.0 * lam * anchor
    return {"w": w, "z": z, "iterations": int(iterations), "primal_residual": float(primal),
            "dual_residual": float(dual), "rho": float(rho)}


def objective_value(ctx, z, zref, anchor, z_source, lam, eta):
    d = np.asarray(z, dtype=float) - zref
    s = ctx["pm"] @ d
    quad = float(s @ ctx["correlation_inv"] @ s)
    return quad + lam * float((z - anchor) @ (z - anchor)) + eta * float(np.sum(np.abs(z - z_source)))


def objective_gradient(ctx, z, zref, anchor, z_source, lam, eta):
    d = np.asarray(z, dtype=float) - zref
    smooth = 2.0 * (ctx["pm"].T @ (ctx["correlation_inv"] @ (ctx["pm"] @ d))) + 2.0 * lam * (z - anchor)
    return smooth + eta * np.sign(z - z_source)


def finite_difference_check(ctx, z, zref, anchor, z_source, lam, eta, coords, step=1e-6):
    """Central-difference cross-check of the implemented objective against the analytic gradient."""
    base = np.array(z, dtype=float, copy=True)
    analytic = objective_gradient(ctx, base, zref, anchor, z_source, lam, eta)
    abs_errors, rel_errors, kinks = [], [], 0
    for j in coords:
        shift = np.zeros_like(base)
        shift[j] = step
        plus = objective_value(ctx, base + shift, zref, anchor, z_source, lam, eta)
        minus = objective_value(ctx, base - shift, zref, anchor, z_source, lam, eta)
        numeric = (plus - minus) / (2.0 * step)
        error = abs(numeric - analytic[j])
        if abs(base[j] - z_source[j]) > 4.0 * step:
            abs_errors.append(error)
            if abs(analytic[j]) > 1e-6:  # a relative error is only meaningful away from gradient cancellation
                rel_errors.append(error / abs(analytic[j]))
        else:
            kinks += 1  # the L1 kink |z - z_source| = 0 lies inside the step: the secant is not the subgradient
    return {"n_coords": int(len(coords)), "max_abs_error": float(max(abs_errors)) if abs_errors else None,
            "max_rel_error": float(max(rel_errors)) if rel_errors else None,
            "l1_kink_coords": int(kinks)}


def kkt_stationarity_residual(ctx, w, zref, anchor, z_source, low, up, arow, b, lam, eta,
                             tol=1e-7, kink_tol=1e-6):
    """Distance from 0 to the set-valued KKT stationarity condition (a real certificate, not a gradient norm).

    0 must belong to  grad_smooth + eta*subgrad(|z-z_source|) + A_tight' lambda, with lambda >= 0 and the L1
    subgradient free in [-eta, eta] on coordinates sitting on the kink. Substituting s = eta*(2u-1), u in [0,1] turns
    the set-valued condition into one non-negative least-squares problem, which is solved exactly here (an NNLS with
    a fixed subgradient would leave an artificial O(eta) residual at the kink).
    """
    d = w - zref
    smooth = 2.0 * (ctx["pm"].T @ (ctx["correlation_inv"] @ (ctx["pm"] @ d))) + 2.0 * lam * (w - anchor)
    n = w.size
    rows = [np.eye(n), -np.eye(n)]
    rhs = [np.asarray(up, dtype=float), -np.asarray(low, dtype=float)]
    if arow is not None:
        rows.append(arow.reshape(1, -1))
        rhs.append(np.array([b], dtype=float))
    A = np.vstack(rows)
    bvec = np.concatenate(rhs)
    slack = A @ w - bvec
    tight = np.abs(slack) <= tol
    kink = np.abs(w - z_source) <= kink_tol
    off_kink = ~kink
    gradient = smooth + eta * np.where(off_kink, np.sign(w - z_source), 0.0)
    blocks, target = [], -gradient
    if tight.any():
        blocks.append(A[tight].T)
    n_kink = int(kink.sum())
    if n_kink:
        selector = np.zeros((n, n_kink))
        selector[np.nonzero(kink)[0], np.arange(n_kink)] = 1.0
        blocks.append(2.0 * eta * selector)
        target = target + eta * selector.sum(axis=1)
    if not blocks:
        return {"kkt_residual": float(np.linalg.norm(gradient)), "n_tight": 0, "n_kink": n_kink}
    design = np.hstack(blocks)
    solution, _ = nnls(design, target)
    if n_kink:
        multipliers = solution[:design.shape[1] - n_kink]
        sub = np.clip(solution[design.shape[1] - n_kink:], 0.0, 1.0)
        residual_vector = gradient + (A[tight].T @ multipliers if tight.any() else 0.0) \
            + eta * (selector @ (2.0 * sub - 1.0))
    else:
        residual_vector = gradient + A[tight].T @ solution
    return {"kkt_residual": float(np.linalg.norm(residual_vector)),
            "n_tight": int(tight.sum()), "n_kink": n_kink}


def problem_hash(*arrays, meta: dict) -> str:
    digest = hashlib.sha256()
    for value in arrays:
        if value is None:
            digest.update(b"none")
            continue
        digest.update(np.ascontiguousarray(np.asarray(value, dtype=np.float64)).tobytes())
    digest.update(json.dumps(meta, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


# ------------------------------------------------------------------------------------------------- strategies
def chemistry_caps(ctx, x_source):
    """Storage-space upper bounds for the four chemistry columns: c_new <= c_source (verifiable source value)."""
    caps, states = {}, {}
    for name in CAPPED_CHEMISTRY:
        j = L.FEATURE_COLS.index(name)
        stored = float(x_source[j])
        caught = bool(np.isclose(stored, ctx["codes"][name], rtol=1e-6, atol=0.0)) if name in ctx["codes"] else False
        if name in L.LOG10_SET:
            physical = 0.0 if caught else float(10.0 ** stored)
            cap = float(ctx["lo"][j]) if physical <= 0.0 else float(np.log10(physical))
        else:
            physical = 0.0 if caught else max(stored, 0.0)
            cap = 0.0 if physical <= 0.0 else physical
        caps[name] = float(min(cap, float(ctx["hi"][j])) if name != NONENAL else cap)
        states[name] = {"stored_source": stored, "physical_source": physical,
                        "censored_source": caught,
                        "state": ("floor_coded_source (physical value not identified)" if caught
                                  else "measured_source_value")}
    return caps, states


def source_predictions(ctx, x_source):
    return {"stale_hops": float(ctx["proxy"].predict_storage(np.asarray(x_source).reshape(1, -1), L.STALE)[0]),
            "t2n": float(ctx["proxy"].predict_storage(np.asarray(x_source).reshape(1, -1), L.T2N)[0])}


def build_problem(ctx, x_source, quantile_anchor_storage):
    """Box + half-space + anchors for one source."""
    caps, cap_states = chemistry_caps(ctx, x_source)
    low = np.array(ctx["low_z"], dtype=float, copy=True)
    up = np.array(ctx["up_z"], dtype=float, copy=True)
    for name, cap in caps.items():
        j = L.FEATURE_COLS.index(name)
        up[j] = min(up[j], float((cap - ctx["centre"][j]) / ctx["scale"][j]))
        low[j] = min(low[j], up[j])   # keep the box non-empty: the chemistry cap wins over the training support
    z_source = (np.asarray(x_source, dtype=float) - ctx["centre"]) / ctx["scale"]
    z_anchor = (np.asarray(quantile_anchor_storage, dtype=float) - ctx["centre"]) / ctx["scale"]
    prediction = source_predictions(ctx, x_source)
    stale_cap = prediction["stale_hops"] + STALE_TOL
    arow = np.asarray(ctx["proxy"].coef_for(L.STALE), dtype=float).copy()
    return {"low": low, "up": up, "z_source": z_source, "z_anchor": z_anchor,
            "caps": caps, "cap_states": cap_states, "zref": ctx["z_mean"].copy(),
            "stale_cap": stale_cap, "arow": arow, "source_prediction": prediction,
            "box_min_proxy": float(np.sum(np.where(arow > 0, arow * low, arow * up))),
            "feasible_set_nonempty": bool(float(np.sum(np.where(arow > 0, arow * low, arow * up))) <= stale_cap)}


def delivered_metrics(ctx, x_source, x_new, problem, strategy, meta):
    """Everything the audit needs for one delivered spectrum, including the five defect statements."""
    z_new = (np.asarray(x_new, dtype=float) - ctx["centre"]) / ctx["scale"]
    prediction = source_predictions(ctx, x_new)
    out = {
        "target_mahalanobis": mahalanobis(ctx, z_new),
        "target_mahalanobis_legacy_centering": mahalanobis(ctx, z_new, legacy=True),
        "l1_change_z": float(np.sum(np.abs(z_new - problem["z_source"]))),
        "mean_abs_change_z": float(np.mean(np.abs(z_new - problem["z_source"]))),
        "stale_hops_source": problem["source_prediction"]["stale_hops"],
        "stale_hops_new": prediction["stale_hops"],
        "stale_hops_nonincreasing": bool(prediction["stale_hops"] <=
                                        problem["source_prediction"]["stale_hops"] + STALE_TOL + 1e-9),
        "t2n_source": problem["source_prediction"]["t2n"],
        "t2n_new": prediction["t2n"],
        "t2n_increasing": bool(prediction["t2n"] > problem["source_prediction"]["t2n"] + 1e-9),
        "chemistry": {},
    }
    for name in CAPPED_CHEMISTRY:
        j = L.FEATURE_COLS.index(name)
        before = float(L.physical_conc(name, np.array([x_source[j]]), ctx["codes"])[0])
        after = float(L.physical_conc(name, np.array([x_new[j]]), ctx["codes"])[0])
        out["chemistry"][name] = {
            "stored_source": float(x_source[j]), "stored_new": float(x_new[j]),
            "physical_source": before, "physical_new": after,
            "nonincreasing": bool(after <= before * (1.0 + 1e-9) + 1e-12),
        }
    out["nonincrease_all"] = bool(all(entry["nonincreasing"] for entry in out["chemistry"].values())
                                  and out["stale_hops_nonincreasing"])
    out["n_constraint_violations"] = int(
        sum(1 for entry in out["chemistry"].values() if not entry["nonincreasing"])
        + (0 if out["stale_hops_nonincreasing"] else 1))
    return out


def audit_transfer_row(ctx, problem, delivered, name, unit, bound_type, bound_value, stored_source,
                       stored_new, residual, verdict):
    return {
        "source_beer": int(delivered["source_beer"]), "repeat": int(delivered["repeat"]),
        "fold": int(delivered["fold"]), "strategy": delivered["strategy"], "field": name,
        "unit": unit, "bound_type": bound_type, "bound_value": float(bound_value),
        "source_state": delivered["source_state"],
        "stored_before": float(stored_source), "stored_after": float(stored_new),
        "residual": float(residual), "verdict": verdict,
    }


# ------------------------------------------------------------------------------------------------- main
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Pils/Lager -> Tripel transfer with a certified QP")
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


STRATEGIES = ("source-fixed", "target-mean-projection", "qp-source-anchor", "qp-quantile-anchor")


def main(argv=None):
    args = parse_args(argv)
    repeats = resolve_repeats(args.repeat)
    started = time.time()
    _OUTPUTS.clear()

    frame, X_raw, Y, styles, beers = load_data()
    splits = V6.load_splits()
    index_of = {int(beer): i for i, beer in enumerate(beers)}
    source_rows_all = np.nonzero(styles == SOURCE_STYLE)[0]
    if source_rows_all.size == 0:
        raise RuntimeError("no %s rows: the transfer example does not exist" % SOURCE_STYLE)

    fingerprints = {
        "data_q3_sha256": V6.sha256_file(V6.DATA_Q3),
        "splits_sha256": V6.sha256_file(V6.SPLITS_CSV),
        "thresholds_sha256": V6.sha256_file(_ROOT / "data/clean/q3_thresholds.json"),
        "q3_lib_sha256": V6.sha256_file(_HERE / "q3_lib.py"),
        "v6_common_sha256": V6.sha256_file(_HERE / "v6_common.py"),
        "target_columns_sha256": V6.sha256_file(_HERE / "target_columns.py"),
    }

    transfer_rows = []
    constraint_rows = []
    certificates = []
    per_fold = []
    gradient_checks = []
    self_distances = []
    legacy_self_distances = []
    energy_cells = []
    per_repeat_summary = []

    for repeat in repeats:
        seed = int(V6.SEEDS[repeat])
        repeat_energy = []
        for fold in range(V6.N_OUTER):
            for rep, f, train_beers, test_beers in V6.iter_outer(splits):
                if rep == repeat and f == fold:
                    break
            train_idx = np.array([index_of[int(b)] for b in train_beers], dtype=int)
            context_idx = train_idx[styles[train_idx] != SOURCE_STYLE]     # the source style is query-only
            ctx = fit_transfer_context(X_raw, Y, styles, context_idx, repeat, fold)
            # ---- fixed-centring assertion: the target mean is at distance ~0 from itself
            self_distance = mahalanobis(ctx, ctx["z_mean"])
            legacy_distance = mahalanobis(ctx, ctx["z_mean"], legacy=True)
            if not self_distance < 1e-8:
                raise AssertionError("target-mean self distance is %.3g (>=1e-8): the PCA centring is still broken"
                                     % self_distance)
            self_distances.append(self_distance)
            legacy_self_distances.append(legacy_distance)
            # ---- source marginal used for the quantile anchor: fitted on this fold's TRAINING source rows
            training_source = np.nonzero((styles == SOURCE_STYLE) & np.isin(beers, train_beers))[0]
            reference_rows = training_source if training_source.size >= 2 else source_rows_all
            X_source_reference = L.apply_median(X_raw[reference_rows], ctx["medians"])
            source_marginals = L.StyleMarginals(0.0, ctx["codes"]).fit(
                X_source_reference, np.array([SOURCE_STYLE] * X_source_reference.shape[0]))
            target_marginals = ctx["marginals"]
            fold_rows = []
            fold_feasible = []
            for source_beer in source_rows_all:
                x_source = L.apply_median(X_raw[source_beer].reshape(1, -1), ctx["medians"])[0]
                uniforms = source_marginals.forward(SOURCE_STYLE, x_source.reshape(1, -1))
                quantile_storage = target_marginals.inverse(TARGET_STYLE, uniforms)[0]
                problem = build_problem(ctx, x_source, quantile_storage)
                fold_feasible.append(bool(problem["feasible_set_nonempty"]))
                base_meta = {"repeat": int(repeat), "fold": int(fold), "source_beer": int(beers[source_beer]),
                             "lambda": float(LAMBDA), "eta": float(ETA)}
                fold_rows.append({"problem": problem, "x_source": x_source, "beer": int(beers[source_beer]),
                                  "meta": base_meta})
            # ---- strategies
            for entry in fold_rows:
                problem = entry["problem"]
                x_source = entry["x_source"]
                for strategy in STRATEGIES:
                    meta = dict(entry["meta"], strategy=strategy,
                                anchor=("source" if strategy == "qp-source-anchor" else
                                        ("quantile" if strategy == "qp-quantile-anchor" else "none")))
                    solved = None
                    if strategy == "source-fixed":
                        x_new = np.array(x_source, dtype=float, copy=True)
                        status, feasible, fallback = "reference", bool(problem["feasible_set_nonempty"]), False
                        certificate = None
                    elif strategy == "target-mean-projection":
                        x_new = ctx["centre"] + ctx["scale"] * np.clip(problem["zref"], problem["low"], problem["up"])
                        status, feasible, fallback = "reference", bool(problem["feasible_set_nonempty"]), False
                        certificate = None
                    else:
                        if not problem["feasible_set_nonempty"]:
                            x_new = np.array(x_source, dtype=float, copy=True)
                            status, feasible, fallback = "infeasible", False, True
                            solved = None
                            certificate = {
                                "problem_hash": problem_hash(problem["low"], problem["up"], problem["z_source"],
                                                             problem["z_anchor"], problem["zref"],
                                                             problem["arow"], np.array([problem["stale_cap"]]),
                                                             meta=meta),
                                "status": "infeasible", "feasible": False, "iterations": 0,
                                "objective": None, "primal_residual": None, "dual_residual": None,
                                "solver": "ADMM (exact convex QP); box minimum of A z already exceeds b",
                                "note": "mathematically infeasible: no point in the declared box satisfies A z <= b",
                            }
                        else:
                            anchor = problem["z_anchor"] if strategy == "qp-quantile-anchor" else problem["z_source"]
                            solved = admm_qp(ctx, problem["zref"], anchor, problem["z_source"], problem["low"],
                                             problem["up"], problem["arow"], problem["stale_cap"], LAMBDA, ETA)
                            w = solved["w"]
                            converged = solved["primal_residual"] < ADMM_TOL and solved["dual_residual"] < ADMM_TOL
                            objective = objective_value(ctx, w, problem["zref"], anchor, problem["z_source"],
                                                        LAMBDA, ETA)
                            violation = max(
                                float(np.max(np.maximum(problem["low"] - w, 0.0))),
                                float(np.max(np.maximum(w - problem["up"], 0.0))),
                                max(0.0, float(problem["arow"] @ w) - problem["stale_cap"]))
                            kkt = kkt_stationarity_residual(ctx, w, problem["zref"], anchor,
                                                            problem["z_source"], problem["low"], problem["up"],
                                                            problem["arow"], problem["stale_cap"], LAMBDA, ETA)
                            coords = np.arange(w.size) if int(entry["beer"]) % 4 == 0 else \
                                seed_rng(seed, 51, fold, entry["beer"], len(strategy)).choice(w.size, size=32,
                                                                                            replace=False)
                            fd = finite_difference_check(ctx, w, problem["zref"], anchor, problem["z_source"],
                                                         LAMBDA, ETA, coords)
                            gradient_checks.append({"repeat": int(repeat), "fold": int(fold),
                                                    "source_beer": int(entry["beer"]), "strategy": strategy,
                                                    **fd})
                            status = "optimal" if converged else "not_converged"
                            feasible = bool(violation <= 1e-8)
                            fallback = not (converged and feasible)
                            certificate = {
                                "problem_hash": problem_hash(problem["low"], problem["up"], problem["z_source"],
                                                             problem["z_anchor"], problem["zref"], problem["arow"],
                                                             np.array([problem["stale_cap"]]), meta=meta),
                                "status": status, "feasible": feasible, "iterations": int(solved["iterations"]),
                                "objective": float(objective),
                                "primal_residual": float(solved["primal_residual"]),
                                "dual_residual": float(solved["dual_residual"]),
                                "max_constraint_violation": float(violation),
                                "kkt_stationarity_residual": float(kkt["kkt_residual"]),
                                "n_tight_constraints": int(kkt["n_tight"]),
                                "solver": "ADMM exact convex QP (t eliminated at t=|z-z_source|); w feasible by prox",
                                "lambda": float(LAMBDA), "eta": float(ETA), "anchor": meta["anchor"],
                                "n_variables": int(problem["z_source"].size),
                                "box_lower_nonneg_columns": int(LINEAR_MASK.sum()),
                                "inequality_rows": 1,
                            }
                            x_new = ctx["centre"] + ctx["scale"] * w
                            if fallback:
                                x_new = np.array(x_source, dtype=float, copy=True)
                        if certificate is not None:
                            certificates.append({"repeat": int(repeat), "fold": int(fold),
                                                 "source_beer": int(entry["beer"]), "strategy": strategy,
                                                 **certificate})
                    delivered = delivered_metrics(ctx, x_source, x_new, problem, strategy, meta)
                    feasible = bool(feasible and delivered["n_constraint_violations"] == 0 and not fallback)
                    delivered.update({"repeat": int(repeat), "fold": int(fold), "source_beer": int(entry["beer"]),
                                      "seed": seed, "strategy": strategy, "status": status,
                                      "feasible": bool(feasible), "fallback_to_source": bool(fallback),
                                      "n_constraint_violations": int(delivered["n_constraint_violations"]),
                                      "source_state": ("source value is the delivered point"
                                                       if fallback or strategy == "source-fixed"
                                                       else "constraints evaluated on the delivered point")})
                    # constraints audit
                    for name in CAPPED_CHEMISTRY:
                        j = L.FEATURE_COLS.index(name)
                        before = delivered["chemistry"][name]["physical_source"]
                        after = delivered["chemistry"][name]["physical_new"]
                        residual = max(0.0, after - before)
                        censored = problem["cap_states"][name]["censored_source"]
                        if residual > 1e-12:
                            verdict = "infeasible"
                        elif censored:
                            verdict = "not_identifiable"
                        elif name in L.DEFECT_KEYS:
                            verdict = "verified"
                        else:
                            verdict = "conditional"
                        constraint_rows.append(audit_transfer_row(
                            ctx, problem, delivered, V6.CHEM_PREFIX + name,
                            (json.load(open(_ROOT / "data/clean/q3_thresholds.json", encoding="utf-8"))["defects"]
                             [name]["unit"] if name in L.DEFECT_KEYS else "mg/L"),
                            "upper_source_value", before, x_source[j], x_new[j], residual, verdict))
                    stale_residual = max(0.0, delivered["stale_hops_new"] - delivered["stale_hops_source"]
                                         - STALE_TOL)
                    constraint_rows.append(audit_transfer_row(
                        ctx, problem, delivered, "stale_hops(ridge-proxy)", "ridge-proxy score (sensory label units)",
                        "upper_source_value_proxy", problem["source_prediction"]["stale_hops"],
                        delivered["stale_hops_source"], delivered["stale_hops_new"], stale_residual,
                        "infeasible" if stale_residual > 1e-12 else "conditional"))
                    for j in np.nonzero(LINEAR_MASK)[0]:
                        name = L.FEATURE_COLS[j]
                        value = float(x_new[j])
                        if value < -1e-12:
                            verdict = "infeasible"
                        elif np.isclose(value, 0.0, atol=1e-12):
                            verdict = "not_identifiable"
                        else:
                            verdict = "verified"
                        constraint_rows.append(audit_transfer_row(
                            ctx, problem, delivered, V6.CHEM_PREFIX + name,
                            "concentration (unit not declared)", "lower_zero", 0.0, x_source[j], x_new[j],
                            max(0.0, -value), verdict))
                    transfer_rows.append({
                        "transfer_id": "R%d-F%d-B%03d-%s" % (repeat, fold, int(entry["beer"]), strategy),
                        "repeat": int(repeat), "fold": int(fold), "source_beer": int(entry["beer"]),
                        "source_style": SOURCE_STYLE, "target_style": TARGET_STYLE, "strategy": strategy,
                        "status": status, "feasible": bool(feasible), "fallback_to_source": bool(fallback),
                        "n_constraint_violations": int(delivered["n_constraint_violations"]),
                        "lambda": float(LAMBDA), "eta": float(ETA), "anchor": meta["anchor"],
                        "target_mahalanobis": delivered["target_mahalanobis"],
                        "target_mahalanobis_legacy": delivered["target_mahalanobis_legacy_centering"],
                        "l1_change_z": delivered["l1_change_z"],
                        "mean_abs_change_z": delivered["mean_abs_change_z"],
                        "stale_hops_source": delivered["stale_hops_source"],
                        "stale_hops_new": delivered["stale_hops_new"],
                        "stale_hops_nonincreasing": delivered["stale_hops_nonincreasing"],
                        "t2n_source": delivered["t2n_source"], "t2n_new": delivered["t2n_new"],
                        "t2n_increasing": delivered["t2n_increasing"],
                        "nonincrease_all": delivered["nonincrease_all"],
                        **{("%s_stored_source" % name): delivered["chemistry"][name]["stored_source"]
                           for name in CAPPED_CHEMISTRY},
                        **{("%s_stored_new" % name): delivered["chemistry"][name]["stored_new"]
                           for name in CAPPED_CHEMISTRY},
                        **{("%s_physical_source" % name): delivered["chemistry"][name]["physical_source"]
                           for name in CAPPED_CHEMISTRY},
                        **{("%s_physical_new" % name): delivered["chemistry"][name]["physical_new"]
                           for name in CAPPED_CHEMISTRY},
                        **{("%s_nonincreasing" % name): delivered["chemistry"][name]["nonincreasing"]
                           for name in CAPPED_CHEMISTRY},
                        **{("opt__" + column): float(x_new[j]) for j, column in enumerate(L.CHEM_COLS)},
                        **{("src__" + column): float(x_source[j]) for j, column in enumerate(L.CHEM_COLS)},
                        **{("ref__" + column): float(ctx["centre"][j] + ctx["scale"][j] * ctx["z_mean"][j])
                           for j, column in enumerate(L.CHEM_COLS)},
                    })
            # ---- energy per strategy for this fold
            for strategy in STRATEGIES:
                block = [row for row in transfer_rows if row["repeat"] == repeat and row["fold"] == fold
                         and row["strategy"] == strategy and not row["fallback_to_source"]]
                if len(block) < 2:
                    continue
                gen = np.stack([(np.array([row["opt__" + column] for column in L.CHEM_COLS])
                                 - ctx["centre"]) / ctx["scale"] for row in block])
                real = ctx["Z_target"]
                m, nreal = gen.shape[0], real.shape[0]
                cross = float(cdist(gen, real).mean())
                aa = float(cdist(gen, gen).sum())
                bb = float(cdist(real, real).sum())
                V = 2.0 * cross - aa / (m * m) - bb / (nreal * nreal)
                within_gen = aa / (m * (m - 1)) if m > 1 else ctx["d_target"]
                within_real = bb / (nreal * (nreal - 1)) if nreal > 1 else ctx["d_target"]
                U = 2.0 * cross - within_gen - within_real
                energy_cells.append({"repeat": int(repeat), "fold": int(fold), "strategy": strategy,
                                     "m": int(m), "n": int(nreal), "V": float(V), "U": float(U),
                                     "d_target": ctx["d_target"], "n_nonfallback": int(m),
                                     "n_attempted": int(len([row for row in transfer_rows
                                                             if row["repeat"] == repeat and row["fold"] == fold
                                                             and row["strategy"] == strategy]))})
            per_fold.append({
                "repeat": int(repeat), "fold": int(fold),
                "nContext": int(len(context_idx)), "nTargetReference": int(len(ctx["target_rows"])),
                "nTrainingSourceRows": int(training_source.size),
                "targetMeanSelfDistance": float(self_distance),
                "targetMeanSelfDistanceLegacy": float(legacy_distance),
                "dTarget": float(ctx["d_target"]),
                "sourceBeers": [int(beers[i]) for i in source_rows_all],
                "feasibleSetNonempty": bool(all(fold_feasible)),
                "nInfeasibleSources": int(sum(1 for flag in fold_feasible if not flag)),
            })
        # per-repeat summary
        repeat_cells = [cell for cell in energy_cells if cell["repeat"] == repeat]
        repeat_primary = [cell for cell in repeat_cells if cell["strategy"] == "qp-quantile-anchor"]
        repeat_rows = [row for row in transfer_rows if row["repeat"] == repeat
                       and row["strategy"] == "qp-quantile-anchor"]
        nonfallback = [row for row in repeat_rows if not row["fallback_to_source"]]
        per_repeat_summary.append({
            "repeat": int(repeat), "seed": seed,
            "nSources": int(len(nonfallback)),
            "transfer-energy": weighted([cell["V"] for cell in repeat_primary], [cell["m"] for cell in repeat_primary]),
            "transfer-energy-U": weighted([cell["U"] for cell in repeat_primary],
                                          [cell["m"] for cell in repeat_primary]),
            "nonincrease-rate": (float(np.mean([row["nonincrease_all"] for row in nonfallback]))
                                 if nonfallback else None),
            "t2n-increases": int(sum(row["t2n_increasing"] for row in nonfallback)),
        })

    # --------------------------------------------------------------------------------- pooling
    def pool_energy(strategy):
        cells = [cell for cell in energy_cells if cell["strategy"] == strategy]
        return (weighted([cell["V"] for cell in cells], [cell["m"] for cell in cells]),
                weighted([cell["U"] for cell in cells], [cell["m"] for cell in cells]),
                weighted([cell["V"] / cell["d_target"] for cell in cells], [cell["m"] for cell in cells]),
                int(sum(cell["m"] for cell in cells)), int(sum(cell["n"] for cell in cells)))

    energy_by_strategy = {}
    for strategy in STRATEGIES:
        V, U, V_norm, m, n = pool_energy(strategy)
        per_fold_values = [{"repeat": cell["repeat"], "fold": cell["fold"], "V": cell["V"], "U": cell["U"],
                            "V_norm": cell["V"] / cell["d_target"], "m": cell["m"], "n": cell["n"]}
                           for cell in energy_cells if cell["strategy"] == strategy]
        energy_by_strategy[strategy] = {"V": V, "U": U, "V_normalized": V_norm, "nSources": m,
                                        "nTargetReference": n, "perFold": per_fold_values}
    primary = energy_by_strategy["qp-quantile-anchor"]

    nonincrease = {}
    for strategy in STRATEGIES:
        rows = [row for row in transfer_rows if row["strategy"] == strategy]
        delivered = [row for row in rows if not row["fallback_to_source"]]
        nonincrease[strategy] = {
            "nAttempted": int(len(rows)),
            "nDelivered": int(len(delivered)),
            "fallbackShare": float(len(rows) - len(delivered)) / max(len(rows), 1),
            "nonincreaseRate": (float(np.mean([row["nonincrease_all"] for row in delivered]))
                                if delivered else None),
            "nonincreaseRateIncludingFallback": (float(np.mean([row["nonincrease_all"] for row in rows]))
                                                 if rows else None),
            "perField": ({name: float(np.mean([row["%s_nonincreasing" % name] for row in delivered]))
                          for name in CAPPED_CHEMISTRY} if delivered else {}),
            "staleProxyRate": (float(np.mean([row["stale_hops_nonincreasing"] for row in delivered]))
                               if delivered else None),
            "t2nDiagnosticIncreaseShare": (float(np.mean([row["t2n_increasing"] for row in delivered]))
                                           if delivered else None),
            "meanTargetMahalanobis": (float(np.mean([row["target_mahalanobis"] for row in delivered]))
                                      if delivered else None),
            "meanL1ChangeZ": (float(np.mean([row["l1_change_z"] for row in delivered]))
                              if delivered else None),
        }

    qp_certificates = [cert for cert in certificates if cert["status"] in ("optimal", "not_converged")]
    max_primal = max((cert["primal_residual"] for cert in qp_certificates
                      if cert.get("primal_residual") is not None), default=None)
    max_dual = max((cert["dual_residual"] for cert in qp_certificates
                    if cert.get("dual_residual") is not None), default=None)
    max_violation = max((cert["max_constraint_violation"] for cert in qp_certificates
                         if cert.get("max_constraint_violation") is not None), default=None)
    gradient_max_abs = max((check["max_abs_error"] for check in gradient_checks
                            if check["max_abs_error"] is not None), default=None)
    gradient_max_rel = max((check["max_rel_error"] for check in gradient_checks
                            if check["max_rel_error"] is not None), default=None)

    metrics = {
        "transfer-energy": finite(primary["V"], "transfer-energy"),
        "transfer-energy-U": finite(primary["U"], "transfer-energy-U"),
        "transfer-energy-normalized": finite(primary["V_normalized"], "transfer-energy-normalized"),
        "target-mean-self-distance": finite(max(self_distances), "target-mean-self-distance"),
        "target-mean-self-distance-legacy": finite(max(legacy_self_distances),
                                                  "target-mean-self-distance-legacy"),
        "qp-max-primal-residual": finite(max_primal, "qp-max-primal-residual"),
        "qp-max-dual-residual": finite(max_dual, "qp-max-dual-residual"),
        "qp-max-constraint-violation": finite(max_violation, "qp-max-constraint-violation"),
        "qp-solves": int(len(qp_certificates)),
        "qp-status-optimal": int(sum(1 for cert in qp_certificates if cert["status"] == "optimal")),
        "qp-status-not-converged": int(sum(1 for cert in qp_certificates if cert["status"] == "not_converged")),
        "qp-status-infeasible": int(sum(1 for cert in certificates if cert["status"] == "infeasible")),
        "nonincrease-rate": finite(nonincrease["qp-quantile-anchor"]["nonincreaseRate"],
                                   "nonincrease-rate"),
        "nonincrease-rate-source-anchor": finite(
            nonincrease["qp-source-anchor"]["nonincreaseRate"], "nonincrease-rate-source-anchor"),
        "n-sources": int(len(source_rows_all)),
        "n-folds": int(len(per_fold)),
        "n-transfer-rows": int(len(transfer_rows)),
        "objective-gradient-fd-max-abs": finite(gradient_max_abs, "objective-gradient-fd-max-abs"),
        "objective-gradient-fd-max-rel": finite(gradient_max_rel, "objective-gradient-fd-max-rel"),
    }
    for strategy in STRATEGIES:
        value = energy_by_strategy[strategy]["V"]
        if value is not None:
            metrics["transfer-energy-%s" % strategy] = finite(value, "transfer-energy-" + strategy)
        rate = nonincrease[strategy]["nonincreaseRate"]
        if rate is not None:
            metrics["nonincrease-rate-%s" % strategy] = finite(rate, "nonincrease-rate-" + strategy)
        metrics["fallback-share-%s" % strategy] = finite(nonincrease[strategy]["fallbackShare"],
                                                         "fallback-share-" + strategy)
    # the per-field non-increase is the substantive statement; it is also a metric key
    for name in CAPPED_CHEMISTRY:
        value = nonincrease["qp-quantile-anchor"]["perField"].get(name)
        if value is not None:
            metrics["nonincrease-rate-%s" % name] = finite(value, "nonincrease-rate-" + name)
    for entry in per_repeat_summary:
        for key in ("transfer-energy", "nonincrease-rate"):
            if entry.get(key) is not None:
                metrics["%s-repeat%d" % (key, entry["repeat"])] = finite(entry[key], key)

    # --------------------------------------------------------------------------------- files
    transfer_frame = pd.DataFrame(transfer_rows)
    transfer_frame.to_csv(_RUN_DIR / "transfers.csv", index=False, lineterminator="\n")
    pd.DataFrame(constraint_rows).to_csv(_RUN_DIR / "transfer_constraints.csv", index=False,
                                         lineterminator="\n")
    with open(_RUN_DIR / "solver_certificates.jsonl", "w", encoding="utf-8") as handle:
        for record in certificates:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    emit_output("protocol", {
        "seeds": [int(V6.SEEDS[r]) for r in repeats],
        "repeats": [int(r) for r in repeats],
        "sourceStyle": SOURCE_STYLE, "targetStyle": TARGET_STYLE,
        "sourceBeers": [int(beers[i]) for i in source_rows_all],
        "splits": str(V6.SPLITS_CSV), "splitFingerprints": fingerprints,
        "fitScope": ("each outer fold: median/centre/scale/floor codes/marginals/label proxy/target reference are "
                     "fitted on that fold's TRAINING rows only, with the source style excluded; the source beers "
                     "are query inputs"),
        "nComponents": int(N_COMPONENTS), "kappa": float(KAPPA),
        "lambda": float(LAMBDA), "eta": float(ETA),
        "solver": ("exact ADMM for the declared convex QP: primal-dual, exact box+half-space prox by bisection, "
                   "Woodbury solve for the rank-10 quadratic; t eliminated at t=|z-z_source| because eta>0"),
        "solverRejected": ("scipy.optimize.minimize SLSQP was benchmarked on the 462-variable form (z and t): "
                           "26-31 s per solve at status=8 with constraint violations up to 7e-4, so it is not used"),
        "qp": ("min (z-zref)' Q_t (z-zref) + lambda||z-z_anchor||^2 + eta*sum(t), s.t. -t<=z-z_source<=t, t>=0, "
               "l<=z<=u, A z<=b; Q_t = P' diag(1/sd)^2 Sigma_corr^-1 diag(1/sd)^2 P (rank 10)"),
        "anchors": {"qp-source-anchor": "the declared literal anchor z_source",
                    "qp-quantile-anchor": ("the source beer mapped through its own marginal ranks onto the target "
                                           "marginals (source quantiles preserved against the target reference); "
                                           "this is the delivered variant")},
        "constraints": {
            "box": "declared observed training support; the 33 LINEAR_CALIBRATED columns are also >= 0",
            "chemistryCaps": {name: "c_new <= c_source (physical), verifiable source value" for name in
                              L.DEFECT_KEYS},
            "chemicalNonIncrease": {"column": NONENAL, "rule": "c_new <= c_source (a measured column, not t2n)"},
            "proxyRow": {"column": "stale_hops", "rule": "linear ridge proxy <= source prediction + 1e-9",
                         "state": "PROXY, not a chemical measurement"},
            "t2n": "diagnostic only, never a constraint",
        },
        "centering": ("score(z) = ((z - z_mean) P - score_mean)/score_sd; the fitted z_mean is subtracted both in "
                      "the objective and in every reported distance (the v5 defect was the missing subtraction)"),
    })
    emit_output("per_fold", per_fold)
    emit_output("per_repeat", per_repeat_summary)
    emit_output("energy_by_strategy", energy_by_strategy)
    emit_output("nonincrease_by_strategy", nonincrease)
    emit_output("certificates_summary", {
        "solves": len(qp_certificates), "infeasible": int(sum(1 for cert in certificates
                                                             if cert["status"] == "infeasible")),
        "statusCounts": {status: int(sum(1 for cert in qp_certificates if cert["status"] == status))
                         for status in ("optimal", "not_converged")},
        "maxPrimalResidual": max_primal, "maxDualResidual": max_dual,
        "maxConstraintViolation": max_violation,
        "maxIterations": int(max((cert["iterations"] for cert in qp_certificates), default=0)),
        "maxKktStationarityResidual": max((cert.get("kkt_stationarity_residual") or 0.0)
                                          for cert in qp_certificates),
        "residualDefinitions": {
            "primal_residual": "max |z - w|_inf of the ADMM consensus split (w is feasible by construction)",
            "dual_residual": "rho * max |w_k - w_{k-1}|_inf, the scaled ADMM dual residual (A = I)",
            "kkt_stationarity_residual": ("norm of grad_smooth + eta*subgrad(L1) + A_tight' lambda with lambda>=0 "
                                          "from NNLS on the tight constraint rows; the L1 subgradient is 0 on the "
                                          "kink so the set-valued condition is respected"),
        },
    })
    emit_output("objective_gradient_check", {
        "method": "central finite differences (h=1e-6) against the analytic gradient of the implemented objective",
        "maxAbsError": gradient_max_abs, "maxRelError": gradient_max_rel,
        "checks": gradient_checks,
        "explanation": ("the objective is a rank-10 quadratic plus lambda*L2 plus eta*L1; it is smooth except at the "
                        "L1 kink |z_i-z_source,i|=0. At those coordinates the central difference returns the secant "
                        "subgradient, which is why the kink coordinates are counted and excluded from the relative "
                        "error instead of being averaged away"),
    })
    emit_output("target_mean_assertion", {
        "assertion": "target mean to itself < 1e-8 with the fixed centring",
        "maxObserved": max(self_distances), "maxObservedLegacyCentering": max(legacy_self_distances),
        "perFold": [{"repeat": row["repeat"], "fold": row["fold"],
                     "fixed": row["targetMeanSelfDistance"], "legacy": row["targetMeanSelfDistanceLegacy"]}
                    for row in per_fold],
        "oldValueFromIndependentRecheck": 0.6044870518234862,
    })
    emit_output("notes", [
        "source-fixed and target-mean-projection are references: they never pass through the QP, so their constraint "
        "verdicts are statements about the reference point, not about an optimiser success.",
        "target-mean-projection enforces only the box, so it can (and does) violate the non-increase caps; that is "
        "exactly why the QP exists.",
        "a solve that does not meet the tolerance is labelled status=not_converged/infeasible, the delivered point is "
        "the SOURCE point, and the row is marked fallback_to_source=True: 'migration not completed', never a success.",
        "the stale_hops constraint is a training-internal linear proxy and is reported as a proxy, not a chemical or "
        "sensory measurement.",
        "trans-2-nonenal (the measured column) carries the non-increase statement for the oxidation defect; the t2n "
        "sensory proxy is reported as a diagnostic and its increases are counted, not hidden.",
        "the energy statistic here is V = 2*mean d(G,R) - sum d(G,G)/m^2 - sum d(R,R)/n^2 and U = 2*mean d(G,R) - "
        "mean d(G,G) - mean d(R,R) (signed, can be negative; never clipped or square-rooted).",
        "the 231 stored chemical columns are used as-is; the 226+5 derived-feature identities are NOT verified here.",
    ])
    flush_outputs()

    for entry in per_repeat_summary:
        payload = {"seed": entry["seed"], "repeat": entry["repeat"], "n_sources": entry["nSources"],
                   "transfer-energy": entry["transfer-energy"], "transfer-energy-U": entry["transfer-energy-U"],
                   "nonincrease-rate": entry["nonincrease-rate"], "t2n-increases": entry["t2n-increases"],
                   "qp-max-primal-residual": max_primal, "qp-max-dual-residual": max_dual}
        V6.write_json(_RUN_DIR / ("run-seed-%d.json" % entry["seed"]), payload)

    emit_metrics(metrics)
    elapsed = time.time() - started
    print("[q3_transfer_fix] repeats=%s rows=%d solves=%d elapsed=%.1fs" % (
        repeats, len(transfer_rows), len(qp_certificates), elapsed))
    for key in ("transfer-energy", "transfer-energy-U", "transfer-energy-normalized",
                "target-mean-self-distance", "target-mean-self-distance-legacy",
                "qp-max-primal-residual", "qp-max-dual-residual", "qp-max-constraint-violation",
                "nonincrease-rate", "nonincrease-rate-source-anchor",
                "objective-gradient-fd-max-abs", "objective-gradient-fd-max-rel",
                "qp-status-optimal", "qp-status-not-converged", "qp-status-infeasible"):
        print("  %-42s %s" % (key, metrics.get(key)))
    for strategy in STRATEGIES:
        print("  energy[%s] V=%.4f U=%.4f nonincrease=%s" % (
            strategy, energy_by_strategy[strategy]["V"] or float("nan"),
            energy_by_strategy[strategy]["U"] or float("nan"),
            nonincrease[strategy]["nonincreaseRate"]))
    return metrics


if __name__ == "__main__":
    main()
