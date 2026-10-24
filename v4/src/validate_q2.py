#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""src/validate_q2.py — Q2 独立复算（reviewer 所有，不 import modeler 的任何代码）。

用途（阶段 B，GO 之后）：
  1. 结构化核对 experiments/<EXP>/sets.json 与实验登记的 evaluation 声明；
  2. 独立复算 topk-jaccard（逐维方法两两 Jaccard 平均 → 维度平均），与台账
     experiments[].metrics["topk-jaccard"] 按 contest.yaml 的 reproductionTolerance 比对；
  3. 用注册 split 的 TRAIN 文件独立复算 50 个感官维度 × 声明特征的 max |Pearson r|，
     报告是否出现 ≥ correlationThreshold 的泄漏嫌疑（Q2 选择只在训练行内进行）。

判定口径：
  - status="recomputed"：复算完成；passed 由 delta 是否在容差内决定（exit 0/1）；
  - status="refused"：证据缺失/字段不符，绝不冒充通过（exit 2）。
输出：validation/q2-recompute.json（task-5 写域 validation/）（结构 + 复算 + 泄漏审计 + 结论）。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except Exception as exc:  # pragma: no cover
    print(json.dumps({"status": "refused", "error": "PYTHON_DEPS", "message": repr(exc)}))
    sys.exit(2)


def load_ledger(project: Path) -> dict:
    return json.loads((project / "state" / "ledger.json").read_text("utf-8"))


def find(items, key: str, value: str):
    for item in items or []:
        if item.get(key) == value:
            return item
    return None


def read_tolerance(project: Path) -> tuple[float, float]:
    """从 contest.yaml 读 reproductionTolerance（协议来源，不手抄）。缺项退回工具默认并标记。"""
    text = (project / "contest.yaml").read_text("utf-8")
    abs_m = re.search(r"^\s*absolute:\s*([0-9.eE+\-]+)\s*$", text, re.M)
    rel_m = re.search(r"^\s*relative:\s*([0-9.eE+\-]+)\s*$", text, re.M)
    absolute = float(abs_m.group(1)) if abs_m else None
    relative = float(rel_m.group(1)) if rel_m else None
    if absolute is None and relative is None:
        raise SystemExit("refused: contest.yaml has no reproductionTolerance")
    return absolute, relative


def within(observed: float, expected: float, absolute, relative) -> dict:
    delta = float(observed) - float(expected)
    abs_ok = absolute is not None and abs(delta) <= absolute
    denom = max(abs(float(expected)), 1e-12)
    rel_ok = relative is not None and abs(delta) / denom <= relative
    return {
        "delta": delta,
        "absolute": absolute,
        "relative": relative,
        "absOk": bool(abs_ok),
        "relOk": bool(rel_ok),
        "passed": bool(abs_ok or rel_ok),
    }


def jaccard(a, b) -> float:
    sa, sb = set(a), set(b)
    union = sa | sb
    if not union:
        raise ValueError("empty union")
    return len(sa & sb) / len(union)


def artifact_path(project: Path, exp: dict, rel: str) -> Path:
    """evaluation 产物必须是实验目录内的相对文件，且已登记在 outputFiles（hash 由台账负责）。"""
    if not rel or rel.startswith("/") or ".." in rel:
        raise ValueError("evaluation artifact must be experiment-relative: %r" % (rel,))
    path = project / "experiments" / exp["id"] / rel
    if not path.exists():
        raise FileNotFoundError(str(path))
    recorded = [f.get("path") for f in (exp.get("outputFiles") or [])]
    expected = "experiments/%s/%s" % (exp["id"], rel)
    if expected not in recorded and rel not in recorded:
        raise ValueError("evaluation file was not registered as an output: " + expected)
    return path


def structural_check(rows, dims, methods, k) -> dict:
    problems = []
    if not isinstance(rows, list):
        problems.append("sets.json is not a JSON array")
        return {"ok": False, "problems": problems}
    if len(rows) != len(dims) * len(methods):
        problems.append("rows=%d but dimensions×methods=%d×%d=%d"
                        % (len(rows), len(dims), len(methods), len(dims) * len(methods)))
    seen = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append("row %d is not an object" % i)
            continue
        dim, method, items = row.get("dimension"), row.get("method"), row.get("items")
        if dim not in dims:
            problems.append("row %d has undeclared dimension %r" % (i, dim))
        if method not in methods:
            problems.append("row %d has undeclared method %r" % (i, method))
        key = (dim, method)
        if key in seen:
            problems.append("duplicate (dimension,method) %r" % (key,))
        seen.add(key)
        if not isinstance(items, list) or len(items) != k or len(set(items)) != k:
            problems.append("row %d items must be exactly %d distinct values" % (i, k))
    return {"ok": not problems, "problems": problems,
            "rows": len(rows), "dimensions": len(dims), "methods": len(methods), "topK": k}


