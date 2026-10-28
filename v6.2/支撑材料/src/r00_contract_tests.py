# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""r00_contract_tests.py — small synthetic oracles: does the code compute the declared model?

Every test uses synthetic data with a known analytical answer, or frozen metadata invariants.
Nothing here touches the contest training data for fitting and nothing here is a performance
claim. This is the "算的是否真是写的模型" gate: if the implementation and the declared
mathematics disagree, a smaller validation number is meaningless.

Tests
  1 graph_reduced_rank   min ||Yc-ZcB||^2/n + lam||B||^2 + gam tr(B'LB)  s.t. rank(B) <= r
                         closed form B = A^{-1} C Vr Vr'  (A = Zc'Zc/n + lam I + gam L,
                         C = Zc'Yc/n): attained analytic lower bound, Cholesky and eigen
                         factorisations agree, r = min(n,p) reduces to graph ridge, gam = 0
                         reduces to ordinary ridge, L = diag(sum|W|)-W is PSD.
  2 qp_active_set        min 1/2||z-z0||^2 s.t. l<=z<=u, Az<=b: SLSQP with analytic jacobian
                         cross-checked against exhaustive active-set KKT enumeration (unique
                         solution), with primal/dual/complementarity residuals reported.
  3 energy_toy           two groups both {0,1}: unbiased U = -1, empirical V = 0, sign kept.
  4 gradient_fd          composite objective with a box projection: analytic gradient vs central
                         finite differences, smooth region required, active-clip case reported.
  5 split_invariants     NESTED-CV-1: 3x3x3, train/test disjoint, inner inside outer training,
                         every (repeat, outer) covers all 250 rows, manifest seeds vs
                         contest.yaml evaluation.tuning.
  6 ridge_equivalence    plain Ridge (gam=0, r=50) vs graph Ridge at the same lam: the difference
                         is exactly the added gam*L term.

Run:  python src/r00_contract_tests.py
Writes: outputs/contracts/v6/contract_tests.json
        outputs/audit/v6/contract_tests.json   (byte-identical mirror)
Exit: 0 all six tests pass; 5 one or more failed (each failure named on stderr).
"""

from __future__ import annotations

import datetime
import itertools
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True  # never leave new build artefacts under src/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import v6_common  # noqa: E402

PROJECT = v6_common.PROJECT
PRIMARY = PROJECT / "outputs/contracts/v6"
MIRROR = PROJECT / "outputs/audit/v6"

TOL_ALGEBRA = 1e-10
TOL_FD = 1e-6


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


# -------------------------------------------------------------------------------------- test 1
def _graph_solve(zc: np.ndarray, yc: np.ndarray, lam: float, gam: float, lap: np.ndarray,
                 rank: int) -> dict:
    n, p = zc.shape
    a = zc.T @ zc / n + lam * np.eye(p) + gam * lap
    c = zc.T @ yc / n
    full = np.linalg.solve(a, c)
    # eigen route: top-r eigenvectors of C'A^{-1}C
    _, vectors = np.linalg.eigh(c.T @ full)
    vectors = vectors[:, ::-1][:, :rank]
    beta_eigen = full @ vectors @ vectors.T
    # Cholesky route: A = L L', SVD of L^{-1} C, truncate, back-substitute
    chol = np.linalg.cholesky(a)
    m = np.linalg.solve(chol, c)
    u, s, vt = np.linalg.svd(m, full_matrices=False)
    truncated = (u[:, :rank] * s[:rank]) @ vt[:rank]
    beta_chol = np.linalg.solve(chol.T, truncated)
    return {"A": a, "C": c, "full": full, "eigen": beta_eigen, "chol": beta_chol,
            "singularValues": s}


def _graph_objective(beta, zc, yc, lam, gam, lap):
    n = zc.shape[0]
    return (float(np.sum((yc - zc @ beta) ** 2) / n) + lam * float(np.sum(beta ** 2))
            + gam * float(np.trace(beta.T @ lap @ beta)))


def test_graph_reduced_rank() -> dict:
    rng = np.random.default_rng(20261025)
    n, p, q, rank = 23, 8, 5, 2
    z = rng.normal(size=(n, p)) + np.arange(p)
    y = rng.normal(size=(n, q)) + np.arange(q)
    zc, yc = z - z.mean(0), y - y.mean(0)
    weights = np.abs(rng.normal(size=(p, p)))
    weights = (weights + weights.T) / 2.0
    np.fill_diagonal(weights, 0.0)
    lap = np.diag(weights.sum(axis=1)) - weights
    lam, gam = 0.7, 0.3

    solved = _graph_solve(zc, yc, lam, gam, lap, rank)
    lower_bound = float(np.sum(yc ** 2) / n - np.sum(solved["singularValues"][:rank] ** 2))
    attained = _graph_objective(solved["eigen"], zc, yc, lam, gam, lap)

    # a random rank-r competitor must be no better than the bound
    competitor = _graph_solve(zc, yc, lam, gam, lap, rank)["full"] @ rng.normal(size=(q, rank)) \
        @ rng.normal(size=(rank, q))
    competitor_objective = _graph_objective(competitor, zc, yc, lam, gam, lap)

    # r = min(n,p) must equal graph ridge; gam = 0 must equal ordinary ridge
    full_rank = min(n, p)
    graph_ridge = _graph_solve(zc, yc, lam, gam, lap, full_rank)
    graph_ridge_gap = float(np.max(np.abs(graph_ridge["eigen"] - graph_ridge["full"])))
    ridge_plain = np.linalg.solve(zc.T @ zc / n + lam * np.eye(p), zc.T @ yc / n)
    gam0 = _graph_solve(zc, yc, lam, 0.0, lap, q)
    ridge_gap = float(np.max(np.abs(gam0["eigen"] - ridge_plain)))

    # L is PSD and equals 1/2 sum_ij w_ij (z_i - z_j)^2
    psd_min = math.inf
    identity_gap = 0.0
    null_vector = np.ones(p)
    null_vector_quadratic = float(null_vector @ lap @ null_vector)
    for _ in range(200):
        probe = rng.normal(size=p)
        quadratic = float(probe @ lap @ probe)
        psd_min = min(psd_min, quadratic)
        difference = 0.0
        for i in range(p):
            for j in range(p):
                difference += 0.5 * weights[i, j] * (probe[i] - probe[j]) ** 2
        identity_gap = max(identity_gap, abs(quadratic - difference))

    checks = {
        "objectiveGapToAnalyticBound": abs(attained - lower_bound),
        "factorisationGap": float(np.max(np.abs(solved["eigen"] - solved["chol"]))),
        "matrixRank": int(np.linalg.matrix_rank(solved["eigen"], tol=1e-9)),
        "competitorObjectiveAboveBound": float(competitor_objective - lower_bound),
        "graphRidgeGapAtFullRank": graph_ridge_gap,
        "plainRidgeGapAtGammaZero": ridge_gap,
        "laplacianQuadraticFormMin": float(psd_min),
        "laplacianNullVectorQuadratic": null_vector_quadratic,
        "laplacianIdentityGap": float(identity_gap),
    }
    passed = (
        checks["objectiveGapToAnalyticBound"] <= TOL_ALGEBRA
        and checks["factorisationGap"] <= TOL_ALGEBRA
        and checks["matrixRank"] <= rank
        and checks["competitorObjectiveAboveBound"] >= -TOL_ALGEBRA
        and checks["graphRidgeGapAtFullRank"] <= TOL_ALGEBRA
        and checks["plainRidgeGapAtGammaZero"] <= TOL_ALGEBRA
        and checks["laplacianQuadraticFormMin"] >= -TOL_ALGEBRA
        and abs(checks["laplacianNullVectorQuadratic"]) <= TOL_ALGEBRA
        and checks["laplacianIdentityGap"] <= TOL_ALGEBRA
    )
    return {
        "name": "graph_reduced_rank",
        "passed": bool(passed),
        "metric": checks["objectiveGapToAnalyticBound"],
        "tolerance": TOL_ALGEBRA,
        "detail": {
            "problem": ("min ||Yc-ZcB||^2/n + lam||B||^2 + gam tr(B'LB) subject to "
                        "rank(B)<=r; closed form B = A^{-1} C Vr Vr'"),
            "dimensions": {"n": n, "p": p, "q": q, "rank": rank, "lam": lam, "gam": gam},
            "objective": attained,
            "analyticLowerBound": lower_bound,
            **checks,
            "interpretation": (
                "the implemented solver attains the analytic optimum and the two factorisations "
                "coincide; the unconstrained cases collapse to ridge exactly"),
        },
    }


# -------------------------------------------------------------------------------------- test 2
def _active_set_oracle(z0: np.ndarray, constraints: list, tol: float = 1e-9) -> list:
    """Enumerate every feasible KKT point of  min 1/2||z-z0||^2  s.t.  a_i'z <= c_i."""
    n = len(z0)
    solutions = []
    for size in range(0, n + 1):
        for subset in itertools.combinations(range(len(constraints)), size):
            if size:
                normals = np.array([constraints[i][0] for i in subset])
                offsets = np.array([constraints[i][1] for i in subset])
                gram = normals @ normals.T
                if np.linalg.matrix_rank(gram, tol=1e-12) < size:
                    continue
                multipliers = np.linalg.solve(gram, normals @ z0 - offsets)
                if np.any(multipliers < -tol):
                    continue
                point = z0 - normals.T @ multipliers
            else:
                point = z0.copy()
            if any(a @ point - c > tol for a, c in constraints):
                continue
            objective = 0.5 * float(np.sum((point - z0) ** 2))
            if not any(abs(objective - item[0]) <= 1e-9
                       and np.max(np.abs(point - item[1])) <= 1e-8 for item in solutions):
                solutions.append((objective, point))
    return solutions


def test_qp_active_set() -> dict:
    from scipy.optimize import minimize

    z0 = np.array([1.5, -0.5, 0.3, 2.0])
    lower = np.zeros(4)
    upper = np.ones(4)
    matrix = np.array([[1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 1.0]])
    rhs = np.array([1.2, 0.8])

    constraints = []
    for i in range(4):
        normal = np.zeros(4)
        normal[i] = -1.0
        constraints.append((normal, -lower[i]))          # -z_i <= -l_i
        normal = np.zeros(4)
        normal[i] = 1.0
        constraints.append((normal, upper[i]))            #  z_i <=  u_i
    for row in range(matrix.shape[0]):
        constraints.append((matrix[row].copy(), rhs[row]))

    enumeration = _active_set_oracle(z0, constraints)
    if not enumeration:
        return {"name": "qp_active_set", "passed": False, "metric": float("nan"),
                "tolerance": 1e-8,
                "detail": {"error": "active-set enumeration found no feasible KKT point"}}
    enumeration.sort(key=lambda item: item[0])
    objective_oracle, point_oracle = enumeration[0]

    objective = lambda v: 0.5 * float(np.sum((v - z0) ** 2))  # noqa: E731
    gradient = lambda v: v - z0  # noqa: E731
    scipy_constraints = [
        {"type": "ineq", "fun": (lambda v, a=a, c=c: c - float(a @ v)),
         "jac": (lambda v, a=a: -a)}
        for a, c in constraints]
    result = minimize(objective, np.zeros(4), jac=gradient, method="SLSQP",
                      bounds=list(zip(lower, upper)), constraints=scipy_constraints,
                      options={"ftol": 1e-15, "maxiter": 1000})

    point = np.asarray(result.x, dtype=float)
    primal = max(0.0, float(np.max(point - upper)), float(np.max(lower - point)),
                 float(np.max(matrix @ point - rhs)))
    active = [index for index, (a, c) in enumerate(constraints) if abs(a @ point - c) <= 1e-7]
    if active:
        normals = np.array([constraints[i][0] for i in active])
        offsets = np.array([constraints[i][1] for i in active])
        gram = normals @ normals.T
        multipliers = np.linalg.pinv(gram) @ (normals @ (z0 - point))
        stationarity = float(np.max(np.abs(point - z0 + normals.T @ multipliers)))
        complementarity = float(np.max(np.abs(multipliers * (normals @ point - offsets))))
        min_multiplier = float(np.min(multipliers))
    else:
        stationarity = float(np.max(np.abs(point - z0)))
        complementarity = 0.0
        min_multiplier = 0.0

    checks = {
        "objectiveSlSqp": objective(point),
        "objectiveOracle": objective_oracle,
        "objectiveGap": abs(objective(point) - objective_oracle),
        "solutionGap": float(np.max(np.abs(point - point_oracle))),
        "primalResidual": primal,
        "dualResidual": stationarity,
        "complementarityResidual": complementarity,
        "minMultiplier": min_multiplier,
        "distinctFeasibleKktPoints": len(enumeration),
        "scipySuccess": bool(result.success),
        "optimalPoint": [float(v) for v in point_oracle],
        "boxActive": int(np.sum((point <= lower + 1e-9) | (point >= upper - 1e-9))),
        "generalActive": int(np.sum(np.abs(matrix @ point - rhs) <= 1e-7)),
        "cvxpyAvailable": False,
    }
    passed = (checks["objectiveGap"] <= 1e-8 and checks["solutionGap"] <= 1e-7
              and checks["primalResidual"] <= 1e-8 and checks["dualResidual"] <= 1e-8
              and checks["complementarityResidual"] <= 1e-8
              and checks["minMultiplier"] >= -1e-8
              and checks["distinctFeasibleKktPoints"] == 1)
    return {
        "name": "qp_active_set",
        "passed": bool(passed),
        "metric": checks["objectiveGap"],
        "tolerance": 1e-8,
        "detail": {
            "problem": ("min 1/2||z-z0||^2 subject to 0<=z<=1 and "
                        "[[1,1,0,0],[0,0,1,1]] z <= [1.2,0.8]; strictly convex and feasible, so "
                        "the solution is unique and cross-checkable by exhaustive active sets"),
            "solverA": "scipy.optimize.minimize(SLSQP) with the analytic jacobian",
            "solverB": "exhaustive active-set KKT enumeration (cvxpy is not installed)",
            **checks,
            "kktViolation": max(checks["primalResidual"], checks["dualResidual"],
                                checks["complementarityResidual"],
                                max(0.0, -checks["minMultiplier"])),
        },
    }


# -------------------------------------------------------------------------------------- test 3
def _pairwise(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)


def energy_statistics(gen: np.ndarray, real: np.ndarray) -> dict:
    gen = np.asarray(gen, dtype=float)
    real = np.asarray(real, dtype=float)
    m, n = len(gen), len(real)
    within_gen = float(_pairwise(gen, gen).sum())
    within_real = float(_pairwise(real, real).sum())
    cross = float(2.0 * _pairwise(gen, real).mean())
    u = cross - within_gen / (m * (m - 1)) - within_real / (n * (n - 1))
    v = cross - within_gen / m**2 - within_real / n**2
    return {"U": float(u), "V": float(v), "crossMeanDistance": cross,
            "withinGenSum": within_gen, "withinRealSum": within_real}


def test_energy_toy() -> dict:
    toy = np.array([[0.0], [1.0]])
    stats = energy_statistics(toy, toy)
    # an independent hand calculation of the same two-point case
    hand_u = 1.0 - (0.0 + 1.0 + 1.0 + 0.0) / 2 - (0.0 + 1.0 + 1.0 + 0.0) / 2
    hand_v = 1.0 - (0.0 + 1.0 + 1.0 + 0.0) / 4 - (0.0 + 1.0 + 1.0 + 0.0) / 4

    rng = np.random.default_rng(20261025)
    a = rng.normal(size=(7, 3))
    b = a + 0.01 * rng.normal(size=(7, 3))
    near = energy_statistics(a, b)
    checks = {
        "U": stats["U"],
        "V": stats["V"],
        "UmatchesHand": abs(stats["U"] - hand_u),
        "VmatchesHand": abs(stats["V"] - hand_v),
        "signPreserved": stats["U"] < 0.0,
        "nearIdenticalSampleU": near["U"],
        "nearIdenticalSampleV": near["V"],
        "zeroUIndicatesIdentical": bool(abs(stats["V"]) <= 1e-12),
    }
    passed = (checks["UmatchesHand"] <= 1e-12 and checks["VmatchesHand"] <= 1e-12
              and checks["signPreserved"] and checks["zeroUIndicatesIdentical"])
    return {
        "name": "energy_toy",
        "passed": bool(passed),
        "metric": checks["U"],
        "tolerance": 1e-12,
        "detail": {
            "definition": {
                "U_unbiased": ("2 mean_ij ||g_i-r_j|| - sum_{i!=j}||g_i-g_j||/(m(m-1)) "
                               "- sum_{i!=j}||r_i-r_j||/(n(n-1))"),
                "V_empirical": ("2 mean_ij ||g_i-r_j|| - sum||g_i-g_j||/m^2 "
                                "- sum||r_i-r_j||/n^2"),
            },
            "toy": "both groups are the two points {0,1}",
            **checks,
            "interpretation": ("U = -1 and V = 0 for two identical two-point samples; a negative "
                               "U is a finite-sample property, not a bug, so clipping it to zero "
                               "and then taking a square root would silently hide it"),
        },
    }


# -------------------------------------------------------------------------------------- test 4
def test_gradient_finite_difference() -> dict:
    rng = np.random.default_rng(20261026)
    m_shape, n_dim = 6, 5
    matrix = rng.normal(size=(m_shape, n_dim))
    offset = rng.normal(size=m_shape)
    target = rng.normal(size=m_shape)
    lam = 0.35
    v_smooth = np.array([0.1, 0.2, -0.1, 0.3, 0.0])
    # choose the additive shift so that at v_smooth every row sits exactly at 0.5 (strictly inside)
    shift = 0.5 - (matrix @ v_smooth + offset)
    v_clipped = v_smooth + np.array([1.0, -1.5, 2.0, -1.0, 0.5])

    def clip(value):
        return np.clip(value, 0.0, 1.0)

    def objective(v):
        projected = clip(matrix @ v + offset + shift)
        return 0.5 * float(np.sum((projected - target) ** 2)) + 0.5 * lam * float(v @ v)

    def gradient(v):
        linear = matrix @ v + offset + shift
        active = ((linear > 0.0) & (linear < 1.0)).astype(float)
        return matrix.T @ (active * (clip(linear) - target)) + lam * v

    def fd_gradient(v, h=1e-6):
        out = np.zeros_like(v)
        for i in range(len(v)):
            step = np.zeros_like(v)
            step[i] = h
            out[i] = (objective(v + step) - objective(v - step)) / (2 * h)
        return out

    def compare(v):
        analytic = gradient(v)
        numeric = fd_gradient(v)
        return {"maxAbsDiff": float(np.max(np.abs(analytic - numeric))),
                "maxRelDiff": float(np.max(np.abs(analytic - numeric)
                                           / np.maximum(np.abs(numeric), 1e-12)))}

    smooth = compare(v_smooth)
    clipped = compare(v_clipped)
    # knot case: move along feature j so that row 0 lands exactly on the lower knot 0
    column = int(np.argmax(np.abs(matrix[0])))
    v_knot = v_smooth.copy()
    v_knot[column] += -0.5 / matrix[0, column]
    knot = compare(v_knot)

    linear_smooth = matrix @ v_smooth + offset + shift
    linear_clipped = matrix @ v_clipped + offset + shift
    knot_value = float(matrix[0] @ v_knot + offset[0] + shift[0])
    checks = {
        "smoothMaxAbsDiff": smooth["maxAbsDiff"],
        "smoothMaxRelDiff": smooth["maxRelDiff"],
        "clippedMaxAbsDiff": clipped["maxAbsDiff"],
        "clippedMaxRelDiff": clipped["maxRelDiff"],
        "knotMaxAbsDiff": knot["maxAbsDiff"],
        "rowsInsideAtSmoothPoint": int(np.sum((linear_smooth > 0) & (linear_smooth < 1))),
        "rowsClippedAtClippedPoint": int(np.sum((linear_clipped < 0) | (linear_clipped > 1))),
        "firstRowAtKnot": knot_value,
        "allRows": int(m_shape),
    }
    passed = checks["smoothMaxAbsDiff"] <= TOL_FD and checks["clippedMaxAbsDiff"] <= TOL_FD
    return {
        "name": "gradient_finite_difference",
        "passed": bool(passed),
        "metric": checks["smoothMaxAbsDiff"],
        "tolerance": TOL_FD,
        "detail": {
            "objective": ("f(v) = 1/2||clip(Mv+b+s, 0, 1) - t||^2 + 1/2 lam ||v||^2 with an "
                          "analytic gradient dP/dx = 1 on 0<x<1 and 0 outside"),
            "smoothRegion": "the shift is chosen so all 6 rows sit at 0.5, strictly inside",
            "clippedRegion": "some rows clipped, evaluation point off the knots",
            "knotCase": ("feature chosen so row 0 lands exactly on the lower knot 0, where the "
                         "projection is not differentiable; a difference there is allowed and "
                         "reported instead of hidden"),
            **checks,
            "conclusion": ("the implemented gradient matches central finite differences to better "
                           "than the threshold wherever the objective is differentiable; the only "
                           "discrepancy is at an explicit non-differentiable knot"),
        },
    }


# -------------------------------------------------------------------------------------- test 5
def test_split_invariants() -> dict:
    table = v6_common.load_splits()
    manifest = json.loads(v6_common.SPLITS_MANIFEST.read_text(encoding="utf-8"))
    checks = []

    def check(name, condition, detail=None):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    check("rowCountIs2250", len(table) == 2250, len(table))
    check("columnsPresent", {"beer", "repeat", "outer_fold", "inner_fold", "role", "style"}
          .issubset(set(table.columns)), sorted(table.columns))
    check("repeats", sorted(table["repeat"].unique().tolist()) == [0, 1, 2],
          sorted(table["repeat"].unique().tolist()))
    check("outerFolds", sorted(table["outer_fold"].unique().tolist()) == [0, 1, 2],
          sorted(table["outer_fold"].unique().tolist()))
    check("roles", set(table["role"].unique().tolist()) == {"inner", "outer_test"},
          sorted(table["role"].unique().tolist()))
    roles_consistent = bool(((table["role"] == "outer_test") == (table["inner_fold"] == -1)).all())
    check("outerTestHasInnerFoldMinusOne", roles_consistent)

    overlap = 0
    duplicate_test_rows = 0
    uncovered = 0
    inner_partition_bad = 0
    inner_empty = 0
    style_missing = 0
    per_fold = {}
    for repeat in range(3):
        for outer in range(3):
            part = table[(table["repeat"] == repeat) & (table["outer_fold"] == outer)]
            test_rows = part[part["role"] == "outer_test"]
            inner_rows = part[part["role"] == "inner"]
            test_beers = set(int(b) for b in test_rows["beer"])
            if len(test_beers) != len(test_rows):
                duplicate_test_rows += 1
            inner_beers = set(int(b) for b in inner_rows["beer"])
            overlap += len(test_beers & inner_beers)
            covered = test_beers | inner_beers
            if covered != set(range(1, 251)):
                uncovered += 1
            fold_counts = inner_rows["inner_fold"].value_counts().to_dict()
            if set(fold_counts) != {0, 1, 2}:
                inner_partition_bad += 1
            if any(count == 0 for count in fold_counts.values()):
                inner_empty += 1
            inner_sum = sum(int(v) for v in fold_counts.values())
            if inner_sum != len(inner_beers):
                inner_partition_bad += 1
            merged = np.concatenate([
                inner_rows.loc[inner_rows["inner_fold"] == j, "beer"].to_numpy(dtype=int)
                for j in range(3)])
            if sorted(merged.tolist()) != sorted(inner_beers):
                inner_partition_bad += 1
            styles_train = set(inner_rows["style"].astype(str))
            styles_test = set(test_rows["style"].astype(str))
            if len(styles_train) != 22 or len(styles_test) != 22:
                style_missing += 1
            per_fold[f"r{repeat}f{outer}"] = {
                "nTest": int(len(test_rows)), "nInner": int(len(inner_rows)),
                "nStylesTest": len(styles_test), "nStylesTrain": len(styles_train)}
            key = f"r{repeat}f{outer}"
            manifest_fold = manifest["fold_checks"][key]
            if (manifest_fold["n_test"] != int(len(test_rows))
                    or manifest_fold["n_train"] != int(len(inner_rows))):
                checks.append({"check": f"manifestCounts_{key}", "passed": False,
                               "detail": {"manifest": manifest_fold,
                                          "csv": {"n_test": int(len(test_rows)),
                                                  "n_train": int(len(inner_rows))}}})
            else:
                checks.append({"check": f"manifestCounts_{key}", "passed": True})

    check("outerTrainTestOverlap", overlap == 0, overlap)
    check("outerTestRowsUnique", duplicate_test_rows == 0, duplicate_test_rows)
    check("everyOuterFoldCovers250Rows", uncovered == 0, uncovered)
    check("innerFoldsPartitionOuterTraining", inner_partition_bad == 0, inner_partition_bad)
    check("stylesPresentInEveryFold", style_missing == 0, style_missing)

    contest_text = (PROJECT / "contest.yaml").read_text(encoding="utf-8")
    tuning_match = re.search(r'^\s*tuning:\s*"([^"]+)"', contest_text, flags=re.MULTILINE)
    tuning = tuning_match.group(1) if tuning_match else ""
    parsed = dict(re.findall(r'(\w+)\s*=\s*([A-Za-z0-9_,\.\-]+)', tuning))
    tuning_seeds = [int(value) for value in parsed.get("seeds", "").split(",") if value]
    agreement = {
        "repeats": (parsed.get("repeats") is not None
                    and int(parsed["repeats"]) == int(manifest["repeats"])),
        "outerFolds": (parsed.get("outer_folds") is not None
                       and int(parsed["outer_folds"]) == int(manifest["outer_folds"])),
        "innerFolds": (parsed.get("inner_folds") is not None
                       and int(parsed["inner_folds"]) == int(manifest["inner_folds"])),
        "stratify": parsed.get("stratify") == manifest["stratify"],
        "seeds": tuning_seeds == [int(s) for s in manifest["seeds"]],
    }
    check("contestYamlTuningMatchesManifest", all(agreement.values()),
          {"parsed": parsed, "manifestSeeds": manifest["seeds"], "agreement": agreement})

    split_seed = _find_split_seed(contest_text)
    check("manifestSplitsHash",
          manifest.get("splits_sha256") == v6_common.sha256_file(v6_common.SPLITS_CSV),
          {"manifest": manifest.get("splits_sha256"),
           "file": v6_common.sha256_file(v6_common.SPLITS_CSV)})
    check("manifestSourceHash",
          manifest.get("source_sha256") == v6_common.sha256_file(v6_common.DATA_Q1),
          {"manifest": manifest.get("source_sha256"),
           "file": v6_common.sha256_file(v6_common.DATA_Q1)})
    check("manifestRowCount", int(manifest.get("n_rows", -1)) == len(table),
          manifest.get("n_rows"))

    failures = [entry["check"] for entry in checks if not entry["passed"]]
    return {
        "name": "split_invariants",
        "passed": not failures,
        "metric": len(failures),
        "tolerance": 0,
        "detail": {
            "source": str(v6_common.SPLITS_CSV.relative_to(PROJECT)),
            "manifest": str(v6_common.SPLITS_MANIFEST.relative_to(PROJECT)),
            "structure": {"repeats": 3, "outerFolds": 3, "innerFolds": 3, "rows": len(table)},
            "perFold": per_fold,
            "contestYaml": {
                "tuning": tuning,
                "parsed": parsed,
                "legacyHoldoutSeed": split_seed,
                "note": ("evaluation.split.seed governs the legacy single holdout, not this "
                         "nested CV; the nested seeds live in evaluation.tuning"),
                "agreement": agreement,
            },
            "checks": checks,
            "failures": failures,
        },
    }


def _find_split_seed(text: str):
    """Return the seed declared under evaluation.split (the legacy holdout), if present."""
    in_split = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "split:":
            in_split = True
            continue
        if in_split:
            if stripped.startswith("seed:"):
                try:
                    return int(stripped.split(":", 1)[1].strip())
                except ValueError:
                    return None
            if stripped and not line.startswith("    "):
                in_split = False
    return None


# -------------------------------------------------------------------------------------- test 6
def test_ridge_equivalence() -> dict:
    rng = np.random.default_rng(20261027)
    n, p, q, rank = 40, 60, 50, 50
    z = rng.normal(size=(n, p))
    y = rng.normal(size=(n, q))
    zc, yc = z - z.mean(0), y - y.mean(0)
    weights = np.abs(rng.normal(size=(p, p)))
    weights = (weights + weights.T) / 2.0
    np.fill_diagonal(weights, 0.0)
    lap = np.diag(weights.sum(axis=1)) - weights
    lam, gam = 1.3, 0.4

    base = zc.T @ zc / n + lam * np.eye(p)
    c = zc.T @ yc / n
    ridge = np.linalg.solve(base, c)
    graph = _graph_solve(zc, yc, lam, gam, lap, rank)
    graph_zero = _graph_solve(zc, yc, lam, 0.0, lap, rank)

    gamma_only_residual = float(np.max(np.abs(base @ graph["eigen"] - c)))
    expected_residual = float(np.max(np.abs(gam * (lap @ graph["eigen"]))))
    identity_gap = abs(gamma_only_residual - expected_residual)
    rank_of_c = int(np.linalg.matrix_rank(c, tol=1e-9))
    checks = {
        "gammaZeroGapToPlainRidge": float(np.max(np.abs(graph_zero["eigen"] - ridge))),
        "gammaPositiveDifference": float(np.max(np.abs(graph["eigen"] - ridge))),
        "gammaOnlyResidual": gamma_only_residual,
        "expectedGammaResidual": expected_residual,
        "identityGap": identity_gap,
        "rankOfCrossMoment": rank_of_c,
        "lowRankConstraintInactive": rank >= rank_of_c,
        "objectivePlain": _graph_objective(ridge, zc, yc, lam, 0.0, lap),
        "objectiveGraph": _graph_objective(graph["eigen"], zc, yc, lam, gam, lap),
    }
    passed = (checks["gammaZeroGapToPlainRidge"] <= TOL_ALGEBRA
              and checks["gammaPositiveDifference"] > 1e-6
              and checks["identityGap"] <= TOL_ALGEBRA
              and checks["lowRankConstraintInactive"])
    return {
        "name": "ridge_equivalence",
        "passed": bool(passed),
        "metric": checks["gammaZeroGapToPlainRidge"],
        "tolerance": TOL_ALGEBRA,
        "detail": {
            "problem": ("same design, same lam, same r: with gam=0 and r>=rank(Zc'Yc) the graph "
                        "low-rank solution must equal plain Ridge; with gam>0 the only difference "
                        "in the normal equations is the gam*L term"),
            "dimensions": {"n": n, "p": p, "q": q, "r": rank, "lam": lam, "gam": gam},
            **checks,
            "interpretation": ("A(gam) B = C with A(gam) = Zc'Zc/n + lam I + gam L, so "
                               "base B = C - gam L B; the measured identity gap shows the "
                               "difference is exactly the graph penalty"),
        },
    }


# ----------------------------------------------------------------------------------------- main
def main() -> int:
    tests = [
        test_graph_reduced_rank(),
        test_qp_active_set(),
        test_energy_toy(),
        test_gradient_finite_difference(),
        test_split_invariants(),
        test_ridge_equivalence(),
    ]
    failures = [test["name"] for test in tests if not test["passed"]]
    document = {
        "schema": "v6-contract-tests-1",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "scope": ("synthetic oracles and frozen-metadata invariants only; no contest fitting, no "
                  "contest performance number, no write outside the audit output"),
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "script": "src/r00_contract_tests.py",
        },
        "tests": tests,
        "summary": {"total": len(tests), "passed": len(tests) - len(failures),
                    "failed": failures, "allPassed": not failures},
    }
    text = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode()
    for target in (PRIMARY / "contract_tests.json", MIRROR / "contract_tests.json"):
        _atomic_write(target, text)

    print(json.dumps({
        "ok": not failures,
        "script": "src/r00_contract_tests.py",
        "outputs": ["outputs/contracts/v6/contract_tests.json",
                    "outputs/audit/v6/contract_tests.json"],
        "passed": f"{len(tests) - len(failures)}/{len(tests)}",
        "failed": failures,
        "metrics": {test["name"]: test["metric"] for test in tests},
        "tolerances": {test["name"]: test["tolerance"] for test in tests},
    }, ensure_ascii=False))
    if failures:
        for test in tests:
            if not test["passed"]:
                print(f"CONTRACT TEST FAILED: {test['name']} metric={test['metric']} "
                      f"tolerance={test['tolerance']}", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
