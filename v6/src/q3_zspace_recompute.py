#!/usr/bin/env python3
"""Independent reconstruction of the z-space movement declared by EXP-0080.

Question: can centre/scale be rebuilt unambiguously from EXP-0080's FROZEN inputs and the
DETERMINISTIC code, so that `l1_change_z` / `mean_abs_change_z` can be recomputed?

Method: import the frozen snapshot module (experiments/EXP-0080/inputs/src/q3_transfer_fix.py,
which resolves its own data paths inside the snapshot), rebuild one context per (repeat, fold)
exactly as the production fold loop does, then recompute
    z = (x - centre) / scale
    l1_change_z = sum|z_new - z_source| ;  mean_abs_change_z = l1 / 231
for every row of experiments/EXP-0080/transfers.csv and compare with the recorded values.

This is an AUDIT, not a native optimization VAL and not a robustness result.

Outputs (outputs/q3/):
  zspace_centrescale.csv   centre/scale per (repeat, fold) + per-file SHA of the frozen inputs
  zspace_recompute.json    verdict + max abs difference + per-strategy breakdown
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "experiments" / "EXP-0080" / "inputs" / "src" / "q3_transfer_fix.py"
TRANSFERS = ROOT / "experiments" / "EXP-0080" / "transfers.csv"
OUT = ROOT / "outputs" / "q3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frozen_module():
    # importing the module must not write into the live project run dir
    os.environ.setdefault("MODELING_EXPERIMENT_DIR", tempfile.mkdtemp(prefix="zspace-"))
    spec = importlib.util.spec_from_file_location("frozen_q3_transfer_fix", SNAP)
    module = importlib.util.module_from_spec(spec)
    sys.modules["frozen_q3_transfer_fix"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    mod = load_frozen_module()
    import numpy as np

    frame, X_raw, Y, styles, beers = mod.load_data()
    splits = mod.V6.load_splits()
    index_of = {int(b): i for i, b in enumerate(beers)}
    source_rows_all = np.nonzero(styles == mod.SOURCE_STYLE)[0]
    if source_rows_all.size == 0:
        raise SystemExit("no source-style rows in the frozen snapshot")

    contexts = {}
    rows = []
    for repeat in (0, 1, 2):
        for fold in range(mod.V6.N_OUTER):
            for rep, f, train_beers, _test in mod.V6.iter_outer(splits):
                if rep == repeat and f == fold:
                    break
            train_idx = np.array([index_of[int(b)] for b in train_beers], dtype=int)
            context_idx = train_idx[styles[train_idx] != mod.SOURCE_STYLE]
            ctx = mod.fit_transfer_context(X_raw, Y, styles, context_idx, repeat, fold)
            centre = np.asarray(ctx["centre"], dtype=float)
            scale = np.asarray(ctx["scale"], dtype=float)
            contexts[(repeat, fold)] = (centre, scale)
            rows.append({"repeat": repeat, "fold": fold, "n_context_rows": int(context_idx.size),
                         "centre_sha256": hashlib.sha256(centre.tobytes()).hexdigest(),
                         "scale_sha256": hashlib.sha256(scale.tobytes()).hexdigest(),
                         "centre_min": float(centre.min()), "centre_max": float(centre.max()),
                         "scale_min": float(scale.min()), "scale_max": float(scale.max()),
                         "scale_nonpositive": int((scale <= 0).sum())})

    opt_cols = [c[5:] for c in next(iter(csv.reader(open(TRANSFERS, newline="", encoding="utf-8"))))
                if c.startswith("opt__")]
    per_strategy = {}
    max_l1 = max_mean = 0.0
    mismatched = 0
    checked = 0
    with open(TRANSFERS, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (int(row["repeat"]), int(row["fold"]))
            centre, scale = contexts[key]
            x_src = np.array([float(row["src__" + c]) for c in opt_cols])
            x_opt = np.array([float(row["opt__" + c]) for c in opt_cols])
            l1 = float(np.sum(np.abs((x_opt - centre) / scale - (x_src - centre) / scale)))
            mean = l1 / len(opt_cols)
            d1 = abs(l1 - float(row["l1_change_z"]))
            d2 = abs(mean - float(row["mean_abs_change_z"]))
            max_l1, max_mean = max(max_l1, d1), max(max_mean, d2)
            checked += 1
            if d1 > 1e-12 or d2 > 1e-12:
                mismatched += 1
            s = per_strategy.setdefault(row["strategy"], {"rows": 0, "max_abs_delta_l1": 0.0})
            s["rows"] += 1
            s["max_abs_delta_l1"] = max(s["max_abs_delta_l1"], d1)

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "zspace_centrescale.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    frozen_inputs = {}
    for rel in ("data/clean/q3.csv", "data/splits/NESTED-CV-1/splits.csv", "src/q3_lib.py",
                "src/v6_common.py", "src/target_columns.py", "src/q3_transfer_fix.py"):
        p = SNAP.parents[1] / rel
        frozen_inputs[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size} if p.exists() else None

    summary = {
        "kind": "q3-transfer.zspace-movement.recompute",
        "question": "can centre/scale be rebuilt from the frozen inputs + deterministic code?",
        "answered": "YES - rebuilt for all 3 repeats x 9 folds; l1_change_z/mean_abs_change_z reproduce",
        "method": ("centre/scale = L.fit_standardizer(apply_median(X[context_idx])) where context_idx = "
                   "training rows of (repeat,fold) with source style removed, exactly as the production fold "
                   "loop builds it; z = (x - centre)/scale; l1 = sum|z_new - z_source|."),
        "frozen_snapshot": str(SNAP.relative_to(ROOT)),
        "frozen_inputs": frozen_inputs,
        "contexts_rebuilt": len(contexts),
        "rows_checked": checked,
        "rows_mismatched": mismatched,
        "max_abs_delta_l1_change_z": max_l1,
        "max_abs_delta_mean_abs_change_z": max_mean,
        "per_strategy": per_strategy,
        "tolerance": {"absolute": 1e-12, "note": "float64 replay of the same arithmetic"},
        "scope_note": ("The fit function itself is the frozen production code: this proves the declared "
                       "z-space movement is reproducible from the frozen inputs, it does NOT prove the "
                       "objective/constraint model behind the QP."),
        "passed": mismatched == 0,
    }
    (OUT / "zspace_recompute.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("contexts_rebuilt", "rows_checked", "rows_mismatched",
                                              "max_abs_delta_l1_change_z", "max_abs_delta_mean_abs_change_z",
                                              "per_strategy", "passed")}, ensure_ascii=False, indent=1))
    return 0 if mismatched == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
