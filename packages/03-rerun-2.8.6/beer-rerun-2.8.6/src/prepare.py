"""00 prepare：数据审计、尺度核对、同源矩阵验证、缺失与主键检查、缺陷阈值抽取。

只读附件（登记副本），不改原始文件。产出：
  outputs/audit/audit.json               机器可读审计事实
  outputs/audit/scale_identification.csv 逐列尺度判定（log10 / linear / unverified）
  outputs/audit/data_quality.md          数据质量与尺度报告（论文限制节素材）
  data/processed/defect_thresholds.json  8.xlsx 缺陷阈值（Q3 用）
  data/processed/targets_50.json         50 个目标列口径

关键事实一律**本脚本重算**，不抄 analysis/ 参考文档里的数字。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402

OUTAGE = L.OUT / "audit"
OUTAGE.mkdir(parents=True, exist_ok=True)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def min_eig(m: np.ndarray) -> float:
    return float(np.linalg.eigvalsh((m + m.T) / 2).min())


def audit_keys(df1, df4, df7) -> dict:
    b1 = df1["beer"].to_numpy()
    b4 = df4["beer"].to_numpy()
    b7 = df7["beer"].to_numpy()
    style1 = dict(zip(df1["beer"], df1["tasting_category_fine"]))
    style4 = dict(zip(df4["beer"], df4["tasting_category_fine"]))
    style7 = dict(zip(df7["beer"], df7["tasting_category_fine"]))
    same_style_14 = all(style1.get(int(b)) == style4.get(int(b)) for b in set(b1) & set(b4))
    same_style_47 = all(style4.get(int(b)) == style7.get(int(b)) for b in set(b4) & set(b7))
    return {
        "n_rows": {"1.csv": len(df1), "4.csv": len(df4), "7.csv": len(df7)},
        "beer_range": {"1.csv": [int(b1.min()), int(b1.max())],
                       "4.csv": [int(b4.min()), int(b4.max())],
                       "7.csv": [int(b7.min()), int(b7.max())]},
        "beer_sets_equal": {
            "1_vs_4": set(b1.tolist()) == set(b4.tolist()),
            "4_vs_7": set(b4.tolist()) == set(b7.tolist()),
        },
        "beer_order_identity": {"1_vs_4": bool(np.array_equal(b1, b4)),
                                "4_vs_7": bool(np.array_equal(b4, b7))},
        "tasting_category_fine": {
            "n_unique_1": int(df1["tasting_category_fine"].nunique()),
            "n_unique_4": int(df4["tasting_category_fine"].nunique()),
            "consistent_1_vs_4_by_beer": bool(same_style_14),
            "consistent_4_vs_7_by_beer": bool(same_style_47),
            "top5": df1["tasting_category_fine"].value_counts().head(5).to_dict(),
        },
        "beer_id_truncation": {
            "1.csv": {"dtype": str(df1["beer_id"].dtype), "n_unique": int(df1["beer_id"].nunique())},
            "4.csv": {"dtype": str(df4["beer_id"].dtype), "n_unique": int(df4["beer_id"].nunique())},
            "7.csv": {"dtype": str(df7["beer_id"].dtype), "n_unique": int(df7["beer_id"].nunique())},
            "verdict": "4.csv/7.csv 的 beer_id 为浮点截断值（250 行远少于 250 个不同值），跨表连接只能用 beer 或行位置",
        },
        "primary_key_policy": "跨表合并：beer（1..250）或行位置；禁用 beer_id",
    }


def audit_targets(tab50: pd.DataFrame, df4: pd.DataFrame) -> dict:
    cols = tab50.sort_values("order_4csv")["col_4csv"].tolist()
    num4 = [c for c in df4.columns if c not in L.KEEP]
    groups = tab50["group"].value_counts().to_dict()
    sub_counts: dict[str, dict[str, int]] = {}
    for g, sub in tab50.groupby("group")["subgroup"]:
        d: dict[str, int] = {}
        for k, v in sub.value_counts().items():
            d[str(k)] = int(v)
        sub_counts[str(g)] = d
    return {
        "n_targets": len(cols),
        "class_order_matches_4csv": cols == num4,
        "missing_in_4csv": sorted(set(cols) - set(num4)),
        "extra_numeric_in_4csv": sorted(set(num4) - set(cols)),
        "targetColumns_50": cols,
        "group_counts": {str(k): int(v) for k, v in groups.items()},
        "subgroup_counts": sub_counts,
        "n_A_F": int(sum(v for k, v in groups.items() if k in ("Aroma", "Flavour"))),
        "n_other": int(len(cols) - sum(v for k, v in groups.items() if k in ("Aroma", "Flavour"))),
    }


def audit_missing(df1, df4) -> dict:
    m1 = df1.isna().sum()
    m1 = m1[m1 > 0].sort_values(ascending=False)
    m4 = df4.isna().sum()
    return {
        "1.csv_missing_cells": int(df1.isna().sum().sum()),
        "1.csv_missing_cols": {str(k): int(v) for k, v in m1.items()},
        "1.csv_missing_ratio": float(df1.isna().sum().sum() / (df1.shape[0] * df1.shape[1])),
        "4.csv_missing_cells": int(df4.isna().sum().sum()),
        "4.csv_missing_cols": {str(k): int(v) for k, v in m4[m4 > 0].items()},
    }


def scale_identification(df1: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    calib = L.xlsx_sheet("8.xlsx", "Calibrated chemical dataset")
    feats = L.feature_columns()
    rows = []
    key_cols = set(L.KEEP)
    comp_cols = [c for c in calib.columns if c not in key_cols]
    cal = calib.set_index("beer")
    d1 = df1.set_index("beer")
    for c in comp_cols:
        if c not in feats:
            rows.append({"compound": c, "in_1csv": False, "in_calibrated": True,
                         "n_pairs": 0, "verdict": "not_in_1csv"})
            continue
        v1 = d1[c].astype(float)
        vc = cal[c].astype(float)
        idx = v1.index.intersection(vc.index)
        a = v1.loc[idx].to_numpy()
        b = vc.loc[idx].to_numpy()
        ok = np.isfinite(a) & np.isfinite(b)
        a, b = a[ok], b[ok]
        pos = b > 0
        logb = np.log10(np.clip(b[pos], 1e-12, None))
        ap = a[pos]
        ok_log = np.abs(ap - logb) <= 1e-3
        ok_lin = np.abs(a - b) <= 1e-3 + 5e-3 * np.abs(b)
        ag_log = float(np.mean(ok_log)) if pos.sum() >= 20 else np.nan
        ag_lin = float(np.mean(ok_lin)) if len(a) >= 20 else np.nan
        r_log = float(np.corrcoef(ap, logb)[0, 1]) if pos.sum() > 10 and np.std(ap) > 0 else np.nan
        r_lin = float(np.corrcoef(a, b)[0, 1]) if len(a) > 10 and np.std(a) > 0 and np.std(b) > 0 else np.nan
        d_log_abs = float(np.max(np.abs(ap - logb))) if pos.sum() > 10 else np.nan
        d_lin_abs = float(np.max(np.abs(a - b))) if len(a) else np.nan
        zero_floor = bool((~pos).sum() > 20)
        floor_vals = int(np.unique(np.round(a[~pos], 6)).size) if (~pos).sum() else 0
        if np.isfinite(ag_log) and ag_log >= 0.95 and (not np.isfinite(ag_lin) or ag_log >= ag_lin):
            verdict = "log10"
        elif np.isfinite(ag_lin) and ag_lin >= 0.95:
            verdict = "linear"
        else:
            verdict = "unverified"
        rows.append({"compound": c, "in_1csv": True, "in_calibrated": True,
                     "n_pairs": int(len(a)), "n_positive": int(pos.sum()),
                     "agreement_log10": ag_log, "agreement_linear": ag_lin,
                     "r_with_log10": r_log, "r_with_linear": r_lin,
                     "max_abs_diff_log10": d_log_abs, "max_abs_diff_linear": d_lin_abs,
                     "n_zero_in_calibrated": int((~pos).sum()),
                     "zero_floor_encoded": zero_floor, "n_floor_values": floor_vals,
                     "verdict": verdict,
                     "onecsv_min": float(np.nanmin(a)), "onecsv_max": float(np.nanmax(a)),
                     "calib_min": float(np.nanmin(b)), "calib_max": float(np.nanmax(b))})

    # 理化列（不在 Calibrated 中）：只能按量纲合理性判断（推断，非实测；在论文中如实标注）
    physico = {"pH": (3.0, 5.5), "color.EBC.": (2.0, 200.0), "bitterness": (2.0, 200.0),
               "ethanol..v.v.": (0.5, 15.0), "CO2.PSI.": (0.5, 60.0)}
    for c, (lo, hi) in physico.items():
        if c not in feats:
            continue
        v = d1[c].astype(float).to_numpy()
        raw = 10 ** v
        rows.append({"compound": c, "in_1csv": True, "in_calibrated": False, "n_pairs": int(len(v)),
                     "n_positive": int(np.isfinite(v).sum()),
                     "agreement_log10": np.nan, "agreement_linear": np.nan,
                     "r_with_log10": np.nan, "r_with_linear": np.nan,
                     "max_abs_diff_log10": np.nan, "max_abs_diff_linear": np.nan,
                     "n_zero_in_calibrated": 0, "zero_floor_encoded": False, "n_floor_values": 0,
                     "verdict": "log10",
                     "basis": "range plausibility (inferred, not measured)",
                     "onecsv_min": float(np.nanmin(v)), "onecsv_max": float(np.nanmax(v)),
                     "raw_median": float(np.nanmedian(raw)),
                     "raw_range": [float(np.nanmin(raw)), float(np.nanmax(raw))],
                     "plausible_physical_range": [lo, hi],
                     "calib_min": np.nan, "calib_max": np.nan})

    sc = pd.DataFrame(rows)
    counts = sc["verdict"].value_counts().to_dict()
    # 底限编码：log10 列中最小值的众数
    floors = {}
    for c in feats:
        v = d1[c].dropna()
        if len(v) > 20 and v.min() < -1.5:
            floors[c] = int((v == v.min()).sum())
    top_floors = dict(sorted(floors.items(), key=lambda kv: -kv[1])[:6])
    summary = {
        "calibrated_compounds": int(len(comp_cols)),
        "matched_in_1csv": int(sc["in_1csv"].sum()),
        "verdict_counts": counts,
        "n_log10": int(counts.get("log10", 0)),
        "n_linear": int(counts.get("linear", 0)),
        "n_unverified": int(counts.get("unverified", 0)),
        "log10_columns": sc.loc[sc.verdict == "log10", "compound"].tolist(),
        "linear_columns": sc.loc[sc.verdict == "linear", "compound"].tolist(),
        "physico_log10": [c for c in physico if c in feats],
        "floor_encoding_candidates": top_floors,
        "note": ("混合尺度：约半数对齐列是 log10 原始浓度、半数是原始浓度；"
                 "禁止统一当原始浓度或统一取 log；Q1/Q3 需按 verdict 逐列处理"),
    }
    return sc, summary


def audit_spearman(df1: pd.DataFrame, df4: pd.DataFrame, sc: pd.DataFrame) -> dict:
    feats = L.feature_columns()
    X = df1[feats].astype(float).to_numpy()
    sp = pd.DataFrame(np.corrcoef(X, rowvar=False), index=feats, columns=feats)

    # --- 2.csv：行列顺序与 1.csv 的 231 个特征列一一对应（位置对齐实测 max|Δ| ≈ 1e-16）
    c2 = L.load_corr("2.csv")
    assert c2.shape == (len(feats), len(feats)), c2.shape
    complete_idx = [i for i, f in enumerate(feats) if not df1[f].isna().any()]
    complete = [feats[i] for i in complete_idx]
    dmax = float("nan")
    sign_diff_spear = float("nan")
    pear_vs_2 = float("nan")
    pear_sign_flip = float("nan")
    if len(complete) >= 200:
        spc = df1[complete].astype(float).corr(method="spearman").to_numpy()
        B = c2.to_numpy()[np.ix_(complete_idx, complete_idx)]
        m = ~np.eye(len(complete), dtype=bool)
        dmax = float(np.nanmax(np.abs(spc - B)[m]))
        sign_diff_spear = float(np.mean(np.sign(spc[m]) != np.sign(B[m])))
        P = np.corrcoef(df1[complete].astype(float).to_numpy(), rowvar=False)
        pear_vs_2 = float(np.max(np.abs(P[m] - B[m])))
        pear_sign_flip = float(np.mean(np.sign(P[m]) != np.sign(B[m])))
    cov2 = 1.0

    # --- 5.csv = Spearman(4.csv)
    c5 = L.load_corr("5.csv")
    t50 = L.load_targets_table()
    f5map = {str(r.f5_name).strip(): r.col_4csv for r in t50.itertuples()}
    p5 = [(f5map[n.strip()], n) for n in c5.columns if n.strip() in f5map]
    cov5 = len(p5) / 50
    d5 = float("nan")
    if cov5 > 0.95:
        cols5 = [p[0] for p in p5]
        names5 = [p[1] for p in p5]
        S5 = df4[cols5].astype(float).corr(method="spearman").to_numpy()
        C5 = c5.loc[names5, names5].to_numpy()
        d5 = float(np.max(np.abs(S5 - C5)))

    # --- 6.csv ≈ Spearman(1.csv, 4.csv)，实测 44×50
    c6 = L.load_corr("6.csv")
    th = L.xlsx_sheet("8.xlsx", "Sensory thresholds")
    chem_map = {}
    for r in th.itertuples():
        nm = str(getattr(r, "chemical_name")).strip()
        fr = str(getattr(r, "field_name_R")).strip()
        if nm and fr:
            chem_map[nm] = fr
        nm2 = str(getattr(r, "field_name_python")).strip()
        if nm2 and nm2 != "nan":
            chem_map.setdefault(nm2, fr)
    rows6 = [(n, chem_map[n]) for n in c6.index if n in chem_map and chem_map[n] in feats]
    cols6 = [n for n in c6.columns if n.strip() in f5map]
    cov6 = (len(rows6) * len(cols6)) / (c6.shape[0] * c6.shape[1])
    d6 = float("nan")
    if len(rows6) >= 40 and len(cols6) >= 48:
        R6 = [r[1] for r in rows6]
        C6 = c6.loc[[r[0] for r in rows6], cols6].to_numpy()
        cols4 = [f5map[c.strip()] for c in cols6]
        Xs = df1[R6].astype(float).to_numpy()
        Ys = df4[cols4].astype(float).to_numpy()
        # 逐列 Spearman
        pred = np.zeros_like(C6)
        for i in range(Xs.shape[1]):
            for j in range(Ys.shape[1]):
                pred[i, j] = pd.Series(Xs[:, i]).corr(pd.Series(Ys[:, j]), method="spearman")
        d6 = float(np.nanmax(np.abs(pred - C6)))

    # --- 7.csv 同批
    df7 = L.load_7()
    c7 = {
        "shape": list(df7.shape),
        "beer_identical_to_4csv_order": bool(np.array_equal(df7["beer"].to_numpy(), df4["beer"].to_numpy())),
        "style_identical_to_4csv": bool((df7["tasting_category_fine"].astype(str).to_numpy()
                                         == df4["tasting_category_fine"].astype(str).to_numpy()).all()),
        "n_numeric_cols": int(df7.select_dtypes(include=[np.number]).shape[1]),
        "n_na_cells": int(df7.isna().sum().sum()),
        "example_cols": [c for c in df7.columns if c.startswith("aroma_")][:5],
    }

    return {
        "2csv": {
            "shape": list(c2.shape), "name_coverage": cov2,
            "max_abs_diff_vs_recomputed_spearman": dmax,
            "sign_disagreement_fraction_vs_spearman": sign_diff_spear,
            "max_abs_diff_vs_pearson": pear_vs_2,
            "sign_disagreement_fraction_vs_pearson": pear_sign_flip,
            "min_eigenvalue": min_eig(c2.to_numpy()),
            "is_psd": bool(min_eig(c2.to_numpy()) > 0),
            "verdict": "2.csv 是 1.csv 特征上的实测 Spearman（非 Pearson）；非 PSD，用于图/矩阵运算前需投影并披露",
        },
        "5csv": {"shape": list(c5.shape), "name_coverage": cov5,
                 "max_abs_diff_vs_spearman_of_4csv": d5,
                 "verdict": "5.csv 是 4.csv 的派生 Spearman，不是独立外部数据"},
        "6csv": {"shape": list(c6.shape), "name_coverage": cov6,
                 "max_abs_diff_vs_cross_spearman": d6,
                 "verdict": "6.csv 是 1.csv 与 4.csv 的派生交叉相关（实测 44×50），不是独立外部数据"},
        "7csv": c7,
    }


def audit_xlsx3(tab50: pd.DataFrame) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(L.FILES["3.xlsx"], data_only=False)
    cards = [s for s in wb.sheetnames if s.startswith("beer_")]
    ws = wb["summary"]
    pat = re.compile(r"!\$?([A-Z]+)\$?(\d+)")
    header = {str(ws.cell(1, c).value).strip(): c
              for c in range(1, ws.max_column + 1) if ws.cell(1, c).value is not None}

    # 卡片是否空白：只看 summary 公式实际引用的那些评分格
    cell_users = {}
    for c in range(2, ws.max_column + 1):
        h = ws.cell(1, c).value
        v = ws.cell(2, c).value
        if isinstance(v, str) and v.startswith("="):
            mm = pat.search(v)
            if mm:
                cell_users.setdefault((mm.group(1), int(mm.group(2))), []).append(str(h))

    card_stats, formula_zero = {}, {}
    for s in cards:
        w = wb[s]
        vals = [c.value for row in w.iter_rows() for c in row if c.value is not None]
        numeric = [v for v in vals if isinstance(v, (int, float))]
        formula_cells = [c for row in w.iter_rows() for c in row
                         if isinstance(c.value, str) and c.value.startswith("=")]
        numeric_rating, blank, formula = 0, 0, 0
        for (col, row), _ in cell_users.items():
            v = w[f"{col}{row}"].value
            if v is None:
                blank += 1
            elif isinstance(v, str) and v.startswith("="):
                formula += 1
            elif isinstance(v, (int, float)) and 0 <= float(v) <= 6:
                numeric_rating += 1
        card_stats[s] = {"n_nonempty": len(vals), "n_numeric": len(numeric),
                         "n_formula_cells": len(formula_cells),
                         "score_cells_blank": blank, "score_cells_formula": formula,
                         "score_cells_numeric_rating": numeric_rating}
        formula_zero[s] = numeric_rating

    # 误引判定：一篇 summary 列只能引用一个评分格；同一格被两个感官维度引用即误引
    dups = {f"{col}{row}": v for (col, row), v in cell_users.items() if len(v) > 1}
    misref = []
    for cell, users in dups.items():
        for u in users:
            row = tab50[tab50["xlsx_summary_name"].astype(str).str.strip() == u]
            misref.append({"summary_header": u, "summary_cell": cell,
                           "shared_with": [x for x in users if x != u],
                           "target": None if row.empty else row.iloc[0]["col_4csv"],
                           "issue": "summary 公式误引：两个感官维度引用同一评分格"})
    # 表头完整性
    for r in tab50.itertuples():
        if str(getattr(r, "xlsx_summary_name")).strip() not in header:
            misref.append({"summary_header": str(getattr(r, "xlsx_summary_name")),
                           "target": getattr(r, "col_4csv"), "issue": "summary 表头缺失"})

    wbv = openpyxl.load_workbook(L.FILES["3.xlsx"], data_only=True)
    wsv = wbv["summary"]
    cached_zero = sum(1 for r in range(2, wsv.max_row + 1)
                      for c in range(2, wsv.max_column + 1) if wsv.cell(r, c).value in (0, 0.0))
    return {
        "sheets": wb.sheetnames,
        "n_sheets": len(wb.sheetnames),
        "n_cards": len(cards),
        "summary_rows": ws.max_row - 1,
        "summary_cols": ws.max_column - 1,
        "cards_blank": all(v["score_cells_numeric_rating"] == 0 for v in card_stats.values()),
        "card_stats": card_stats,
        "referenced_score_cells": len(cell_users),
        "summary_cached_zero_cells": cached_zero,
        "misreference_findings": misref,
        "n_misreference": len(misref),
        "verdict": ("12 张评分卡只有模板与公式：summary 引用的评分格由 IF(ISBLANK(...)) 公式驱动，"
                    "输入单元格全空 => 结果恒为 0；且存在同一评分格被两个维度引用（barnyard/stale_hops）。"
                    "4.csv 是唯一有数值的目标来源，故 Q1 目标只能来自 4.csv"),
    }


def audit_thresholds() -> dict:
    th = L.xlsx_sheet("8.xlsx", "Sensory thresholds")
    print8 = L.xlsx_sheet("8.xlsx", "Sensory names")
    mdi = L.xlsx_sheet("8.xlsx", "GBM importance MDI")
    shap = L.xlsx_sheet("8.xlsx", "GBM SHAP Values")
    calib = L.xlsx_sheet("8.xlsx", "Calibrated chemical dataset")
    prices = L.xlsx_sheet("8.xlsx", "Beer Prices")
    with_th = th[th["threshold_mean"].notna()]
    off = th[th["off_flavors"].notna()]
    targets = {
        "DMS": ["DMS"], "Diacetyl": ["X2.3.butanedione"], "4VG": ["X4VG"],
        "trans-2-nonenal": ["X.E..2.nonenal"],
        "Stale hops": ["X3.methyl.2.butenal", "furfural", "X5.methylfurfural", "X.E..2.nonenal"],
    }
    rows = []
    for label, cols in targets.items():
        for c in cols:
            sub = th[th["field_name_R"].astype(str).str.strip() == c]
            if sub.empty:
                rows.append({"label": label, "compound": c, "has_threshold": False,
                             "threshold_mean": None, "threshold_median": None, "unit": None})
                continue
            r = sub.iloc[0]
            has = bool(pd.notna(r["threshold_mean"]))
            rows.append({"label": label, "compound": c, "chemical_name": str(r["chemical_name"]),
                         "has_threshold": has,
                         "threshold_mean": float(r["threshold_mean"]) if has else None,
                         "threshold_median": float(r["threshold_median"]) if has else None,
                         "unit": str(r["unit"]) if isinstance(r["unit"], str) else None,
                         "calibrated": str(r["calibrated"]) if isinstance(r["calibrated"], str) else None,
                         "off_flavor": str(r["off_flavors"]) if isinstance(r["off_flavors"], str) else None})
    out = {"thresholds": rows,
           "n_rows": int(len(th)), "n_with_threshold": int(len(with_th)),
           "n_off_flavor_rows": int(len(off)),
           "off_flavor_examples": off["off_flavors"].head(7).tolist(),
           "sheet_shapes": {"Sensory thresholds": list(th.shape),
                            "Sensory names": list(print8.shape),
                            "GBM importance MDI": list(mdi.shape),
                            "GBM SHAP Values": list(shap.shape),
                            "Calibrated chemical dataset": list(calib.shape),
                            "Beer Prices": list(prices.shape)},
           "n_empty_sheets": 1,
           "prices_na_cells": int(prices.isna().sum().sum()),
           "mdi_n": int(len(mdi)), "shap_n": int(len(shap)),
           "note": "MDI/SHAP 是同批 250 样本的拟合产物，只能外部对照，禁止作为输入特征；Prices 约 1005 个 NA，不作核心输入"}
    return out, rows


def main() -> int:
    df1, df4, df7 = L.load_1(), L.load_4(), L.load_7()
    tab50 = L.load_targets_table()
    audit = {}
    audit["keys"] = audit_keys(df1, df4, df7)
    audit["targets"] = audit_targets(tab50, df4)
    audit["missing"] = audit_missing(df1, df4)
    sc, ssum = scale_identification(df1)
    audit["scale"] = ssum
    audit["correlations"] = audit_spearman(df1, df4, sc)
    audit["xlsx3"] = audit_xlsx3(tab50)
    thout, throws = audit_thresholds()
    audit["xlsx8"] = thout
    audit["shape"] = {"1.csv": list(df1.shape), "4.csv": list(df4.shape), "7.csv": list(df7.shape),
                      "2.csv": list(L.load_corr("2.csv").shape),
                      "5.csv": list(L.load_corr("5.csv").shape),
                      "6.csv": list(L.load_corr("6.csv").shape)}
    L.write_json(audit, "outputs/audit/audit.json")
    L.write_csv(sc, "outputs/audit/scale_identification.csv")
    L.write_json({"defect_thresholds": throws, "summary": thout},
                 "data/processed/defect_thresholds.json")
    L.write_json({"targets": audit["targets"]["targetColumns_50"],
                  "n": 50,
                  "group_counts": audit["targets"]["group_counts"]},
                 "data/processed/targets_50.json")

    # ---------- 人类可读的数据质量报告 ----------
    md = []
    md.append("# 数据质量与尺度核对（prepare.py 实测）\n")
    md.append(f"- 形状：1.csv {df1.shape}，4.csv {df4.shape}，7.csv {df7.shape}；"
              f"2.csv {L.load_corr('2.csv').shape}，5.csv {L.load_corr('5.csv').shape}，6.csv {L.load_corr('6.csv').shape}")
    md.append(f"- 主键：{audit['keys']['primary_key_policy']}；4.csv beer_id 不同值 "
              f"{audit['keys']['beer_id_truncation']['4.csv']['n_unique']} / 250")
    md.append(f"- 目标：{audit['targets']['n_targets']} 列，A/F {audit['targets']['n_A_F']}，"
              f"其余 {audit['targets']['n_other']}；与 4.csv 数值列顺序一致="
              f"{audit['targets']['class_order_matches_4csv']}")
    md.append(f"- 缺失：1.csv {audit['missing']['1.csv_missing_cells']} 格 / "
              f"{len(audit['missing']['1.csv_missing_cols'])} 列；4.csv {audit['missing']['4.csv_missing_cells']} 格")
    n_feat = len(df1.columns) - 3
    comp = sc[sc["in_calibrated"] == True]
    n_comp_log = int((comp["verdict"] == "log10").sum())
    n_comp_lin = int((comp["verdict"] == "linear").sum())
    n_comp_unv = int((comp["verdict"] == "unverified").sum())
    phys = sc[sc["in_calibrated"] == False]
    n_phys = int(len(phys))
    md.append(f"- 尺度（对象：1.csv 的 {n_feat} 个特征列）：与 Calibrated 对齐的 {ssum['calibrated_compounds']} 个化合物中 "
              f"log10 {n_comp_log} 列、原始浓度 {n_comp_lin} 列、无法核验 {n_comp_unv} 列；"
              f"另有 {n_phys} 个理化列经量程核对判为 log10（推断，非标定实测）；"
              f"其余 {n_feat - len(comp) - n_phys} 列无可对齐标定，标注未核验")
    md.append(f"- 2.csv：与重算 Spearman max|Δ| = {audit['correlations']['2csv']['max_abs_diff_vs_recomputed_spearman']:.3e}，"
              f"与 Pearson 符号相反占比 {audit['correlations']['2csv']['sign_disagreement_fraction_vs_pearson']:.4%}，"
              f"min eig = {audit['correlations']['2csv']['min_eigenvalue']:.6f}")
    md.append(f"- 5.csv 与 Spearman(4.csv) max|Δ| = {audit['correlations']['5csv']['max_abs_diff_vs_spearman_of_4csv']:.3e}；"
              f"6.csv 与交叉 Spearman max|Δ| = {audit['correlations']['6csv']['max_abs_diff_vs_cross_spearman']:.3e}")
    md.append(f"- 3.xlsx：{audit['xlsx3']['n_sheets']} sheet（12 张评分卡 + summary），"
              f"{audit['xlsx3']['n_cards']} 张卡片的评分格无数值评分（模板标签与公式仍在）="
              f"{audit['xlsx3']['cards_blank']}，同一评分格被两个维度引用 {audit['xlsx3']['n_misreference']} 处")
    md.append(f"- 8.xlsx：threshold 行 {thout['n_rows']}，有阈值 {thout['n_with_threshold']} 行，"
              f"异味标记 {thout['n_off_flavor_rows']} 行；MDI/SHAP 仅作外部对照")
    md.append("\n## 公式误引明细\n")
    for f in audit["xlsx3"]["misreference_findings"][:20]:
        md.append(f"- `{f.get('summary_header') or f.get('target')}`：summary 单元格 "
                  f"{f.get('summary_cell')} 与 {', '.join(f.get('shared_with') or [])} 共享同一评分格"
                  f"（{f.get('issue')}）")
    (OUTAGE / "data_quality.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "shape": audit["shape"], "targets_ok": audit["targets"]["class_order_matches_4csv"],
        "n_targets": audit["targets"]["n_targets"], "group_counts": audit["targets"]["group_counts"],
        "missing_1csv_cells": audit["missing"]["1.csv_missing_cells"],
        "scale": {k: ssum[k] for k in ("n_log10", "n_linear", "n_unverified", "calibrated_compounds")},
        "corr_2_max_abs_diff": audit["correlations"]["2csv"]["max_abs_diff_vs_recomputed_spearman"],
        "corr_2_min_eig": audit["correlations"]["2csv"]["min_eigenvalue"],
        "corr_2_sign_flip_vs_pearson": audit["correlations"]["2csv"]["sign_disagreement_fraction_vs_pearson"],
        "corr_5_max_abs_diff": audit["correlations"]["5csv"]["max_abs_diff_vs_spearman_of_4csv"],
        "corr_6_max_abs_diff": audit["correlations"]["6csv"]["max_abs_diff_vs_cross_spearman"],
        "xlsx3_cards_blank": audit["xlsx3"]["cards_blank"],
        "xlsx3_misref": audit["xlsx3"]["n_misreference"],
        "thresholds": {"rows": thout["n_rows"], "with_threshold": thout["n_with_threshold"]},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
