#!/usr/bin/env python3
"""Lead 独立复核脚本（2026 MathCup 赛道A 数据口径五问）。
只读 work/my-new-contest/data/raw/ 与 problem/，输出 analysis/assets/verification.json。
不依赖 scipy：相关性用 pandas rank + Pearson 实现。
"""
import json, hashlib, re, sys
from pathlib import Path
import numpy as np
import pandas as pd
import openpyxl

ROOT = Path(__file__).resolve().parents[4]          # MATHORCUP
RAW = ROOT / "work/my-new-contest/data/raw"
PROB = ROOT / "work/my-new-contest/problem"
OUT = ROOT / "work/my-new-contest/analysis/assets"
OUT.mkdir(parents=True, exist_ok=True)

R = {}
def sha256(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
         "μ": "mu", "ω": "omega", "τ": "tau", "φ": "phi", "θ": "theta", "λ": "lambda"}
def norm(s):
    s = str(s)
    for k, v in GREEK.items():
        s = s.replace(k, v)
    s = s.replace("\r", " ").replace("\n", " ").replace("_x000D_", " ")
    return re.sub(r"\s+", " ", s).strip().lower()

# ---------- 0. 文件清单 / 哈希 ----------
meta4 = ["beer", "beer_id", "tasting_category_fine"]
raw_files = ["1.csv", "2.csv", "3.xlsx", "4.csv", "5.csv", "6.csv", "7.csv", "8.xlsx", "数据说明.txt"]
R["files"] = {n: {"size": (RAW / n).stat().st_size, "sha256": sha256(RAW / n)} for n in raw_files}
pdf = next(PROB.glob("*.pdf"))
R["pdf"] = {"name": pdf.name, "sha256": sha256(pdf), "size": pdf.stat().st_size}

# ---------- 1. 1.csv ----------
df1 = pd.read_csv(RAW / "1.csv")
feat1 = [c for c in df1.columns if c not in meta4]
R["csv1"] = {
    "shape": list(df1.shape), "n_meta": 3, "n_features": len(feat1),
    "missing_total": int(df1[feat1].isna().sum().sum()),
    "missing_cols": {k: int(v) for k, v in df1[feat1].isna().sum()[df1[feat1].isna().sum() > 0].items()},
    "n_beer_unique": int(df1["beer"].nunique()),
    "n_beer_id_unique": int(df1["beer_id"].nunique()),
    "n_category": int(df1["tasting_category_fine"].nunique()),
    "categories": sorted(df1["tasting_category_fine"].dropna().unique().tolist()),
}

# ---------- 2. 4.csv targetColumns ----------
df4 = pd.read_csv(RAW / "4.csv")
targets = [c for c in df4.columns if c not in meta4]
A = [c for c in targets if c.startswith("A_")]
F = [c for c in targets if c.startswith("F_")]
O = [c for c in targets if c not in A + F]
R["targets"] = {"n": len(targets), "A": A, "F": F, "other": O, "order": targets,
                "n_missing": int(df4[targets].isna().sum().sum())}
num4 = df4[targets]
colstat = pd.DataFrame({
    "mean": num4.mean(), "sd": num4.std(), "min": num4.min(), "max": num4.max(),
    "n_unique": num4.nunique(), "skew": num4.skew(),
})
colstat["range_width"] = colstat["max"] - colstat["min"]
colstat["is_integer"] = [bool(np.allclose(num4[c].dropna(), np.round(num4[c].dropna()), atol=1e-9)) for c in targets]
mu_lo = np.maximum(0, -colstat["min"]); mu_hi = 6 - colstat["max"]
feas = mu_lo <= mu_hi
R["csv4_scale"] = {
    "global_mean": float(num4.values.mean()), "global_sd": float(num4.values.std(ddof=1)),
    "col_mean_absmax": float(colstat["mean"].abs().max()),
    "col_sd_min": float(colstat["sd"].min()), "col_sd_median": float(colstat["sd"].median()),
    "col_sd_max": float(colstat["sd"].max()),
    "col_sd_all_close_1": bool(np.allclose(colstat["sd"], 1, atol=0.05)),
    "n_integer_cols": int(colstat["is_integer"].sum()),
    "n_unique_min": int(colstat["n_unique"].min()),
    "n_unique_median": float(colstat["n_unique"].median()),
    "n_unique_max": int(colstat["n_unique"].max()),
    "range_width_min": float(colstat["range_width"].min()),
    "range_width_median": float(colstat["range_width"].median()),
    "range_width_max": float(colstat["range_width"].max()),
    "n_cols_range_le_6": int((colstat["range_width"] <= 6).sum()),
    "centered_raw_feasible_cols": int(feas.sum()),
    "centered_raw_mu_interval_width_median": float((mu_hi - mu_lo)[feas].median()),
}
R["csv4_scale"]["per_col"] = colstat.round(6).reset_index().rename(columns={"index": "column"}).to_dict("records")

