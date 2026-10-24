#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""src/validate_q3.py — Q3 独立复算与泄漏风险核对（reviewer 所有，不 import modeler 代码）。

口径（由 Lead 在 2026-10-24 拍板，见 report/validation-notes.md §0.2）：
  MCON-0001 的结构化约束是 7 个 `excess__<化合物>` 列、全部 `max:0`，其中
      excess = 原始浓度 / 阈值 − 1   （阈值取数据集同名 `thr__*` 列的 threshold_mean）
  原始浓度按 data_quality.json#perColumnCheck[col].transform 逐列反变换：
      log10      → 10**v
      raw        → v
      zeroFloor  → 存储值等于 floor code 时原始浓度按 0，否则 10**v
  约束满足率 = 一行 7 个 excess 全部 ≤0 才算该行满足。

本脚本做两类核对，二者都必须成立才算通过：
  (A) pack 等价复算：只用 generated_profiles.csv 里的 excess__* 列，复算满足率，
      与 experiments[].metrics["constraint-satisfaction"] 按 contest.yaml 容差比对；
  (B) 独立复算：不信任 excess 列，从生成谱的 chem__<化合物> 列 + 数据集 thr__* 阈值 +
      scaleAudit 变换重新算 excess，再算满足率；与 (A) 逐列比对，任何不一致都是发现。
      同时用同一套公式算 250 个真实样本的基率（当前应为 6/250 = 2.4%），
      作为"该指标天然很低"的真实参照。
附带核对：
  - 输入/表头不得出现 MDI/SHAP/Price；声明的 features 不得含原始标签列 style/style_holdout/
    tasting_category_fine（style 作为生成条件可以编码，但不能以原始列名直接当特征）；
  - style_holdout 的数据层事实（留出风格 Tripel/Kriek/Lambic）；
  - 生成行相对训练行的记忆化率；
  - transfer_report.csv 的缺陷恶化事实（若有）。

