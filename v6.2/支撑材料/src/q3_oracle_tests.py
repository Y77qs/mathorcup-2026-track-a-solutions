#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""q3_oracle_tests.py — small, exact oracle checks for the v6 Q3 corrections.

This is NOT evidence about the real experiments; it is the "cheap known-answer" layer that must hold before the
198-QP batch and the generator are believable. Every check states the identity it proves, uses a case whose answer is
known independently of the production code, and prints PASS/FAIL:

  1. half-space intercept (positive AND negative c): the declared row is a'z_new <= b with
     b = a'z_source + TOl = f(z_source) - c + tol, and f(z_new) - f(z_source) equals (a'z_new - b) + tol exactly.
     The pre-v6 b (f(z_source)+tol) is shown to be wrong by exactly -c, and `problem_hash` is shown to consume b.
  2. NA / floor / imputation separation: a missing or floor-coded SOURCE cell is not_identifiable and is excluded from
     the verified denominator, while its numeric bound check is labelled conditional; a measured cell is verified.
  3. unimputed marginals: an imputed value never enters the empirical sample/support; per-(style, column) valid counts
     equal the raw mask; omega = n_eff/(n_eff+kappa) uses valid counts (not the style row count) and falls back to the
     declared pooled marginal below MIN_STYLE_OBS.
  4. inner selection V: V = 2 mean d(G,R) - sum d(G,G)/m^2 - sum d(R,R)/n^2, U signed, V - U has the exact closed form,
     U can be negative while V stays positive, and the inner selection scores with the same helper and D_train as the
     outer table.
  5. `_project_box_halfspace`: the projection lands in the box AND below the half-space, leaves an already feasible
     point alone, and refuses an empty intersection.

Run (the same environment as the scripts):
    python src/q3_oracle_tests.py
Environment is defaulted below so a plain run writes only under state/devrun/q3_v6fix/oracle_tests.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
os.environ.setdefault("MODELING_PROJECT_DIR", str(_ROOT))
os.environ.setdefault("MODELING_EXPERIMENT_DIR", str(_ROOT / "state/devrun/q3_v6fix/oracle_tests"))
os.environ.setdefault("MODELING_DATA_FILE", str(_ROOT / "data/clean/q3.csv"))
os.environ.setdefault("MODELING_SEED", "20261025")
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import q3_lib as L            # noqa: E402
import q3_fix as QF           # noqa: E402
import q3_transfer_fix as QT  # noqa: E402

N = len(L.FEATURE_COLS)
PASSES = []
FAILURES = []


def check(name, condition, detail=""):
    if condition:
        PASSES.append(name)
        print("PASS  %-72s %s" % (name, detail))
    else:
        FAILURES.append((name, detail))
        print("FAIL  %-72s %s" % (name, detail))


class FakeProxy:
    """A stand-in ridge proxy with an exactly known affine form (so the intercept algebra is testable)."""

    def __init__(self, coef, intercept):
        self.coef = np.asarray(coef, dtype=float)
        self.intercept = float(intercept)

    def coef_for(self, target):
        return self.coef

    def intercept_for(self, target):
        return self.intercept

    def predict_storage(self, X, target=None):
        X = np.asarray(X, dtype=float)
        return X @ self.coef + self.intercept


def make_ctx(coef, intercept, codes=None, lo_value=-10.0, hi_value=10.0):
    identity = np.eye(N)   # the delivered-metric path needs a score map; the identity keeps every distance exact
    return {"centre": np.zeros(N), "scale": np.ones(N),
            "lo": np.full(N, lo_value), "hi": np.full(N, hi_value),
            "low_z": np.full(N, -5.0), "up_z": np.full(N, 5.0), "z_mean": np.zeros(N),
            "pca": identity, "pm": identity, "correlation_inv": identity,
            "score_mean": np.zeros(N), "score_sd": np.ones(N),
            "codes": dict(codes or {}), "proxy": FakeProxy(coef, intercept)}


def base_source():
    """A storage-scale source row whose capped columns are ordinary measured values."""
    row = np.zeros(N)
    row[L.FEATURE_COLS.index("DMS")] = 0.5
    row[L.FEATURE_COLS.index("X2.3.butanedione")] = 0.5
    row[L.FEATURE_COLS.index("X4VG")] = -4.0
    row[L.FEATURE_COLS.index("X.E..2.nonenal")] = 0.01
    return row