# ---------- 3. 3.xlsx ----------
wb3 = openpyxl.load_workbook(RAW / "3.xlsx", data_only=True)
wb3f = openpyxl.load_workbook(RAW / "3.xlsx", data_only=False)
s3 = {"sheetnames": wb3.sheetnames, "n_sheets": len(wb3.sheetnames)}
ws = wb3["summary"]
rows = list(ws.iter_rows(values_only=True))
hdr = [str(x) if x is not None else "" for x in rows[0]]
s3["summary_shape"] = [ws.max_row, ws.max_column]
s3["summary_header"] = hdr
s3["summary_n_sensory"] = len([h for h in hdr[1:] if h and h != "comments"])
s3["summary_sensory_header"] = [h for h in hdr[1:] if h and h != "comments"]
s3["summary_max_abs_value"] = float(np.nanmax(np.abs(np.array(
    [[x for x in r[1:-1]] for r in rows[1:]], dtype=float))))
beer = {}
for s in [x for x in wb3.sheetnames if x.startswith("beer_")]:
    wsd, wsf = wb3[s], wb3f[s]
    vals = [c.value for row in wsd.iter_rows() for c in row if c.value is not None]
    formulas = [c.value for row in wsf.iter_rows() for c in row
                if isinstance(c.value, str) and c.value.startswith("=")]
    q = [wsd.cell(r, 17).value for r in range(1, wsd.max_row + 1)]
    ag = [wsd.cell(r, 33).value for r in range(1, wsd.max_row + 1)]
    beer[s] = {
        "dims": [wsd.max_row, wsd.max_column],
        "nonempty_cells": len(vals),
        "numeric_cells": sum(isinstance(v, (int, float)) for v in vals),
        "n_formulas": len(formulas),
        "formula_examples": formulas[:4],
        "Q_nonzero_scores": [v for v in q if isinstance(v, (int, float)) and v != 0],
        "AG_nonzero_scores": [v for v in ag if isinstance(v, (int, float)) and v != 0],
        "beer_no_S3": wsd["S3"].value,
    }
s3["beer"] = beer
s3["beer_identical_templates"] = len({json.dumps({k: v for k, v in b.items() if k not in ("beer_no_S3",)}, sort_keys=True, default=str) for b in beer.values()}) == 1
wb3.close(); wb3f.close()
# 3.xlsx summary 50 维 vs 4.csv 50 维命名对齐
def canon_target(x):
    x = str(x)
    m = {"A_ester_fruity": "A_esters_fruity", "F_ester_fruity": "F_esters_fruity",
         "4vg": "X4vg", "bitternes": "bitternes"}
    return m.get(x, x)
s3["summary_vs_targets"] = {
    "unmatched_summary": [h for h in s3["summary_sensory_header"] if canon_target(h) not in targets],
    "unmatched_targets": [t for t in targets if t not in {canon_target(h) for h in s3["summary_sensory_header"]}],
    "exact_same_order": [canon_target(h) for h in s3["summary_sensory_header"]] == targets,
}
R["xlsx3"] = s3

# ---------- 4. 名称映射表 ----------
thr = pd.read_excel(RAW / "8.xlsx", sheet_name="Sensory thresholds")
map_R_to_disp = {str(r.field_name_R): str(r.chemical_name) for r in thr.itertuples() if pd.notna(r.field_name_R) and pd.notna(r.chemical_name)}
disp_to_R = {}
for k, v in map_R_to_disp.items():
    disp_to_R.setdefault(norm(v), k)