判定口径：status="recomputed" 且 passed=true 才通过（exit 0）；不一致 exit 1；
证据缺失/字段不符一律 status="refused"（exit 2），绝不冒充通过。
输出：validation/q3-recompute.json（task-5 写域 validation/）。
"""

from __future__ import annotations

import argparse
import hashlib
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

FORBIDDEN_PATTERN = re.compile(r"(?:mdi|shap|price)", re.IGNORECASE)
RAW_LABEL_COLUMNS = ("style", "style_holdout", "tasting_category_fine", "beer", "beer_id")


def load_json(path: Path):
    return json.loads(path.read_text("utf-8"))


def find(items, key: str, value: str):
    for item in items or []:
        if item.get(key) == value:
            return item
    return None


def read_tolerance(project: Path):
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
    return {"delta": delta, "absolute": absolute, "relative": relative,
            "absOk": bool(abs_ok), "relOk": bool(rel_ok), "passed": bool(abs_ok or rel_ok)}


def numeric(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------------------------------------------------------
# constraints / scale helpers
# ---------------------------------------------------------------------------------------------------------------
def parse_excess_constraints(constraints) -> dict:
    """constraints: [{column:'excess__X', max:0}] -> [{boundColumn, compound, min, max}]"""
    if not isinstance(constraints, list) or not constraints:
        return {"ok": False, "problems": ["model contract has no structured constraints"]}
    problems, parsed = [], []
    for i, bound in enumerate(constraints):
        if not isinstance(bound, dict) or not isinstance(bound.get("column"), str):
            problems.append("constraint %d is not {column,min?,max?}" % i)
            continue
        column = bound["column"]
        if not column.startswith("excess__"):
            problems.append("constraint %d does not target an excess__ column: %r" % (i, column))
            continue
        lo, hi = bound.get("min"), bound.get("max")
        if lo is None and hi is None:
            problems.append("constraint %d has neither min nor max" % i)
            continue
        for name, value in (("min", lo), ("max", hi)):
            if value is not None and numeric(value) is None:
                problems.append("constraint %d has non-finite %s=%r" % (i, name, value))
        if lo is not None and hi is not None and numeric(lo) is not None and numeric(hi) is not None \
                and float(lo) > float(hi):
            problems.append("constraint %d min>max" % i)
        parsed.append({"boundColumn": column, "compound": column[len("excess__"):],
                       "min": None if lo is None else float(lo),
                       "max": None if hi is None else float(hi)})
    return {"ok": not problems, "problems": problems, "bounds": parsed}


def rows_satisfying(frame: pd.DataFrame, bounds) -> tuple:
    """一行满足全部 bound 才算满足（与 pack 的 strict '>' 判定一致：恰好等于 max 算满足）。"""
    violations = {b["boundColumn"]: 0 for b in bounds}
    valid = 0
    for _, row in frame.iterrows():
        ok = True
        for b in bounds:
            x = numeric(row[b["boundColumn"]])
            if x is None:
                ok = False
                violations[b["boundColumn"]] += 1
                continue
            if b["min"] is not None and x < b["min"]:
                ok = False
                violations[b["boundColumn"]] += 1
            elif b["max"] is not None and x > b["max"]:
                ok = False
                violations[b["boundColumn"]] += 1
        if ok:
            valid += 1
    return valid, violations


def load_scale_audit(project: Path) -> dict:
    path = project / "data" / "processed" / "data_quality.json"
    if not path.exists():
        return {"ok": False, "reason": "data/processed/data_quality.json missing"}
    doc = load_json(path)
    percol = doc.get("perColumnCheck")
    if not isinstance(percol, dict):
        return {"ok": False, "reason": "data_quality.json has no perColumnCheck"}
    return {"ok": True, "perColumnCheck": percol}


def floor_code(info: dict):
    """zeroFloor 的 floor code：优先 recurringValues 里出现次数最多的常量，否则 min。"""
    rec = info.get("recurringValues") or []
    if rec and isinstance(rec[0], (list, tuple)) and len(rec[0]) == 2:
        value = rec[0][0]
        if numeric(value) is not None:
            return float(value)
    stats = info.get("stats") or {}
    if numeric(stats.get("min")) is not None:
        return float(stats["min"])
    return None


def inverse_transform(values, transform: str, floor, tolerance: float = 1e-12):
    v = pd.to_numeric(values, errors="coerce")
    if transform == "log10":
        return 10.0 ** v
    if transform == "raw":
        return v
    if transform == "zeroFloor":
        if floor is None:
            raise ValueError("zeroFloor column has no floor code")
        return pd.Series(np.where(np.abs(v - floor) <= tolerance, 0.0, 10.0 ** v), index=v.index)
    raise ValueError("unknown transform " + repr(transform))


def excess_from_chem(frame: pd.DataFrame, compound: str, threshold: float, transform: str, floor):
    col = "chem__" + compound
    if col not in frame.columns:
        raise KeyError(col)
    raw = inverse_transform(frame[col], transform, floor)
    return raw / float(threshold) - 1.0


# ---------------------------------------------------------------------------------------------------------------
# audits
# ---------------------------------------------------------------------------------------------------------------
def threshold_crosscheck(project: Path, details) -> dict:
    """核对数据集 thr__* 常量与 q3_thresholds.json 记录的 8.xlsx threshold_mean 是否一致。

    q3_thresholds.json 里的 thresholdMean 是文档层四舍五入后的值（如 0.206333 vs 0.206333333），
    因此以相对 1e-5 判"一致"；不一致只记录为发现，最终 bound 以数据集 thr__ 列为准。
    """
    path = project / "data" / "processed" / "q3_thresholds.json"
    if not path.exists():
        return {"ok": False, "reason": "q3_thresholds.json missing"}
    doc = load_json(path)
    table = {}
    for row in doc.get("thresholdColumns") or []:
        col = row.get("tableColumn")
        if col:
            table[col] = row
    rows = []
    consistent = True
    for item in details:
        thr_col = item["thresholdColumn"]
        doc_row = table.get(thr_col)
        if not doc_row:
            rows.append({"thresholdColumn": thr_col, "sheet": None, "note": "not in q3_thresholds.json"})
            continue
        sheet_value = numeric(doc_row.get("thresholdMean"))
        dataset_value = float(item["threshold"])
        rel = None
        if sheet_value not in (None, 0.0) and sheet_value is not None:
            rel = abs(dataset_value - sheet_value) / abs(sheet_value)
        agree = rel is not None and rel <= 1e-5
        consistent = consistent and agree
        rows.append({"thresholdColumn": thr_col, "sheetMean": sheet_value,
                     "datasetConstant": dataset_value, "relativeDiff": rel,
                     "sheetUnit": doc_row.get("unit"), "agreeWithin1e-5": agree})
    return {"ok": True, "consistent": consistent, "rows": rows,
            "note": "数据集 thr__* 是约束的实际来源；q3_thresholds 的 thresholdMean 四舍五入到 6 位。"}


def forbidden_input_audit(project: Path, ledger: dict, exp: dict, samples: pd.DataFrame) -> dict:
    features = [str(f) for f in ((exp.get("params") or {}).get("features") or [])]
    dataset = find(ledger.get("datasets"), "id", exp.get("datasetId"))
    dataset_columns = []
    if dataset and dataset.get("processedPath"):
        try:
            dataset_columns = [str(c) for c in pd.read_csv(project / dataset["processedPath"], nrows=0).columns]
        except Exception:
            dataset_columns = []
    # MDI/SHAP/Prices 是 8.xlsx 的拟合产物/非核心列，出现在数据集或输入清单里就是真实泄漏风险。
    hits_features = [f for f in features if FORBIDDEN_PATTERN.search(f)]
    hits_dataset = [c for c in dataset_columns if FORBIDDEN_PATTERN.search(c)]
    # 原始标签列不得直接当输入特征；style 作为条件应编码成 style_onehot__* 之类的条件列。
    raw_labels = [f for f in features if f in RAW_LABEL_COLUMNS]
    return {"ok": not (hits_features or hits_dataset or raw_labels),
            "features": features, "datasetColumns": len(dataset_columns),
            "forbiddenInFeatures": hits_features, "forbiddenInDataset": hits_dataset,
            "rawLabelColumnsInFeatures": raw_labels,
            "note": ("MDI/SHAP 是同批 250 样本的拟合产物，禁止作输入；Prices 不作核心输入；"
                     "style/style_holdout 是条件/留出标签，只能编码后作为条件列，不能以原始列名直接当特征。")}


def style_holdout_audit(project: Path, ledger: dict, exp: dict, samples: pd.DataFrame) -> dict:
    dataset = find(ledger.get("datasets"), "id", exp.get("datasetId"))
    if not dataset or not dataset.get("processedPath"):
        return {"ok": False, "reason": "no dataset processedPath"}
    path = project / dataset["processedPath"]
    if not path.exists():
        return {"ok": False, "reason": "dataset file missing: " + str(path)}
    df = pd.read_csv(path)
    if "style_holdout" not in df.columns:
        return {"ok": False, "reason": "dataset has no style_holdout column"}
    held = sorted({str(v) for v in df["style_holdout"].dropna().unique()})
    heldout_styles = []
    if "style" in df.columns:
        heldout_styles = sorted({str(v) for v in df.loc[
            df["style_holdout"].astype(str).str.lower().str.contains("heldout"), "style"].dropna().unique()})
    style_col = next((c for c in ("style", "tasting_category_fine", "style_holdout") if c in samples.columns), None)
    generated = sorted({str(v) for v in samples[style_col].dropna().unique()}) if style_col else []
    return {"ok": True, "dataset": dataset["id"], "styleHoldoutValues": held,
            "heldOutStyles": heldout_styles, "generatedStyleColumn": style_col,
            "generatedStyles": generated,
            "note": "留出风格是否真的未参与训练只能由模型代码/读取路径静态审查补证；本项只给数据事实。"}


def memorization_audit(project: Path, ledger: dict, exp: dict, samples: pd.DataFrame) -> dict:
    split = find(ledger.get("splits"), "id", exp.get("splitId"))
    if not split or not split.get("trainPath"):
        return {"ok": False, "reason": "no registered train split"}
    train_path = project / split["trainPath"]
    if not train_path.exists():
        return {"ok": False, "reason": "train file missing: " + str(train_path)}
    train = pd.read_csv(train_path)
    pairs = []
    for col in samples.columns:
        for candidate in (col, "chem__" + str(col), str(col).replace("chem__", "")):
            if candidate in train.columns and candidate not in RAW_LABEL_COLUMNS:
                pairs.append((col, candidate))
                break
    if not pairs:
        return {"ok": False, "reason": "no shared non-label columns between generated samples and train file",
                "sampleColumns": [str(c) for c in samples.columns][:20]}
    gen_frame = samples[[c for c, _ in pairs]].copy()
    train_frame = train[[c for _, c in pairs]].copy()
    gen_frame.columns = [f"c{i}" for i in range(len(pairs))]
    train_frame.columns = [f"c{i}" for i in range(len(pairs))]
    def row_hash(frame):
        return frame.apply(lambda r: hashlib.sha256(
            json.dumps([round(float(v), 8) if isinstance(v, (int, float, np.floating)) else str(v)
                        for v in r], ensure_ascii=False).encode("utf-8")).hexdigest(), axis=1)
    gen_hashes = set(row_hash(gen_frame))
    train_hashes = set(row_hash(train_frame))
    dup = len(gen_hashes & train_hashes)
    return {"ok": True, "pairs": pairs, "generatedRows": int(len(samples)),
            "duplicateRows": int(dup), "duplicateRate": (dup / len(samples)) if len(samples) else None,
            "note": "整行完全重复比例；描述性证据，不等同于模型复制训练行。"}


def _violation_flags(frame: pd.DataFrame, bounds) -> dict:
    """返回 {boundColumn: bool Series}（True=违反），与 pack 的 strict 判定一致。"""
    flags = {}
    for b in bounds:
        x = pd.to_numeric(frame[b["boundColumn"]], errors="coerce")
        bad = pd.Series(False, index=frame.index)
        if b.get("max") is not None:
            bad = bad | (x > b["max"])
        if b.get("min") is not None:
            bad = bad | (x < b["min"])
        flags[b["boundColumn"]] = bad.fillna(True)
    return flags


def _satisfaction(frame: pd.DataFrame, bounds):
    if not len(frame):
        return None
    flags = _violation_flags(frame, bounds)
    ok = pd.Series(True, index=frame.index)
    for series in flags.values():
        ok &= ~series
    return float(ok.mean())


def _source_defect_rows(project: Path, ledger: dict, exp: dict, bounds) -> dict:
    """从注册数据集独立重算所有 Pils/Lager 源行的缺陷状态（用于 transfer 的 source 侧）。"""
    dataset = find(ledger.get("datasets"), "id", exp.get("datasetId"))
    scale = load_scale_audit(project)
    if not dataset or not dataset.get("processedPath") or not scale["ok"]:
        return {"ok": False, "reason": "dataset or scale audit unavailable"}
    data = pd.read_csv(project / dataset["processedPath"])
    if "style" not in data.columns:
        return {"ok": False, "reason": "dataset has no style column"}
    src = data[data["style"].astype(str) == "Pils/Lager"].copy()
    if not len(src):
        return {"ok": False, "reason": "no Pils/Lager rows in dataset"}
    percol = scale["perColumnCheck"]
    frame = pd.DataFrame(index=src.index)
    details = []
    for b in bounds:
        comp = b["compound"]
        thr_col = "thr__" + comp
        if thr_col not in data.columns:
            return {"ok": False, "reason": "dataset has no " + thr_col}
        info = percol.get(comp)
        if not isinstance(info, dict):
            return {"ok": False, "reason": "no scale audit for " + comp}
        threshold = float(pd.to_numeric(data[thr_col], errors="coerce").dropna().unique()[0])
        floor = floor_code(info) if info["transform"] == "zeroFloor" else None
        try:
            frame[b["boundColumn"]] = excess_from_chem(src, comp, threshold, info["transform"], floor)
        except Exception as exc:
            return {"ok": False, "reason": "cannot compute source excess for %s: %s" % (comp, exc)}
        details.append({"compound": comp, "threshold": threshold, "transform": info["transform"], "floor": floor})
    flags = _violation_flags(frame, bounds)
    counts = {col: int(series.sum()) for col, series in flags.items()}
    rows = []
    for i in range(len(src)):
        bad = [col for col, series in flags.items() if bool(series.iloc[i])]
        rows.append({"sourceRow": int(src["row"].iloc[i]) if "row" in src.columns else int(src.index[i]),
                     "violations": bad, "nViolations": len(bad),
                     "excess": {col: (float(frame[col].iloc[i]) if numeric(frame[col].iloc[i]) is not None else None)
                                for col in frame.columns}})
    return {"ok": True, "nSourceRows": int(len(src)), "perCompoundViolationCounts": counts,
            "satisfyingAll7": int(sum(1 for r in rows if r["nViolations"] == 0)),
            "rows": rows, "details": details,
            "note": "源行 = 数据集中全部 Pils/Lager 行；按数据集行序编号，未依赖 modeler 代码。"}


def clipping_audit(project: Path, exp: dict, bounds) -> dict:
    """核对 constraint-satisfaction=1.0 是否来自约束投影：未投影文件的违规数 vs 已投影文件。"""
    expdir = project / "experiments" / exp["id"]
    out = {}
    outputs = {}
    op = expdir / "outputs.json"
    if op.exists():
        try:
            outputs = load_json(op)
        except Exception:
            outputs = {}
    declared = ((outputs.get("defectCounts") or {}).get("clippedPerCompound")) or {}
    unc = expdir / "generated_profiles_unconstrained.csv"
    if unc.exists():
        df = pd.read_csv(unc)
        flags = _violation_flags(df, bounds)
        counts = {b["boundColumn"]: int(flags[b["boundColumn"]].sum()) for b in bounds}
        out["unconstrainedViolations"] = counts
        out["unconstrainedSatisfaction"] = _satisfaction(df, bounds)
        out["declaredClippedPerCompound"] = declared
        # outputs 的 key 是裸化合物名，转成 excess__ 前缀比较
        comparable = {b["boundColumn"]: [counts.get(b["boundColumn"]),
                                        declared.get(b["compound"])]
                      for b in bounds}
        out["unconstrainedVsDeclared"] = comparable
        out["unconstrainedCountsMatchDeclared"] = all(v[0] == v[1] for v in comparable.values())
        out["nRowsUnconstrained"] = int(len(df))
    else:
        out["reason"] = "generated_profiles_unconstrained.csv not present"
    con = expdir / "generated_profiles.csv"
    if con.exists():
        df = pd.read_csv(con)
        at_bound = {}
        for b in bounds:
            x = pd.to_numeric(df[b["boundColumn"]], errors="coerce")
            at_bound[b["boundColumn"]] = int((x.abs() <= 1e-12).sum())
        out["constrainedRowsExactlyAtBound"] = at_bound
        out["nRowsConstrained"] = int(len(df))
        out["note"] = ("'恰好等于阈值' 的行数近似为被投影/裁剪的行数；未投影文件里的违规数应等于 "
                       "outputs.defectCounts.clippedPerCompound。这直接说明 1.0 的构造来源。")
    return out


def transfer_profiles_audit(project: Path, ledger: dict, exp: dict, bounds) -> dict:
    """独立复算 Q3 transfer：constrained vs rawshift 逐行/配对，以及 source→constrained 的不恶化率。

    支持 modeler 的 transfer_profiles.csv（sample_id/style + chem__ + excess__ 行），
    也兼容 <缺陷>_before/_after 宽表（本函数只处理前者，后者回退到 transfer_audit）。
    """
    expdir = project / "experiments" / exp["id"]
    outputs = {}
    op = expdir / "outputs.json"
    if op.exists():
        try:
            outputs = load_json(op)
        except Exception:
            outputs = {}
    rel = (outputs.get("artifacts") or {}).get("transferFile")
    chosen = None
    for cand in [rel, "transfer_report.csv", "transfer_profiles.csv"]:
        if cand and (expdir / cand).exists():
            chosen = cand
            break
    if not chosen:
        return {"ok": False, "reason": "no transfer file found (looked for outputs.artifacts.transferFile, "
                                       "transfer_report.csv, transfer_profiles.csv)"}
    df = pd.read_csv(expdir / chosen)
    excess_cols = [b["boundColumn"] for b in bounds if b["boundColumn"] in df.columns]
    if len(excess_cols) != len(bounds) or "style" not in df.columns:
        return {"ok": False, "reason": "transfer file %s is not a profiles table with excess columns" % chosen,
                "columns": [str(c) for c in df.columns][:20]}
    style = df["style"].astype(str)
    cons = df[style.str.contains("constrained", case=False, na=False)].copy()
    raw = df[style.str.contains("rawshift", case=False, na=False)].copy()
    result = {
        "ok": True, "file": chosen, "layout": "profiles(style,excess__)",
        "nRows": int(len(df)),
        "constrained": {"rows": int(len(cons)),
                        "perCompoundViolationCounts": {c: int(_violation_flags(cons, bounds)[c].sum()) for c in excess_cols},
                        "satisfaction": _satisfaction(cons, bounds)} if len(cons) else None,
        "rawshift": {"rows": int(len(raw)),
                     "perCompoundViolationCounts": {c: int(_violation_flags(raw, bounds)[c].sum()) for c in excess_cols},
                     "satisfaction": _satisfaction(raw, bounds)} if len(raw) else None,
    }
    # pair constrained vs rawshift by trailing numeric suffix
    pairs = []
    if len(cons) and len(raw):
        def suffix(frame):
            return frame["sample_id"].astype(str).str.extract(r"(\d+)$")[0].fillna("").astype(str)
        cons["_k"] = suffix(cons)
        raw["_k"] = suffix(raw)
        for _, cr in cons.iterrows():
            match = raw[raw["_k"] == cr["_k"]]
            if not len(match):
                continue
            rr = match.iloc[0]
            cbad = sorted(col for col in excess_cols if numeric(cr[col]) is not None and numeric(cr[col]) > 0)
            rbad = sorted(col for col in excess_cols if numeric(rr[col]) is not None and numeric(rr[col]) > 0)
            pairs.append({"suffix": cr["_k"], "constrainedViolations": len(cbad),
                          "rawshiftViolations": len(rbad),
                          "newUnderShift": sorted(set(rbad) - set(cbad))})
    result["pairedRawshiftVsConstrained"] = pairs
    result["rawshiftNonworsenRate"] = (
        float(sum(1 for p in pairs if p["constrainedViolations"] <= p["rawshiftViolations"]) / len(pairs))
        if pairs else None)
    # source side
    src = _source_defect_rows(project, ledger, exp, bounds)
    result["source"] = src
    declared = (outputs.get("defectCounts") or {})
    if src.get("ok") and declared.get("sourcePilsLager"):
        # 用 outputs 声明的 source 计数交叉验证源行重算（按 excess 列名对齐）
        decl = {k: int(v) for k, v in declared["sourcePilsLager"].items()}
        mine = {("excess__" + comp): src["perCompoundViolationCounts"].get("excess__" + comp)
                for comp in [b["compound"] for b in bounds]}
        comparable = {k: [mine.get(k), decl.get(k)] for k in decl}
        result["sourceVsDeclared"] = comparable
        result["sourceCountsMatchDeclared"] = all(v[0] == v[1] for v in comparable.values())
    # source -> constrained nonworsen (dataset order assumed; validated by aggregate counts above)
    if src.get("ok") and len(pairs) and result.get("sourceCountsMatchDeclared") is True:
        src_rows = src["rows"]
        n = min(len(src_rows), len(pairs))
        worsened = 0
        detail = []
        for i in range(n):
            sbad = set(src_rows[i]["violations"])
            cbad_cols = [col for col in excess_cols if numeric(cons.iloc[i][col]) is not None and numeric(cons.iloc[i][col]) > 0]
            new = sorted(sbad - set(cbad_cols))
            if len(cbad_cols) > len(sbad) or new:
                worsened += 1
            detail.append({"pair": i, "sourceViolations": len(sbad), "constrainedViolations": len(cbad_cols),
                           "newViolations": new})
        result["sourceToConstrained"] = {
            "pairs": n, "worsened": int(worsened),
            "nonworsenRate": float((n - worsened) / n) if n else None,
            "detail": detail,
            "orderBasis": "dataset 行序（聚合计数已与 outputs.sourcePilsLager 核对一致）",
        }
        # 与 modeler 完全相同的定义（cell-wise：after <= before + 1e-12，over 7 化合物 × n 源行），
        # 独立复算 constrained / rawshift 两条 transfer 的不恶化率。
        cons_sorted = cons.copy()
        cons_sorted["_k"] = cons_sorted["sample_id"].astype(str).str.extract(r"(\d+)$")[0].fillna("").astype(str)
        cons_sorted = cons_sorted.sort_values("_k").reset_index(drop=True)
        raw_sorted = raw.copy()
        raw_sorted["_k"] = raw_sorted["sample_id"].astype(str).str.extract(r"(\d+)$")[0].fillna("").astype(str)
        raw_sorted = raw_sorted.sort_values("_k").reset_index(drop=True)
        m = min(len(src_rows), len(cons_sorted), len(raw_sorted))
        def cellwise(after_frame):
            per = {b["boundColumn"]: {"nonworsenCells": 0, "cells": 0, "newlyViolated": 0}
                   for b in bounds}
            for i in range(m):
                for b in bounds:
                    col = b["boundColumn"]
                    before = src_rows[i]["excess"].get(col)
                    after = numeric(after_frame.loc[i, col])
                    if before is None or after is None:
                        continue
                    per[col]["cells"] += 1
                    if after <= before + 1e-12:
                        per[col]["nonworsenCells"] += 1
                    if before <= 0 and after > 0:
                        per[col]["newlyViolated"] += 1
            total_nw = sum(v["nonworsenCells"] for v in per.values())
            total = sum(v["cells"] for v in per.values())
            return {"perCompound": per,
                    "nonworsenCells": total_nw, "cells": total,
                    "nonworsenRate": (total_nw / total) if total else None}
        result["sourceToConstrainedCellwise"] = cellwise(cons_sorted)
        result["sourceToRawshiftCellwise"] = cellwise(raw_sorted)
        result["pairingBasis"] = ("constrained/rawshift 按 sample_id 尾部数字排序，源行按数据集行序；"
                                  "源行与 constrained 的 7 个缺陷值应逐格相同（shift 把缺陷位移 0），"
                                  "若 cellwise constrained 率=1 则配对自洽")
    result["ledgerMetrics"] = {k: (exp.get("metrics") or {}).get(k) for k in (
        "defect-nonworsen-rate", "defect-nonworsen-rate-rawshift",
        "transfer-satisfaction-constrained", "transfer-satisfaction-rawshift", "transfer-satisfaction-source")}
    result["declaredDefectCounts"] = {
        "clippedPerCompound": declared.get("clippedPerCompound"),
        "generatedUnconstrained": declared.get("generatedUnconstrained"),
        "realAll250SatisfyingAll7": declared.get("realAll250SatisfyingAll7"),
        "realHeldoutSatisfyingAll7": declared.get("realHeldoutSatisfyingAll7"),
        "unassessableDefects": declared.get("unassessableDefects"),
    }
    return result


def transfer_audit(project: Path, exp: dict) -> dict:
    path = project / "experiments" / exp["id"] / "transfer_report.csv"
    if not path.exists():
        return {"ok": False, "reason": "transfer_report.csv not present"}
    df = pd.read_csv(path)
    worsened = []
    # 形态 A：一行一缺陷，列 defect/before/after（或 compound/from/to）。
    defect_col = next((c for c in df.columns if str(c).lower() in ("defect", "compound", "item")), None)
    before_col = next((c for c in df.columns if str(c).lower() in ("before", "src", "source", "pre")), None)
    after_col = next((c for c in df.columns if str(c).lower() in ("after", "dst", "target", "post")), None)
    if defect_col and before_col and after_col:
        for _, row in df.iterrows():
            b, a = numeric(row[before_col]), numeric(row[after_col])
            if b is None or a is None:
                continue
            worsened.append({"defect": str(row[defect_col]), "meanDelta": a - b, "worsened": bool(a > b)})
        return {"ok": True, "layout": "one-row-per-defect", "columns": [str(c) for c in df.columns],
                "worsened": worsened, "note": "meanDelta>0 表示该缺陷在迁移后变差（按原始列方向，不翻转）。"}
    # 形态 B：宽表，列名形如 <缺陷>_before / <缺陷>_after。
    pairs = []
    for col in df.columns:
        m = re.match(r"^(.*?)(?:_|\.)?(before|after|src|dst|source|target|pre|post)$", str(col), re.IGNORECASE)
        if m:
            pairs.append((m.group(1), m.group(2), str(col)))
    for base in sorted({p[0] for p in pairs}):
        before = next((c for b, w, c in pairs if b == base and w.lower() in ("before", "src", "source", "pre")), None)
        after = next((c for b, w, c in pairs if b == base and w.lower() in ("after", "dst", "target", "post")), None)
        if before and after:
            delta = pd.to_numeric(df[after], errors="coerce") - pd.to_numeric(df[before], errors="coerce")
            worsened.append({"defect": base, "n": int(delta.notna().sum()),
                             "meanDelta": float(delta.mean()) if delta.notna().any() else None,
                             "worsenedRows": int((delta > 0).sum())})
    return {"ok": bool(pairs), "layout": "wide-before-after", "columns": [str(c) for c in df.columns],
            "pairs": pairs, "worsened": worsened,
            "note": "只有列名可机械配对时才给数值；否则需要人工核对 transfer_report 的结构。"}


# ---------------------------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--experiment-id", required=True)
    ap.add_argument("--baseline-experiment-id", default=None,
                    help="可选：同口径基线实验（缺省时不做数值对比）")
    ap.add_argument("--out", default="validation/q3-recompute.json")
    args = ap.parse_args()

    project = Path(args.project_dir).resolve()
    ledger_path = project / "state" / "ledger.json"
    if not ledger_path.exists():
        print(json.dumps({"status": "refused", "error": "no ledger: " + str(ledger_path)}))
        return 2
    ledger = load_json(ledger_path)
    exp = find(ledger.get("experiments"), "id", args.experiment_id)
    if not exp:
        print(json.dumps({"status": "refused", "error": "no experiment " + args.experiment_id}))
        return 2
    if exp.get("status") != "succeeded":
        print(json.dumps({"status": "refused",
                          "error": "experiment status is %r, not succeeded" % exp.get("status")}))
        return 2
    evaluation = (exp.get("params") or {}).get("evaluation") or {}
    if evaluation.get("kind") != "constraint-satisfaction":
        print(json.dumps({"status": "refused",
                          "error": "experiment evaluation.kind is %r, expected constraint-satisfaction"
                                   % evaluation.get("kind")}))
        return 2
    metric_key = evaluation.get("metricKey") or "constraint-satisfaction"
    reported = (exp.get("metrics") or {}).get(metric_key)
    if not isinstance(reported, (int, float)) or isinstance(reported, bool) or not math.isfinite(float(reported)):
        print(json.dumps({"status": "refused", "error": "experiment records no numeric %r" % metric_key}))
        return 2

    quality = ledger.get("quality") or {}
    contract = find(quality.get("modelContracts"), "id", evaluation.get("modelContractId"))
    if not contract:
        print(json.dumps({"status": "refused",
                          "error": "no model contract %r" % evaluation.get("modelContractId")}))
        return 2
    if contract.get("questionId") not in (None, exp.get("questionId")):
        print(json.dumps({"status": "refused", "error": "model contract belongs to another question"}))
        return 2
    parsed = parse_excess_constraints(contract.get("constraints"))
    if not parsed["ok"]:
        print(json.dumps({"status": "refused", "reason": "malformed model contract constraints",
                          "bounds": parsed}))
        return 2
    bounds = parsed["bounds"]

    rel = evaluation.get("samplesFile") or "generated_profiles.csv"
    samples_path = project / "experiments" / exp["id"] / rel
    if not samples_path.exists():
        print(json.dumps({"status": "refused", "error": "samples file missing: " + str(samples_path)}))
        return 2
    samples = pd.read_csv(samples_path)

    missing_cols = [b["boundColumn"] for b in bounds if b["boundColumn"] not in samples.columns]
    if missing_cols:
        print(json.dumps({"status": "refused",
                          "reason": "generated samples miss declared constraint columns",
                          "missingColumns": missing_cols}))
        return 2

    # (A) pack 等价复算：只用 excess__* 列
    valid_pack, violations_pack = rows_satisfying(samples, bounds)
    value_pack = valid_pack / len(samples) if len(samples) else None

    absolute, relative = read_tolerance(project)
    comparison_pack = within(value_pack, float(reported), absolute, relative)

    # (B) 独立复算：从 chem__* + thr__* + scaleAudit 重算 excess
    dataset = find(ledger.get("datasets"), "id", exp.get("datasetId"))
    scale = load_scale_audit(project)
    independent = {"available": False, "reason": None}
    value_ind = None
    base_rate = None
    if not dataset or not dataset.get("processedPath"):
        independent["reason"] = "experiment has no registered dataset with processedPath"
    elif not scale["ok"]:
        independent["reason"] = scale.get("reason")
    else:
        data_path = project / dataset["processedPath"]
        if not data_path.exists():
            independent["reason"] = "dataset file missing: " + str(data_path)
        else:
            data = pd.read_csv(data_path)
            percol = scale["perColumnCheck"]
            thresholds, transforms, details = {}, {}, []
            ok = True
            for b in bounds:
                comp = b["compound"]
                thr_col = "thr__" + comp
                if thr_col not in data.columns:
                    independent["reason"] = "dataset has no threshold column " + thr_col
                    ok = False
                    break
                thr_values = pd.to_numeric(data[thr_col], errors="coerce").dropna().unique()
                if len(thr_values) != 1:
                    independent["reason"] = "threshold column %s is not a constant (%d distinct)" % (thr_col, len(thr_values))
                    ok = False
                    break
                info = percol.get(comp)
                if not isinstance(info, dict) or info.get("transform") not in ("log10", "raw", "zeroFloor"):
                    independent["reason"] = "scaleAudit has no usable transform for " + comp
                    ok = False
                    break
                thresholds[comp] = float(thr_values[0])
                transforms[comp] = info
                details.append({"compound": comp, "thresholdColumn": thr_col,
                                "threshold": thresholds[comp], "transform": info["transform"],
                                "floor": floor_code(info) if info["transform"] == "zeroFloor" else None,
                                "excessColumn": b["boundColumn"]})
            if ok:
                ind_frame = pd.DataFrame(index=samples.index)
                for b in bounds:
                    comp = b["compound"]
                    try:
                        ind_frame[b["boundColumn"]] = excess_from_chem(
                            samples, comp, thresholds[comp], transforms[comp]["transform"],
                            floor_code(transforms[comp]) if transforms[comp]["transform"] == "zeroFloor" else None)
                    except KeyError:
                        independent["reason"] = "generated samples miss chem__%s needed for independent recompute" % comp
                        ok = False
                        break
                    except ValueError as exc:
                        independent["reason"] = str(exc)
                        ok = False
                        break
                if ok:
                    ind_bounds = [{"boundColumn": b["boundColumn"], "min": b["min"], "max": b["max"]} for b in bounds]
                    valid_ind, violations_ind = rows_satisfying(ind_frame, ind_bounds)
                    value_ind = valid_ind / len(ind_frame) if len(ind_frame) else None
                    disagreements = []
                    for b in bounds:
                        a = pd.to_numeric(samples[b["boundColumn"]], errors="coerce")
                        c = ind_frame[b["boundColumn"]]
                        mask = a.notna() & c.notna()
                        if int(mask.sum()) == 0:
                            disagreements.append({"column": b["boundColumn"], "reason": "no comparable rows"})
                            continue
                        max_diff = float((a[mask] - c[mask]).abs().max())
                        if max_diff > max(absolute or 0.0, 1e-9):
                            disagreements.append({"column": b["boundColumn"], "maxAbsDiff": max_diff})
                    independent = {"available": True, "value": value_ind,
                                   "valid": int(valid_ind), "n": int(len(ind_frame)),
                                   "perColumnViolations": violations_ind,
                                   "excessDetail": details,
                                   "thresholdCrossCheck": threshold_crosscheck(project, details),
                                   "excessColumnDisagreements": disagreements,
                                   "excessColumnsAgree": not disagreements,
                                   "reportedVsIndependent": within(value_ind, float(reported), absolute, relative)}
                    # 真实样本基率（同一套公式、同一批阈值/变换）
                    base_frame = pd.DataFrame(index=data.index)
                    base_ok = True
                    for b in bounds:
                        comp = b["compound"]
                        col = "chem__" + comp
                        if col not in data.columns:
                            base_ok = False
                            break
                        base_frame[b["boundColumn"]] = excess_from_chem(
                            data, comp, thresholds[comp], transforms[comp]["transform"],
                            floor_code(transforms[comp]) if transforms[comp]["transform"] == "zeroFloor" else None)
                    if base_ok:
                        base_valid, base_viol = rows_satisfying(
                            base_frame, [{"boundColumn": b["boundColumn"], "min": b["min"], "max": b["max"]} for b in bounds])
                        base_rate = {"valid": int(base_valid), "n": int(len(base_frame)),
                                     "value": base_valid / len(base_frame),
                                     "perColumnViolations": base_viol,
                                     "note": "250 个真实样本同时满足全部 7 个 excess≤0 的比例；指标天然很低是数据事实。"}

    forbidden = forbidden_input_audit(project, ledger, exp, samples)
    style = style_holdout_audit(project, ledger, exp, samples)
    memo = memorization_audit(project, ledger, exp, samples)
    transfer = transfer_profiles_audit(project, ledger, exp, bounds)
    if not transfer.get("ok"):
        fallback = transfer_audit(project, exp)
        transfer = {"profiles": transfer, "tableFallback": fallback,
                    "ok": bool(fallback.get("ok")), "reason": transfer.get("reason")}
    clipping = clipping_audit(project, exp, bounds)

    baseline = None
    if args.baseline_experiment_id:
        base_exp = find(ledger.get("experiments"), "id", args.baseline_experiment_id)
        if base_exp and base_exp.get("status") == "succeeded":
            base_metric = (base_exp.get("metrics") or {}).get(metric_key)
            if isinstance(base_metric, (int, float)) and not isinstance(base_metric, bool):
                baseline = {"experimentId": base_exp["id"], "metric": float(base_metric),
                            "candidate": float(reported), "difference": float(reported) - float(base_metric),
                            "note": "Q3 direction=maximize；difference>0 表示候选高于基线。"}
        else:
            baseline = {"requested": args.baseline_experiment_id, "available": False}

    # 独立复算是 reviewer 的签署条件，不是可选项：generated_profiles.csv 必须带 chem__* 列，
    # 否则只能做 pack 等价复算（等于相信模型自己写的 excess 列），本脚本拒绝给 passed。
    if not independent.get("available"):
        independent_ok = False
        status = "needs_review"
        limit_reason = ("independent recompute unavailable: " + str(independent.get("reason"))
                        + "; generated_profiles.csv must carry the chem__* columns used to compute excess__*")
    else:
        independent_ok = (independent.get("excessColumnsAgree") is True
                          and independent.get("reportedVsIndependent", {}).get("passed") is True)
        limit_reason = None
    passed = bool(comparison_pack["passed"]) and bool(forbidden["ok"]) and bool(independent_ok)
    if independent.get("available"):
        status = "recomputed" if passed else "failed"
    result = {
        "status": status,
        "limitation": limit_reason,
        "experimentId": exp["id"],
        "questionId": exp.get("questionId"),
        "metricKey": metric_key,
        "reported": float(reported),
        "recomputedFromExcessColumns": value_pack,
        "comparisonReportedVsExcess": comparison_pack,
        "perColumnViolations": violations_pack,
        "sampleSize": int(len(samples)),
        "independentRecompute": independent,
        "baseRateOnRealSamples": base_rate,
        "forbiddenInputs": forbidden,
        "styleHoldout": style,
        "memorization": memo,
        "transfer": transfer,
        "clipping": clipping,
        "baselineComparison": baseline,
        "passed": passed,
        "note": ("constraint-satisfaction 只证明生成谱满足声明的数值约束，不是真实酿造验证、"
                 "不是因果结论；trans-2-nonenal 与 Stale hops 在附件里没有数值阈值，属不可评估限制。"),
    }
    out_path = project / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: result[k] for k in ("status", "experimentId", "metricKey", "reported",
                                             "recomputedFromExcessColumns", "passed")}, ensure_ascii=False))
    if independent.get("available"):
        print("independent=%r  baseRate=%r" % (independent.get("value"),
                                               (base_rate or {}).get("value")))
    print("wrote " + str(out_path))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