def recompute_topk_jaccard(rows, dims, methods, k) -> tuple[float, dict]:
    sets = {}
    for row in rows:
        sets[(row["dimension"], row["method"])] = list(row["items"])
    per_dim = {}
    for dim in dims:
        vals = []
        for i in range(len(methods)):
            for j in range(i + 1, len(methods)):
                a = sets.get((dim, methods[i]))
                b = sets.get((dim, methods[j]))
                if a is None or b is None:
                    raise ValueError("missing set for %s|%s" % (dim, methods[i]))
                if len(a) != k or len(b) != k:
                    raise ValueError("non-topK set for %s" % dim)
                vals.append(jaccard(a, b))
        per_dim[dim] = float(np.mean(vals)) if vals else float("nan")
    overall = float(np.mean(list(per_dim.values())))
    return overall, per_dim


def leakage_audit(project: Path, ledger: dict, exp: dict, dims, features, threshold) -> dict:
    """用注册 split 的 TRAIN 文件复算 feature~target 的 max |r|（Q2 只在训练行内选 Top-3）。"""
    split = find(ledger.get("splits"), "id", exp.get("splitId"))
    if not split or not split.get("trainPath"):
        return {"ok": False, "reason": "no registered train split for " + str(exp.get("splitId"))}
    train_path = project / split["trainPath"]
    if not train_path.exists():
        return {"ok": False, "reason": "train file missing: " + str(train_path)}
    df = pd.read_csv(train_path)
    feats = [f for f in features or [] if f in df.columns]
    missing = [f for f in (features or []) if f not in df.columns]
    present_dims = [d for d in dims if d in df.columns]
    if not feats or not present_dims:
        return {"ok": False, "reason": "no usable feature/dimension columns in train file",
                "missingFeatures": missing[:20], "missingDimensions": [d for d in dims if d not in df.columns][:20]}
    rows = []
    for dim in present_dims:
        y = pd.to_numeric(df[dim], errors="coerce")
        block = df[feats]
        sub = block.copy()
        sub[dim] = y
        corr = sub.corr(numeric_only=True)[dim].drop(labels=[dim], errors="ignore")
        corr = corr.dropna()
        if corr.empty:
            continue
        best = corr.abs().idxmax()
        my_top3 = corr.abs().sort_values(ascending=False).head(3).index.tolist()
        rows.append({"dimension": dim, "bestFeature": str(best),
                     "r": float(corr.loc[best]), "absR": float(abs(corr.loc[best])),
                     "pairs": int(len(df)), "myTop3": [str(c) for c in my_top3]})
    rows.sort(key=lambda r: r["absR"], reverse=True)
    over = [r for r in rows if r["absR"] >= threshold]
    return {"ok": True, "trainPath": split["trainPath"], "threshold": threshold,
            "maxAbsR": rows[0]["absR"] if rows else None,
            "top5": rows[:5], "violations": over, "checkedDimensions": len(rows),
            "missingFeatures": missing[:20],
            "myTop3": {r["dimension"]: r["myTop3"] for r in rows}}