# --------------------------------------------------------------------------------- 1. half-space intercept
def test_halfspace_intercept():
    direction = np.zeros(N)
    direction[L.FEATURE_COLS.index("DMS") + 7] = 2.0
    source = base_source()
    for label, intercept_c in (("positive", 0.3), ("negative", -0.4)):
        ctx = make_ctx(direction, intercept_c)
        problem = QT.build_problem(ctx, source, source, x_raw_source=source)
        z_source = problem["z_source"]
        f_source = float(direction @ z_source + intercept_c)
        b = float(problem["stale_cap"])
        b_expected = float(direction @ z_source + QT.STALE_TOL)
        b_old = float(problem["stale_cap_old_definition"])
        check("halfspace[%s]: b == a'z_source + tol" % label, abs(b - b_expected) <= 1e-12,
              "b=%.12g" % b)
        check("halfspace[%s]: b == f(z_source) - c + tol" % label,
              abs(b - (f_source - intercept_c + QT.STALE_TOL)) <= 1e-12)
        check("halfspace[%s]: recorded c and a'z_source match" % label,
              abs(problem["stale_intercept_c"] - intercept_c) <= 1e-15
              and abs(problem["stale_a_dot_source"] - float(direction @ z_source)) <= 1e-12)
        # b_old = f(z_source)+tol and b = f(z_source)-c+tol, so b_old - b == c exactly
        check("halfspace[%s]: pre-v6 b is off by exactly +c" % label,
              abs((b_old - b) - intercept_c) <= 1e-12, "b_old-b=%.3g, c=%.3g" % (b_old - b, intercept_c))

        # the whole point of the fix: the two forms of "not worse" agree for ANY candidate point
        rng = np.random.default_rng(7)
        for trial in range(5):
            z_new = np.clip(z_source + rng.normal(scale=0.5, size=N), problem["low"], problem["up"])
            x_new = z_new  # centre=0, scale=1
            f_new = float(direction @ z_new + intercept_c)
            residual = float(direction @ z_new - b)
            check("halfspace[%s] trial%d: f(z_new)-f(z_source) == (a'z_new-b)+tol" % (label, trial),
                  abs((f_new - f_source) - (residual + QT.STALE_TOL)) <= 1e-12,
                  "gap=%.3g" % ((f_new - f_source) - (residual + QT.STALE_TOL)))
            delivered = QT.delivered_metrics(ctx, source, x_new, problem, "oracle", {})
            check("halfspace[%s] trial%d: delivered residual equals a'z_new-b" % (label, trial),
                  abs(delivered["stale_halfspace_residual"] - residual) <= 1e-12)
            check("halfspace[%s] trial%d: delivered delta equals f(z_new)-f(z_source)" % (label, trial),
                  abs(delivered["stale_prediction_delta"] - (f_new - f_source)) <= 1e-12)
            check("halfspace[%s] trial%d: production identity error ~ 0" % (label, trial),
                  delivered["stale_halfspace_identity_error"] <= 1e-9)

        # problem_hash must consume the corrected b: two different b values cannot share a hash
        digest = lambda value: QT.problem_hash(problem["low"], problem["up"], problem["z_source"],
                                               problem["z_anchor"], problem["zref"], problem["arow"],
                                               np.array([value]), meta={"repeat": 0, "fold": 0})
        check("halfspace[%s]: problem_hash consumes b (new b != old b hash)" % label, digest(b) != digest(b_old))


