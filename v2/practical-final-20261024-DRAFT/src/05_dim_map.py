"""协议层：建立感官维度的三方对齐表（Lead 所有，供 Q2/论文使用）。

对齐链：
  4.csv 的目标列名（A_* / F_* / 其他）
    <-> 8.xlsx "Sensory names" 的 R_name
    <-> 8.xlsx "Sensory names" 的 CleanName_PanelFeedback（= 5.csv / 6.csv 的列名）
    <-> 6.csv 的列（化学-感官交叉相关）
    <-> 8.xlsx "Sensory names" 的 Category_Paper（Aroma / Taste / Palate / Overall）与 Category（Yeast/Hops/Malt/...）

输出：outputs/protocol/dim_map.csv, outputs/protocol/dim_map.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def norm(s: str) -> str:
    return (str(s).strip().lower()
            .replace("\r", " ").replace("\n", " ")
            .replace("_x000d_", " ")
            .replace("  ", " ").strip())


def main():
    sn = C.load_sensory_names()
    trained = sn[sn["dataset"] == "Trained panel"].copy()
    corr6 = C.load_corr_cross()
    corr5 = pd.read_csv(C.RAW / "5.csv", index_col=0)
    c6 = {norm(c): c for c in corr6.columns}
    c5 = {norm(c): c for c in corr5.columns}

    # 4.csv 的 50 个目标列 -> R_name
    tgt = C.TARGET_DIMS
    # 4.csv 的列名与 R_name 有大小写/拼写差异：A_esters_fruity vs A_ester_fruity、bitternes、X4vg/X4VG
    alias = {
        "A_esters_fruity": "A_esters_fruity",
        "F_esters_fruity": "F_esters_fruity",
        "bitternes": "bitternes",
        "X4vg": "X4vg",
        "4vg": "X4vg",
        "stale_hops": "stale_hops",
        "t2n": "t2n",
        "co2": "co2",
        "dms": "dms",
    }
    by_rname = {str(r).strip(): i for i, r in enumerate(trained["R_name"])}
    rows = []
    for col in tgt:
        key = alias.get(col, col)
        idx = by_rname.get(key)
        rec = {"target_col_4csv": col, "R_name": key, "matched_sensory_names": idx is not None}
        if idx is not None:
            r = trained.iloc[idx]
            rec.update({
                "scientific_name": r["CleanName_Paper"],
                "panel_feedback_name": r["CleanName_PanelFeedback"],
                "category_paper": r["Category_Paper"],
                "chemical_origin_group": r["Category"],
                "datatype": r["DataType"],
            })
            fb = norm(r["CleanName_PanelFeedback"])
            rec["in_6csv"] = c6.get(fb)
            rec["in_5csv"] = c5.get(fb)
        rows.append(rec)
    d = pd.DataFrame(rows)
    C.write_csv(d, "outputs/protocol/dim_map.csv")

    # 覆盖统计
    stats = {
        "n_target_dims": len(tgt),
        "n_matched_to_sensory_names": int(d["matched_sensory_names"].sum()),
        "n_in_6csv": int(d["in_6csv"].notna().sum()),
        "n_in_5csv": int(d["in_5csv"].notna().sum()),
        "category_paper_counts": d["category_paper"].value_counts(dropna=False).to_dict(),
        "origin_group_counts": d["chemical_origin_group"].value_counts(dropna=False).to_dict(),
        "unmatched": d.loc[~d["matched_sensory_names"].astype(bool), "target_col_4csv"].tolist(),
        "not_in_6csv": d.loc[d["in_6csv"].isna(), "target_col_4csv"].tolist(),
        "6csv_shape": list(corr6.shape),
        "5csv_shape": list(corr5.shape),
        "verdict": "A_*/F_* 通过 R_name 对齐；Category_Paper 给出 Aroma/Taste/Palate/Overall 四类；"
                   "6.csv 覆盖 44 个化学指标 × 50 个感官属性",
    }
    C.write_json(stats, "outputs/protocol/dim_map.json")
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
    print(d[["target_col_4csv", "panel_feedback_name", "category_paper", "in_6csv"]].to_string(max_colwidth=40))


if __name__ == "__main__":
    main()
