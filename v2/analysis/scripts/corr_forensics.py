#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corr_forensics.py — 2.csv 相关矩阵类型取证（Pearson vs Spearman）
==================================================================
只用 raw 数据独立重算，不引用 A/ 往期结果。

输入（只读）: work/my-new-contest/data/raw/{1.csv,2.csv,4.csv,5.csv,6.csv,8.xlsx}
输出:        work/my-new-contest/analysis/corr/*

运行:
  PY=/Users/baozhashizitou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
  $PY analysis/scripts/corr_forensics.py

结论（脚本会打印）: 2.csv = 成对完整样本 Spearman，最大绝对误差 ~1e-15（机器精度）。
"""
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- paths
SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]            # work/my-new-contest
RAW = ROOT / "data" / "raw"
OUT = ROOT / "analysis" / "corr"
OUT.mkdir(parents=True, exist_ok=True)
META = {"script": str(SCRIPT.relative_to(ROOT))}

# ---------------------------------------------------------------- helpers
def fix_mojibake(s):
    """8.xlsx 中部分 chemical_name 是 UTF-8 被 latin-1 误解码（如 E-Î²-damascenone）。"""
    s = str(s)
    try:
        t = s.encode("latin-1").decode("utf-8")
        return t if t != s else s
    except Exception:
        return s


def norm_chem(s):
    """2.csv 显示名 / 8.xlsx chemical_name 的规范化 key：去重音、希腊字母→拉丁、小写、压空白。"""
    s = fix_mojibake(str(s))
    for a, b in [("α", "a"), ("β", "b"), ("γ", "g"), ("δ", "d"), ("ε", "e")]:
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


def norm_sensory(s):
    """5.csv/6.csv 感官显示名的规范化 key：统一 \\r\\n、_x000D_、换行。"""
    s = str(s)
    s = s.replace("_x000D_", " ").replace("\r", " ").replace("\n", " ")
    return " ".join(s.split())


def rank_col(v):
    """pandas 平均秩（等价 R rank 默认 ties='average'）。"""
    return pd.Series(v).rank().to_numpy()


def pairwise_corr(X, method="spearman"):
    """成对完整样本（pairwise complete）相关矩阵。

    method='spearman' 时，每一对 (i,j) 先在该对完整样本上取平均秩，再做 Pearson
    ——这正是 R `cor(x, method='spearman', use='pairwise.complete.obs')` 的语义。
    """
    a = np.asarray(X, dtype=float)
    n = a.shape[1]
    M = np.eye(n)
    for i in range(n):
        xi = a[:, i]
        for j in range(i + 1, n):
            xj = a[:, j]
            m = ~np.isnan(xi) & ~np.isnan(xj)
            if m.sum() < 3:
                M[i, j] = M[j, i] = np.nan
                continue
            u, v = xi[m], xj[m]
            if method == "spearman":
                u, v = rank_col(u), rank_col(v)
            M[i, j] = M[j, i] = np.corrcoef(u, v)[0, 1]
    return M


def err_stats(recomputed, target):
    """矩阵级误差统计（仅有限元素）。"""
    r = np.asarray(recomputed, float)
    t = np.asarray(target, float)
    m = np.isfinite(r) & np.isfinite(t)
    d = np.abs(r[m] - t[m])
    if d.size == 0:
        return {"n": 0}
    return {
        "n_elements": int(d.size),
        "max_abs_error": float(d.max()),
        "median_abs_error": float(np.median(d)),
        "q90_abs_error": float(np.quantile(d, 0.90)),
        "q99_abs_error": float(np.quantile(d, 0.99)),
        "frac_lt_1e-6": float(np.mean(d < 1e-6)),
        "frac_lt_0.01": float(np.mean(d < 0.01)),
        "elementwise_corr": float(np.corrcoef(r[m], t[m])[0, 1]) if d.size > 2 else None,
    }


def offdiag_mask(n):
    return np.tril_indices(n, -1)


def matrix_props(M, names=None, label=""):
    """相关矩阵属性：对称性、对角、NaN、范围、PSD（最小特征值，对称化后）。"""
    A = np.asarray(M, float)
    n = A.shape[0]
    props = {
        "label": label,
        "shape": [int(A.shape[0]), int(A.shape[1])],
        "is_square": bool(A.ndim == 2 and A.shape[0] == A.shape[1]),
        "n_rows": int(A.shape[0]),
        "n_cols": int(A.shape[1]),
        "n_nan": int(np.isnan(A).sum()),
        "min": float(np.nanmin(A)),
        "max": float(np.nanmax(A)),
    }
    if props["is_square"]:
        props["max_abs_symmetry_error"] = float(np.nanmax(np.abs(A - A.T)))
        diag = np.diag(A)
        props["diag_min"] = float(np.nanmin(diag))
        props["diag_max"] = float(np.nanmax(diag))
        props["diag_all_one"] = bool(np.allclose(diag, 1.0, atol=1e-12))
        props["n_offdiag_negative"] = int((A[offdiag_mask(n)] < 0).sum())
        eig = np.linalg.eigvalsh((A + A.T) / 2.0)
        props["min_eigenvalue"] = float(eig.min())
        props["max_eigenvalue"] = float(eig.max())
        props["is_psd_tol_1e-10"] = bool(eig.min() >= -1e-10)
        props["n_eig_below_neg_1e-10"] = int((eig < -1e-10).sum())
    if names is not None:
        lab = [norm_chem(x) for x in names]
        props["row_names_unique"] = bool(len(set(lab)) == len(lab))
        if props["is_square"] and M is not None:
            props["row_col_names_identical"] = True  # 由调用方对 csv 行列分别校验
    return props


# ---------------------------------------------------------------- load
c1 = pd.read_csv(RAW / "1.csv")
c2 = pd.read_csv(RAW / "2.csv", index_col=0)
c4 = pd.read_csv(RAW / "4.csv")
c5 = pd.read_csv(RAW / "5.csv", index_col=0)
c6 = pd.read_csv(RAW / "6.csv", index_col=0)
xl = pd.ExcelFile(RAW / "8.xlsx")
thr = pd.read_excel(xl, sheet_name="Sensory thresholds")
snames = pd.read_excel(xl, sheet_name="Sensory names")

feat1 = list(c1.columns[3:])              # 231 个特征
featset = set(feat1)
names2 = list(c2.index)                    # 231 个显示名

# ---------------------------------------------------------------- 1) 名称映射
sub = thr[thr["field_name_R"].isin(featset)].copy()
by_chem = {}
for _, r in sub.iterrows():
    for k in ["chemical_name", "chemical_name_short"]:
        if pd.notna(r[k]):
            by_chem.setdefault(norm_chem(r[k]), set()).add(r["field_name_R"])

rows, unmapped, ambiguous = [], [], []
for disp in names2:
    cand = by_chem.get(norm_chem(disp), set())
    if len(cand) == 1:
        rows.append((disp, next(iter(cand))))
    elif len(cand) == 0:
        unmapped.append(disp)
    else:
        ambiguous.append((disp, sorted(cand)))
mapping = pd.DataFrame(rows, columns=["csv2_name", "csv1_column"])

# 映射覆盖率与 1:1 校验
map_detail = mapping.merge(
    thr[["field_name_R", "field_name_python", "chemical_name", "calibrated"]],
    left_on="csv1_column", right_on="field_name_R", how="left",
)
map_detail["is_summary_col"] = map_detail["csv1_column"].str.endswith("_sum")
map_detail.to_csv(OUT / "name_mapping_2csv_to_1csv.csv", index=False, encoding="utf-8-sig")

mapping_ok = {
    "n_csv1_features": len(feat1),
    "n_csv2_names": len(names2),
    "n_matched": len(mapping),
    "n_unmapped": len(unmapped),
    "unmapped": unmapped,
    "ambiguous": ambiguous,
    "bijective": bool(len(mapping) == len(names2) == len(set(mapping["csv1_column"])) == len(feat1)),
    "csv1_features_not_used": sorted(featset - set(mapping["csv1_column"])),
    "summary_cols_1csv": [f for f in feat1 if f.endswith("_sum")],
}

# 按 2.csv 显示名顺序重排数据的列（列值与 2.csv 行列一一对应）
X2 = c1[mapping["csv1_column"].tolist()].astype(float).copy()
X2.columns = names2

# 1.csv 特征列缺失情况（决定必须用 pairwise complete 的原因）
nan_cols = X2.isna().sum()
nan_info = {
    "n_rows_1csv": int(c1.shape[0]),
    "n_nan_in_features": int(nan_cols.sum()),
    "n_cols_with_nan": int((nan_cols > 0).sum()),
    "cols_with_nan": {k: int(v) for k, v in nan_cols[nan_cols > 0].items()},
}

# ---------------------------------------------------------------- 2) 2.csv vs 重算
n = len(names2)
M2 = c2.to_numpy(float)
off = offdiag_mask(n)
diag = np.diag_indices(n)

S2 = pairwise_corr(X2, "spearman")         # 成对完整 Spearman
P2 = pairwise_corr(X2, "pearson")          # 成对完整 Pearson

# 备选假设：listwise（整行删除）Spearman
Xc = X2.dropna(axis=0, how="any")
listwise_n_rows = int(len(Xc))
S2_listwise = pairwise_corr(Xc, "spearman") if len(Xc) > 2 else np.full((n, n), np.nan)

# 备选假设：log10 变换后再 Pearson（非正值用 x-min+min_pos 平移保证可对数）
Xlog = X2.copy()
for col in Xlog.columns:
    v = Xlog[col]
    mn = np.nanmin(v)
    if mn <= 0:
        pos = v[v > 0]
        shift = -mn + (np.nanmin(pos) if len(pos) else 1.0)
        v = v + shift
    Xlog[col] = np.log10(v)
P2_log = pairwise_corr(Xlog, "pearson")

# 备选假设：秩变换后再 Pearson（数学上恒等于 Spearman，用于证明“差异可由秩变换解释”）
P2_rank = pairwise_corr(X2, "spearman")    # 同一个函数：先秩后 Pearson

hypotheses = {
    "H_spearman_pairwise": S2,
    "H_spearman_listwise": S2_listwise,
    "H_pearson_pairwise": P2,
    "H_pearson_log10": P2_log,
    "H_pearson_on_ranks": P2_rank,
}
error_stats = {"matrix": "2.csv", "shape": [int(M2.shape[0]), int(M2.shape[1])],
               "comparison": "element-wise on full 231x231 matrix (off-diagonal focus)"}
for k, R in hypotheses.items():
    error_stats[k] = {
        "offdiag": err_stats(R[off], M2[off]),
        "including_diag": err_stats(R[diag], M2[diag]),
    }
error_stats["H_spearman_listwise"]["n_rows_used_listwise"] = listwise_n_rows
with open(OUT / "error_stats.json", "w", encoding="utf-8") as f:
    json.dump({"meta": META, "mapping": mapping_ok, "h2": error_stats}, f,
              ensure_ascii=False, indent=2)

# 长表：逐元素对照
rec_long = pd.DataFrame({
    "feature_a": np.array(names2)[off[0]],
    "feature_b": np.array(names2)[off[1]],
    "value_2csv": M2[off],
    "spearman_recomputed": S2[off],
    "pearson_recomputed": P2[off],
    "pearson_log10": P2_log[off],
})
rec_long["diff_spearman"] = rec_long["spearman_recomputed"] - rec_long["value_2csv"]
rec_long["diff_pearson"] = rec_long["pearson_recomputed"] - rec_long["value_2csv"]
rec_long.to_csv(OUT / "2csv_vs_recomputed.csv", index=False, encoding="utf-8-sig")

pd.DataFrame(S2, index=names2, columns=names2).to_csv(
    OUT / "2csv_spearman_recomputed.csv", encoding="utf-8-sig")
pd.DataFrame(P2, index=names2, columns=names2).to_csv(
    OUT / "2csv_pearson_recomputed.csv", encoding="utf-8-sig")

# 决定性样例：|Pearson - 2.csv| 最大的 6 对 + 若干 Spearman 与 Pearson 分歧最大的对
sample = rec_long.copy()
sample["abs_diff_pearson"] = sample["diff_pearson"].abs()
sample["abs_diff_spearman"] = sample["diff_spearman"].abs()
top_pairs = sample.sort_values("abs_diff_pearson", ascending=False).head(6)[
    ["feature_a", "feature_b", "value_2csv", "spearman_recomputed", "pearson_recomputed",
     "pearson_log10", "diff_spearman", "diff_pearson", "abs_diff_spearman"]
]
top_pairs.to_csv(OUT / "sample_pairs.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 3) 矩阵属性
props_2 = matrix_props(M2, names2, "2.csv")
props_2.update({
    "file": "data/raw/2.csv",
    "n_features_1csv": len(feat1),
    "row_names_equal_col_names": bool(list(c2.index) == list(c2.columns)),
    "row_names_unique_normalized": bool(len({norm_chem(x) for x in c2.index}) == len(c2.index)),
    "all_names_mapped_to_1csv": bool(len(mapping) == len(feat1) == len(names2)),
    "is_correlation_like_minus1_1": bool(np.nanmin(M2) >= -1 - 1e-12 and np.nanmax(M2) <= 1 + 1e-12),
})

# 重算矩阵自身属性 + 交叉核对（证明 2.csv 与重算矩阵同源，而非近似）
eig_S = np.linalg.eigvalsh((S2 + S2.T) / 2.0)
props_2.update({
    "n_feature_nan_in_1csv": nan_info["n_nan_in_features"],
    "n_cols_with_nan_in_1csv": nan_info["n_cols_with_nan"],
    "cols_with_nan_in_1csv": nan_info["cols_with_nan"],
    "recomputed_spearman": {
        "max_abs_symmetry_error": float(np.abs(S2 - S2.T).max()),
        "diag_all_one": bool(np.allclose(np.diag(S2), 1.0, atol=1e-12)),
        "min_eigenvalue": float(eig_S.min()),
        "min_eigenvalue_matches_2csv_absdiff": float(abs(eig_S.min() - props_2["min_eigenvalue"])),
        "n_elements_with_abs_diff_lt_1e-12": int((np.abs(S2 - M2) < 1e-12).sum()),
        "n_offdiag_total": int(off[0].size),
    },
    "pearson_vs_2csv_sign_disagreements": int(
        (np.sign(P2[off]) != np.sign(M2[off])).sum()),
    "pearson_vs_2csv_sign_disagreements_frac": float(
        np.mean(np.sign(P2[off]) != np.sign(M2[off]))),
    "pandas_corr_spearman_vs_2csv_max_abs": float(
        np.nanmax(np.abs(X2.corr(method="spearman").to_numpy() - M2))),
    "pandas_corr_pearson_vs_2csv_max_abs": float(
        np.nanmax(np.abs(X2.corr(method="pearson").to_numpy() - M2))),
})

# ---------------------------------------------------------------- 4) 5.csv = Spearman(4.csv)?
tp = snames[snames["dataset"] == "Trained panel"].copy()
tp["disp"] = tp["CleanName_PanelFeedback"].map(norm_sensory)
sen4 = list(c4.columns[3:])
name5 = list(c5.index)
name5_key = {norm_sensory(x): i for i, x in enumerate(name5)}

# 4.csv 列(R_name) -> 5.csv 显示名
map45 = {}
for _, r in tp.iterrows():
    if r["R_name"] in sen4 and r["disp"] in name5_key:
        map45[r["R_name"]] = r["disp"]
order4 = [c for c in sen4 if c in map45]           # 4.csv 感官列顺序
M5 = c5.to_numpy(float)
perm5 = [name5_key[norm_sensory(map45[c])] for c in order4]
M5a = M5[np.ix_(perm5, perm5)]

X4 = c4[order4].astype(float)
S5 = pairwise_corr(X4, "spearman")
P5 = pairwise_corr(X4, "pearson")
err5_s = err_stats(S5, M5a)
err5_p = err_stats(P5, M5a)
props_5 = matrix_props(M5, name5, "5.csv")
props_5.update({
    "file": "data/raw/5.csv",
    "shape_read": [int(c5.shape[0]), int(c5.shape[1])],
    "raw_columns_in_file": int(pd.read_csv(RAW / "5.csv", nrows=0).shape[1]),
    "n_4csv_sensory_cols": len(sen4),
    "n_mapped_4to5": len(map45),
    "names_unmapped": [c for c in sen4 if c not in map45],
    "row_names_equal_col_names": bool(list(c5.index) == list(c5.columns)),
    "input_4csv_shape": [int(c4.shape[0]), int(c4.shape[1])],
})
pd.DataFrame({
    "sensory_a": np.repeat(np.array(order4), len(order4)),
    "sensory_b": np.tile(np.array(order4), len(order4)),
    "value_5csv": M5a.ravel(),
    "spearman_recomputed": S5.ravel(),
    "pearson_recomputed": P5.ravel(),
}).to_csv(OUT / "5csv_vs_recomputed.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 5) 6.csv = Spearman(1.csv, 4.csv)?
names6_row = list(c6.index)      # 化学特征显示名（44）
names6_col = list(c6.columns)    # 感官显示名（50）
M6 = c6.to_numpy(float)

# 6.csv 行名 -> 1.csv 列名：复用 2.csv 的映射（若 6.csv 行名是 2.csv 名字的子集）
map2 = dict(zip(mapping["csv2_name"], mapping["csv1_column"]))
row_map6 = {r: map2[r] for r in names6_row if r in map2}
row_unmapped6 = [r for r in names6_row if r not in map2]
# 6.csv 列(感官显示名) -> 4.csv 列名
sen4_key = {norm_sensory(map45[c]): c for c in order4} if order4 else {}
col_map6 = {s: sen4_key.get(norm_sensory(s)) for s in names6_col}
col_unmapped6 = [s for s in names6_col if col_map6[s] is None]

rows6 = [r for r in names6_row if r in row_map6]
cols6 = [s for s in names6_col if col_map6[s] is not None]
X6a = c1[[row_map6[r] for r in rows6]].astype(float).to_numpy()
X6b = c4[[col_map6[s] for s in cols6]].astype(float).to_numpy()
S6 = np.full((len(rows6), len(cols6)), np.nan)
P6 = np.full_like(S6, np.nan)
for i in range(len(rows6)):
    for j in range(len(cols6)):
        u, v = X6a[:, i], X6b[:, j]
        m = ~np.isnan(u) & ~np.isnan(v)
        if m.sum() < 3:
            continue
        P6[i, j] = np.corrcoef(u[m], v[m])[0, 1]
        S6[i, j] = np.corrcoef(rank_col(u[m]), rank_col(v[m]))[0, 1]
# 对齐到 6.csv 原顺序（rows6/cols6 是剔除未映射后的子序列，正常情况下就是原顺序）
idx_r = [names6_row.index(r) for r in rows6]
idx_c = [names6_col.index(s) for s in cols6]
M6a = M6[np.ix_(idx_r, idx_c)]
err6_s = err_stats(S6, M6a)
err6_p = err_stats(P6, M6a)
props_6 = {
    "label": "6.csv", "file": "data/raw/6.csv",
    "shape_read": [int(c6.shape[0]), int(c6.shape[1])],
    "raw_columns_in_file": int(pd.read_csv(RAW / "6.csv", nrows=0).shape[1]),
    "n_rows_chemical": len(names6_row),
    "n_cols_sensory": len(names6_col),
    "n_nan": int(np.isnan(M6).sum()),
    "min": float(np.nanmin(M6)), "max": float(np.nanmax(M6)),
    "n_rows_mapped_to_1csv": len(rows6),
    "rows_unmapped": row_unmapped6,
    "n_cols_mapped_to_4csv": len(cols6),
    "cols_unmapped": col_unmapped6,
    "problem_statement_says": "46x50",
    "actual": "44x50 (44 chemical rows x 50 sensory columns)",
}
pd.DataFrame({
    "chemical": np.repeat(np.array(rows6), len(cols6)),
    "sensory": np.tile(np.array(cols6), len(rows6)),
    "value_6csv": M6a.ravel(),
    "spearman_recomputed": S6.ravel(),
    "pearson_recomputed": P6.ravel(),
}).to_csv(OUT / "6csv_vs_recomputed.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 6) 汇总
summary = {
    "meta": META,
    "2csv": {
        "verdict": "Spearman (pairwise complete), NOT Pearson",
        "spearman_max_abs_error": error_stats["H_spearman_pairwise"]["offdiag"]["max_abs_error"],
        "spearman_median_abs_error": error_stats["H_spearman_pairwise"]["offdiag"]["median_abs_error"],
        "spearman_elementwise_corr": error_stats["H_spearman_pairwise"]["offdiag"]["elementwise_corr"],
        "pearson_max_abs_error": error_stats["H_pearson_pairwise"]["offdiag"]["max_abs_error"],
        "pearson_median_abs_error": error_stats["H_pearson_pairwise"]["offdiag"]["median_abs_error"],
        "pearson_elementwise_corr": error_stats["H_pearson_pairwise"]["offdiag"]["elementwise_corr"],
        "listwise_spearman_max_abs_error": error_stats["H_spearman_listwise"]["offdiag"]["max_abs_error"],
        "log10_pearson_max_abs_error": error_stats["H_pearson_log10"]["offdiag"]["max_abs_error"],
        "log10_pearson_median_abs_error": error_stats["H_pearson_log10"]["offdiag"]["median_abs_error"],
        "min_eigenvalue_2csv": props_2["min_eigenvalue"],
        "min_eigenvalue_recomputed_spearman": props_2["recomputed_spearman"]["min_eigenvalue"],
        "is_psd": props_2["is_psd_tol_1e-10"],
        "pearson_sign_disagreements": props_2["pearson_vs_2csv_sign_disagreements"],
        "pearson_sign_disagreements_frac": props_2["pearson_vs_2csv_sign_disagreements_frac"],
        "n_elements_abs_diff_lt_1e-12": props_2["recomputed_spearman"]["n_elements_with_abs_diff_lt_1e-12"],
        "n_offdiag_total": props_2["recomputed_spearman"]["n_offdiag_total"],
        "nan_in_1csv_features": nan_info["n_nan_in_features"],
        "row_names_equal": props_2["row_names_equal_col_names"],
        "mapping_bijective": mapping_ok["bijective"],
        "n_unmapped": mapping_ok["n_unmapped"],
    },
    "5csv": {"is_spearman_of_4csv": err5_s["max_abs_error"] < 1e-8,
             "spearman_max_abs_error": err5_s["max_abs_error"],
             "pearson_max_abs_error": err5_p["max_abs_error"],
             "shape": props_5["shape"], "mapping_complete": len(map45) == len(sen4)},
    "6csv": {"is_spearman_cross_1csv_4csv": err6_s["max_abs_error"] < 1e-8,
             "spearman_max_abs_error": err6_s["max_abs_error"],
             "pearson_max_abs_error": err6_p["max_abs_error"],
             "shape_actual": props_6["shape_read"],
             "shape_statement": "46x50", "mapping_complete": len(rows6) == len(names6_row) and len(cols6) == len(names6_col)},
}
with open(OUT / "matrix_properties.json", "w", encoding="utf-8") as f:
    json.dump({"meta": META, "2csv": props_2, "5csv": props_5, "6csv": props_6}, f,
              ensure_ascii=False, indent=2)
with open(OUT / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- print
def p(x):
    return f"{x:.6g}"

print("=" * 78)
print("1) 名称映射: 2.csv 231 名 <-> 1.csv 231 列  ->", "OK" if mapping_ok["bijective"] else "FAIL",
      "| unmapped:", mapping_ok["n_unmapped"], "| summary cols:", mapping_ok["summary_cols_1csv"])
print("2) 2.csv vs 重算（off-diagonal, n=%d）:" % error_stats["H_spearman_pairwise"]["offdiag"]["n_elements"])
for k in ["H_spearman_pairwise", "H_pearson_pairwise", "H_spearman_listwise", "H_pearson_log10"]:
    s = error_stats[k]["offdiag"]
    print(f"   {k:24s} max={p(s['max_abs_error']):>12s} median={p(s['median_abs_error']):>12s} corr={p(s['elementwise_corr'])}")
print("3) 2.csv 属性:", json.dumps({k: props_2[k] for k in [
    "n_nan", "max_abs_symmetry_error", "diag_all_one", "min", "max",
    "min_eigenvalue", "is_psd_tol_1e-10", "row_names_equal_col_names"]}, ensure_ascii=False))
print("   PSD: 2.csv min_eig=", p(props_2["min_eigenvalue"]), "| 重算 Spearman min_eig=",
      p(props_2["recomputed_spearman"]["min_eigenvalue"]),
      "| Pearson 与 2.csv 符号相反的元素对:", props_2["pearson_vs_2csv_sign_disagreements"],
      "/", props_2["recomputed_spearman"]["n_offdiag_total"])
print("4) 5.csv = Spearman(4.csv)?", summary["5csv"]["is_spearman_of_4csv"],
      "max_abs=", p(err5_s["max_abs_error"]), "| Pearson wrongly assumed max_abs=", p(err5_p["max_abs_error"]),
      "| shape", props_5["shape"])
print("5) 6.csv = Spearman(1.csv,4.csv)?", summary["6csv"]["is_spearman_cross_1csv_4csv"],
      "max_abs=", p(err6_s["max_abs_error"]), "| Pearson wrongly assumed max_abs=", p(err6_p["max_abs_error"]),
      "| shape", props_6["shape_read"], "(题面称 46x50)")
print("6) 决定性样例（2.csv vs Pearson vs Spearman）:")
for _, r in top_pairs.head(5).iterrows():
    print(f"   {r['feature_a']} | {r['feature_b']}: 2.csv={r['value_2csv']:+.4f} "
          f"Spearman={r['spearman_recomputed']:+.4f} Pearson={r['pearson_recomputed']:+.4f}")
print("=" * 78)
print("输出目录:", OUT)
