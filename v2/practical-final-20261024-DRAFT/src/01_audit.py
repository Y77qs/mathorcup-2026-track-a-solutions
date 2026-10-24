"""01 审计：把题面/附件的一致性核对、缺失机制、log10 底数、Spearman 属性、
beer_id 脱敏、派生列关系全部落成可回读的 JSON。

输出：outputs/audit/audit.json, outputs/audit/missing_detail.csv
仅读 data/raw，不写 data/clean。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main():
    audit = {"files": {}}
    for p in sorted(C.RAW.iterdir()):
        if p.is_file():
            audit["files"][p.name] = {"sha256": sha256(p), "bytes": p.stat().st_size}

    f = C.load_features()
    t = C.load_targets()
    r7 = C.load_ratebeer()
    corr_c = C.load_corr_compound()
    corr_x = C.load_corr_cross()
    corr_s = pd.read_csv(C.RAW / "5.csv", index_col=0)

    X = f[C.feature_columns()]
    audit["shapes"] = {
        "1.csv": list(f.shape), "2.csv": list(corr_c.shape), "4.csv": list(C.read_csv_raw("4.csv").shape),
        "5.csv": list(corr_s.shape), "6.csv": list(corr_x.shape), "7.csv": list(r7.shape),
    }
    audit["C1_n_samples"] = {
        "1.csv_rows": int(len(f)), "unique_beer": int(f["beer"].nunique()),
        "unique_beer_id": int(f["beer_id"].nunique()), "statement_says": 226,
        "verdict": "data=250; statement 226 为笔误",
    }

    # ---- C2: 2.csv 是 Spearman 还是 Pearson
    nmap = {}
    sn = C.load_sensory_names()
    for _, row in C.load_calibrated_chemicals().iloc[:0].iterrows():
        pass
    # 用 8.xlsx Sensory thresholds 的 field_name_python / chemical_name_short 建立 1.csv 列 -> 2.csv 名
    th = pd.read_excel(C.RAW / "8.xlsx", sheet_name="Sensory thresholds")
    name2short = {}
    for _, row in th.iterrows():
        fp = str(row["field_name_python"]).strip()
        cs = str(row["chemical_name_short"]).strip()
        if fp and cs and cs.lower() != "nan":
            name2short.setdefault(fp, cs)
    col2short = {k: v for k, v in name2short.items() if k in X.columns}
    common_cols = [c for c in col2short if col2short[c] in corr_c.index]
    pairs = []
    rng = np.random.default_rng(C.RNG_SEED)
    idx = rng.choice(len(common_cols), size=min(40, len(common_cols)), replace=False)
    for i in idx:
        a = common_cols[i]
        for _ in range(3):
            b = common_cols[rng.integers(len(common_cols))]
            if b == a:
                continue
            m = X[[a, b]].dropna()
            if len(m) < 30:
                continue
            pairs.append({
                "a": a, "b": b,
                "pearson": float(m[a].corr(m[b])),
                "spearman": float(m[a].corr(m[b], method="spearman")),
                "file_2csv": float(corr_c.loc[col2short[a], col2short[b]]),
            })
    d = pd.DataFrame(pairs)
    d["err_spearman"] = (d["spearman"] - d["file_2csv"]).abs()
    d["err_pearson"] = (d["pearson"] - d["file_2csv"]).abs()
    audit["C2_corr_type"] = {
        "n_pairs": int(len(d)),
        "max_abs_err_vs_spearman": float(d["err_spearman"].max()),
        "max_abs_err_vs_pearson": float(d["err_pearson"].max()),
        "median_abs_err_vs_spearman": float(d["err_spearman"].median()),
        "median_abs_err_vs_pearson": float(d["err_pearson"].median()),
        "examples": d.head(6).round(6).to_dict(orient="records"),
        "verdict": "2.csv = Spearman（题面'皮尔逊'为误写）",
    }
    C.write_csv(d.round(8), "outputs/audit/corr_type_check.csv")

    # ---- C3: 3.xlsx 是否为已填评分卡
    xl = pd.ExcelFile(C.RAW / "3.xlsx")
    sheets = xl.sheet_names
    fill = {}
    for s in sheets:
        raw = pd.read_excel(C.RAW / "3.xlsx", sheet_name=s, header=None)
        num = raw.apply(pd.to_numeric, errors="coerce")
        v = num.iloc[:, 2:15].values.ravel()
        fill[s] = {"shape": list(raw.shape), "numeric_cells": int(np.isfinite(v).sum()),
                   "cells_gt0": int((np.nan_to_num(v) > 0).sum())}
    summ = pd.read_excel(C.RAW / "3.xlsx", sheet_name="summary", header=None)
    audit["C3_scorecard"] = {
        "sheets": sheets, "n_beer_sheets": len([s for s in sheets if s.startswith("beer_")]),
        "statement_says": 10, "per_sheet": fill,
        "summary_numeric_sum_of_scores": float(np.nansum(
            pd.to_numeric(summ.iloc[1:, 1:51].stack(), errors="coerce").values)),
        "summary_header": [str(x) for x in summ.iloc[0, 1:51].tolist()],
        "verdict": "3.xlsx 为空白评分卡模板（维度与 0-6 刻度的定义），不含已评分样本",
    }

    # ---- C5: 维度分组
    audit["C5_dims"] = {
        "n_aroma": len(C.AROMA_DIMS), "n_flavour": len(C.FLAVOUR_DIMS),
        "n_palate": len(C.PALATE_DIMS), "n_total": len(C.TARGET_DIMS),
        "target_cols_in_4csv": [c for c in C.read_csv_raw("4.csv").columns
                                if c not in C.KEYS],
        "verdict": "50 维（Aroma 15 + Flavour 15 + 口感/缺陷/总体 20），题面'约 40'为近似说法",
    }

    # ---- C4 / C6 / C7 / C9 / C10 / C11
    audit["C4_cross_corr_shape"] = {"6.csv": list(corr_x.shape), "statement_says": [46, 50],
                                    "verdict": "实测 44x50"}
    uniq = {c: int(t[c].nunique()) for c in C.TARGET_DIMS}
    audit["C6_targets_continuous"] = {
        "min_unique": int(min(uniq.values())), "max_unique": int(max(uniq.values())),
        "n_missing": int(t[C.TARGET_DIMS].isna().sum().sum()),
        "example_dims": {k: uniq[k] for k in C.TARGET_DIMS[:6]},
        "verdict": "4.csv 各列 172-249 个不同取值，确为连续标准化值，不是整数化后的 z",
    }

    cal = C.load_calibrated_chemicals()
    logcheck = []
    for _, row in cal.head(6).iterrows():
        beer = int(row["beer"])
        src = f[f["beer"] == beer].iloc[0]
        for col in ["acetaldehyde", "DMS", "ethyl_acetate", "linalool", "bitterness", "pH"]:
            if col in cal.columns and col in X.columns and pd.notna(row.get(col)):
                v = float(src[col])
                conc = float(row[col])
                if np.isfinite(v) and np.isfinite(conc) and v != 0:
                    logcheck.append({
                        "beer": beer, "col": col, "log10_value": v, "calibrated": conc,
                        "10^v": float(10 ** v), "exp(v)": float(np.exp(v)),
                        "rel_err_log10": float(abs(10 ** v - conc) / max(abs(conc), 1e-12)),
                        "rel_err_ln": float(abs(np.exp(v) - conc) / max(abs(conc), 1e-12)),
                    })
    lc = pd.DataFrame(logcheck)
    audit["C7_log_base"] = {
        "n_checks": int(len(lc)),
        "median_rel_err_log10": float(lc["rel_err_log10"].median()),
        "median_rel_err_ln": float(lc["rel_err_ln"].median()),
        "examples": lc.head(6).round(8).to_dict(orient="records"),
        "verdict": "底数 = log10；负值对应原始浓度 < 1",
    }
    C.write_csv(lc.round(10), "outputs/audit/log_base_check.csv")

    t4 = C.read_csv_raw("4.csv")
    audit["C9_beer_id"] = {
        "1csv_unique_beer_id": int(f["beer_id"].nunique()),
        "4csv_unique_beer_id": int(t4["beer_id"].nunique()),
        "4csv_example": t4["beer_id"].head(3).tolist(),
        "1csv_example": f["beer_id"].head(3).tolist(),
        "order_of_beer_column_equal": bool(f["beer"].tolist() == t4["beer"].tolist()
                                           == r7["beer"].tolist()),
        "verdict": "4/7.csv 的 beer_id 已脱敏（尾数归零）；三表 beer 列顺序完全一致，按 beer 连接",
    }

    na7 = r7.isna().sum()
    audit["C10_ratebeer_na"] = {
        "cols_all_missing": na7[na7 == len(r7)].index.tolist(),
        "n_cols_with_na": int((na7 > 0).sum()), "shape": list(r7.shape),
    }

    miss = X.isna().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    rows_missing = int(X.isna().any(axis=1).sum())
    audit["C11_missing"] = {
        "n_missing_cells": int(X.isna().sum().sum()),
        "n_cols_with_missing": int((X.isna().sum() > 0).sum()),
        "n_rows_with_missing": rows_missing,
        "by_column": {k: int(v) for k, v in miss.items()},
        "verdict": "73 个缺失，集中在 9 列 63 行",
    }
    md = X.isna().sum().rename("n_missing").to_frame()
    md["pct"] = md["n_missing"] / len(X)
    C.write_csv(md, "outputs/audit/missing_detail.csv")

    # 缺失机制：缺失行 vs 完整行的风格分布与目标均值差异
    have_miss = X.isna().any(axis=1).values
    style = f["tasting_category_fine"]
    ct = pd.crosstab(style, have_miss)
    from scipy.stats import chi2_contingency
    chi2, p_style = (chi2_contingency(ct) if ct.shape[1] == 2 else (np.nan, np.nan))[:2]
    tgt_diff = {}
    for c in ["A_hops_all", "A_esters_all", "F_malt_all", "overall"]:
        a = t.loc[have_miss, c].values
        b = t.loc[~have_miss, c].values
        tgt_diff[c] = {"mean_with_missing": float(np.nanmean(a)),
                       "mean_complete": float(np.nanmean(b)),
                       "diff": float(np.nanmean(a) - np.nanmean(b))}
    audit["C11b_missing_mechanism"] = {
        "chi2_style_vs_missing": float(chi2), "p_style": float(p_style),
        "target_mean_shift": tgt_diff,
        "verdict": ("缺失与风格分布无显著关联" if p_style > 0.05 else "缺失与风格相关，需按风格分层插补")
                   + "；样本量小，仅供参考",
    }

    # ---- C12 派生列关系（聚合列是否可由其他列重建）
    agg_probe = {}
    for agg in C.AGG_FEATURES:
        if agg not in X.columns:
            continue
        others = [c for c in X.columns if c != agg]
        y = X[agg]
        best = []
        for c in others:
            m = pd.concat([y, X[c]], axis=1).dropna()
            if len(m) > 30:
                best.append((c, float(m.iloc[:, 0].corr(m.iloc[:, 1]))))
        best.sort(key=lambda z: -abs(z[1]))
        agg_probe[agg] = {"top_corr_cols": best[:3]}
    audit["C12_aggregates"] = {
        "agg_cols": [c for c in C.AGG_FEATURES if c in X.columns],
        "top_correlates": agg_probe,
        "leak_note": "8.xlsx 的 GBM importance MDI / GBM SHAP Values 是用 4.csv 目标训练的产物，"
                      "只能作外部对照，禁止作特征",
    }

    # ---- 8.xlsx 角色
    audit["x8_sheets"] = {
        "Sensory thresholds": {"rows": int(len(th)), "with_threshold": int(th["threshold_mean"].notna().sum()),
                               "off_flavor_rows": int(th["off_flavors"].notna().sum())},
        "Sensory names": {"rows": int(len(sn))},
        "Calibrated chemical dataset": {"shape": list(cal.shape)},
        "GBM importance MDI": {"rows": int(len(pd.read_excel(C.RAW / "8.xlsx", sheet_name="GBM importance MDI")))},
        "GBM SHAP Values": {"shape": list(pd.read_excel(C.RAW / "8.xlsx", sheet_name="GBM SHAP Values").shape)},
    }

    audit["class_balance"] = f["tasting_category_fine"].value_counts().to_dict()
    audit["feature_kinds"] = {
        "n_features": len(X.columns),
        "n_all_missing": int((X.isna().sum() == len(X)).sum()),
        "n_constant": int((X.nunique() <= 1).sum()),
    }

    C.write_json(audit, "outputs/audit/audit.json")
    print(json.dumps({k: audit[k] for k in ["C1_n_samples", "C2_corr_type", "C7_log_base", "C11_missing"]},
                     ensure_ascii=False, indent=2, default=str)[:3000])


if __name__ == "__main__":
    main()