sn = pd.read_excel(RAW / "8.xlsx", sheet_name="Sensory names")
sn_tp = sn[sn["dataset"] == "Trained panel"].copy()
sens_map = {}
for r in sn_tp.itertuples():
    sens_map[str(r.R_name)] = str(r.CleanName_PanelFeedback)
# 5.csv / 6.csv 列名（感官 display） -> 4.csv target
disp5_to_target = {}
for t in targets:
    if t in sens_map:
        disp5_to_target[norm(sens_map[t])] = t
R["mapping"] = {
    "R_to_display_n": len(map_R_to_disp),
    "csv1_to_display_coverage": sum(1 for c in feat1 if c in map_R_to_disp),
    "sensory_trained_panel_n": len(sn_tp),
    "sensory_map_n": len(sens_map),
    "target_to_5col_n": sum(1 for t in targets if t in sens_map),
    "target_to_5col_missing": [t for t in targets if t not in sens_map],
}

# ---------- 5. 2.csv ----------
df2 = pd.read_csv(RAW / "2.csv", index_col=0)
names2 = [str(c) for c in df2.columns]
R["corr2"] = {
    "shape": list(df2.shape),
    "index_eq_columns_order": list(map(str, df2.index)) == names2,
    "positional_match_with_1csv": len(names2) == len(feat1),
    "name_examples": {feat1[i]: names2[i] for i in [0, 1, 2, 4, 230]},
}
X = df1[feat1]
spear = X.corr(method="spearman")
pear = X.corr(method="pearson")
M2 = df2.values
R["corr2"].update({
    "max_abs_err_spearman": float(np.nanmax(np.abs(spear.values - M2))),
    "median_abs_err_spearman": float(np.nanmedian(np.abs(spear.values - M2))),
    "max_abs_err_pearson": float(np.nanmax(np.abs(pear.values - M2))),
    "median_abs_err_pearson": float(np.nanmedian(np.abs(pear.values - M2))),
    "symmetry_max_abs": float(np.nanmax(np.abs(M2 - M2.T))),
    "diag_all_one": bool(np.allclose(np.diag(M2), 1.0)),
    "nan_count": int(np.isnan(M2).sum()),
    "min_eig": float(np.linalg.eigvalsh(M2).min()),
    "range": [float(np.nanmin(M2)), float(np.nanmax(M2))],
})
# 决定性样例：找 Spearman 与 Pearson 差异最大的化合物对
tri = np.triu_indices(len(feat1), 1)
err_p = np.abs(pear.values - M2)[tri]
err_s = np.abs(spear.values - M2)[tri]
k = int(np.argmax(err_p - err_s))
i, j = tri[0][k], tri[1][k]
R["corr2"]["decisive_pair"] = {
    "feature1": feat1[i], "feature1_display": names2[i],
    "feature2": feat1[j], "feature2_display": names2[j],
    "2csv_value": float(M2[i, j]),
    "recomputed_spearman": float(spear.values[i, j]),
    "recomputed_pearson": float(pear.values[i, j]),
}

# ---------- 6. 5.csv / 6.csv ----------
df5 = pd.read_csv(RAW / "5.csv", index_col=0)
cols5 = {norm(c): str(c) for c in df5.columns}
t5 = [t for t in targets if norm(sens_map.get(t, "")) in cols5]
col5_of_t = {t: cols5[norm(sens_map[t])] for t in t5}
R["corr5"] = {"shape": list(df5.shape), "n_targets": len(t5),
              "n_missing_targets": [t for t in targets if t not in t5]}
if len(t5) >= 2:
    S5 = df4[t5].corr(method="spearman").values
    M5 = df5.loc[[col5_of_t[t] for t in t5], [col5_of_t[t] for t in t5]].values
    R["corr5"].update({
        "max_abs_err_spearman": float(np.nanmax(np.abs(S5 - M5))),
        "median_abs_err_spearman": float(np.nanmedian(np.abs(S5 - M5))),
        "diag_all_one": bool(np.allclose(np.diag(M5), 1.0)),
        "symmetry_max_abs": float(np.nanmax(np.abs(M5 - M5.T))),
    })
    # 表头行列名顺序是否与 5.csv 一致
    R["corr5"]["col_order_matches_targets"] = [t for t in t5] == [t for t in targets if t in t5]

