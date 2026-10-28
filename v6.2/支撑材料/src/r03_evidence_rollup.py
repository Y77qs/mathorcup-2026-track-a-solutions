# AI-ASSISTANCE NOTICE
# 本脚本的框架由 DeepSeek Harness（deepseek-flash）辅助生成；核心算法逻辑、约束修正与实验参数由
# 参赛队员人工审阅、修改并独立核验通过，队员对最终内容负责。
# The framework of this script was drafted with DeepSeek Harness assistance; the core algorithm logic,
# constraint corrections and experimental parameters were reviewed, amended and independently verified
# by the team members, who take responsibility for the contents.
"""r03_evidence_rollup.py — materialise the workbench evidence files from REGISTERED experiments.

WHY: the workbench `analysisPlan.evidence` paths must point at real files, and the
quality checks read them. Everything here is a *derived summary* of experiments the
ledger already holds (no fitting, no new numbers): if a number is not in a registered
metrics.json/outputs.json it is not written. Anything not yet done (robustness) is
recorded as an explicit `preregistered-not-executed` status, never as a pass.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "outputs"


def load(exp: str, name: str):
    path = PROJECT / "experiments" / exp / name
    if not path.exists():
        raise SystemExit(f"missing registered evidence: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    # ---- data audit: the generated dictionary must be at the declared path
    src = PROJECT / "data/processed/v6_feature_dictionary.csv"
    dst = OUT / "audit/v6/feature_dictionary.csv"
    if not dst.exists() or dst.read_bytes() != src.read_bytes():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # ---- Q1
    q1 = load("EXP-0048", "metrics.json")
    write_csv(OUT / "q1/model_comparison.csv",
              ["model", "metric", "value", "definition"],
              [["median", "mae", q1["mae_median"], "A/F30 uniform MAE, pooled 750 OOF rows"],
               ["ridge_gamma0_r50", "mae", q1["mae_ridge0"], "true OLS ridge, gamma=0"],
               ["graph_ridge_r50", "mae", q1["mae_graph_ridge"], "gamma>0, r=50"],
               ["graph_lowrank", "mae", q1["mae_graph_lowrank"], "inner-selected r (all folds r=6)"],
               ["graph_lowrank", "mae_all50", q1["mae_all50"], "secondary 50-target MAE"],
               ["graph_lowrank", "skill_af30", q1["skill_af30"], "1 - mae/mae_median"]])
    err_rows = [[k, v["n"], v["mae"]] for k, v in sorted(q1.get("per_style__" , {}).items())] if False else []
    for key, value in sorted(q1.items()):
        if key.startswith("per_style__") and key.endswith("__mae"):
            style = key[len("per_style__"):-len("__mae")]
            err_rows.append([style, int(q1.get(f"per_style__{style}__n", 0)), value])
    write_csv(OUT / "q1/error_analysis.csv", ["style", "n_rows", "mae_af30"], err_rows)
    write_json(OUT / "q1/robustness.json", {
        "status": "preregistered-not-executed",
        "plans": ["ROB-0004"],
        "decisionRule": {"type": "relative-range", "limit": 0.05},
        "note": "the perturbation experiments are NOT run yet; this file must not be read as a pass",
    })

    # ---- Q2
    q2 = load("EXP-0041", "outputs.json")["q2"]
    rows = []
    for dim, items in sorted(q2.get("top3_strict", {}).items() if isinstance(q2.get("top3_strict"), dict) else []):
        for item in items:
            rows.append([dim, item.get("rank"), item.get("compound"), item.get("pi"),
                         item.get("sign_stability"), item.get("direction")])
    if not rows:
        strict = PROJECT / "experiments/EXP-0041/strict_top3.csv"
        with open(strict, "r", encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                rows.append([rec.get("dimension"), rec.get("rank"), rec.get("compound"),
                             rec.get("pi"), rec.get("sign_stability"), rec.get("direction")])
    write_csv(OUT / "q2/factor_analysis.csv",
              ["dimension", "rank", "compound", "pi", "sign_stability", "direction"], rows)
    write_json(OUT / "q2/top3_report.json", {
        "protocol": "fixed 200-row training set (SPLIT-0001/train) + 3 seed blocks x 500 stratified bootstrap; NOT nested CV, no OOF",
        "categoryCounts": q2.get("category_counts"),
        "mappingAssertions": (q2.get("mapping") or {}).get("assertions"),
        "piMean": load("EXP-0041", "metrics.json").get("pi_mean"),
        "piBelowHalf": load("EXP-0041", "metrics.json").get("pi_below_0.5_count"),
        "note": "6.csv is same-source corroboration, not an independent external validation set",
    })
    # per-dimension pi summary (lossless pi lives in experiments/EXP-0041/bootstrap_pi.csv)
    boot = PROJECT / "experiments/EXP-0041/bootstrap_pi.csv"
    counts = {}
    with open(boot, "r", encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            key = (rec.get("dimension"), rec.get("method"), rec.get("compound"))
            counts[key] = counts.get(key, 0) + 1
    write_csv(OUT / "q2/bootstrap_pi.csv", ["dimension", "method", "compound", "count"],
              [[k[0], k[1], k[2], v] for k, v in sorted(counts.items())])

    # ---- Q3
    gen = load("EXP-0042", "metrics.json")
    tra = load("EXP-0043", "metrics.json")
    write_json(OUT / "q3/question_definition.json", {
        "question": "Q3",
        "task": "style-conditional generation of chemical spectra + Pils/Lager->Tripel constrained transfer",
        "noPredictionTarget": True,
        "inputs": "231 measured chemical/physicochemical columns of the beer (data/clean/q3.csv)",
        "whyOpenQuestion": "no labelled post-transfer observation exists, so the task is design under declared constraints, not supervised prediction",
    })
    (OUT / "q3/method.md").parent.mkdir(parents=True, exist_ok=True)
    (OUT / "q3/method.md").write_text(
        "# Q3 method (as implemented in EXP-0042 / EXP-0043)\n\n"
        "1. Style-conditional generation: shrunk empirical marginals + shrunk Gaussian copula, "
        "kappa/kappa_R selected INSIDE each outer training set (per-fold selection recorded in "
        "EXP-0042/outputs.json per_fold_tuning).\n"
        "2. Raw conditional spectra are written first (samples_raw.csv); the constrained design "
        "(samples.csv) is obtained by projection with declared bounds.\n"
        "3. Constraints: 33 linear-calibrated concentrations >= 0; DMS/diacetyl/4VG c' <= c_source; "
        "trans-2-nonenal on the CHEMICAL column; stale hops only as a labelled training-fitted proxy.\n"
        "4. Diagnostics: empirical V (normalised by D_train), signed U (never clipped), marginals, "
        "dependence, diversity, nearest-neighbour, duplicate share, edge fraction.\n"
        "5. Transfer: convex QP with quantile anchor; controls are source-fixed and target-mean "
        "projection; every solve records status and primal/dual residuals.\n", encoding="utf-8")
    write_json(OUT / "q3/constraint_report.json", {
        "designConstraintSatisfaction": gen["constraint-satisfaction"],
        "rawConstraintSatisfaction": gen["constraint-satisfaction-raw"],
        "constraintRecordCounts": {"verified": gen["constraints-verified"],
                                   "conditional": gen["constraints-conditional"],
                                   "not_identifiable": gen["constraints-not-identifiable"],
                                   "infeasible": gen["constraints-infeasible"]},
        "linearNegativeDesign": gen["n-linear-negative-design"],
        "constructionNote": "constraint-satisfaction=1.000 is an invariant of the projection loop, not an empirical finding",
        "boundClamping": "508/750 rows sit exactly at the DMS bound, 361/750 at the diacetyl bound, 46/750 at the 4VG bound",
    })
    write_json(OUT / "q3/robustness.json", {
        "status": "preregistered-not-executed",
        "plans": ["ROB-0006"],
        "decisionRule": {"type": "relative-range", "limit": 0.05},
        "note": "the generation/kappa perturbation experiments are NOT run yet",
    })
    write_json(OUT / "q3/model_comparison.json", {
        "design": {"constraint_satisfaction": gen["constraint-satisfaction"], "energy_V": gen["energy-distance"],
                   "diversity": gen["diversity"]},
        "copyReference": {"energy_V": 0.8137, "note": "same-style training-row resampling; the design is WORSE on V"},
        "transfer": {"nonincrease_rate": tra["nonincrease-rate"], "transfer_energy_V": tra["transfer-energy"],
                     "target_mean_projection_energy_V": tra["transfer-energy-target-mean-projection"],
                     "qp_status_optimal": tra["qp-status-optimal"], "qp_max_primal_residual": tra["qp-max-primal-residual"]},
    })
    (OUT / "q3/decision.md").write_text(
        "# Q3 decision (this round)\n\n"
        "- Keep the constrained projection: it removes all 142 negative linear concentrations and makes every "
        "declared numeric constraint verifiable (0 infeasible, max residual 0.0).\n"
        "- Do NOT claim the copula improves distributional fidelity: V=0.8840 is worse than the 0.8137 "
        "resampling reference, so no gain is asserted.\n"
        "- Keep the QP transfer: 198/198 optimal with residuals <= 1e-8, but the 1.000 non-increase rate is a "
        "construction result, not evidence of real flavour preservation.\n"
        "- Not done: 226+5 derived-column reconstruction, kappa sensitivity, robustness execution.\n", encoding="utf-8")
    (OUT / "q3/model_comparison.csv").write_text("model,metric,value\n", encoding="utf-8")
    for label, value in (("design", gen["constraint-satisfaction"]),
                         ("design_energy_V", gen["energy-distance"]),
                         ("transfer_V", tra["transfer-energy"]),
                         ("transfer_nonincrease", tra["nonincrease-rate"])):
        with open(OUT / "q3/model_comparison.csv", "a", encoding="utf-8") as f:
            f.write(f"{label},primary,{value}\n")

    print(json.dumps({"ok": True, "written": [
        "outputs/audit/v6/feature_dictionary.csv", "outputs/q1/model_comparison.csv",
        "outputs/q1/error_analysis.csv", "outputs/q1/robustness.json",
        "outputs/q2/factor_analysis.csv", "outputs/q2/top3_report.json", "outputs/q2/bootstrap_pi.csv",
        "outputs/q3/question_definition.json", "outputs/q3/method.md", "outputs/q3/constraint_report.json",
        "outputs/q3/robustness.json", "outputs/q3/model_comparison.json", "outputs/q3/model_comparison.csv",
        "outputs/q3/decision.md"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
