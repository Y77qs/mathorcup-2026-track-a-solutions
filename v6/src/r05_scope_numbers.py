#!/usr/bin/env python3
"""Scope numbers used by the corrected Q3 claims (REV-0051 / REV-0052 findings).

1) Pooled energy-distance by style subset: the confirmatory metric pools ALL estimable styles
   (n_gen-weighted). This script recomputes the same pooling restricted to Tripel/Kriek/Lambic,
   so "all estimable styles" and "the three named styles" are two separate traceable numbers.
2) Strategy-labelled design movement for the transfer rows (stored |new - source| per column,
   max and mean) restricted to the delivered QP strategy named in the claim.

Reads only experiments/EXP-0079/q3_metrics.csv and experiments/EXP-0080/transfers.csv.
Writes outputs/q3/style_and_displacement_scope.json.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]


def sha(rel):
    p = P / rel
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 1) pooled energy-distance
rows = list(csv.DictReader(open(P / "experiments/EXP-0079/q3_metrics.csv", newline="", encoding="utf-8")))
def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


design = [r for r in rows if str(r.get("stage")) == "design" and r.get("model") == "copula-selected"
          and _num(r.get("E_V_norm")) is not None and _num(r.get("n_gen")) is not None]


def weighted_pool(sub):
    w = [float(r["n_gen"]) for r in sub]
    v = [float(r["E_V_norm"]) for r in sub]
    return sum(a * b for a, b in zip(w, v)) / sum(w), len(sub), sum(w)


all_styles, n_all, w_all = weighted_pool(design)
named = [r for r in design if r["style"] in ("Tripel", "Kriek", "Lambic")]
named_pool, n_named, w_named = weighted_pool(named)
by_style = {}
for s in sorted({r["style"] for r in design}):
    sub = [r for r in design if r["style"] == s]
    val, n, w = weighted_pool(sub)
    by_style[s] = {"cells": n, "n_gen": w, "energy_distance_pooled": val}

# ---------------------------------------------------------------- 2) transfer displacement
t = list(csv.DictReader(open(P / "experiments/EXP-0080/transfers.csv", newline="", encoding="utf-8")))
STRAT = "qp-quantile-anchor"
qp = [r for r in t if r["strategy"] == STRAT]
disp = {}
for col in ("DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal"):
    d = [abs(float(r[f"{col}_stored_new"]) - float(r[f"{col}_stored_source"])) for r in qp]
    disp[col] = {"rows": len(d), "max_abs_stored": max(d), "mean_abs_stored": sum(d) / len(d)}
# target approach vs movement (Pareto inputs, reported, not a new claim)
pareto = {}
for s in sorted({r["strategy"] for r in t}):
    sub = [r for r in t if r["strategy"] == s]
    pareto[s] = {
        "rows": len(sub),
        "target_mahalanobis_mean": sum(float(r["target_mahalanobis"]) for r in sub) / len(sub),
        "mean_abs_change_z_mean": sum(float(r["mean_abs_change_z"]) for r in sub) / len(sub),
    }

out = {
    "kind": "q3-scope-numbers",
    "recordedAt": "2026-10-26T15:00:00Z",
    "energy_distance_pooling": {
        "definition": "n_gen-weighted mean of E_V_norm over design cells",
        "all_estimable_styles": {"value": all_styles, "cells": n_all, "n_gen": w_all,
                                 "styles": len({r["style"] for r in design})},
        "tripel_kriek_lambic": {"value": named_pool, "cells": n_named, "n_gen": w_named},
        "per_style": by_style,
        "source": "experiments/EXP-0079/q3_metrics.csv",
        "sourceSha256": sha("experiments/EXP-0079/q3_metrics.csv"),
        "note": "the confirmatory metric energy-distance=0.8840256215416039 pools ALL estimable styles; "
                "the three named styles pool to a much larger distance, so a three-style scope must not "
                "reuse the all-style number",
    },
    "transfer_displacement": {
        "strategy": STRAT,
        "per_column": disp,
        "note": "stored |new - source| per column: max and mean; this is DESIGN MOVEMENT, not a constraint residual",
    },
    "transfer_target_vs_movement": {
        "per_strategy": pareto,
        "note": "target_mahalanobis and mean_abs_change_z are reported so a Pareto view can be built; "
                "no dual-threshold (mean/median) scenario exists in the confirmatory round",
    },
    "inputs": {"EXP-0079/q3_metrics.csv": sha("experiments/EXP-0079/q3_metrics.csv"),
               "EXP-0080/transfers.csv": sha("experiments/EXP-0080/transfers.csv")},
}
outp = P / "outputs/q3/style_and_displacement_scope.json"
outp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"all": all_styles, "named": named_pool, "named_cells": n_named,
                  "disp": {k: {kk: round(vv, 9) for kk, vv in v.items() if kk != "rows"} for k, v in disp.items()},
                  "sha256": hashlib.sha256(outp.read_bytes()).hexdigest()}, ensure_ascii=False, indent=1))