df6 = pd.read_csv(RAW / "6.csv", index_col=0)
R["corr6"] = {"shape": list(df6.shape),
              "n_rows": df6.shape[0], "n_cols": df6.shape[1],
              "col_order_same_as_5csv": list(map(str, df6.columns)) == list(map(str, df5.columns)),
              "n_cols_matched_targets": sum(1 for c in df6.columns if norm(c) in {norm(sens_map.get(t, "")) for t in targets})}
# 6.csv 行 -> 1.csv 特征
feat6 = [disp_to_R.get(norm(r), None) for r in df6.index]
R["corr6"]["rows_mapped_to_1csv"] = sum(1 for x in feat6 if x is not None)
R["corr6"]["rows_unmapped"] = [str(r) for r, x in zip(df6.index, feat6) if x is None]
# 6.csv 列 -> 4.csv target
col6_to_target = {c: t for c in df6.columns for t in targets if norm(c) == norm(sens_map.get(t, ""))}
R["corr6"]["cols_mapped_to_targets"] = len(col6_to_target)
R["corr6"]["cols_unmapped"] = [str(c) for c in df6.columns if c not in col6_to_target]
if len(col6_to_target) == df6.shape[1] and all(x is not None for x in feat6):
    # 逐行计算 Spearman 交叉相关（行=1.csv 特征，列=4.csv target）
    sub = df1[[x for x in feat6]].copy(); sub.columns = [str(i) for i in df6.index]
    sens = df4[[col6_to_target[c] for c in df6.columns]].copy()
    sens.columns = [str(c) for c in df6.columns]
    X6 = sub.values.astype(float); Y6 = sens.values.astype(float)
    r6 = np.zeros((len(feat6), df6.shape[1]))
    for a in range(len(feat6)):
        for b in range(df6.shape[1]):
            u, v = X6[:, a], Y6[:, b]
            m = ~np.isnan(u) & ~np.isnan(v)   # 成对完整样本
            ru = pd.Series(u[m]).rank().values
            rv = pd.Series(v[m]).rank().values
            r6[a, b] = np.corrcoef(ru, rv)[0, 1]
    R["corr6"]["max_abs_err_spearman"] = float(np.nanmax(np.abs(r6 - df6.values)))
    R["corr6"]["median_abs_err_spearman"] = float(np.nanmedian(np.abs(r6 - df6.values)))

# ---------- 7. 8.xlsx ----------
x8 = {}
wb8 = openpyxl.load_workbook(RAW / "8.xlsx", read_only=True, data_only=True)
for s in wb8.sheetnames:
    ws = wb8[s]; rws = list(ws.iter_rows(values_only=True))
    x8[s] = {"dims": [ws.max_row, ws.max_column],
             "header": [str(v)[:30] if v is not None else "" for v in (rws[0] if rws else [])][:12],
             "n_rows": len(rws)}
