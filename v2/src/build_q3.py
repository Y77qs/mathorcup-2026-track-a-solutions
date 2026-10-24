"""03 构建 DATA-Q3：风格标签 + 化合物域 + 8.xlsx 缺陷阈值 + **显式风格留出**。

Q3 是条件生成题（不是普通预测）：
  * 风格标签 = 1.csv 的 tasting_category_fine（22 类）；
  * 跨风格迁移的评估必须用 **风格留出（style holdout）**，不能用随机 split 冒充；
    本脚本把 Tripel / Kriek / Lambic 这些风格整类划入 style_holdout，其余风格为 train；
  * 阈值来自 8.xlsx Sensory thresholds（261 行中仅 43 行有阈值），按题面点名的
    DMS / Diacetyl / 4VG / trans-2-nonenal / Stale hops 逐化合物对齐；
  * MDI/SHAP 是同批 250 样本的拟合产物 => 绝不作输入特征；Prices 有大量 NA => 不作核心证据。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L

HOLDOUT_STYLES = ["Tripel", "Kriek", "Lambic"]

DEFECT_SPEC = {
    "DMS": ["DMS"],
    "Diacetyl": ["X2.3.butanedione"],
    "4VG": ["X4VG"],
    "trans-2-nonenal": ["X.E..2.nonenal"],
    "Stale hops": ["X3.methyl.2.butenal", "furfural", "X5.methylfurfural", "X.E..2.nonenal"],
}


PHYSICO_DESC = {
    "pH": "1.csv pH 列；量程核对显示为 log10(pH)（推断；非 8.xlsx 标定实测）",
    "color.EBC.": "1.csv 色度列；量程核对显示为 log10(EBC)（推断）",
    "bitterness": "1.csv 苦度列；量程核对显示为 log10(IBU)（推断）",
    "ethanol..v.v.": "1.csv 酒精度列；量程核对显示为 log10(% v/v)（推断）",
    "CO2.PSI.": "1.csv 二氧化碳列；量程核对显示为 log10(PSI)（推断）",
}


def main() -> int:
    df1 = L.load_1()
    feats = L.feature_columns()
    smap = L.scale_map()
    th = L.xlsx_sheet("8.xlsx", "Sensory thresholds")

    base = df1[["beer", "beer_id", "tasting_category_fine"] + feats].copy()
    base = base.sort_values("beer").reset_index(drop=True)
    styles = sorted(base["tasting_category_fine"].astype(str).unique())
    unknown = [s for s in HOLDOUT_STYLES if s not in styles]
    hold = [s for s in HOLDOUT_STYLES if s in styles]
    assert hold, f"style holdout 风格必须在 22 类中，实际 {styles}"

    base["style_holdout"] = base["tasting_category_fine"].astype(str).isin(hold).astype(int)
    base["split_role"] = np.where(base["style_holdout"] == 1, "style_holdout", "train")

    # 缺陷阈值列（参考常数，逐化合物）
    thr_spec = {}
    for label, comps in DEFECT_SPEC.items():
        thr_spec[label] = []
        for c in comps:
            sub = th[th["field_name_R"].astype(str).str.strip() == c]
            if sub.empty:
                thr_spec[label].append({"compound": c, "has_threshold": False})
                continue
            r = sub.iloc[0]
            has = bool(pd.notna(r["threshold_mean"]))
            unit = r["unit"] if isinstance(r["unit"], str) else None
            thr_spec[label].append({
                "compound": c, "has_threshold": has,
                "threshold_mean": float(r["threshold_mean"]) if has else None,
                "threshold_median": float(r["threshold_median"]) if has else None,
                "unit": unit,
                "scale_in_1csv": smap.get(c, {}).get("verdict", "unverified"),
                "zero_floor_encoded": bool(smap.get(c, {}).get("zero_floor", False)),
            })
            if has:
                base[f"threshold__{c}"] = float(r["threshold_mean"])
                base[f"threshold_unit__{c}"] = unit or "unknown"
            else:
                base[f"threshold__{c}"] = np.nan
                base[f"threshold_unit__{c}"] = "no threshold in 8.xlsx"

    o = "data/clean/q3.csv"
    L.write_csv(base, o)
    asg = base[["beer", "tasting_category_fine", "style_holdout", "split_role"]].copy()
    L.write_csv(asg, "data/processed/q3_style_holdout_assignment.csv")
    L.write_json({"holdout_styles": hold, "unknown_styles": unknown,
                  "all_styles": styles, "n_styles": len(styles),
                  "counts": base["split_role"].value_counts().to_dict(),
                  "rationale": "跨风格迁移必须整类留出；Tripel/Kriek/Lambic 作为目标风格留出，其余风格训练",
                  "defect_spec": thr_spec},
                 "data/processed/q3_style_holdout.json")

    # 字段清单
    desc, units = {}, {}
    desc.update({"beer": "样本主键（1..250）", "beer_id": "1.csv 整数 id（仅引用）",
                 "tasting_category_fine": "风格标签（22 类），Q3 的条件变量",
                 "style_holdout": "1=该风格整体留出（跨风格迁移评估集）",
                 "split_role": "train / style_holdout（显式构造，非随机划分）"})
    units.update({"beer": "id", "beer_id": "id", "tasting_category_fine": "label",
                  "style_holdout": "flag", "split_role": "label"})
    for c in feats:
        v = smap.get(c, {})
        sc = v.get("verdict", "unverified")
        desc[c] = PHYSICO_DESC.get(c) or ("1.csv 化合物列；尺度=" + ("log10(浓度)" if sc == "log10" else
                                             "原始浓度" if sc == "linear" else "未核验"))
        units[c] = "log10(concentration)" if sc == "log10" else ("concentration" if sc == "linear" else "unknown")
    for c in base.columns:
        if c.startswith("threshold_unit__"):
            units[c] = "label"
            desc[c] = "阈值单位（来自 8.xlsx）"
        elif c.startswith("threshold__"):
            desc[c] = ("8.xlsx Sensory thresholds 的 threshold_mean（参考常数，逐样本重复）；"
                       "用于 OAV/超过阈值检查，不是观测值")
            units[c] = "mg/L (mostly)"
    prof_paths = [str(p.relative_to(L.ROOT)) for p in sorted(L.PROC.glob("profile-*.json"))]
    fields = L.build_fields(list(base.columns), prof_paths, desc, units)
    L.write_json(fields, "data/processed/fields_q3.json")

    print(json.dumps({
        "shape": list(base.shape), "styles": len(styles), "holdout_styles": hold,
        "unknown_styles": unknown,
        "n_holdout": int(base["style_holdout"].sum()),
        "holdout_counts": asg[asg.style_holdout == 1]["tasting_category_fine"].value_counts().to_dict(),
        "threshold_cols": [c for c in base.columns if c.startswith("threshold__")],
        "csv": o,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
