#!/usr/bin/env python3
# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""Confirmatory-round robustness products (ROB-0007, ROB-0011, ROB-0015..ROB-0017).

Writes ONE file per scope so pilot-round ROB-0001..0006 is never spliced into the
confirmatory round:
  outputs/q1/robustness_confirmatory.json            ROB-0007  (MODEL-0048 / EXP-0073) — unchanged
  outputs/q2/robustness_confirmatory.json            ROB-0015  (EXP-0125 reference + EXP-0126)
  outputs/q3/robustness_generation_confirmatory.json ROB-0016  (EXP-0127 reference + EXP-0128)
  outputs/q3/robustness_transfer_confirmatory.json   ROB-0017  (EXP-0129 reference + EXP-0130)
  outputs/robustness/INDEX-confirmatory.json         index + explicit separation note

Every number is copied from the ledger / executed artifacts (no hand-typed metric).
Supplementary readings are reported next to (not instead of) the decision metric.

WHY THE IDS CHANGED AGAIN. ROB-0012/0013/0014 were pre-registered but never executed
(pending history). The executed plans are ROB-0015/0016/0017, whose method is recorded in
the ledger as `param-perturbation` with the FROZEN SEED BLOCK as the perturbed object; the
real method must therefore not be described as `multiple-seeds`. Each executed plan links
two blocks (repeat 0 reference + repeat 1), so the decision uses n=2, not n=3.

The third seed block (repeat 2) was run AFTER the plans were registered (EXP-0131/0132/0133)
and the tool refuses to overwrite an executed plan. Those runs are reported as a separate
"supplementary seed block, NOT merged into the plan record" field; they are never folded
into the plan values, the spread or the decision.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L = json.loads((ROOT / "state" / "ledger.json").read_text(encoding="utf-8"))
EXP = {e["id"]: e for e in L["experiments"]}
ROB = {p["id"]: p for p in L["quality"]["robustnessPlans"]}

Q1_PLAN = "ROB-0007"          # unchanged (provenance-repair twin ROB-0011 carries the same values)
Q2_PLAN = "ROB-0015"
Q3G_PLAN = "ROB-0016"
Q3T_PLAN = "ROB-0017"

SUPPLEMENTARY = {
    "Q2": ("EXP-0131", "topk-jaccard",
           "repeat-2 frozen seed block executed AFTER the plan was registered; NOT part of "
           "the ROB-0015 execution set and not merged into its values/spread/decision"),
    "Q3gen": ("EXP-0132", "energy-distance",
              "repeat-2 frozen seed block executed AFTER the plan was registered; NOT part of "
              "the ROB-0016 execution set and not merged into its values/spread/decision"),
    "Q3mig": ("EXP-0133", "nonincrease-rate",
              "repeat-2 frozen seed block executed AFTER the plan was registered; NOT part of "
              "the ROB-0017 execution set and not merged into its values/spread/decision"),
}


class RobustnessProductError(SystemExit):
    """A named refusal: a product is being written from an unexecuted / hollow plan."""


def require_executed(rob_id):
    p = ROB[rob_id]
    if not p.get("executedAt") or p.get("executionStatus") != "completed" or not p.get("result"):
        raise RobustnessProductError(
            f"r05_robustness_products: {rob_id} 尚未执行（executedAt={p.get('executedAt')!r}, "
            f"executionStatus={p.get('executionStatus')!r}, result={'none' if not p.get('result') else 'present'}, "
            f"experimentIds={p.get('experimentIds')!r}）。请由台账持有者执行该稳健性计划后再生成产物；"
            "本脚本不会用空值占位，也不会回退到旧实验。")
    if not p.get("experimentIds"):
        raise RobustnessProductError(
            f"r05_robustness_products: {rob_id} 没有链接实验（experimentIds 为空），无法生成执行值。")
    return p