# --------------------------------------------------------------------------------- 2. NA/floor/imputation states
def test_source_state_verdicts():
    ctx = make_ctx(np.zeros(N), 0.0, codes={"X4VG": -2.0})
    raw = base_source()
    raw[L.FEATURE_COLS.index("X2.3.butanedione")] = np.nan      # source cell missing -> training-median imputation
    raw[L.FEATURE_COLS.index("X4VG")] = -2.0                    # source cell is a non-detect code
    imputed = raw.copy()
    imputed[L.FEATURE_COLS.index("X2.3.butanedione")] = 0.247   # stands in for the fold training median
    caps, states = QT.chemistry_caps(ctx, imputed, raw)
    check("source-state: missing butanedione is_na", states["X2.3.butanedione"]["is_na"] is True)
    check("source-state: missing butanedione basis is training median",
          states["X2.3.butanedione"]["imputation_basis"] == "training_fold_median")
    check("source-state: missing butanedione keeps the raw value as None",
          states["X2.3.butanedione"]["raw_source_value"] is None)
    check("source-state: floor-coded 4VG is_floor", states["X4VG"]["is_floor"] is True)
    check("source-state: measured DMS is neither NA nor floor",
          states["DMS"]["is_na"] is False and states["DMS"]["is_floor"] is False)

    verdicts = {
        "DMS(measured)": QT.source_nonincreasing_verdict(0.0, states["DMS"], "DMS"),
        "butanedione(missing)": QT.source_nonincreasing_verdict(0.0, states["X2.3.butanedione"],
                                                                "X2.3.butanedione"),
        "X4VG(floor)": QT.source_nonincreasing_verdict(0.0, states["X4VG"], "X4VG"),
        "nonenal(measured)": QT.source_nonincreasing_verdict(0.0, states["X.E..2.nonenal"], "X.E..2.nonenal"),
        "DMS(violated)": QT.source_nonincreasing_verdict(1.0, states["DMS"], "DMS"),
    }
    check("verdict: measured defect is verified", verdicts["DMS(measured)"] == "verified")
    check("verdict: missing source is not_identifiable", verdicts["butanedione(missing)"] == "not_identifiable")
    check("verdict: floor-coded source is not_identifiable", verdicts["X4VG(floor)"] == "not_identifiable")
    check("verdict: measured nonenal is conditional on its storage->concentration convention",
          verdicts["nonenal(measured)"] == "conditional")
    check("verdict: a numeric violation is failed", verdicts["DMS(violated)"] == "failed")

    check("bound-check: missing source is conditional_on_imputation",
          QT.bound_check_verdict(0.0, states["X2.3.butanedione"]) == "conditional_on_imputation")
    check("bound-check: floor source is conditional_floor_code",
          QT.bound_check_verdict(0.0, states["X4VG"]) == "conditional_floor_code")
    check("bound-check: measured source is verified", QT.bound_check_verdict(0.0, states["DMS"]) == "verified")
    check("bound-check: violation is failed", QT.bound_check_verdict(1.0, states["DMS"]) == "failed")

    # the verified denominator must exclude the unidentified records (this is the pre-v6 defect)
    records = list(verdicts.values())[:4]
    verified = sum(1 for value in records if value == "verified")
    identifiable = sum(1 for value in records if value != "not_identifiable")
    check("verdict: NA/floor excluded from the verified denominator", verified == 1 and identifiable == 2,
          "verified=%d identifiable=%d" % (verified, identifiable))


