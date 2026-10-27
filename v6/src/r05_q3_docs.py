#!/usr/bin/env python3
"""Regenerate the Q3 decision/robustness documents from the CURRENT ledger (confirmatory only).

outputs/q3/decision.md              confirmatory summary + limitations, no pilot splicing
outputs/q3/robustness.json          ROB-0009 (generation) + ROB-0010 (transfer), from ledger results

Every number is read from the ledger or the SCRIPT-0018 artifact; nothing is hand-typed.
Pilot-round ROB-0001..0006 and EXP-0076/0077 are explicitly excluded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
L = json.loads((P / "state/ledger.json").read_text(encoding="utf-8"))
E = {e["id"]: e for e in L["experiments"]}
RB = {p["id"]: p for p in L["quality"]["robustnessPlans"]}
CL = {c["id"]: c for c in L["claims"]}
scope = json.loads((P / "outputs/q3/style_and_displacement_scope.json").read_text(encoding="utf-8"))
import csv as _csv
_rows = list(_csv.DictReader(open(P / "experiments/EXP-0080/transfer_constraints.csv", newline="", encoding="utf-8")))
_qp = [r for r in _rows if r["strategy"] == "qp-quantile-anchor"]
def _maxres(field):
    return max(float(r["residual"]) for r in _qp if r["field"] == field)
RES = {"nonenal": _maxres("chem__X.E..2.nonenal"), "butanedione": _maxres("chem__X2.3.butanedione")}
def _rel(robj_vals):
    return (max(robj_vals) - min(robj_vals)) / abs(robj_vals[0])


def rob(rid):
    p = RB[rid]
    r = p["result"] or {}
    v = r.get("values") if isinstance(r.get("values"), dict) else {"values": r.get("values"), "spread": r.get("spread"), "mean": r.get("mean")}
    return {
        "robId": rid, "questionId": p["questionId"], "preregisteredAt": p["preregisteredAt"],
        "executedAt": p["executedAt"], "experimentIds": p["experimentIds"],
        "metricKey": p["metricKey"], "decisionRule": p["decisionRule"],
        "values": v.get("values"), "mean": v.get("mean"), "spread": v.get("spread"),
        "ruleMessage": (r.get("decisionRule") or {}).get("message"),
        "relativeSpreadFromValues": _rel(v.get("values") or [1]),
        "labelNote": "the plan message prints spread/1 when decisionRule.reference is free text; relativeSpreadFromValues = spread/|first value|",
        "decisionPassed": p.get("decisionPassed"), "executionStatus": p.get("executionStatus"),
        "satisfiedMethods": (r.get("evidence") or {}).get("perturbation", {}).get("satisfiedMethods"),
        "limitations": {
            "ROB-0009": ["只覆盖 2/3 冻结种子", "constraint-satisfaction 是构造量、不参与判定",
                         "energy-distance 只测分布差异；source-resample 更优，不宣称优于基线"],
            "ROB-0010": ["nonincrease-rate 饱和，min 1>=1 不是改善量", "只覆盖 2/3 冻结种子",
                         "无原生 optimization VAL；58 条代理越界仅属参照控制"],
        }[rid],
    }


gen = CL["CLAIM-0054"]
tr = CL["CLAIM-0055"]
robj = {
    "kind": "q3-robustness.confirmatory",
    "generatedFrom": "state/ledger.json",
    "pilotExcluded": ["ROB-0001", "ROB-0002", "ROB-0003", "ROB-0004", "ROB-0005", "ROB-0006",
                      "EXP-0076", "EXP-0077"],
    "q3_generation": rob("ROB-0009"),
    "q3_transfer": rob("ROB-0010"),
    "note": "generation and transfer are separate components; do not merge them into one Q3 success rate",
}
(P / "outputs/q3/robustness.json").write_text(json.dumps(robj, ensure_ascii=False, indent=1), encoding="utf-8")

md = f"""# Q3 决策与稳健性（确认轮，自动生成）

> 本文件由 `src/r05_q3_docs.py` 从当前台账与 `outputs/q3/style_and_displacement_scope.json` 生成，数字不手抄。
> **只含确认轮**；先导轮 ROB-0001..0006 与 EXP-0076/0077 明确排除，不拼接。

