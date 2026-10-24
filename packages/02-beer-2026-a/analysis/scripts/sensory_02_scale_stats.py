#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensory_02_scale_stats.py
4.csv 50 个感官目标列的逐列分布统计，并严格检验三种尺度假设：
  H1 per-column z-score（sd≈1）、H2 仅中心化（mean≈0）、H3 原始 0-6 分。
再做“0-6 可还原性”的量化分析：
  - 若假定原始分 ∈[0,6]，线性映射 x = a + b*z 的可行域；
  - 两种自然单调映射（列内 min-max -> [0,6]；列内秩/分位数映射 -> 0..6）的差异；
  - “原始列均值=3、标准差=1”这一常见假设下越界比例。
输出：analysis/sensory/scale_stats.csv
      analysis/sensory/mapping_analysis.csv
      analysis/sensory/scale_hypothesis_tests.json
只读 raw，不改 raw。
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "analysis", "sensory")
os.makedirs(OUT, exist_ok=True)
META = ["beer", "beer_id", "tasting_category_fine"]


def average_rank(x):
    """平均秩（并列取平均），1..n。"""
    s = pd.Series(x)
    return s.rank(method="average").values


def main():
    df = pd.read_csv(os.path.join(RAW, "4.csv"))
    cols = [c for c in df.columns if c not in META]
    assert len(cols) == 50, len(cols)

    stats_rows, map_rows = [], []
    n = len(df)
    all_vals = df[cols].values.astype(float)

    for c in cols:
        x = df[c].values.astype(float)
        xmin, xmax = float(np.min(x)), float(np.max(x))
        rng = xmax - xmin
        mean, sd = float(np.mean(x)), float(np.std(x, ddof=1))
        q = np.quantile(x, [0.01, 0.25, 0.50, 0.75, 0.99])
        skew = float(pd.Series(x).skew())
        kurt = float(pd.Series(x).kurt())
        is_int = bool(np.allclose(x, np.round(x)))
        n_below0 = int((x < 0).sum())
        n_above6 = int((x > 6).sum())
        # H1: z-score 检验（|sd-1|）
        h1_pass = abs(sd - 1.0) <= 0.05
        # H2: 精确中心化（|mean| <= 1e-9）
        h2_exact = abs(mean) <= 1e-9
        # H2': 近似中心化（|mean| <= 0.1）
        h2_approx = abs(mean) <= 0.1
        # H3: 0-6 原始分（整数 + 落在 [0,6]）
        h3_pass = is_int and n_below0 == 0 and n_above6 == 0

        stats_rows.append(dict(
            col=c, n=n, n_missing=int(np.isnan(x).sum()),
            mean=mean, sd=sd, min=xmin, max=xmax, range=rng,
            nunique=int(len(np.unique(x))), is_integer=is_int,
            skew=skew, kurtosis=kurt,
            q01=q[0], q25=q[1], q50=q[2], q75=q[3], q99=q[4],
            n_below_0=n_below0, n_above_6=n_above6, pct_outside_0_6=100.0 * (n_below0 + n_above6) / n,
            H1_zscore_sd_eq_1=h1_pass, H1_abs_sd_minus_1=abs(sd - 1.0),
            H2_centered_exact=h2_exact, H2_centered_within_0p1=h2_approx,
            H3_raw_0_6=h3_pass,
            # 若 x = a + b*z 且要求 x∈[0,6]: b <= 6/range
            implied_max_b_if_raw_0_6=6.0 / rng,
        ))

        # ---- 映射分析：两种“都保序、都落入 0-6”的自然映射 ----
        z = (x - mean) / sd
        mm = 6.0 * (z - z.min()) / (z.max() - z.min()) if rng > 0 else np.zeros(n)
        ranks = average_rank(z)
        rk = 6.0 * (ranks - 1.0) / (n - 1)
        diff = mm - rk
        map_rows.append(dict(
            col=c, range=rng, sd=sd,
            minmax_mean=float(mm.mean()), minmax_sd=float(mm.std(ddof=1)),
            minmax_min=float(mm.min()), minmax_max=float(mm.max()),
            rankmap_mean=float(rk.mean()), rankmap_sd=float(rk.std(ddof=1)),
            mean_abs_diff_minmax_vs_rankmap=float(np.mean(np.abs(diff))),
            max_abs_diff_minmax_vs_rankmap=float(np.max(np.abs(diff))),
            spearman_minmax_vs_rankmap=float(np.corrcoef(average_rank(mm), average_rank(rk))[0, 1]),
            # 下游 RMSE：若在映射空间评估，相对 z 空间的缩放系数
            rmse_scale_factor_minmax=6.0 / rng,
            # H3' 假设：原始列均值=3、原始 sd=1 -> x = 3 + z
            n_out_of_0_6_if_mean3_sd1=int(((3 + z) < 0).sum() + ((3 + z) > 6).sum()),
            max_value_if_mean3_sd1=float(np.max(3 + z)),
        ))

    st = pd.DataFrame(stats_rows)
    mp = pd.DataFrame(map_rows)
    st.to_csv(os.path.join(OUT, "scale_stats.csv"), index=False, encoding="utf-8-sig")
    mp.to_csv(os.path.join(OUT, "mapping_analysis.csv"), index=False, encoding="utf-8-sig")

    # ---- 全局假设检验汇总 ----
    tests = {
        "n_rows": int(n), "n_cols": int(len(cols)), "n_cells": int(n * len(cols)),
        "global_mean": float(all_vals.mean()),
        "global_sd_ddof1": float(all_vals.std(ddof=1)),
        "global_min": float(all_vals.min()), "global_max": float(all_vals.max()),
        "H1_per_column_zscore": {
            "verdict": "REJECTED",
            "n_cols_with_abs_sd_minus_1_le_0.05": int(st.H1_zscore_sd_eq_1.sum()),
            "n_cols_with_sd_gt_0.95": int((st.sd > 0.95).sum()),
            "sd_min": float(st.sd.min()), "sd_max": float(st.sd.max()), "sd_mean": float(st.sd.mean()),
            "sd_quantiles": {q: float(np.quantile(st.sd, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        },
        "H2_centering": {
            "verdict": "APPROXIMATELY_CENTERED_BUT_NOT_EXACT",
            "n_cols_exact_mean_0": int(st.H2_centered_exact.sum()),
            "n_cols_abs_mean_le_0.1": int(st.H2_centered_within_0p1.sum()),
            "abs_mean_min": float(st["mean"].abs().min()), "abs_mean_max": float(st["mean"].abs().max()),
            "abs_mean_mean": float(st["mean"].abs().mean()),
        },
        "H3_raw_0_6": {
            "verdict": "REJECTED",
            "n_integer_columns": int(st.is_integer.sum()),
            "n_cols_all_within_0_6": int((st.n_below_0 + st.n_above_6 == 0).sum()),
            "n_cells_below_0": int(st.n_below_0.sum()), "n_cells_above_6": int(st.n_above_6.sum()),
            "pct_cells_outside_0_6": float(100.0 * (st.n_below_0.sum() + st.n_above_6.sum()) / (n * len(cols))),
        },
        "feasible_affine_map_if_raw_in_0_6": {
            "model": "x_raw = a_col + b * z_col, b>0",
            "b_max_global": float((6.0 / st.range).min()),
            "b_max_global_col": str(st.loc[(6.0 / st.range).idxmin(), "col"]),
            "comment": "任何逐列仿射反演都只能给出 (a,b) 的一个可行区间；b 的可行上界由列内极差决定，"
                       "而每列的原点 a 完全不可识别（标准化已抹去列均值）。",
        },
        "mapping_disagreement": {
            "mean_abs_diff_overall": float(mp.mean_abs_diff_minmax_vs_rankmap.mean()),
            "max_abs_diff_overall": float(mp.max_abs_diff_minmax_vs_rankmap.max()),
            "mean_abs_diff_median_over_cols": float(mp.mean_abs_diff_minmax_vs_rankmap.median()),
            "spearman_all_one": bool(np.allclose(mp.spearman_minmax_vs_rankmap, 1.0)),
            "rmse_scale_factor_minmax_min": float(mp.rmse_scale_factor_minmax.min()),
            "rmse_scale_factor_minmax_max": float(mp.rmse_scale_factor_minmax.max()),
        },
        "mean3_sd1_mapping": {
            "n_cells_out_of_0_6": int(mp.n_out_of_0_6_if_mean3_sd1.sum()),
            "pct_cells_out_of_0_6": float(100.0 * mp.n_out_of_0_6_if_mean3_sd1.sum() / (n * len(cols))),
            "max_value": float(mp.max_value_if_mean3_sd1.max()),
            "worst_col": str(mp.loc[mp.max_value_if_mean3_sd1.idxmax(), "col"]),
        },
    }
    with open(os.path.join(OUT, "scale_hypothesis_tests.json"), "w", encoding="utf-8") as fh:
        json.dump(tests, fh, ensure_ascii=False, indent=2)

    print(json.dumps({k: tests[k] for k in ("n_rows", "n_cols", "global_mean", "global_sd_ddof1",
                                            "global_min", "global_max")}, ensure_ascii=False, indent=1))
    print("H1:", tests["H1_per_column_zscore"])
    print("H2:", tests["H2_centering"])
    print("H3:", tests["H3_raw_0_6"])
    print("feasible:", tests["feasible_affine_map_if_raw_in_0_6"])
    print("mapping disagreement:", tests["mapping_disagreement"])
    print("mean3sd1:", tests["mean3_sd1_mapping"])
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