# --------------------------------------------------------------------------------- 3. unimputed marginals
def test_unimputed_marginals():
    rows, cols = 5, N
    matrix = np.zeros((rows, cols))
    matrix[:, 0] = [1.0, 2.0, 3.0, 4.0, 5.0]
    matrix[:, 1] = [2.0, 4.0, 8.0, 40.0, np.nan]    # imputed median = 6.0, which is NOT an observed value
    valid = np.isfinite(matrix)
    imputed = L.apply_median(matrix, L.column_medians(matrix))
    check("marginal: median imputation really produces the unseen value 6.0",
          abs(imputed[4, 1] - 6.0) <= 1e-12)
    styles = np.array(["a"] * rows)
    masked = L.StyleMarginals(5.0, {}).fit(imputed, styles, valid=valid)
    legacy = L.StyleMarginals(5.0, {}).fit(imputed, styles)          # no mask -> imputed value enters the sample
    check("marginal: imputed 6.0 absent from the valid-only support",
          6.0 not in set(np.round(masked.marg["a"][1].grid_x, 12)))
    check("marginal: imputed 6.0 present in the unmasked (legacy) support",
          6.0 in set(np.round(legacy.marg["a"][1].grid_x, 12)))
    check("marginal: valid count excludes the NaN cell", masked.state[1]["n_valid"] == 4,
          "n_valid=%d" % masked.state[1]["n_valid"])
    check("marginal: continuous denominator equals the valid count", masked.state[1]["n_continuous"] == 4)
    expected_u = [-0.5, 0.5, 1.5, 2.5, 1e9]
    del expected_u
    u_values = masked.marg["a"][1].grid_u
    check("marginal: the empirical CDF uses mid-ranks of the 4 VALID observations only",
          np.allclose(u_values, [1.0 / 8, 3.0 / 8, 5.0 / 8, 7.0 / 8], atol=1e-12),
          "u=%s" % np.round(u_values, 6).tolist())

    # omega must use n_eff, not the style row count
    matrix2 = np.zeros((6, N))
    matrix2[:, 0] = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    matrix2[3:, 0] = np.nan                          # 3 valid observations of column 0, 6 style rows
    valid2 = np.isfinite(matrix2)
    imputed2 = L.apply_median(matrix2, L.column_medians(matrix2))
    small = L.StyleMarginals(5.0, {}).fit(imputed2, np.array(["a"] * 6), valid=valid2)
    check("marginal: omega uses n_eff (3) not the style row count (6)",
          abs(small.state[0]["omega"] - 3.0 / (3.0 + 5.0)) <= 1e-15
          and abs(small.state[0]["omega"] - 6.0 / (6.0 + 5.0)) > 1e-6,
          "omega=%.6g" % small.state[0]["omega"])
    matrix2b = matrix2.copy()
    matrix2b[2:, 0] = np.nan                         # only 2 valid observations -> declared pooled fallback
    valid2b = np.isfinite(matrix2b)
    imputed2b = L.apply_median(matrix2b, L.column_medians(matrix2b))
    small_b = L.StyleMarginals(5.0, {}).fit(imputed2b, np.array(["a"] * 6), valid=valid2b)
    check("marginal: n_valid below MIN_STYLE_OBS falls back to the pooled marginal",
          small_b.state[0]["status"].startswith("pooled_fallback") and small_b.state[0]["omega"] == 0.0)
    check("marginal: the pooled fallback is counted in the summary",
          small_b.summary["nPooledFallbackCells"] >= 1)

    # floor two-part mixture: the atom mass uses n_valid, the continuous part uses n_continuous
    matrix3 = np.zeros((4, N))
    code = -2.0
    matrix3[:, 0] = [code, code, 1.0, 2.0]
    valid3 = np.ones((4, N), dtype=bool)
    floored = L.StyleMarginals(0.0, {L.FEATURE_COLS[0]: code}).fit(matrix3, np.array(["a"] * 4), valid=valid3)
    state = floored.state[0]
    check("floor: mass denominator is n_valid and floor count is explicit",
          state["n_valid"] == 4 and state["n_floor"] == 2 and
          abs(state["pi_style_floor"] - 0.5) <= 1e-12,
          "n_valid=%d n_floor=%d pi=%.3g" % (state["n_valid"], state["n_floor"], state["pi_style_floor"]))
    check("floor: continuous denominator is the non-floor count",
          state["n_continuous"] == 2 and state["continuous_denominator"] == 2)
    check("floor: floor code detection matches the declared code map",
          bool(L.floor_mask(matrix3, {L.FEATURE_COLS[0]: code})[:2, 0].all()))

    # real data: every (style, column) valid count must equal the raw mask
    frame = __import__("pandas").read_csv(_ROOT / "data/clean/q3.csv")
    raw = frame[L.CHEM_COLS].to_numpy(dtype=float)
    style_array = frame["tasting_category_fine"].astype(str).to_numpy()
    raw_valid = np.isfinite(raw)
    real = L.StyleMarginals(5.0, {}).fit(L.apply_median(raw, L.column_medians(raw)), style_array,
                                         valid=raw_valid)
    mismatches = 0
    for record in real.state:
        rows_of_style = np.nonzero(style_array == record["style"])[0]
        j = L.FEATURE_COLS.index(record["column"])
        if int(raw_valid[rows_of_style, j].sum()) != record["n_valid"]:
            mismatches += 1
    check("marginal(real data): per-(style,column) n_valid equals the raw mask everywhere",
          mismatches == 0, "cells=%d mismatches=%d" % (len(real.state), mismatches))
    n_missing_cells = int((~raw_valid).sum())
    n_style_missing = int(sum(record["n_style_rows"] - record["n_valid"] for record in real.state))
    check("marginal(real data): the missing cells are excluded from the style samples exactly once",
          n_style_missing == n_missing_cells, "style=missing=%d, file missing=%d" % (n_style_missing, n_missing_cells))