wb8.close()
x8["Sensory names"]["dataset_counts"] = sn["dataset"].value_counts().to_dict()
x8["Sensory names"]["n_trained_R_name_in_targets"] = int(sn_tp["R_name"].isin(targets).sum())
x8["Sensory names"]["n_ratebeer"] = int((sn["dataset"] == "Ratebeer").sum())
x8["Sensory thresholds"]["n_rows"] = len(thr)
x8["Sensory thresholds"]["n_threshold_numeric"] = int(pd.to_numeric(thr["threshold_mean"], errors="coerce").notna().sum())
x8["Sensory thresholds"]["n_off_flavors"] = int(thr["off_flavors"].notna().sum())
x8["Sensory thresholds"]["n_calibrated_yes"] = int((thr["calibrated"].astype(str).str.lower() == "yes").sum())
import pandas as pd
shap = pd.read_excel(RAW / "8.xlsx", sheet_name="GBM SHAP Values", header=None)
x8["GBM SHAP Values"]["shape"] = list(shap.shape)
x8["GBM SHAP Values"]["first_col_counts"] = {str(k): int(v) for k, v in shap.iloc[:, 0].value_counts().items()}
x8["GBM SHAP Values"]["first_row_meta"] = [str(v)[:20] for v in shap.iloc[0, :4].tolist()]
cal = pd.read_excel(RAW / "8.xlsx", sheet_name="Calibrated chemical dataset")
x8["Calibrated chemical dataset"]["shape"] = list(cal.shape)
x8["Calibrated chemical dataset"]["columns"] = [str(c) for c in cal.columns]
x8["Calibrated chemical dataset"]["n_chem_cols"] = cal.shape[1] - 3
mdI = pd.read_excel(RAW / "8.xlsx", sheet_name="GBM importance MDI", header=None)
x8["GBM importance MDI"]["shape"] = list(mdI.shape)
pr = pd.read_excel(RAW / "8.xlsx", sheet_name="Beer Prices")
x8["Beer Prices"]["shape"] = list(pr.shape)
x8["Beer Prices"]["na_total"] = int(pr.isna().sum().sum())
x8["Beer Prices"]["columns"] = [str(c) for c in pr.columns]
R["xlsx8"] = x8

# ---------- 8. 7.csv ----------
df7 = pd.read_csv(RAW / "7.csv")
sens7 = [c for c in df7.columns if c not in meta4]
na7 = df7[sens7].isna().sum()
R["csv7"] = {
    "shape": list(df7.shape), "n_sensory": len(sens7),
    "na_total": int(df7[sens7].isna().sum().sum()),
    "n_all_na_cols": int((na7 == len(df7)).sum()),
    "all_na_cols": [str(c) for c in sens7 if na7[c] == len(df7)],
    "meta_equal_4csv": bool(df7[meta4].equals(df4[meta4])),
    "sd_median": float(df7[sens7].std().median()),
    "sd_all_close_1": bool(np.allclose(df7[sens7].std().dropna(), 1, atol=0.05)),
    "mean_absmax": float(df7[sens7].mean().abs().max()),
}

# ---------- 9. 题面断言 vs 实际 ----------
claims = [
    ("题面：226 种不同啤酒", "1.csv 唯一 beer 数", R["csv1"]["n_beer_unique"], R["csv1"]["n_beer_unique"] == 226),
    ("题面：2.csv 单元格为皮尔逊相关系数", "2.csv 与 Spearman 重算 max|err|",
     R["corr2"]["max_abs_err_spearman"], R["corr2"]["max_abs_err_spearman"] < 1e-10),
    ("题面：3.xlsx 10 个 sheet", "3.xlsx 实际 sheet 数", R["xlsx3"]["n_sheets"], R["xlsx3"]["n_sheets"] == 10),
    ("题面：Aroma+Flavour 共约 40 个感官维度", "4.csv 感官列数", R["targets"]["n"], R["targets"]["n"] == 40),
    ("题面：6.csv 46×50", "6.csv 实际 shape", R["corr6"]["shape"], R["corr6"]["shape"] == [46, 50]),
    ("题面：7.csv 187 个感官属性", "7.csv 感官列数", R["csv7"]["n_sensory"], R["csv7"]["n_sensory"] == 187),
    ("题面：1.csv 200 多种风味化合物", "1.csv 特征列数", R["csv1"]["n_features"], R["csv1"]["n_features"] > 200),
]
R["discrepancies"] = [{"claim": a, "actual_desc": b, "actual": c, "claim_holds": bool(d)} for a, b, c, d in claims]

json.dump(R, open(OUT / "verification.json", "w"), ensure_ascii=False, indent=1, default=str)
print("=== LEAD VERIFY SUMMARY ===")
print(json.dumps({k: R[k] for k in ["targets", "csv4_scale", "corr2", "corr5", "corr6", "csv7", "discrepancies"]},
                 ensure_ascii=False, indent=1, default=str)[:12000])
print("\nwritten:", OUT / "verification.json")
