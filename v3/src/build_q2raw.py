"""01 构建 DATA-Q2raw：4.csv 的 50 个**原始标准化列** + 1.csv 的 231 个特征。

用途：Q2 化合物-风味关联/贡献分析（同期关联，非因果）。
禁止：不得用于 Q1 训练目标（Q1 用 mapped grade 版本），不得把 5/6/7 派生矩阵当特征。
缺失：1.csv 的 73 个缺失格**保留 NaN**，插补只在训练折内做（防止泄漏）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L

PHYSICO_DESC = {
    "pH": "1.csv pH 列；量程核对显示为 log10(pH)（推断；非 8.xlsx 标定实测）",
    "color.EBC.": "1.csv 色度列；量程核对显示为 log10(EBC)（推断）",
    "bitterness": "1.csv 苦度列；量程核对显示为 log10(IBU)（推断）",
    "ethanol..v.v.": "1.csv 酒精度列；量程核对显示为 log10(% v/v)（推断）",
    "CO2.PSI.": "1.csv 二氧化碳列；量程核对显示为 log10(PSI)（推断）",
}


DESC4 = {
    "beer": "样本主键（1..250）",
    "beer_id": "1.csv 的整数 beer_id（仅引用，不作连接键）",
    "tasting_category_fine": "风格标签，22 类（题目 Q3 的 style 标签）",
}


def main() -> int:
    df1, df4 = L.load_1(), L.load_4()
    feats = L.feature_columns()
    t50 = L.target_columns()
    tab = L.load_targets_table().set_index("col_4csv")
    smap = L.scale_map()

    base = df1[["beer", "beer_id", "tasting_category_fine"] + feats].copy()
    tg = df4[["beer"] + t50].copy()
    df = base.merge(tg, on="beer", how="inner").sort_values("beer").reset_index(drop=True)
    assert len(df) == 250 and df["beer"].is_unique, df.shape
    style_ok = (df.set_index("beer")["tasting_category_fine"].astype(str)
                == df4.set_index("beer")["tasting_category_fine"].astype(str).loc[df["beer"]].values)
    assert style_ok.all(), "1.csv 与 4.csv 的风格标签必须逐 beer 一致"

    out = "data/clean/q2_raw.csv"
    L.write_csv(df, out)

    # 字段清单：完整列（来自 profile），逐列注明尺度
    desc, units = {}, {}
    for c in ["beer", "beer_id", "tasting_category_fine"]:
        desc[c] = DESC4[c]
        units[c] = "id" if c != "tasting_category_fine" else "label"
    for c in feats:
        v = smap.get(c, {})
        scale = v.get("verdict", "unverified")
        if scale == "log10":
            desc[c] = PHYSICO_DESC.get(c) or ("1.csv 化合物/理化列；经 8.xlsx Calibrated 数据集逐列核对为 log10(原始浓度)；"
                       "负值表示原始浓度<1" + ("；零值按检测底限编码" if v.get("zero_floor") else ""))
        elif scale == "linear":
            desc[c] = "1.csv 化合物列；经 8.xlsx Calibrated 数据集逐列核对为**原始浓度**（非 log）"
        else:
            desc[c] = "1.csv 化合物列；无可对齐标定，尺度未核验（不得声称 log 或原始）"
        units[c] = "log10(concentration)" if scale == "log10" else ("concentration" if scale == "linear" else "unknown")
    for c in t50:
        grp = tab.loc[c, "group"]
        desc[c] = (f"4.csv 感官目标（{grp}）；标准化/中心化后的连续值，缩放参数未知；"
                   "**不是原始 0–6 分**，仅作 Q2 关联分析的目标")
        units[c] = "standardized unit (unknown scale)"

    profs = sorted((L.PROC).glob("profile-*.json"))
    prof_paths = [str(p.relative_to(L.ROOT)) for p in profs]
    fields = L.build_fields(list(df.columns), prof_paths, desc, units)
    L.write_json(fields, "data/processed/fields_q2raw.json")

    print(f"[Q2raw] shape={df.shape} features={len(feats)} targets={len(t50)}")
    print(f"[Q2raw] missing cells={int(df.isna().sum().sum())} "
          f"cols_with_nan={int((df.isna().sum() > 0).sum())}")
    print(f"[Q2raw] fields={len(fields)} -> data/processed/fields_q2raw.json")
    print(f"[Q2raw] csv -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
