#!/usr/bin/env python3
"""Scope numbers used by the current Q3 claims (REV-0051 / REV-0052 + v6 rework).

1) Pooled energy-distance by style subset: the confirmatory metric pools ALL estimable
   styles (n_gen-weighted). This script recomputes the same pooling restricted to
   Tripel/Kriek/Lambic, so "all estimable styles" and "the three named styles" are two
   separate traceable numbers. Both are reported with the un-normalised V and the
   signed U in the same block, because V and U answer different questions.
2) Strategy-labelled design movement for the transfer rows (stored |new - source| per
   column, max and mean) restricted to the delivered QP strategy named in the claim.
3) The four-layer source-state verdict counts (verified / conditional / not_identifiable
   / failed) and the full-feasible-region mean-projection baseline that the v6 transfer
   round added; both are cross-checked against the experiment's own metrics.json.

Reads only:
  experiments/EXP-0109/q3_metrics.csv          (generation, per-cell energy readings)
  experiments/EXP-0109/metrics.json            (pooled readings + cell counts)
  experiments/EXP-0110/transfers.csv           (per-row transfer movement)
  experiments/EXP-0110/transfer_verdicts.csv   (per field/bound-type verdict counts)
  experiments/EXP-0110/outputs.json            (strategy aggregates, cross-check)
  experiments/EXP-0110/metrics.json            (strategy readings, cross-check)
Writes outputs/q3/style_and_displacement_scope.json.

No value is hand-typed: every number is recomputed from the files above and every
recomputation is asserted against the experiment's own metrics.json. A mismatch is a
named failure (SystemExit), never a silent fallback to an older run.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]

GEN_DIR = "experiments/EXP-0109"
TR_DIR = "experiments/EXP-0110"
GEN_CSV = f"{GEN_DIR}/q3_metrics.csv"
GEN_METRICS = f"{GEN_DIR}/metrics.json"
TR_CSV = f"{TR_DIR}/transfers.csv"
TR_VERDICTS = f"{TR_DIR}/transfer_verdicts.csv"
TR_OUTPUTS = f"{TR_DIR}/outputs.json"
TR_METRICS = f"{TR_DIR}/metrics.json"
OUT = "outputs/q3/style_and_displacement_scope.json"

STRAT = "qp-quantile-anchor"
NAMED_STYLES = ("Tripel", "Kriek", "Lambic")
COLS = ("DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal")
VERDICTS = ("verified", "conditional", "not_identifiable", "failed")


def sha(rel):
    h = hashlib.sha256()
    with open(P / rel, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(rel):
    return json.loads((P / rel).read_text(encoding="utf-8"))


def rows(rel):
    with open(P / rel, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def fail(msg):
    raise SystemExit(f"r05_scope_numbers: {msg}")


def require_close(name, got, want, rel_tol=1e-9):
    if want is None:
        fail(f"{name}: 参照值缺失，不能声称一致")
    if got is None:
        fail(f"{name}: 重算值缺失")
    if abs(got - want) > rel_tol * max(abs(want), 1e-300):
        fail(f"{name}: 重算 {got!r} 与 metrics {want!r} 不一致（rel_tol={rel_tol}）")


# ---------------------------------------------------------------- 1) pooled energy-distance
gen_metrics = load_json(GEN_METRICS)
gen_rows = rows(GEN_CSV)
design = [r for r in gen_rows
          if str(r.get("stage")) == "design" and r.get("model") == "copula-selected"
          and num(r.get("E_V_norm")) is not None and num(r.get("n_gen")) is not None]
if not design:
    fail(f"{GEN_CSV} 中没有可用的设计谱格（stage=design, model=copula-selected）")


def weighted_pool(sub):
    w = [float(r["n_gen"]) for r in sub]
    v = [float(r["E_V_norm"]) for r in sub]
    return sum(a * b for a, b in zip(w, v)) / sum(w), len(sub), sum(w)


all_value, n_all, w_all = weighted_pool(design)
named = [r for r in design if r["style"] in NAMED_STYLES]
if not named:
    fail(f"{GEN_CSV} 中没有 {NAMED_STYLES} 三个风格的设计谱格")
named_value, n_named, w_named = weighted_pool(named)
by_style = {}
for s in sorted({r["style"] for r in design}):
    sub = [r for r in design if r["style"] == s]
    val, n, w = weighted_pool(sub)
    by_style[s] = {"cells": n, "n_gen": w, "energy_distance_pooled": val}

# cross-checks against the experiment's own pooled readings. The subset number is NOT a
# registered metric (only its un-normalised V and U are), so the subset normalised value is
# recomputed here and the cell counts are the ones cross-checked.
require_close("all-estimable pooled V", all_value, gen_metrics.get("energy-distance"))
if int(n_all) != int(gen_metrics.get("n-cells-estimable", -1)):
    fail(f"可估格数 {n_all} 与 metrics n-cells-estimable {gen_metrics.get('n-cells-estimable')} 不一致")
if int(w_all) != int(gen_metrics.get("n-samples-estimable", -1)):
    fail(f"进入能量距离的生成份数 {w_all} 与 metrics n-samples-estimable "
         f"{gen_metrics.get('n-samples-estimable')} 不一致")
if int(n_named) != int(gen_metrics.get("n-cells-subset", -1)):
    fail(f"三风格格数 {n_named} 与 metrics n-cells-subset {gen_metrics.get('n-cells-subset')} 不一致")
if n_all + int(gen_metrics.get("n-cells-excluded-energy", 0)) != int(gen_metrics.get("n-cells", -1)):
    fail("可估格数 + 被排除格数 与 metrics n-cells 不一致")
if int(gen_metrics.get("n-samples", 0)) - int(w_all) != int(gen_metrics.get("n-cells-excluded-energy", -1)):
    fail("总样本 − 进入能量距离的份数 与 metrics n-cells-excluded-energy 不一致")

# ---------------------------------------------------------------- 2) transfer displacement
transfer = rows(TR_CSV)
qp = [r for r in transfer if r["strategy"] == STRAT]
if not qp:
    fail(f"{TR_CSV} 中没有策略 {STRAT} 的行")
disp = {}
for col in COLS:
    d = [abs(num(r[f"{col}_stored_new"]) - num(r[f"{col}_stored_source"])) for r in qp]
    if any(v is None for v in d):
        fail(f"{TR_CSV} 的 {col} 存储空间位移存在缺失值")
    disp[col] = {"rows": len(d), "max_abs_stored": max(d), "mean_abs_stored": sum(d) / len(d)}

# target approach vs movement (Pareto inputs, reported, not a new claim)
pareto = {}
for s in sorted({r["strategy"] for r in transfer}):
    sub = [r for r in transfer if r["strategy"] == s]
    for key in ("target_mahalanobis", "mean_abs_change_z", "l1_change_z"):
        if num(sub[0].get(key)) is None:
            fail(f"{TR_CSV} 策略 {s} 缺少数值列 {key}")
    pareto[s] = {
        "rows": len(sub),
        "target_mahalanobis_mean": sum(num(r["target_mahalanobis"]) for r in sub) / len(sub),
        "mean_abs_change_z_mean": sum(num(r["mean_abs_change_z"]) for r in sub) / len(sub),
        "l1_change_z_max": max(num(r["l1_change_z"]) for r in sub),
        "nonincrease_all": all(str(r.get("nonincrease_all")).lower() == "true" for r in sub),
    }

# ---------------------------------------------------------------- 3) verdict layers
tr_metrics = load_json(TR_METRICS)
verdict_rows = [r for r in rows(TR_VERDICTS) if r["strategy"] == STRAT]
if not verdict_rows:
    fail(f"{TR_VERDICTS} 中没有策略 {STRAT} 的核验记录")
counts = {v: 0 for v in VERDICTS}
by_bound_type = {}
for r in verdict_rows:
    v = r["verdict"]
    if v not in counts:
        fail(f"{TR_VERDICTS} 出现未登记的核验状态 {v!r}")
    n = int(float(r["n"]))
    counts[v] += n
    by_bound_type.setdefault(r["bound_type"], {k: 0 for k in VERDICTS})[v] += n
records = sum(counts.values())
verified_denominator = sum(int(float(r["verifiedDenominator"])) for r in verdict_rows
                           if r["verdict"] == "verified")
for metric_key, got in (("verdict-records-primary", records),
                        ("verdict-verified-primary", counts["verified"]),
                        ("verdict-verified-denominator-primary", verified_denominator),
                        ("verdict-conditional-primary", counts["conditional"]),
                        ("verdict-not-identifiable-primary", counts["not_identifiable"]),
                        ("verdict-failed-primary", counts["failed"])):
    if int(tr_metrics.get(metric_key, -1)) != int(got):
        fail(f"重算 {metric_key}={got} 与 metrics {tr_metrics.get(metric_key)!r} 不一致")
if verified_denominator + counts["not_identifiable"] != records:
    fail(f"可核验分母 {verified_denominator} + 不可识别 {counts['not_identifiable']} 不等于记录数 {records}")

# ---------------------------------------------------------------- 4) baselines
tr_outputs = load_json(TR_OUTPUTS)
energy_by_strategy = tr_outputs["energy_by_strategy"]
noninc_by_strategy = tr_outputs["nonincrease_by_strategy"]
BASELINE_KEYS = {
    "full_feasible_mean_projection": "target-mean-projection-full",
    "box_only_mean_projection": "target-mean-projection",
    "source_fixed": "source-fixed",
    "delivered_qp": STRAT,
}
baselines = {}
for label, strat in BASELINE_KEYS.items():
    if strat not in energy_by_strategy or strat not in noninc_by_strategy:
        fail(f"{TR_OUTPUTS} 缺少策略 {strat} 的聚合读数")
    e = energy_by_strategy[strat]
    n = noninc_by_strategy[strat]
    baselines[label] = {
        "strategy": strat,
        "transfer_energy": e["V"],
        "transfer_energy_normalized": e["V_normalized"],
        "transfer_energy_U": e["U"],
        "nonincrease_rate": n["nonincreaseRate"],
        "stale_proxy_rate": n["staleProxyRate"],
        "chem4_nonincreasing": all(float(v) == 1.0 for v in n["perField"].values()),
    }
# the delivered QP row must equal the registered primary metrics
require_close("delivered transfer-energy", baselines["delivered_qp"]["transfer_energy"],
              tr_metrics.get("transfer-energy"))
require_close("delivered normalized transfer-energy",
              baselines["delivered_qp"]["transfer_energy_normalized"],
              tr_metrics.get("transfer-energy-normalized"))
require_close("delivered nonincrease-rate", baselines["delivered_qp"]["nonincrease_rate"],
              tr_metrics.get("nonincrease-rate"))
for label, metric_key in (("full_feasible_mean_projection", "transfer-energy-target-mean-projection-full"),
                          ("box_only_mean_projection", "transfer-energy-target-mean-projection"),
                          ("source_fixed", "transfer-energy-source-fixed")):
    require_close(f"{label} transfer-energy", baselines[label]["transfer_energy"],
                  tr_metrics.get(metric_key))
for label, metric_key in (("full_feasible_mean_projection", "nonincrease-rate-target-mean-projection-full"),
                          ("box_only_mean_projection", "nonincrease-rate-target-mean-projection"),
                          ("source_fixed", "nonincrease-rate-source-fixed")):
    require_close(f"{label} nonincrease-rate", baselines[label]["nonincrease_rate"],
                  tr_metrics.get(metric_key))

out = {
    "kind": "q3-scope-numbers",
    "derivedFrom": "confirmatory v6 run: EXP-0109 generation + EXP-0110 transfer",
    "energy_distance_pooling": {
        "definition": "n_gen-weighted mean of E_V_norm over the cells of the delivered generator (copula-selected, stage=design)",
        "valueDefinition": "E_V_norm = normalised empirical energy distance V; V_raw = the same statistic before normalisation; U_signed = the signed counterpart (may be negative, never clipped at zero)",
        "all_estimable_styles": {"value": all_value, "V_raw": gen_metrics.get("energy-V-raw"),
                                 "U_signed": gen_metrics.get("energy-U-signed"),
                                 "cells": n_all, "n_gen": w_all,
                                 "styles": len({r["style"] for r in design})},
        "tripel_kriek_lambic": {"value": named_value,
                                "V_raw": gen_metrics.get("energy-V-subset-tripel-kriek-lambic"),
                                "U_signed": gen_metrics.get("energy-U-subset-tripel-kriek-lambic"),
                                "cells": n_named, "n_gen": w_named},
        "per_style": by_style,
        "source": GEN_CSV,
        "sourceSha256": sha(GEN_CSV),
        "metricsSource": GEN_METRICS,
        "metricsSourceSha256": sha(GEN_METRICS),
        "note": ("the confirmatory metric energy-distance pools ALL estimable styles; the three named "
                 "styles pool to a much larger distance, so a three-style scope must not reuse the "
                 "all-style number. V_raw and U_signed are read from the same run's metrics.json and are "
                 "not interchanged with the normalised V."),
    },
    "transfer_displacement": {
        "strategy": STRAT,
        "per_column": disp,
        "source": TR_CSV,
        "sourceSha256": sha(TR_CSV),
        "note": "stored |new - source| per column: max and mean; this is DESIGN MOVEMENT, not a constraint residual",
    },
    "transfer_verdicts": {
        "strategy": STRAT,
        "counts": counts,
        "records": records,
        "verified_denominator": verified_denominator,
        "by_bound_type": by_bound_type,
        "source": TR_VERDICTS,
        "sourceSha256": sha(TR_VERDICTS),
        "note": ("four-layer source-state verdict over the declared upper-bound records of the delivered "
                 "strategy; not-identifiable records are excluded from the verified denominator and are "
                 "never counted as verified or as failed"),
    },
    "transfer_baselines": {
        "definition": ("full feasible region = box ∩ the single stale-proxy half-space; the full-feasible "
                       "mean projection is the reference baseline, the box-only mean projection is a "
                       "diagnostic control, and source-fixed is the no-transfer control"),
        "baselines": baselines,
        "source": TR_METRICS,
        "metricsSourceSha256": sha(TR_METRICS),
        "outputsSource": TR_OUTPUTS,
        "outputsSourceSha256": sha(TR_OUTPUTS),
    },
    "transfer_target_vs_movement": {
        "per_strategy": pareto,
        "source": TR_CSV,
        "sourceSha256": sha(TR_CSV),
        "note": ("target_mahalanobis and mean_abs_change_z are reported so a Pareto view can be built; "
                 "l1_change_z_max and nonincrease_all are copied so the delivered strategy can be checked "
                 "against the no-transfer control"),
    },
    "inputs": {GEN_CSV: sha(GEN_CSV), GEN_METRICS: sha(GEN_METRICS),
               TR_CSV: sha(TR_CSV), TR_VERDICTS: sha(TR_VERDICTS),
               TR_OUTPUTS: sha(TR_OUTPUTS), TR_METRICS: sha(TR_METRICS)},
}
outp = P / OUT
outp.parent.mkdir(parents=True, exist_ok=True)
outp.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({"all": all_value, "all_cells": n_all, "all_n_gen": w_all,
                  "named": named_value, "named_cells": n_named, "named_n_gen": w_named,
                  "verdicts": counts, "records": records,
                  "baselines": {k: (v["transfer_energy"], v["nonincrease_rate"])
                                for k, v in baselines.items()},
                  "disp": {k: {kk: round(vv, 9) for kk, vv in v.items() if kk != "rows"}
                           for k, v in disp.items()},
                  "sha256": hashlib.sha256(outp.read_bytes()).hexdigest()},
                 ensure_ascii=False, indent=1))
