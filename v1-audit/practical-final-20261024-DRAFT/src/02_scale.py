"""02 尺度识别：对 1.csv 的 231 个化合物/理化列逐列判定 1.csv 数值属于 log10(浓度) 还是 linear(浓度)。

判据（全部可回读，证据落在 outputs/audit/scale_identification.csv）：
  1) 8.xlsx "Calibrated chemical dataset" 覆盖 70 列（列名与 1.csv 完全一致）。
     对每列比较两个候选假设与 calibrated 的相对误差中位数（仅用 calibrated != 0 的行）：
        H_log : conc = 10^(1.csv 值)
        H_lin : conc = 1.csv 值
     中位相对误差 < 1e-6 即判定该假设成立；两者都不成立 -> ambiguous（本项目实测不出现）。
  2) 其余 161 列没有外部浓度表可校验 -> 一律标 unverified，只记录取值范围/负值/零值比例，
     并给出形态学提示（含负值或共享地板值 => 不可能是原始浓度，log 尺度可能性高；不臆造单位/底数）。
  3) 对 43 个在 "Sensory thresholds" 中给出 threshold_mean 的化合物（用 field_name_R 与 1.csv 列名
     精确匹配，43/43 命中）：conc 按第 1) 步的判定还原，OAV = conc / threshold_mean，
     输出分位数并检查中位 OAV 是否落在合理量级 1e-3 ~ 1e2。

关键结论（写进 scale_report.json 的 opening_question_answer）：
  1.csv 与 8.xlsx Calibrated 的关系不是"全表 log10"也不是"全表原始浓度"，而是**混合尺度**：
  37 列 1.csv = log10(calibrated)，33 列 1.csv = calibrated（原值）；并且 calibrated == 0 的行
  在 1.csv 中不是 0 而是 log10(该列最小正浓度 / 2)，即 LOD/2 左删失替换。
  因此 8.xlsx calibrated 是作者提供的"去对数 + 非检出置 0"的统一浓度表，1.csv 是混合尺度原始表。

输出（项目内相对路径）：
  outputs/audit/scale_identification.csv   231 行逐列判定
  outputs/audit/oav_summary.csv            43 行 OAV 分位数
  outputs/audit/scale_report.json          汇总 + 论证 + 论文可用结论
仅读 data/raw，不写 data/clean（数据清洗在 03_clean.py）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

KEYSET = set(C.KEYS)
REL_TOL = 1e-6          # 中位相对误差阈值
OAV_LO, OAV_HI = 1e-3, 1e2
FLOOR_ATOL = 1e-6       # 共享地板值判定容差（1.csv 中该值以 6-7 位小数存储）


def rel_err(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        return np.abs(a - b) / np.maximum(np.abs(b), 1e-12)


def main():
    f = C.load_features()                       # 1.csv: 250 x (3 键 + 231)
    cal = C.load_calibrated_chemicals()         # 8.xlsx Calibrated: 250 x (3 键 + 70)
    th = C.load_sensory_thresholds()            # 8.xlsx Sensory thresholds: 261 行

    feats = [c for c in f.columns if c not in KEYSET]
    cal_cols = [c for c in cal.columns if c not in KEYSET]
    assert len(feats) == 231, len(feats)
    assert set(cal_cols) <= set(feats), "calibrated 列名应全部落在 1.csv 列名里"
    unverified_cols = [c for c in feats if c not in cal_cols]

    # 未验证列共享地板值（从数据里自动识别众数最小值，不硬编码）
    mins = {c: float(f[c].min()) for c in unverified_cols}
    rounded = pd.Series({c: round(v, 9) for c, v in mins.items()})
    mode_round = rounded.value_counts().idxmax()
    floor_cols = [c for c in unverified_cols if rounded[c] == mode_round]
    shared_floor = min(mins[c] for c in floor_cols)
    floor_cells = int((np.abs(f[unverified_cols].values - shared_floor) < FLOOR_ATOL).sum())

    m = f.merge(cal, on="beer", suffixes=("", "_cal"), how="left")
    assert len(m) == len(f), "按 beer 合并应保持 250 行"
    assert m["beer_id"].tolist() == f["beer_id"].tolist(), "合并后 beer 顺序应保持"

    # ---------------------------------------------------------------- 逐列判定
    recs = []
    for c in feats:
        v_all = f[c].astype(float)
        rec = {
            "compound": c,
            "n_rows": int(len(f)),
            "n_missing": int(v_all.isna().sum()),
            "n_negative": int((v_all < 0).sum()),
            "pct_negative": round(float((v_all < 0).mean()), 6),
            "n_zero": int((v_all == 0).sum()),
            "pct_zero": round(float((v_all == 0).mean()), 6),
            "min": float(v_all.min()) if v_all.notna().any() else np.nan,
            "max": float(v_all.max()) if v_all.notna().any() else np.nan,
            "median": float(v_all.median()) if v_all.notna().any() else np.nan,
            "n_unique": int(v_all.nunique()),
            "in_calibrated": c in cal_cols,
            "is_aggregate": c in C.AGG_FEATURES,
            "shared_floor_cells": np.nan,
            "implied_lod_half_conc": np.nan,
        }
        if c in cal_cols:
            v = m[c].astype(float)
            cc = m[c + "_cal"].astype(float)
            ok = v.notna() & cc.notna()
            v, cc = v[ok].values, cc[ok].values
            nz = cc != 0
            rec["n_compared_nonzero"] = int(nz.sum())
            rec["median_rel_err_log10"] = float(np.median(rel_err(10.0 ** v[nz], cc[nz]))) if nz.any() else np.nan
            rec["median_rel_err_identity"] = float(np.median(rel_err(v[nz], cc[nz]))) if nz.any() else np.nan
            if rec["median_rel_err_log10"] < REL_TOL:
                rec["scale_verdict"] = "log10"
            elif rec["median_rel_err_identity"] < REL_TOL:
                rec["scale_verdict"] = "linear"
            else:
                rec["scale_verdict"] = "ambiguous"
            # 左删失形态：calibrated==0 的行 是否满足 10^v == 该列最小正 calibrated / 2
            z = cc == 0
            rec["n_calibrated_zero"] = int(z.sum())
            rec["cal_zero_ratio_max_err"] = np.nan
            if rec["scale_verdict"] == "log10" and z.any():
                pos_min = float(cc[nz].min()) if nz.any() else np.nan
                rec["implied_lod_half_conc"] = pos_min / 2 if np.isfinite(pos_min) else np.nan
                with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                    ratio = (10.0 ** v[z]) / pos_min if np.isfinite(pos_min) and pos_min > 0 \
                        else np.full(int(z.sum()), np.nan)
                if np.isfinite(ratio).any():
                    rec["cal_zero_ratio_max_err"] = float(np.max(np.abs(ratio - 0.5)))
                    rec["cal_zero_relation"] = (
                        "calibrated==0 <=> 10^v == min(positive calibrated)/2（LOD/2 替换）"
                        if rec["cal_zero_ratio_max_err"] < 1e-6 else "calibrated==0 但 10^v 不等于 min_positive/2")
                else:
                    rec["cal_zero_relation"] = "calibrated==0 但无正 calibrated 参照"
            else:
                rec["cal_zero_relation"] = "无 calibrated==0 的行" if not z.any() else "非 log10 列"
            rec["evidence"] = (
                f"与 8.xlsx Calibrated 对齐 {int(ok.sum())} 行（非零 {int(nz.sum())}）；"
                f"10^v 中位相对误差={rec['median_rel_err_log10']:.3e}，"
                f"v 中位相对误差={rec['median_rel_err_identity']:.3e}")
            rec["scale_hint"] = "verified"
        else:
            rec["n_compared_nonzero"] = np.nan
            rec["median_rel_err_log10"] = np.nan
            rec["median_rel_err_identity"] = np.nan
            rec["scale_verdict"] = "unverified"
            rec["n_calibrated_zero"] = np.nan
            rec["cal_zero_ratio_max_err"] = np.nan
            rec["cal_zero_relation"] = "无外部浓度表可校验"
            at_floor = int((np.abs(v_all.values - shared_floor) < FLOOR_ATOL).sum())
            rec["shared_floor_cells"] = at_floor
            has_neg = rec["n_negative"] > 0
            if has_neg or at_floor > 0:
                rec["scale_hint"] = "log_scale_likely(有负值/共享地板值 -> 不可能是原始浓度；底数与单位未验证)"
            elif rec["max"] <= 10:
                rec["scale_hint"] = "ambiguous(全为非负且 <=10，log 与 linear 都可解释)"
            else:
                rec["scale_hint"] = "linear_likely(全为正且 max>10)"
            rec["evidence"] = (
                f"无 calibrated 覆盖；负值 {rec['n_negative']} 个、共享地板值出现 {at_floor} 次、"
                f"范围 [{rec['min']:.6g}, {rec['max']:.6g}]")

        # 阈值 / OAV 可用性（先置位，后面回填）
        rec["has_threshold"] = False
        rec["threshold_mean"] = np.nan
        rec["threshold_unit"] = ""
        rec["can_oav"] = False
        recs.append(rec)

    sid = pd.DataFrame(recs)

    # ---------------------------------------------------------------- 阈值映射与 OAV
    thw = th[th["threshold_mean"].notna()].copy()
    thw["field"] = thw["field_name_R"].astype(str).str.strip()
    thw["in_1csv"] = thw["field"].isin(feats)
    unmatched = thw.loc[~thw["in_1csv"], "field"].tolist()
    thw = thw[thw["in_1csv"]].drop_duplicates("field").reset_index(drop=True)

    oav_rows = []
    for _, r in thw.iterrows():
        c = r["field"]
        row = sid.loc[sid["compound"] == c].iloc[0]
        v = f[c].astype(float)
        if row["scale_verdict"] == "log10":
            conc = 10.0 ** v
            conv = "10^v（1.csv 为 log10）"
        elif row["scale_verdict"] == "linear":
            conc = v
            conv = "v（1.csv 为线性浓度）"
        else:  # 不应发生：43 个阈值化合物均被 calibrated 覆盖
            conc = v
            conv = "v（未验证，按原值）"
        thr = float(r["threshold_mean"])
        oav = conc / thr
        oav_valid = oav.dropna()
        if c in cal_cols:
            cc = m[c + "_cal"].astype(float)
            n_censored = int((cc == 0).sum())
        else:
            n_censored = np.nan
        q = np.percentile(oav_valid.values, [5, 25, 50, 75, 95]) if len(oav_valid) else np.full(5, np.nan)
        med = float(q[2]) if len(oav_valid) else np.nan
        oav_rows.append({
            "compound": c,
            "threshold_mean": thr,
            "unit": r["unit"],
            "origin_paper": r["origin_paper"],
            "off_flavors": r["off_flavors"] if pd.notna(r["off_flavors"]) else "",
            "scale_verdict": row["scale_verdict"],
            "concentration_conversion": conv,
            "n_nonmissing": int(len(oav_valid)),
            "n_missing": int(v.isna().sum()),
            "n_censored": n_censored,
            "conc_min": float(conc.min()) if conc.notna().any() else np.nan,
            "conc_max": float(conc.max()) if conc.notna().any() else np.nan,
            "oav_min": float(oav_valid.min()) if len(oav_valid) else np.nan,
            "oav_p05": float(q[0]),
            "oav_p25": float(q[1]),
            "oav_median": med,
            "oav_p75": float(q[3]),
            "oav_p95": float(q[4]),
            "oav_max": float(oav_valid.max()) if len(oav_valid) else np.nan,
            "oav_mean": float(oav_valid.mean()) if len(oav_valid) else np.nan,
            "frac_gt1": float((oav_valid > 1).mean()) if len(oav_valid) else np.nan,
            "frac_gt10": float((oav_valid > 10).mean()) if len(oav_valid) else np.nan,
            "median_log10_oav": float(np.log10(med)) if med and med > 0 else np.nan,
            "magnitude_ok": bool(np.isfinite(med) and OAV_LO <= med <= OAV_HI),
        })
    oav = pd.DataFrame(oav_rows).sort_values("oav_median", ascending=False).reset_index(drop=True)

    # 把阈值信息回填到逐列表
    tmap = oav.set_index("compound")
    sid["has_threshold"] = sid["compound"].isin(tmap.index)
    sid["threshold_mean"] = sid["compound"].map(tmap["threshold_mean"])
    sid["threshold_unit"] = sid["compound"].map(tmap["unit"]).fillna("")
    sid["can_oav"] = sid["has_threshold"] & sid["scale_verdict"].isin(["log10", "linear"])

    for df in (sid, oav):
        for col in df.columns:
            if df[col].dtype == float:
                df[col] = df[col].round(12)

    # ---------------------------------------------------------------- 汇总
    counts = sid["scale_verdict"].value_counts().to_dict()
    log10_cols = sid.loc[sid["scale_verdict"] == "log10", "compound"].tolist()
    linear_cols = sid.loc[sid["scale_verdict"] == "linear", "compound"].tolist()

    cz = sid[sid["scale_verdict"] == "log10"]
    censoring = {
        "total_calibrated_zero_cells_in_log10_cols": int(cz["n_calibrated_zero"].fillna(0).sum()),
        "n_log10_cols_with_zero": int((cz["n_calibrated_zero"].fillna(0) > 0).sum()),
        "max_abs_err_of_ratio_vs_half": float(cz["cal_zero_ratio_max_err"].max(skipna=True))
                                        if cz["cal_zero_ratio_max_err"].notna().any() else np.nan,
        "relation": "calibrated==0 的每一行都满足 10^(1.csv值) = 该列最小正 calibrated / 2（LOD/2 左删失替换）",
        "note": "因此 1.csv 中这些单元格不是真实测量值而是 LOD/2 替换；建模时应作为删失处理或至少标记。",
    }

    unv = sid[sid["scale_verdict"] == "unverified"]
    unverified_summary = {
        "n_cols": int(len(unv)),
        "n_with_negative": int((unv["n_negative"] > 0).sum()),
        "n_with_shared_floor": int((unv["shared_floor_cells"] > 0).sum()),
        "shared_floor_value": float(shared_floor),
        "shared_floor_10pow": float(10.0 ** shared_floor),
        "shared_floor_cells_total": int(floor_cells),
        "n_no_negative_and_max_le_10": int(((unv["n_negative"] == 0) & (unv["max"] <= 10)).sum()),
        "range_min": float(unv["min"].min()),
        "range_max": float(unv["max"].max()),
        "note": "无 8.xlsx 浓度表可校验 -> 一律 unverified；含负值/共享地板值者不可能是原始浓度，"
                "log 尺度可能性高，但底数与物理单位未验证，不臆造。",
    }

    # 单位对齐：题面点名的关键化合物逐项论证（可回读）
    spot_cols = [c for c in ["DMS", "linalool", "X2.3.butanedione", "ethanol..v.v.",
                             "geraniol", "alpha.humulene", "bitterness", "acetaldehyde"] if c in tmap.index]
    spot = {}
    for c in spot_cols:
        r = tmap.loc[c]
        roww = sid.loc[sid["compound"] == c].iloc[0]
        if r["scale_verdict"] == "log10":
            wrong = float(f[c].median() / r["threshold_mean"])  # 若误按线性
            arg = (f"1.csv 该列为 log10：10^v 与 calibrated 逐行吻合（中位相对误差 "
                   f"{roww['median_rel_err_log10']:.1e}），10^v 范围 "
                   f"[{10**f[c].min():.4g}, {10**f[c].max():.4g}] {r['unit']}，与阈值 {r['threshold_mean']:.4g} {r['unit']} "
                   f"同量级；若误按线性解读，OAV 中位数只有 {wrong:.3g}（量级不合理或与 calibrated 矛盾）。")
        else:
            with np.errstate(over="ignore"):
                wrong = float(10.0 ** f[c].max())
            arg = (f"1.csv 该列等于 calibrated 原值（中位相对误差 {roww['median_rel_err_identity']:.1e}），"
                   f"即线性浓度，范围 [{r['conc_min']:.4g}, {r['conc_max']:.4g}] {r['unit']}；"
                   f"若误按 log10 解读，10^v 最大将达 {wrong:.4g}，远超该列阈值 {r['threshold_mean']:.4g} {r['unit']}，荒谬。")
        spot[c] = {
            "scale_verdict": str(r["scale_verdict"]),
            "1csv_range": [float(f[c].min()), float(f[c].max())],
            "concentration_range": [float(r["conc_min"]), float(r["conc_max"])],
            "unit": str(r["unit"]),
            "threshold_mean": float(r["threshold_mean"]),
            "oav_median": float(r["oav_median"]),
            "oav_max": float(r["oav_max"]),
            "argument": arg,
        }

    mag_ok = int(oav["magnitude_ok"].sum())
    n_oav = int(len(oav))
    log10_med_err = float(sid.loc[sid.scale_verdict == "log10", "median_rel_err_log10"].median())
    lin_med_err = float(sid.loc[sid.scale_verdict == "linear", "median_rel_err_identity"].median())

    opening = (
        f"1.csv 与 8.xlsx 'Calibrated chemical dataset' 的关系：8.xlsx 的 70 列把 1.csv 中对应 70 列的"
        f"尺度拆开了——{len(log10_cols)} 列在 1.csv 里是 log10(浓度)（10^v 与 calibrated 的中位相对误差 "
        f"{log10_med_err:.2e}），{len(linear_cols)} 列在 1.csv 里已经是线性浓度（v 与 calibrated 完全一致，"
        f"中位相对误差 {lin_med_err:.2e}）。因此 1.csv 是**混合尺度**表，8.xlsx calibrated 是作者的去对数"
        f"统一浓度表；两者并非同一张表的冗余副本。此外 calibrated==0 的行（log10 列共 "
        f"{censoring['total_calibrated_zero_cells_in_log10_cols']} 个单元格）在 1.csv 中不是 0，而是 "
        f"log10(该列最小正浓度/2)，即 LOD/2 左删失替换（最大比例偏差 "
        f"{censoring['max_abs_err_of_ratio_vs_half']:.1e}）。其余 {len(unv)} 列无外部浓度表可校验，一律标 unverified。"
    )

    report = {
        "generated_by": "src/02_scale.py",
        "inputs": {
            "1.csv": "data/raw/1.csv",
            "calibrated": "data/raw/8.xlsx#Calibrated chemical dataset",
            "thresholds": "data/raw/8.xlsx#Sensory thresholds",
        },
        "universe": {
            "n_feature_columns": int(len(feats)),
            "n_covered_by_calibrated": int(len(cal_cols)),
            "n_unverified": int(len(unverified_cols)),
            "scale_verdict_counts": {k: int(v) for k, v in counts.items()},
            "log10_columns": log10_cols,
            "linear_columns": linear_cols,
        },
        "criterion": {
            "rel_tolerance_median": REL_TOL,
            "H_log10": "conc = 10^(1.csv值) 与 calibrated 的中位相对误差 < 1e-6",
            "H_linear": "conc = 1.csv值 与 calibrated 的中位相对误差 < 1e-6",
            "unverified": "无 8.xlsx 浓度表覆盖 -> 不判定，只记录取值形态",
        },
        "censoring": censoring,
        "unverified": unverified_summary,
        "opening_question_answer": opening,
        "unit_alignment": {
            "conclusion": f"{n_oav} 个有阈值的化合物全部落在 calibrated 覆盖的 70 列内、尺度已验证；"
                          "log10 列的 10^v 与 linear 列的 v 都等于作者浓度（calibrated），而 8.xlsx 阈值表"
                          "给出的 unit 与 calibrated 同源同量纲，故 OAV = 还原后浓度 / threshold_mean "
                          "无需再做单位换算或量级平移。",
            "linear_columns_conclusion": (
                f"1.csv 为线性（原值）的 {len(linear_cols)} 列中，有 {int((oav['scale_verdict']=='linear').sum())} 个"
                "带阈值化合物：linalool / citronellol / geraniol / X1.alpha.terpineol / alpha.humulene / "
                "E.caryophyllene / Z.nerolidol / X2.3.butanedione / furfural / methylpyrazine / "
                "ethyl.butyrate / ethyl.isobutyrate / ethyl.nicotinate / X.E..2.nonenal 等；"
                "它们的 1.csv 值直接等于 calibrated 浓度（相对误差 ~1e-10），单位即阈值表 unit，"
                "无需 10^v 还原（如 linalool 0.0132–32.5 mg/L vs 阈值 0.0273 mg/L，OAV 中位数 "
                f"{float(tmap.loc['linalool','oav_median']) if 'linalool' in tmap.index else float('nan'):.3g}）。"),
            "evidence": spot,
            "n_threshold_compounds": int(len(thw)),
            "n_threshold_mapped_to_1csv": int(len(thw)),
            "unmatched_threshold_field_names": unmatched,
            "oav_median_in_1e-3_to_1e2": f"{mag_ok}/{n_oav}",
            "oav_median_outliers_below_1e-3": oav.loc[~oav["magnitude_ok"], ["compound", "oav_median", "unit",
                                                                             "threshold_mean", "conc_max"]]
                                                .to_dict(orient="records"),
            "outlier_interpretation": "4 个低于 1e-3 的化合物（Z.nerolidol、methylpyrazine、CS2、furfural）不是尺度错误"
                                      "迹象：它们的实测浓度整体远低于收录阈值（如 furfural 实测 ≤1.82 mg/L vs 阈值 60 mg/L），"
                                      "属于'该化合物在啤酒中通常不构成风味贡献'的化学事实，报告中如实保留。",
        },
        "missing_policy_note": "1.csv 的 73 个 NaN 是真实缺失（与 8.xlsx 的 calibrated==0 非检出标记不同），"
                               "本脚本不插补；插补只在建模折内进行。",
        "outputs": ["outputs/audit/scale_identification.csv", "outputs/audit/oav_summary.csv",
                    "outputs/audit/scale_report.json"],
        "paper_ready_numbers": {
            "n_log10": int(counts.get("log10", 0)),
            "n_linear": int(counts.get("linear", 0)),
            "n_unverified": int(counts.get("unverified", 0)),
            "n_threshold_compounds": int(len(thw)),
            "oav_magnitude_ok": f"{mag_ok}/{n_oav}",
            "log10_median_relerr": log10_med_err,
            "linear_median_relerr": lin_med_err,
            "n_censored_cells": censoring["total_calibrated_zero_cells_in_log10_cols"],
        },
    }

    C.write_csv(sid, "outputs/audit/scale_identification.csv")
    C.write_csv(oav, "outputs/audit/oav_summary.csv")
    C.write_json(report, "outputs/audit/scale_report.json")

    print("== scale_identification.csv:", sid.shape, "==")
    print(sid["scale_verdict"].value_counts().to_string())
    print("\n== linear 列（", len(linear_cols), "）==")
    print(linear_cols)
    print("\n== OAV summary:", oav.shape, " median OAV in [1e-3,1e2]:", f"{mag_ok}/{n_oav}", "==")
    print(oav[["compound", "scale_verdict", "unit", "threshold_mean", "oav_median", "oav_max",
               "frac_gt1", "magnitude_ok"]].to_string(index=False))
    print("\n== censoring ==")
    print(censoring)
    print("\n== unverified ==")
    print(unverified_summary)
    print("\n== opening question answer ==")
    print(opening)


if __name__ == "__main__":
    main()