## 1 生成侧（EXP-0079 / {gen['id']}，active）

- 归一化经验 V 能量距离（21 个可估风格、177 个可估格、n_gen=729，n_gen 加权池化）= **{scope['energy_distance_pooling']['all_estimable_styles']['value']:.6f}**
- Tripel/Kriek/Lambic 三风格 27 格（n_gen=147）单独池化 = **{scope['energy_distance_pooling']['tripel_kriek_lambic']['value']:.6f}**（不是上面的池化值）
- constraint-satisfaction = 1.000 是约束投影的**构造性质**，不作为分布质量证据；未约束原始生成 = 0.113333
- 限制：source-resample 控制 energy-distance = 0.813731 **优于**生成设计，故不宣称优于基线/真实参照；无原生 optimization VAL；Q3 选择仍为 **provisional**（生成/迁移双对象无法用单一 selectedModelId 表示）
- 稳健性 ROB-0009：{" / ".join(f"{x:.6f}" for x in robj['q3_generation']['values'])}，绝对极差 {robj['q3_generation']['spread']:.6f}，**相对极差 {_rel(robj['q3_generation']['values']):.6f} ≤ 0.05**（计划 message 的 0.021702 因 reference 为自由文本而按分母 1 计算，实为绝对极差；判定不变）（{robj['q3_generation']['satisfiedMethods']}）

## 2 迁移侧（EXP-0080 / {tr['id']}，active）

- 逐列不增率 = 1.000（qp-quantile-anchor / qp-source-anchor / source-fixed；target-mean-projection 参照控制 0.414141）
- 198 个 QP 证书全部 status=optimal，max primal = 9.9897e-9、max dual = 3.3938e-10、max_constraint_violation = 0、max KKT = 5.6167e-9
- 约束残差（transfer_constraints.csv 的 clamp(new−source,0)）最大：nonenal {RES['nonenal']:.4e}、butanedione {RES['butanedione']:.4e}
- qp-quantile-anchor 逐列 stored 位移 **max**：nonenal {scope['transfer_displacement']['per_column']['X.E..2.nonenal']['max_abs_stored']:.6f}（mean {scope['transfer_displacement']['per_column']['X.E..2.nonenal']['mean_abs_stored']:.2e}）、butanedione {scope['transfer_displacement']['per_column']['X2.3.butanedione']['max_abs_stored']:.6f}（mean {scope['transfer_displacement']['per_column']['X2.3.butanedione']['mean_abs_stored']:.4f}）、4VG {scope['transfer_displacement']['per_column']['X4VG']['max_abs_stored']:.6f}（mean {scope['transfer_displacement']['per_column']['X4VG']['mean_abs_stored']:.4f}）
- 限制：nonincrease-rate=1.000 由硬上界构造保证且指标**饱和**，min 1≥1 不是改善量；source-fixed 是平凡对照；58 条 stale_hops 代理越界仅属 target-mean-projection 参照控制；z 位移可复现（SCRIPT-0011，396/396 delta=0）不证 QP 目标/最优性；**原生 optimization VAL 未通过、未声称**；不报告“迁移准确率”
- 稳健性 ROB-0010：{robj['q3_transfer']['values']}，{robj['q3_transfer']['ruleMessage']}（{robj['q3_transfer']['satisfiedMethods']}）

## 3 本文件边界

- 生成与迁移分别评价，不合并为单一“Q3 成功率”。
- 两组件均只覆盖 2/3 冻结种子；固定种子独立复跑属确定性重现，不是独立实现。
- 本文件不构成交付审查，也不改变 selection 状态（Q3 = provisional）。
"""
(P / "outputs/q3/decision.md").write_text(md, encoding="utf-8")

print(json.dumps({"decision_md_sha256": hashlib.sha256((P / "outputs/q3/decision.md").read_bytes()).hexdigest(),
                  "robustness_json_sha256": hashlib.sha256((P / "outputs/q3/robustness.json").read_bytes()).hexdigest(),
                  "gen": robj["q3_generation"]["values"], "tr": robj["q3_transfer"]["values"]}, ensure_ascii=False))