# --------------------------------------------------------------------------------- 4. energy V / U and inner wiring
def test_energy_v_u():
    real = np.array([[-1.0], [1.0]])
    gen = np.array([[-10.0], [10.0]])
    terms = L.energy_distance_terms(gen, real)
    check("energy: V uses the sum form 2cross - aa/m^2 - bb/n^2",
          abs(terms["V"] - (2.0 * 10.0 - 40.0 / 4.0 - 4.0 / 4.0)) <= 1e-12, "V=%.6g" % terms["V"])
    check("energy: U is signed and can be negative while V stays positive",
          terms["U"] < 0.0 < terms["V"], "V=%.6g U=%.6g" % (terms["V"], terms["U"]))
    gap = terms["V"] - terms["U"]
    closed = (terms["sum_gen"] / (terms["m"] ** 2 * (terms["m"] - 1))
              + terms["sum_real"] / (terms["n"] ** 2 * (terms["n"] - 1)))
    check("energy: V - U equals the exact closed form (so V >= U for m,n >= 2)",
          abs(gap - closed) <= 1e-12, "gap=%.6g closed=%.6g" % (gap, closed))

    rng = np.random.default_rng(11)
    A = rng.normal(size=(17, 5))
    B = rng.normal(size=(23, 5))
    outer = QF.energy_statistics(A, B, 1.0)
    shared = L.energy_distance_terms(A, B)
    check("energy: the outer table uses the shared definition",
          abs(outer["V"] - shared["V"]) <= 1e-12 and abs(outer["U"] - shared["U"]) <= 1e-12)

    styles = np.array(["a", "a", "a", "b", "b"])
    Z = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [5.0, 5.0], [6.0, 5.0]])
    d_a = L.style_dtrain(Z, styles, "a")
    manual = (np.linalg.norm(Z[0] - Z[1]) + np.linalg.norm(Z[0] - Z[2]) + np.linalg.norm(Z[1] - Z[2])) / 3.0
    check("energy: D_train is the mean pairwise distance of the style's rows", abs(d_a - manual) <= 1e-12)
    single = L.style_dtrain(np.array([[0.0], [1.0], [3.0]]), np.array(["a", "b", "b"]), "a")
    pooled = (1.0 + 3.0 + 2.0) / 3.0
    check("energy: D_train falls back to the pooled rows for a 1-row style", abs(single - pooled) <= 1e-12)

    inner_source = inspect.getsource(QF.select_hyperparameters_inner)
    check("energy: the inner selection scores with the shared V helper",
          "energy_distance_terms" in inner_source)
    check("energy: the inner selection normalises with the shared D_train",
          "style_dtrain" in inner_source)
    check("energy: the inner selection no longer calls the old sqrt(max(U,0)/dref) metric",
          "normalized_energy_distance" not in inner_source)


# --------------------------------------------------------------------------------- 5. box ∩ half-space projection
def test_projection():
    rng = np.random.default_rng(3)
    arow = rng.normal(size=N)
    low = np.full(N, -1.0)
    up = np.full(N, 1.0)
    point = rng.normal(scale=2.0, size=N)
    b = float(arow @ np.zeros(N))              # a tight but feasible row (0 satisfies it)
    projected = QT._project_box_halfspace(point, low, up, arow, b)
    check("projection: inside the box", bool(np.all(projected >= low - 1e-12) and np.all(projected <= up + 1e-12)))
    check("projection: below the half-space", float(arow @ projected) <= b + 1e-9,
          "a'w-b=%.3g" % (float(arow @ projected) - b))
    inside = np.clip(point, low, up)
    if float(arow @ inside) <= b:
        check("projection: an already feasible point is only box-clipped",
              bool(np.allclose(QT._project_box_halfspace(inside, low, up, arow, b), inside, atol=0, rtol=0)))
    raised = False
    try:
        QT._project_box_halfspace(point, np.zeros(N), np.ones(N), np.ones(N), -1.0)
    except RuntimeError:
        raised = True
    check("projection: an empty box ∩ half-space is refused by name", raised)


def main() -> int:
    print("oracle checks for the v6 Q3 corrections (numpy %s)" % np.__version__)
    test_halfspace_intercept()
    test_source_state_verdicts()
    test_unimputed_marginals()
    test_energy_v_u()
    test_projection()
    print("\n%d passed, %d failed" % (len(PASSES), len(FAILURES)))
    if FAILURES:
        for name, detail in FAILURES:
            print("  FAILED: %s  %s" % (name, detail))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
