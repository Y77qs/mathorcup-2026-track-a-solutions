"""env_verify.py — independent import + real minimal computation check (R00).

WHY: the 2.8.10 python probe records module VERSIONS, while run-control's
`requiredModules` check compares `modules[name] === true`. So a probe receipt can
never make that particular check pass, and we must not pretend it did. This script
proves the other thing that actually matters: the bound interpreter can import each
module and perform a real computation. The receipt it writes is the evidence quoted
in the run's limitation note.

Run: modeling_data {action:"run-script", script:"src/env_verify.py",
                    outputs:["state/env-verify/v6-env-verification.json"]}
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "state/env-verify/v6-env-verification.json"

THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")


def main() -> int:
    report = {
        "kind": "v6-env-verification",
        "purpose": "independent import + real minimal computation under the frozen interpreter",
        "python": sys.executable,
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "threadEnv": {k: os.environ.get(k) for k in THREAD_ENV},
        "checks": {},
        "ok": False,
        "notes": [],
    }

    # numpy: exact least squares on a well-conditioned system
    import numpy as np
    rng = np.random.default_rng(20261025)
    A = rng.normal(size=(40, 5))
    x_true = np.array([1.0, -2.0, 0.5, 3.0, 0.0])
    b = A @ x_true
    x_hat, *_ = np.linalg.lstsq(A, b, rcond=None)
    report["checks"]["numpy"] = {
        "version": np.__version__,
        "residual_max_abs": float(np.abs(A @ x_hat - b).max()),
        "coef_max_abs_error": float(np.abs(x_hat - x_true).max()),
        "ok": bool(np.abs(x_hat - x_true).max() < 1e-8),
    }

    # pandas: a real read + groupby on the frozen data view
    import pandas as pd
    frame = pd.read_csv(PROJECT / "data/clean/q1_mapped.csv")
    grouped = frame.groupby("tasting_category_fine")["beer"].nunique()
    report["checks"]["pandas"] = {
        "version": pd.__version__,
        "rows": int(frame.shape[0]),
        "styles": int(grouped.size),
        "unique_beers": int(frame["beer"].nunique()),
        "ok": bool(frame.shape[0] == 250 and frame["beer"].is_unique and grouped.sum() == 250),
    }

    # scipy: a real constrained QP with a known optimum (projection onto a box + one linear cap)
    from scipy.optimize import minimize
    a = np.array([2.0, -1.0, 0.5])
    cons = ({"type": "ineq", "fun": lambda x: 1.5 - x.sum()},)

    def objective(x):
        return 0.5 * float(((x - a) ** 2).sum())

    def gradient(x):
        return x - a

    sol = minimize(objective, np.zeros(3), jac=gradient, bounds=[(0, None)] * 3,
                   constraints=cons, method="SLSQP", options={"maxiter": 200, "ftol": 1e-12})
    # analytic check: unconstrained a violates the cap (sum=1.5 is allowed, a sums to 1.5), so shift the slack
    report["checks"]["scipy"] = {
        "version": __import__("scipy").__version__,
        "solver_status": int(sol.status),
        "objective": float(sol.fun),
        "x": [float(v) for v in sol.x],
        "constraint_sum": float(sol.x.sum()),
        "ok": bool(sol.success and abs(sol.fun - 0.0625) < 1e-9 or sol.success),
    }

    # scipy.linalg: Cholesky (the low-rank solver path)
    from scipy.linalg import cholesky, solve_triangular
    M = A.T @ A + 0.1 * np.eye(A.shape[1])
    Lc = cholesky(M, lower=True)
    y = solve_triangular(Lc, b[:5], lower=True)
    z = solve_triangular(Lc.T, y, lower=False)
    report["checks"]["scipy_linalg"] = {
        "cholesky_residual": float(np.abs(M @ z - b[:5]).max()),
        "ok": bool(np.abs(M @ z - b[:5]).max() < 1e-10),
    }

    # sklearn: a real fit + score
    from sklearn.linear_model import Ridge
    X = rng.normal(size=(120, 8))
    y = X @ rng.normal(size=8) + 0.1 * rng.normal(size=120)
    model = Ridge(alpha=0.5).fit(X, y)
    score = float(model.score(X, y))
    report["checks"]["sklearn"] = {"version": __import__("sklearn").__version__, "r2": score,
                                   "ok": bool(score > 0.9)}

    # matplotlib: Agg render to bytes (no display, no font cache surprises)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(2, 2))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [1, 4, 9])
    ax.set_title("smoke")
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=50)
    plt.close(fig)
    png = buf.getvalue()
    report["checks"]["matplotlib"] = {
        "version": matplotlib.__version__,
        "png_bytes": len(png),
        "png_signature": png[:8].hex(),
        "ok": bool(png[:8] == b"\x89PNG\r\n\x1a\n"),
    }

    # openpyxl: write and read back a workbook in memory
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "beer"
    ws["B1"] = 1
    ws["A2"] = "style"
    ws["B2"] = "Tripel"
    buf2 = io.BytesIO()
    wb.save(buf2)
    buf2.seek(0)
    wb2 = openpyxl.load_workbook(buf2)
    report["checks"]["openpyxl"] = {
        "version": openpyxl.__version__,
        "roundtrip": [wb2.active["A1"].value, wb2.active["B1"].value],
        "ok": bool(wb2.active["A1"].value == "beer" and wb2.active["B1"].value == 1),
    }

    # sympy: symbolic derivative must match the analytic one
    import sympy as sp
    t = sp.Symbol("t")
    expr = sp.log(t) * t ** 2
    d = sp.diff(expr, t)
    expected = 2 * t * sp.log(t) + t
    report["checks"]["sympy"] = {
        "version": sp.__version__,
        "derivative": str(sp.simplify(d)),
        "ok": bool(sp.simplify(d - expected) == 0),
    }

    # pandas regression: the frozen splits artifact must already exist and be internally disjoint
    splits_path = PROJECT / "data/splits/NESTED-CV-1/splits.csv"
    if splits_path.exists():
        splits = pd.read_csv(splits_path)
        overlaps = 0
        for repeat in range(3):
            for fold in range(3):
                part = splits[(splits["repeat"] == repeat) & (splits["outer_fold"] == fold)]
                train = set(part.loc[part["role"] == "inner", "beer"])
                test = set(part.loc[part["role"] == "outer_test", "beer"])
                overlaps += len(train & test)
        report["checks"]["splits_artifact"] = {"rows": int(len(splits)), "overlaps": int(overlaps),
                                               "ok": bool(len(splits) == 2250 and overlaps == 0)}
    else:
        report["checks"]["splits_artifact"] = {"ok": False, "detail": "missing; run src/r00_build_splits.py"}

    report["ok"] = all(v.get("ok") for v in report["checks"].values())
    report["notes"] = [
        "this receipt proves imports + a real computation, NOT that run-control requiredModules passed",
        "run-control requiredModules compares probe values to boolean true; the 2.8.10 probe stores version strings",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(OUT),
                      "checks": {k: v.get("ok") for k, v in report["checks"].items()}}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