def plan_block(rob_id, label, scope_note):
    p = ROB[rob_id]
    r = p["result"] or {}
    rule = (r.get("decisionRule") or {})
    values = r.get("values")
    return {
        "robId": p["id"],
        "label": label,
        "questionId": p["questionId"],
        "preregisteredAt": p["preregisteredAt"],
        "executedAt": p["executedAt"],
        "experimentIds": p["experimentIds"],
        "referenceExperimentId": p["experimentIds"][0],
        "nExecutedBlocks": len(p["experimentIds"]),
        "methods": p["methods"],
        "methodNote": ("台账记录的方法为 param-perturbation，被扰动的对象是冻结种子块；"
                       "不得写成 multiple-seeds，也不得把两个执行块连同补充块写成 n=3 的计划结果"),
        "perturbations": p["perturbations"],
        "metricKey": p["metricKey"],
        "decisionRule": p["decisionRule"],
        "seeds": p["seeds"],
        "repeats": p["repeats"],
        "budget": p["budget"],
        "dataUse": p["dataUse"],
        "values": values,
        "interval": r.get("interval"),
        "absoluteSpread": r.get("spread"),
        "relativeSpread": (max(values) - min(values)) / abs(values[0]) if values and values[0] else None,
        "decisionOutcome": rule,
        "decisionPassed": p.get("decisionPassed"),
        "executionStatus": p.get("executionStatus"),
        "conclusion": p.get("conclusion"),
        "conclusionScope": p.get("conclusionScope"),
        "satisfiedMethods": (r.get("evidence") or {}).get("perturbation", {}).get("satisfiedMethods"),
        "pairs": (r.get("evidence") or {}).get("perturbation", {}).get("pairs"),
        "scopeNote": scope_note,
    }


def supplementary_block(key):
    exp_id, metric_key, note = SUPPLEMENTARY[key]
    m = EXP.get(exp_id, {}).get("metrics") or {}
    if metric_key not in m:
        raise RobustnessProductError(
            f"r05_robustness_products: 补充种子块 {exp_id} 缺少 metric key '{metric_key}'")
    return {"experimentId": exp_id, "metricKey": metric_key, "value": m[metric_key],
            "inPlanExecutionSet": False, "note": note}


def metrics(exp_id, keys):
    m = EXP[exp_id].get("metrics") or {}
    return {k: m.get(k) for k in keys}


