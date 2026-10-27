#!/usr/bin/env python3
"""Confirmatory-round robustness products (ROB-0007..ROB-0010).

Writes ONE file per scope so pilot-round ROB-0001..0006 is never spliced into the
confirmatory round:
  outputs/q1/robustness_confirmatory.json   ROB-0007  (MODEL-0048 / EXP-0073)
  outputs/q2/robustness_confirmatory.json   ROB-0008  (MODEL-0050 / EXP-0075)
  outputs/q3/robustness_generation_confirmatory.json  ROB-0009 (EXP-0079 generation)
  outputs/q3/robustness_transfer_confirmatory.json    ROB-0010 (EXP-0080 transfer)
  outputs/robustness/INDEX-confirmatory.json          index + explicit separation note

Every number is copied from the ledger / executed artifacts (no hand-typed metric).
Supplementary readings are reported next to (not instead of) the decision metric.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L = json.loads((ROOT / "state" / "ledger.json").read_text(encoding="utf-8"))
EXP = {e["id"]: e for e in L["experiments"]}
ROB = {p["id"]: p for p in L["quality"]["robustnessPlans"]}


def plan_block(rob_id, label, scope_note):
    p = ROB[rob_id]
    r = p["result"] or {}
    rule = (r.get("decisionRule") or {})
    return {
        "robId": p["id"],
        "label": label,
        "questionId": p["questionId"],
        "preregisteredAt": p["preregisteredAt"],
        "executedAt": p["executedAt"],
        "experimentIds": p["experimentIds"],
        "methods": p["methods"],
        "perturbations": p["perturbations"],
        "metricKey": p["metricKey"],
        "decisionRule": p["decisionRule"],
        "seeds": p["seeds"],
        "repeats": p["repeats"],
        "budget": p["budget"],
        "dataUse": p["dataUse"],
        "values": r.get("values"),
        "interval": r.get("interval"),
        "decisionOutcome": rule,
        "decisionPassed": p.get("decisionPassed"),
        "executionStatus": p.get("executionStatus"),
        "conclusion": p.get("conclusion"),
        "conclusionScope": p.get("conclusionScope"),
        "satisfiedMethods": (r.get("evidence") or {}).get("perturbation", {}).get("satisfiedMethods"),
        "pairs": (r.get("evidence") or {}).get("perturbation", {}).get("pairs"),
        "scopeNote": scope_note,
    }


def metrics(exp_id, keys):
    m = EXP[exp_id].get("metrics") or {}
    return {k: m.get(k) for k in keys}


q1 = plan_block("ROB-0007", "Q1 mae stability (confirmatory)", "MODEL-0048 / EXP-0073; train-only 3x3x3 nested CV")
q1["supplementary"] = {e: metrics(e, ("mae_all50", "mae_ridge0", "mae_graph_ridge",
                                      "per_group__Aroma15__mae", "per_group__Flavour15__mae",
                                      "per_group__Other20__mae"))
                       for e in q1["experimentIds"]}
q1["limitations"] = [
    "split-integrity and holdout-metrics stay structurally unsatisfiable (no holdout, EXP-0073 has no splitId); robustness does not remove them",
    "multiple-seeds = frozen repeat blocks 0/1 only (2 of the 3 frozen seeds were executed); the third seed was not run",
    "fixed-seed rerun (VAL-0065/EXP-0083) is deterministic reproduction, not a robustness perturbation",
    "param-perturbation changes only the inner lambda grid (x0.5); no other hyper-parameter was perturbed",
]

q2 = plan_block("ROB-0008", "Q2 topk-jaccard stability (confirmatory)", "MODEL-0050 / EXP-0075; fixed 200-row train set, 50 test rows unused")
q2["supplementary"] = {e: metrics(e, ("topk-jaccard-point", "sign_stability_mean", "cross_repeat_jaccard",
                                      "pi_mean", "pi_below_0.5_count", "n_strict_candidates", "n_extended_candidates"))
                       for e in q2["experimentIds"]}
q2["limitations"] = [
    "topk-jaccard is between-method set agreement, NOT predictive accuracy",
    "6.csv is same-source rank corroboration, not an external validation set",
    "the seed pair also changes bootstrapSeed, so it additionally registers as a budget difference; the decisive budget perturbation is 500->200 (EXP-0091)",
    "two frozen repeats executed (0/1); the third was not run",
]

q3g = plan_block("ROB-0009", "Q3 generation distribution-quality stability (confirmatory)", "EXP-0079 generation; constraint-satisfaction excluded from the decision")
q3g["supplementary"] = {e: metrics(e, ("constraint-satisfaction", "diversity", "duplicate-share",
                                       "profile-spearman", "profile-pooled-spearman",
                                       "constraints-verified", "constraints-conditional",
                                       "constraints-not-identifiable", "constraints-infeasible"))
                        for e in q3g["experimentIds"]}
q3g["constructionNote"] = ("constraint-satisfaction = 1.000 in every run is a CONSTRUCTION property of the constrained "
                           "projection, not evidence of distribution quality; the decision uses energy-distance only")
q3g["limitations"] = [
    "generation and transfer must not be merged into one Q3 success rate",
    "two frozen repeats executed (0/1); the third was not run",
    "energy-distance is a distributional discrepancy, not a scientific validity proof",
]

tr = plan_block("ROB-0010", "Q3 transfer non-worsening stability (confirmatory)", "EXP-0080 transfer; decision metric nonincrease-rate")
tr["supplementary"] = {e: metrics(e, ("qp-status-optimal", "qp-status-infeasible", "qp-status-not-converged",
                                      "qp-max-primal-residual", "qp-max-dual-residual", "qp-max-constraint-violation",
                                      "transfer-energy", "transfer-energy-qp-quantile-anchor",
                                      "transfer-energy-qp-source-anchor",
                                      "nonincrease-rate-target-mean-projection", "qp-solves"))
                       for e in tr["experimentIds"]}
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
    "nonincrease-rate = 1.0 under every perturbation; the metric is bounded and saturates, so stability of the CONSTRAINED QPs does not imply the transfer is 'accurate'",
    "the 58 stale_hops proxy excesses belong exclusively to the target-mean-projection control and are excluded from the decision object (QP strategies: 0)",
    "z-space l1_change_z is reproducible from frozen inputs (SCRIPT-0011) but that does not prove the QP objective/optimality",
    "native optimization-feasibility/optimization-objective remain NOT passed and are not claimed here",
    "two frozen repeats executed (0/1); the third was not run",
]

index = {
    "kind": "confirmatory-robustness.index",
    "recordedAt": "2026-10-26T14:21Z",
    "confirmatory": [
        {"robId": q1["robId"], "file": "outputs/q1/robustness_confirmatory.json", "decisionPassed": q1["decisionPassed"]},
        {"robId": q2["robId"], "file": "outputs/q2/robustness_confirmatory.json", "decisionPassed": q2["decisionPassed"]},
        {"robId": q3g["robId"], "file": "outputs/q3/robustness_generation_confirmatory.json", "decisionPassed": q3g["decisionPassed"]},
        {"robId": tr["robId"], "file": "outputs/q3/robustness_transfer_confirmatory.json", "decisionPassed": tr["decisionPassed"]},
    ],
    "pilot_plans_NOT_confirmatory": ["ROB-0001", "ROB-0002", "ROB-0003", "ROB-0004", "ROB-0005", "ROB-0006"],
    "separationNote": ("ROB-0001..ROB-0006 belong to the pilot/exploratory round and are NOT linked to any ledger record "
                       "of this batch; this index deliberately does not merge their values with the confirmatory ones."),
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

print(json.dumps({
    rid: {"decisionPassed": ROB[rid].get("decisionPassed"),
          "values": (ROB[rid]["result"] or {}).get("values"),
          "spread": (ROB[rid]["result"] or {}).get("spread"),
          "rule": ((ROB[rid]["result"] or {}).get("decisionRule") or {}).get("message")}
    for rid in ("ROB-0007", "ROB-0008", "ROB-0009", "ROB-0010")}, ensure_ascii=False, indent=1))
print("notExecuted:", index["notExecuted"])