def independent_top3_crosscheck(rows, dims, methods, my_top3) -> dict:
    """描述性交叉核对：用 |Pearson r| 在 TRAIN 行上独立取 Top-3，与各方法集合比 Jaccard。

    这不是 pass/fail 判据：我的排序方法与 modeler 的不同，完全一致不是必要条件；
    但重叠高说明 sets 确实来自数据，而不是手填。
    注意命名：sets.json 用裸化合物名（如 color.EBC.），我的特征是 chem__ 前缀，比较前统一去前缀。
    """
    if not my_top3:
        return {"ok": False, "reason": "independent Top-3 unavailable"}
    def norm(name: str) -> str:
        text = str(name)
        return text[len("chem__"):] if text.startswith("chem__") else text
    sets = {(r["dimension"], r["method"]): [norm(x) for x in r["items"]] for r in rows}
    per_dim = {}
    for dim in dims:
        mine = my_top3.get(dim)
        if not mine:
            continue
        mine_n = [norm(x) for x in mine]
        overlaps = {}
        for method in methods:
            items = sets.get((dim, method))
            if items is None:
                continue
            overlaps[method] = jaccard(mine_n, items)
        if overlaps:
            per_dim[dim] = {"myTop3": mine_n, "jaccard": overlaps,
                            "best": max(overlaps.values())}
    if not per_dim:
        return {"ok": False, "reason": "no overlapping dimension between my Top-3 and sets.json"}
    best = float(np.mean([v["best"] for v in per_dim.values()]))
    exact = int(sum(1 for v in per_dim.values() if any(abs(j - 1.0) < 1e-12 for j in v["jaccard"].values())))
    return {"ok": True, "meanBestJaccard": best, "exactMatchDimensions": exact,
            "checkedDimensions": len(per_dim), "perDimension": per_dim,
            "note": ("描述性交叉核对；我的排序用 |Pearson r|（train 行），与 modeler 方法不同，"
                     "不一致不是失败，但高重叠支持 sets 来自数据。")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--experiment-id", required=True)
    ap.add_argument("--baseline-experiment-id", default=None,
                    help="可选：同口径基线实验（Q2 不在 pack 里登记 baseline-compare，数值对比放这里）")
    ap.add_argument("--out", default="validation/q2-recompute.json")
    ap.add_argument("--correlation-threshold", type=float, default=0.9)
    args = ap.parse_args()

    project = Path(args.project_dir).resolve()
    ledger_path = project / "state" / "ledger.json"
    if not ledger_path.exists():
        print(json.dumps({"status": "refused", "error": "no ledger: " + str(ledger_path)}))
        return 2
    ledger = load_ledger(project)
    exp = find(ledger.get("experiments"), "id", args.experiment_id)
    if not exp:
        print(json.dumps({"status": "refused", "error": "no experiment " + args.experiment_id}))
        return 2
    if exp.get("status") != "succeeded":
        print(json.dumps({"status": "refused",
                          "error": "experiment status is %r, not succeeded" % exp.get("status")}))
        return 2
    evaluation = (exp.get("params") or {}).get("evaluation") or {}
    if evaluation.get("kind") != "set-stability":
        print(json.dumps({"status": "refused",
                          "error": "experiment evaluation.kind is %r, expected set-stability" % evaluation.get("kind")}))
        return 2
    dims = list(evaluation.get("dimensions") or [])
    methods = list(evaluation.get("methods") or [])
    k = evaluation.get("topK")
    metric_key = evaluation.get("metricKey") or "topk-jaccard"
    if len(dims) < 1 or len(methods) < 2 or not isinstance(k, int) or k < 1:
        print(json.dumps({"status": "refused",
                          "error": "set-stability needs dimensions, >=2 methods and integer topK"}))
        return 2
    reported = (exp.get("metrics") or {}).get(metric_key)
    if not isinstance(reported, (int, float)) or isinstance(reported, bool) or not math.isfinite(float(reported)):
        print(json.dumps({"status": "refused", "error": "experiment records no numeric %r" % metric_key}))
        return 2

    try:
        sets_path = artifact_path(project, exp, evaluation.get("setsFile") or "sets.json")
        rows = json.loads(sets_path.read_text("utf-8"))
    except Exception as exc:
        print(json.dumps({"status": "refused", "error": "cannot read sets file: " + str(exc)}))
        return 2

    struct = structural_check(rows, dims, methods, k)
    if not struct["ok"]:
        result = {"status": "refused", "reason": "structural check failed", "structural": struct,
                  "experimentId": exp["id"]}
        (project / args.out).parent.mkdir(parents=True, exist_ok=True)
        (project / args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return 2

    recomputed, per_dim = recompute_topk_jaccard(rows, dims, methods, k)
    absolute, relative = read_tolerance(project)
    comparison = within(recomputed, float(reported), absolute, relative)

    features = (exp.get("params") or {}).get("features") or []
    leak = leakage_audit(project, ledger, exp, dims, features, args.correlation_threshold)
    crosscheck = independent_top3_crosscheck(rows, dims, methods, leak.get("myTop3") if leak.get("ok") else None)

    baseline = None
    if args.baseline_experiment_id:
        base_exp = find(ledger.get("experiments"), "id", args.baseline_experiment_id)
        if base_exp and base_exp.get("status") == "succeeded":
            base_metric = (base_exp.get("metrics") or {}).get(metric_key)
            if isinstance(base_metric, (int, float)) and not isinstance(base_metric, bool):
                baseline = {"experimentId": base_exp["id"], "metric": float(base_metric),
                            "candidate": float(reported), "difference": float(reported) - float(base_metric),
                            "note": "Q2 direction=maximize；difference>0 表示候选一致性高于基线（描述性，不作方向性宣称）。"}
            else:
                baseline = {"requested": args.baseline_experiment_id, "available": False,
                            "reason": "baseline does not report " + metric_key}
        else:
            baseline = {"requested": args.baseline_experiment_id, "available": False}

    passed = bool(comparison["passed"])
    result = {
        "status": "recomputed",
        "experimentId": exp["id"],
        "questionId": exp.get("questionId"),
        "metricKey": metric_key,
        "reported": float(reported),
        "recomputed": recomputed,
        "comparison": comparison,
        "passed": passed,
        "structural": struct,
        "perDimension": per_dim,
        "leakageAudit": leak,
        "independentTop3CrossCheck": crosscheck,
        "baselineComparison": baseline,
        "note": ("topk-jaccard = 方法间 Top-k 集合一致性；它是描述性稳定性，不是对外部标签的预测精度，"
                 "也不构成独立外部验证。"),
    }
    out_path = project / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: result[k] for k in ("status", "experimentId", "metricKey", "reported",
                                             "recomputed", "passed")}, ensure_ascii=False))
    print("wrote " + str(out_path))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
