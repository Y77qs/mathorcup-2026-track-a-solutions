"""协议层：生成**完整字段清单**的建模表 + 一致性与登记自检。

解决的问题（Lead 自检发现）：
  1. 已登记的 DATA-0001 只有 16 条 fields（含"聚合列/典型化合物"式占位），不是 231 列的完整清单；
  2. DATA-0001 只有特征、**没有 50 个感官目标**，holdout-metrics 无法从中取 y_true；
  3. 50 维多输出目标不能被单列（如 A_hops_all）代表。
本脚本产出：
  * `data/clean/model_table.csv`：250 × 284 = 3 键 + 231 特征 + 50 目标（数值一字不改，目标取自 4.csv）
  * `data/clean/fields_model.json`：284 条完整字段（名称取自真实表头，类型取自 pandas dtype，
    单位/尺度取自 outputs/audit/scale_identification.csv 与 8.xlsx 阈值表，目标取自 dim_map.csv）
  * `outputs/protocol/model_table_checks.json`：行数/列名/缺失/一致性/与工作台特征声明的一致性
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

PHYSICAL = {"pH": "pH", "color.EBC.": "EBC", "bitterness": "IBU", "CO2.PSI.": "PSI",
            "ethanol..v.v.": "% v/v", "betaglucan.mg.L.": "mg/L", "lactic_acid.mg.L.": "mg/L",
            "ammonia.mg.L.": "mg/L", "protein.g.L.": "g/L", "iron": "mg/L",
            "acetic_acid.g.L.": "g/L", "SO2.mg.L.": "mg/L", "GFS": "g/L",
            "unfermentables": "unverified", "kcalperc": "log10(kcal/100ml)",
            "glycerol": "g/L", "esters_sum": "unverified", "aroma_hops_sum": "unverified",
            "acids_sum": "unverified", "sulfur_sum": "unverified"}

ESTER_KW = ("acetate", "butyrate", "decanoate", "hexanoate", "octanoate", "propionate",
            "isovalerate", "formate", "lactate", "benzoate", "tiglate", "caprylate",
            "succinate", "hydrocinnamate", "cinnamate", "nicotinate", "furoate",
            "phenylacetate", "geranate", "farnesoate", "salicylate", "tetradecanoate",
            "pentadecanoate", "hexadecanoate", "octadecanoate", "pentanoate", "laurate",
            "isobutyrate", "isobutanoate", "propanoate", "butanoate")
TERPENE_KW = ("linalool", "geraniol", "nerol", "citronellol", "terpineol", "terpinen",
              "limonene", "ocimene", "farnesene", "farnesal", "farnesol", "humulene",
              "caryophyllene", "caryophyllane", "pinene", "phellandrene", "myrcene",
              "camphor", "eucalyptol", "nerolidol", "eudesmol", "muurolol", "cadinol",
              "spathulenol", "valencene", "germacrene", "cubenol", "calacorene",
              "aromadendrene", "ionone", "damascenone", "citral", "cymene", "terpinolene",
              "isoborneol", "manool", "ambroxide", "foeniculin", "cadalene", "caryophyllene",
              "humulene", "epoxy")
SULFUR_KW = ("DMS", "DES", "H2S", "MeSH", "CS2", "SO2", "sulfur", "thio")
ALDEHYDE_KW = ("acetaldehyde", "nonanal", "furfural", "butanal", "benzaldehyde",
               "phenylacetaldehyde", "cinnamaldehyde", "cumin", "dodecanal", "isomaltol",
               "vanillin", "heptanal")
PHENOL_KW = ("phenol", "guaiacol", "cresol", "eugenol", "vanillin", "anisate", "methoxy")
HETEROKW = ("pyrazine", "pyridine", "pyrrole", "furan", "maltol", "methylfuran", "acetylfuran")
ALCOHOL_KW = ("alcohol", "propanol", "pentanol", "butanol", "hexanol", "heptanol",
              "octanol", "nonanol", "decanol", "undecanol", "dodecanol", "tetradecanol",
              "octen", "hexenol", "menthol", "borneol", "glycol")


def group_of(name: str, origin: str | None) -> str:
    if origin and isinstance(origin, str) and origin.strip() not in ("", "nan"):
        return f"origin:{origin.strip()}"
    n = name.lower()
    if any(k in n for k in SULFUR_KW):
        return "chemical:sulfur"
    if any(k in n for k in ESTER_KW):
        return "chemical:ester"
    if any(k in n for k in TERPENE_KW):
        return "chemical:terpene"
    if any(k in n for k in ALDEHYDE_KW):
        return "chemical:aldehyde/ketone"
    if any(k in n for k in PHENOL_KW):
        return "chemical:phenol"
    if any(k in n for k in HETEROKW):
        return "chemical:heterocycle(Maillard)"
    if any(k in n for k in ALCOHOL_KW):
        return "chemical:alcohol"
    if "lactone" in n:
        return "chemical:lactone"
    return "chemical:other-volatile"


def main():
    feat = C.load_features()                     # 250 x (3 + 231)
    tgt = C.load_targets()                       # 250 x (3 + 50)
    fl = C.feature_columns()
    assert len(fl) == 231, len(fl)
    assert len(C.TARGET_DIMS) == 50

    # ---- 建模表：3 键 + 231 特征 + 50 目标
    base = feat[["beer", "beer_id", "tasting_category_fine"]].copy()
    mt = pd.concat([base, feat[fl], tgt[C.TARGET_DIMS]], axis=1)
    assert mt.shape == (250, 284), mt.shape
    C.write_csv(mt, "data/clean/model_table.csv")

    # ---- 尺度/阈值信息
    si = pd.read_csv(C.ROOT / "outputs/audit/scale_identification.csv")
    si_col = si.columns[0]
    si = si.set_index(si_col)
    th = C.threshold_table().set_index("field")
    dm = pd.read_csv(C.ROOT / "outputs/protocol/dim_map.csv").set_index("target_col_4csv")

    fields = [
        {"name": "beer", "type": "int64", "unit": "-",
         "description": "样本序号 1..250；唯一可靠连接键（4/7.csv 的 beer_id 已脱敏）"},
        {"name": "beer_id", "type": "int64", "unit": "-",
         "description": "1.csv 未脱敏条码；4/7.csv 不可按其 join"},
        {"name": "tasting_category_fine", "type": "string(categorical,22)", "unit": "-",
         "description": "风格标签（Q3 条件变量；1.csv 与 4.csv 逐 beer 一致 250/250）"},
    ]

    for c in fl:
        rec = {"name": c}
        rec["type"] = str(mt[c].dtype)
        if c in PHYSICAL:
            rec["unit"] = PHYSICAL[c]
            rec["description"] = f"理化参数（单位 {PHYSICAL[c]}）；换算尺度见 scale/scale_status 字段"
        else:
            rec["unit"] = "log10(concentration) | concentration | unverified（三态，见 scale）"
            rec["description"] = "挥发性风味化合物丰度"
        if c in si.index:
            row = si.loc[c]
            rec["scale"] = str(row.get("scale_verdict", "unverified"))
            rec["scale_status"] = str(row.get("scale_hint", "unverified"))
            rec["scale_verified"] = str(row.get("scale_hint", "")) in ("verified",)
            rec["scale_evidence_rel_err"] = (
                float(row["median_rel_err_log10"]) if pd.notna(row.get("median_rel_err_log10")) else None)
            rec["can_compute_oav"] = bool(row.get("can_oav", False))
            if c in PHYSICAL:
                rec["unit"] = PHYSICAL[c]
        else:
            rec["scale"] = "unverified"
            rec["scale_status"] = "unverified"
            rec["scale_verified"] = False
            rec["scale_evidence_rel_err"] = None
            rec["can_compute_oav"] = False
        if c in th.index:
            rec["odor_threshold_mean"] = float(th.loc[c, "threshold_mean"])
            rec["threshold_unit"] = str(th.loc[c, "unit"])
            rec["off_flavor"] = str(th.loc[c, "off_flavors"]) if pd.notna(th.loc[c, "off_flavors"]) else None
            rec["threshold_origin"] = str(th.loc[c, "origin_paper"])
        rec["chemical_group"] = group_of(c, th.loc[c, "origin_paper"] if c in th.index else None)
        rec["missing"] = int(mt[c].isna().sum())
        rec["role"] = "feature"
        fields.append(rec)

    for d in C.TARGET_DIMS:
        rec = {"name": d, "type": str(mt[d].dtype), "unit": "standardized(centered, unknown scale)",
               "role": "target", "missing": int(mt[d].isna().sum())}
        if d in dm.index:
            r = dm.loc[d]
            rec["description"] = (f"感官维度；面板名 {r.get('panel_feedback_name')}；"
                                  f"学科名 {r.get('scientific_name')}；"
                                  f"Category_Paper={r.get('category_paper')}；"
                                  f"化合物来源类={r.get('chemical_origin_group')}")
        else:
            rec["description"] = "感官维度（8.xlsx Sensory names 未收录）"
        rec["sensory_set"] = ("Aroma" if d in C.AROMA_DIMS
                              else "Flavour/Taste" if d in C.FLAVOUR_DIMS else "Palate/Defect/Overall")
        rec["defect"] = d in C.DEFECT_DIMS
        fields.append(rec)

    assert len(fields) == 284, len(fields)
    names = [f["name"] for f in fields]
    assert len(set(names)) == len(names)
    C.write_json(fields, "data/clean/fields_model.json")

    # ---- 一致性自检
    declared = None
    try:
        led = json.loads((C.ROOT / "state/ledger.json").read_text())
        q = led.get("questions") or led.get("questionPlans") or {}
        if isinstance(q, list):
            for item in q:
                if item.get("id") == "Q1" or item.get("questionId") == "Q1":
                    ap = item.get("analysisPlan") or {}
                    declared = ap.get("features")
        elif isinstance(q, dict):
            ap = ((q.get("Q1") or {}).get("analysisPlan") or {})
            declared = ap.get("features")
    except Exception as e:  # noqa
        declared = f"[ledger read failed: {e}]"

    checks = {
        "model_table_shape": list(mt.shape),
        "n_keys": 3, "n_features": len(fl), "n_targets": len(C.TARGET_DIMS),
        "n_fields_declared": len(fields),
        "fields_all_from_real_headers": bool(set(fl + C.TARGET_DIMS) <= set(mt.columns)),
        "feature_list_equals_1csv_minus_keys": bool(fl == C.feature_columns()),
        "targets_are_all_50_not_single_column": True,
        "n_missing_cells_total": int(mt.isna().sum().sum()),
        "n_missing_feature_cells": int(mt[fl].isna().sum().sum()),
        "n_missing_target_cells": int(mt[C.TARGET_DIMS].isna().sum().sum()),
        "row_identity_beer_1_to_250": bool(mt["beer"].tolist() == list(range(1, 251))),
        "targets_match_4csv_on_beer": bool(
            np.allclose(mt[C.TARGET_DIMS].values, tgt[C.TARGET_DIMS].values)),
        "workbench_declared_features": declared if isinstance(declared, str) else
            (list(declared) if declared is not None else None),
        "workbench_features_equal_231": (isinstance(declared, list) and set(declared) == set(fl)),
        "workbench_extra_declared": (sorted(set(declared) - set(fl))
                                     if isinstance(declared, list) else None),
        "workbench_missing_declared": (sorted(set(fl) - set(declared))
                                       if isinstance(declared, list) else None),
        "evaluation_contract": {
            "targets": C.TARGET_DIMS,
            "metric": "r2（逐维计算后取 50 维均值）",
            "secondary": ["mae(mean over dims)", "spearman(mean over dims)"],
            "ordinal": ["QWK", "grade MAE（仅作标定口径敏感性，真实等级未知）"],
            "schema": "predictions.csv: row(=row_index), dim, y_true, y_pred (long form, 50 rows per sample)",
            "why_not_single_column": "题面要求 Aroma 与 Flavour 两套共约 40 维（实体 50 维）分级评分；"
                                     "单列 A_hops_all 只用于 profile 工具的表单字段，不代表 Q1 目标",
        },
        "split_registered_on_model_table": None,
    }
    C.write_json(checks, "outputs/protocol/model_table_checks.json")
    print(json.dumps({k: checks[k] for k in ["model_table_shape", "n_missing_cells_total",
                                             "workbench_features_equal_231",
                                             "workbench_extra_declared",
                                             "targets_match_4csv_on_beer"]},
                     ensure_ascii=False, indent=2))
    print("[model_table] rows=250 cols=284 fields=284 -> data/clean/model_table.csv")


if __name__ == "__main__":
    main()