def metrics_file(exp_id):
    return json.loads((ROOT / "experiments" / exp_id / "metrics.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ Q1 (unchanged: ROB-0007)
require_executed(Q1_PLAN)
q1 = plan_block(Q1_PLAN, "Q1 mae stability (confirmatory)", "MODEL-0048 / EXP-0073; train-only 3x3x3 nested CV")
q1["alsoRegisteredAs"] = "ROB-0011"
q1["supplementary"] = {e: metrics(e, ("mae_all50", "mae_ridge0", "mae_graph_ridge",
                                      "per_group__Aroma15__mae", "per_group__Flavour15__mae",
                                      "per_group__Other20__mae"))
                       for e in q1["experimentIds"]}
q1["limitations"] = [
    "split-integrity and holdout-metrics stay structurally unsatisfiable (no holdout, EXP-0073 has no splitId); robustness does not remove them",
    "multiple-seeds = frozen repeat blocks 0/1 only (2 of the 3 frozen seeds were executed); the third seed was not run in ROB-0007",
    "fixed-seed rerun (VAL-0065/EXP-0083) is deterministic reproduction, not a robustness perturbation",
    "param-perturbation changes only the inner lambda grid (x0.5); no other hyper-parameter was perturbed",
    "ROB-0011 re-executed the same design on the provenance-consistent wrapper and repeated these values; it does not widen the scope above",
]

# ------------------------------------------------------------------ Q2 (ROB-0015)
require_executed(Q2_PLAN)
q2 = plan_block(Q2_PLAN, "Q2 topk-jaccard stability (confirmatory)",
                "MODEL-0050 / EXP-0125 reference; fixed 200-row train set, 50 test rows unused; "
                "two executed frozen seed blocks (repeat 0/1), 500 stratified bootstrap replicates each")
q2_supp_keys = ("topk-jaccard-point", "sign_stability_mean", "sign_stability_legacy_mean",
                "pi_mean", "pi_below_0.5_count", "pi_below_0.5_denominator",
                "n_strict_candidates", "n_extended_candidates",
                "external_6csv_mean_spearman_aligned", "external_6csv_rows_matched")
q2["supplementary"] = {e: metrics(e, q2_supp_keys) for e in q2["experimentIds"]}
q2["supplementarySeedBlock"] = supplementary_block("Q2")
ref_q2 = metrics_file("EXP-0107")
if ref_q2.get("sign_stability_mean") is None or ref_q2.get("sign_stability_legacy_mean") is None:
    raise RobustnessProductError(
        "r05_robustness_products: EXP-0107/metrics.json 缺少 sign_stability_mean 或 "
        "sign_stability_legacy_mean；两种口径必须分开报告。")
q2["signStability"] = {
    "experimentId": "EXP-0107",
    "newDefinition": {
        "key": "sign_stability_mean",
        "value": ref_q2["sign_stability_mean"],
        "definition": "share of bootstrap replicates whose total-Spearman sign agrees with the POINT-ESTIMATE sign of the same (compound, dimension) cell",
    },
    "legacyDefinition": {
        "key": "sign_stability_legacy_mean",
        "value": ref_q2["sign_stability_legacy_mean"],
        "definition": "superseded reading: share of bootstrap replicates with rho > 0, i.e. P(rho>0) — it penalises every cell whose point estimate is negative and must not be called 'sign stability'",
    },
    "directionCounts": {
        "negative_point_estimates": ref_q2.get("sign_negative_point_count"),
        "zero": ref_q2.get("sign_zero_count"),
        "invalid": ref_q2.get("sign_invalid_count"),
        "direction_undetermined": ref_q2.get("sign_direction_undetermined_count"),
        "note": "counted over the delivered rows of the reference run; the legacy P(rho>0) reading is low because negative point estimates are penalised, not because the direction is unstable",
    },
    "legacyReproduction": "150/150 delivered consensus rows reproduce the legacy p_positive value exactly (see experiments/EXP-0107/sign_stability_summary.json legacyReproduction)",
    "warning": "any statement that quotes 0.7226 as 'sign stability' is describing the OLD denominator; the current definition is the agreement-with-point-estimate rate (0.9817)",
}
q2["limitations"] = [
    "topk-jaccard is between-method set agreement, NOT predictive accuracy",
    "6.csv is same-source rank corroboration, not an external validation set",
    "the executed plan has TWO linked blocks (repeat 0/1); the repeat-2 block was run after registration and is reported separately (supplementarySeedBlock), not merged",
    "the ledger records the method as param-perturbation (the perturbed object is the frozen seed block); it is NOT a multiple-seeds plan",
    "there is NO budget perturbation: bootstrap budget is 500 in every block",
    "the bootstrap seed and the split repeat move together inside a seed block, so a seed effect and any residual split effect are not separately identified",
    "sign stability is defined as agreement with the point estimate; the legacy P(rho>0) value is reported separately and is not interchangeable",
]

# ------------------------------------------------------------------ Q3 generation (ROB-0016)
require_executed(Q3G_PLAN)
q3g = plan_block(Q3G_PLAN, "Q3 generation distribution-quality stability (confirmatory)",
                 "EXP-0127 reference; two executed frozen seed blocks (repeat 0/1); "
                 "constraint-satisfaction excluded from the decision")
q3g["supplementary"] = {e: metrics(e, ("constraint-satisfaction", "diversity", "duplicate-share",
                                       "profile-spearman", "profile-pooled-spearman",
                                       "energy-distance-raw", "energy-V-raw", "energy-U-signed",
                                       "energy-V-subset-tripel-kriek-lambic",
                                       "t2n-increases", "t2n-proxy-increase-share",
                                       "nonenal-increases-design",
                                       "constraints-verified", "constraints-conditional",
                                       "constraints-not-identifiable", "constraints-infeasible",
                                       "n-cells-estimable", "n-cells-subset"))
                        for e in q3g["experimentIds"]}
q3g["supplementarySeedBlock"] = supplementary_block("Q3gen")
q3g["constructionNote"] = ("constraint-satisfaction = 1.000 in every run is a CONSTRUCTION property of the "
                           "constrained projection, not evidence of distribution quality; the decision uses "
                           "energy-distance only, and the un-normalised V / signed U are reported alongside it")
q3g["limitations"] = [
    "generation and transfer must not be merged into one Q3 success rate",
    "the executed plan has TWO linked blocks (repeat 0/1); the repeat-2 block was run after registration and is reported separately, not merged",
    "the ledger records the method as param-perturbation (the perturbed object is the frozen seed block); it is NOT a multiple-seeds plan and there is no parameter/budget perturbation",
    "energy-distance is a distributional discrepancy, not a scientific validity proof",
    "the sensory t2n proxy still increases on part of the generated rows while the real chemical trans-2-nonenal never increases; the two are different propositions",
]

# ------------------------------------------------------------------ Q3 transfer (ROB-0017)
require_executed(Q3T_PLAN)
tr = plan_block(Q3T_PLAN, "Q3 transfer non-worsening stability (confirmatory)",
                "EXP-0129 reference; two executed frozen seed blocks (repeat 0/1); decision metric "
                "nonincrease-rate; 198 QP solves of a main run = 11 sources x 9 training contexts x 2 "
                "strategies (repeated solves, not 198 beers)")
tr["supplementary"] = {e: metrics(e, ("qp-status-optimal", "qp-status-infeasible", "qp-status-not-converged",
                                      "qp-max-primal-residual", "qp-max-dual-residual",
                                      "qp-max-constraint-violation",
                                      "qp-max-stale-halfspace-residual", "qp-max-stale-identity-error",
                                      "qp-stale-intercept-c-min", "qp-stale-intercept-c-max",
                                      "transfer-energy", "transfer-energy-U", "transfer-energy-normalized",
                                      "transfer-energy-qp-quantile-anchor",
                                      "transfer-energy-qp-source-anchor",
                                      "transfer-energy-source-fixed",
                                      "transfer-energy-target-mean-projection",
                                      "transfer-energy-target-mean-projection-full",
                                      "nonincrease-rate-target-mean-projection",
                                      "nonincrease-rate-target-mean-projection-full",
                                      "nonenal-nonincrease-rate-primary",
                                      "t2n-proxy-increase-share-primary",
                                      "verdict-verified-primary", "verdict-verified-denominator-primary",
                                      "verdict-conditional-primary", "verdict-not-identifiable-primary",
                                      "verdict-failed-primary", "verdict-records-primary",
                                      "qp-solves"))
                       for e in tr["experimentIds"]}
tr["supplementarySeedBlock"] = supplementary_block("Q3mig")
move = {}
for e in tr["experimentIds"]:
    path = ROOT / "experiments" / e / "transfers.csv"
    if not path.exists():
        move[e] = None
        continue
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    opt = [c[5:] for c in rows[0] if c.startswith("opt__")]
    per = {}
    for row in rows:
        d = sum(abs(float(row["opt__" + c]) - float(row["src__" + c])) for c in opt)
        per.setdefault(row["strategy"], []).append(d)
    move[e] = {s: {"rows": len(v), "mean_stored_abs_change": sum(v) / len(v), "max_stored_abs_change": max(v)}
               for s, v in per.items()}
tr["sourceMovement_storedSpace"] = move
tr["limitations"] = [
    "nonincrease-rate = 1.0 in every executed block; the metric is bounded and saturates, so stability of the CONSTRAINED QPs does not imply the transfer is 'accurate'",
    "the stale_hops proxy excesses belong exclusively to the target-mean-projection control and are excluded from the decision object (QP strategies: 0); the full-feasible mean projection baseline keeps nonincrease-rate = 1.0",
    "the 198 QP solves of a main run are 11 sources x 9 training contexts x 2 strategies (repeated solves of the same source), not 198 independent beers",
    "z-space l1_change_z is checked by the within-artifact identity l1/231 = mean_abs_change_z; the independent centre/scale rebuild (SCRIPT-0011) was NOT rerun for this round and is not cited",
    "native optimization-feasibility/optimization-objective remain NOT passed and are not claimed here",
    "the executed plan has TWO linked blocks (repeat 0/1); the repeat-2 block was run after registration and is reported separately, not merged",
    "the ledger records the method as param-perturbation (the perturbed object is the frozen seed block); it is NOT a multiple-seeds plan",
]

# ------------------------------------------------------------------ index
index = {
    "kind": "confirmatory-robustness.index",
    "derivedFromLedgerRevision": L["revision"],
    "confirmatory": [
        {"robId": q1["robId"], "file": "outputs/q1/robustness_confirmatory.json", "decisionPassed": q1["decisionPassed"]},
        {"robId": q2["robId"], "file": "outputs/q2/robustness_confirmatory.json", "decisionPassed": q2["decisionPassed"]},
        {"robId": q3g["robId"], "file": "outputs/q3/robustness_generation_confirmatory.json", "decisionPassed": q3g["decisionPassed"]},
        {"robId": tr["robId"], "file": "outputs/q3/robustness_transfer_confirmatory.json", "decisionPassed": tr["decisionPassed"]},
    ],
    "q1ProvenanceRepairTwin": {"robId": "ROB-0011", "note": "same design and same values as ROB-0007 on the provenance-consistent wrapper"},
    "superseded_plans_NOT_current_evidence": ["ROB-0008", "ROB-0009", "ROB-0010"],
    "pending_plans_NOT_executed": ["ROB-0012", "ROB-0013", "ROB-0014"],
    "pilot_plans_NOT_confirmatory": ["ROB-0001", "ROB-0002", "ROB-0003", "ROB-0004", "ROB-0005", "ROB-0006"],
    "supplementarySeedBlocks_NOT_in_plan_record": [
        {"block": "Q2", "experimentId": "EXP-0131", "note": SUPPLEMENTARY["Q2"][2]},
        {"block": "Q3gen", "experimentId": "EXP-0132", "note": SUPPLEMENTARY["Q3gen"][2]},
        {"block": "Q3mig", "experimentId": "EXP-0133", "note": SUPPLEMENTARY["Q3mig"][2]},
    ],
    "separationNote": ("ROB-0001..ROB-0006 belong to the pilot/exploratory round and are NOT linked to any ledger record "
                       "of this batch; ROB-0008/0009/0010 are the previous confirmatory round and were replaced; "
                       "ROB-0012/0013/0014 were pre-registered but never executed and are pending history. This index "
                       "deliberately does not merge any of those values with the current ones."),
    "notExecuted": [p["id"] for p in L["quality"]["robustnessPlans"] if not p.get("executedAt")],
    "survivingStructuralGaps": {
        "Q1": ["split-integrity (EXP-0073 has no splitId)", "holdout-metrics (no holdout in train-only nested CV)"],
        "Q3": ["native optimization-feasibility/optimization-objective not passed"],
    },
}

out = {
    "q1": (ROOT / "outputs" / "q1" / "robustness_confirmatory.json", q1),
    "q2": (ROOT / "outputs" / "q2" / "robustness_confirmatory.json", q2),
    "q3g": (ROOT / "outputs" / "q3" / "robustness_generation_confirmatory.json", q3g),
    "q3t": (ROOT / "outputs" / "q3" / "robustness_transfer_confirmatory.json", tr),
    "idx": (ROOT / "outputs" / "robustness" / "INDEX-confirmatory.json", index),
}
for _k, (path, payload) in out.items():
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

print(json.dumps({
    rid: {"decisionPassed": ROB[rid].get("decisionPassed"),
          "experimentIds": ROB[rid].get("experimentIds"),
          "values": (ROB[rid]["result"] or {}).get("values"),
          "spread": (ROB[rid]["result"] or {}).get("spread")}
    for rid in (Q1_PLAN, Q2_PLAN, Q3G_PLAN, Q3T_PLAN)}, ensure_ascii=False, indent=1))
print("supplementary:", json.dumps({k: v[0] for k, v in SUPPLEMENTARY.items()}, ensure_ascii=False))
print("notExecuted:", index["notExecuted"])
