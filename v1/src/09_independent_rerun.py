#!/usr/bin/env python3
"""reviewer 独立复算脚本（09）——不 import 建模者的 src/common.py 或任何 q1/q2/q3 脚本。

用途：
  data      : 独立复算数据事实（Lead 给的数字逐条对比） -> outputs/review/data_facts_recheck.json
  ordinal   : z -> 0-6 分级标定的可证伪检查（S=1/0.75/1.25） -> outputs/review/ordinal_calibration.json
  baseline  : Q1 独立基线（分折中位数插补 + 共表达族聚合 + Ridge）-> outputs/review/independent_baseline.json
  all       : data + ordinal +（若 split 已登记）baseline

纪律：只读 data/raw、data/splits、state/ledger.json；只写 outputs/review/。
独立性：指标函数、标定、聚类、Ridge 全部在本文件内实现；特征/目标/划分只从原始文件或台账读取。
"""
from __future__ import annotations

import argparse
import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SPLITS = ROOT / "data" / "splits"
OUT = ROOT / "outputs" / "review"
OUT.mkdir(parents=True, exist_ok=True)

KEY_COLS = ["beer", "beer_id", "tasting_category_fine"]
GRADES = list(range(7))
S_VALUES = [1.0, 0.75, 1.25]


# ----------------------------------------------------------------------------- io helpers
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(obj, name: str) -> Path:
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def norm_name(value) -> str:
    """统一 8.xlsx 与 5/6.csv 的清洗名：_x000D_ 转义、CR/LF、多空格。"""
    text = str(value)
    text = text.replace("_x000D_", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def load_raw():
    return {
        "f1": pd.read_csv(RAW / "1.csv"),
        "f2": pd.read_csv(RAW / "2.csv", index_col=0),
        "f4": pd.read_csv(RAW / "4.csv"),
        "f5": pd.read_csv(RAW / "5.csv", index_col=0),
        "f6": pd.read_csv(RAW / "6.csv", index_col=0),
        "f7": pd.read_csv(RAW / "7.csv"),
    }


def read_xlsx(sheet: str) -> pd.DataFrame:
    return pd.read_excel(RAW / "8.xlsx", sheet_name=sheet)


# ----------------------------------------------------------------------------- metrics
def r2_cols(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    ss_res = ((y_true - y_pred) ** 2).sum(axis=0)
    ss_tot = ((y_true - y_true.mean(axis=0)) ** 2).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return 1.0 - ss_res / np.where(ss_tot > 0, ss_tot, np.nan)


def mae_cols(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(y_true, float) - np.asarray(y_pred, float)).mean(axis=0)


def spearman_cols(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    from scipy.stats import spearmanr
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    out = np.full(y_true.shape[1], np.nan)
    for j in range(y_true.shape[1]):
        out[j] = spearmanr(y_true[:, j], y_pred[:, j]).statistic
    return out


def qwk(truth, pred, levels: int = 7) -> float:
    """二次加权 kappa（独立实现，0..levels-1 级）。"""
    truth = np.asarray(truth, int).ravel()
    pred = np.asarray(pred, int).ravel()
    obs = np.zeros((levels, levels), float)
    for a, b in zip(truth, pred):
        obs[a, b] += 1.0
    hist_t = np.bincount(truth, minlength=levels).astype(float)
    hist_p = np.bincount(pred, minlength=levels).astype(float)
    expected = np.outer(hist_t, hist_p) / max(len(truth), 1)
    idx = np.arange(levels)
    weight = (idx[:, None] - idx[None, :]) ** 2 / (levels - 1) ** 2
    den = float((weight * expected).sum())
    return float(1.0 - float((weight * obs).sum()) / den) if den > 0 else float("nan")


# ----------------------------------------------------------------------------- data facts
def data_facts() -> dict:
    d = load_raw()
    f1, f2, f4, f5, f6, f7 = (d[k] for k in ["f1", "f2", "f4", "f5", "f6", "f7"])
    cal = read_xlsx("Calibrated chemical dataset")
    thresholds = read_xlsx("Sensory thresholds")
    sensory_names = read_xlsx("Sensory names")

    feats = [c for c in f1.columns if c not in KEY_COLS]
    targets = [c for c in f4.columns if c not in KEY_COLS]
    facts: dict = {}

    # --- shape / keys
    facts["shape"] = {
        "1.csv": list(f1.shape), "2.csv": list(f2.shape), "4.csv": list(f4.shape),
        "5.csv": list(f5.shape), "6.csv": list(f6.shape), "7.csv": list(f7.shape),
        "n_samples": int(len(f1)), "n_features": len(feats), "n_targets": len(targets),
    }

    # --- missing
    miss = f1.isna().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    facts["missing_1csv"] = {
        "total": int(miss.sum()), "n_columns": int(len(miss)), "n_rows": int(f1.isna().any(axis=1).sum()),
        "per_column": {k: int(v) for k, v in miss.items()},
    }

    # --- 2.csv == Spearman? 2.csv 行/列是化学全名，按位置对齐 1.csv 特征（已确认 offset=0）
    rng = np.random.default_rng(42)
    pairs = []
    while len(pairs) < 30:
        i, j = (int(x) for x in rng.integers(0, len(feats), 2))
        if i != j:
            pairs.append((i, j))
    corr_rows = []
    for i, j in pairs:
        a, b = feats[i], feats[j]
        m = f1[[a, b]].dropna()
        if len(m) < 10:
            continue
        pear = float(np.corrcoef(m[a], m[b])[0, 1])
        spear = float(pd.Series(m[a]).corr(pd.Series(m[b]), method="spearman"))
        file_value = float(f2.iloc[i, j])
        corr_rows.append({
            "i": i, "j": j, "col_i": a, "col_j": b, "n": int(len(m)),
            "file_2csv": file_value, "pearson_1csv": pear, "spearman_1csv": spear,
            "abs_diff_spearman": abs(file_value - spear), "abs_diff_pearson": abs(file_value - pear),
        })
    dfc = pd.DataFrame(corr_rows)
    facts["corr_2csv"] = {
        "method": "30 组随机特征对；2.csv 第 i 行/列按 1.csv 特征位置 i 对齐",
        "n_pairs": int(len(dfc)),
        "max_abs_diff_spearman": float(dfc.abs_diff_spearman.max()),
        "max_abs_diff_pearson": float(dfc.abs_diff_pearson.max()),
        "pairs_matching_spearman_5e-4": int((dfc.abs_diff_spearman <= 5e-4).sum()),
        "pairs_matching_pearson_5e-4": int((dfc.abs_diff_pearson <= 5e-4).sum()),
        "symmetric_max_abs": float(np.nanmax(np.abs(f2.values - f2.values.T))),
        "diag_values": sorted({float(x) for x in np.diag(f2.values)})[:3],
        "pairs": corr_rows,
    }

    # --- beer_id 脱敏 / 顺序一致
    facts["ids"] = {
        "beer_id_unique": {"1.csv": int(f1.beer_id.nunique()), "4.csv": int(f4.beer_id.nunique()), "7.csv": int(f7.beer_id.nunique())},
        "beer_order_identical": {
            "1_vs_4": bool((f1.beer.values == f4.beer.values).all()),
            "1_vs_7": bool((f1.beer.values == f7.beer.values).all()),
        },
        "beer_is_1_to_250": bool((f1.beer.values == np.arange(1, 251)).all()),
    }

    # --- 4.csv 连续性
    nu = f4[targets].nunique()
    facts["targets_continuity"] = {
        "distinct_per_column": {"min": int(nu.min()), "max": int(nu.max()), "median": float(nu.median())},
        "low_columns": {k: int(v) for k, v in nu.sort_values().head(15).items()},
        "columns_at_250": [c for c in nu.index if nu[c] == 250],
        "column_mean_range": [float(f4[targets].mean().min()), float(f4[targets].mean().max())],
        "column_std_range": [float(f4[targets].std().min()), float(f4[targets].std().max())],
        "any_integer_valued": bool(np.all(np.isclose(f4[targets].values, np.round(f4[targets].values)))),
        "note": "列均值≈0；列标准差 0.37~0.86（不是 1）",
    }

    # --- 1.csv 尺度：8.xlsx Calibrated 回算
    cal_cols = [c for c in cal.columns if c in feats]
    m = f1[["beer"] + cal_cols].merge(cal[["beer"] + cal_cols], on="beer", suffixes=("_v", "_cal"))
    scale_rows = []
    for c in cal_cols:
        v = m[c + "_v"].astype(float)
        cv = m[c + "_cal"].astype(float)
        ok = v.notna() & cv.notna() & (cv > 0)
        if int(ok.sum()) < 10:
            scale_rows.append({"column": c, "n": int(ok.sum()), "scale": "too-few"})
            continue
        log10_rel = np.abs(np.power(10.0, v[ok]) - cv[ok]) / cv[ok]
        lin_rel = np.abs(v[ok] - cv[ok]) / np.maximum(np.abs(cv[ok]), 1e-12)
        frac_log10 = float((log10_rel <= 0.02).mean())
        frac_lin = float((lin_rel <= 0.02).mean())
        scale = "log10" if frac_log10 >= 0.9 else ("linear" if frac_lin >= 0.9 else "ambiguous")
        scale_rows.append({
            "column": c, "n": int(ok.sum()), "scale": scale,
            "frac_log10_match": frac_log10, "frac_linear_match": frac_lin,
            "median_log10_rel_err": float(np.median(log10_rel)),
            "median_linear_rel_err": float(np.median(lin_rel)),
        })
    scale_df = pd.DataFrame(scale_rows)
    facts["scale_1csv"] = {
        "verifiable_columns": int(len(cal_cols)),
        "counts": {k: int(v) for k, v in scale_df["scale"].value_counts().items()},
        "linear_columns": scale_df.loc[scale_df.scale == "linear", "column"].tolist(),
        "unverifiable_feature_columns": int(len(feats) - len(cal_cols)),
        "rows": scale_rows,
    }

    # --- 阈值表映射 / 缺陷可计算性
    th = thresholds.dropna(subset=["threshold_mean"]).drop_duplicates("field_name_R")
    th["field"] = th["field_name_R"].astype(str).str.strip()
    mapped = [c for c in th["field"].tolist() if c in feats]
    scale_map = dict(zip(scale_df.column, scale_df.scale))
    mapped_rows = [{
        "column": c,
        "in_calibrated": c in scale_map,
        "scale": scale_map.get(c, "unverified"),
        "threshold_mean": float(th.set_index("field").loc[c, "threshold_mean"]),
        "unit": str(th.set_index("field").loc[c, "unit"]),
    } for c in mapped]
    defect_groups = {
        "DMS": ["DMS"],
        "Diacetyl": ["X2.3.butanedione"],
        "4VG": ["X4VG"],
        "trans-2-nonenal": ["X.E..2.nonenal"],
        "Stale hops": ["X.E..2.nonenal", "X3.methyl.2.butenal", "X5.methylfurfural", "furfural"],
    }
    defect_rows = {}
    for label, cols in defect_groups.items():
        rows = []
        for c in cols:
            in_thr = c in set(th["field"])
            rows.append({
                "compound": c,
                "in_1csv": c in feats,
                "has_threshold": bool(in_thr),
                "threshold_mean": float(th.set_index("field").loc[c, "threshold_mean"]) if in_thr else None,
                "unit": str(th.set_index("field").loc[c, "unit"]) if in_thr else None,
                "scale": scale_map.get(c, "unverified"),
            })
        defect_rows[label] = rows
    # 现行 OAV 口径（calibrated 浓度 / 阈值）的独立复算：只用 8.xlsx，不 import common.py
    th_idx = th.set_index("field")
    oav_frames = []
    for field in th_idx.index:
        if field not in cal.columns:
            continue
        thr = float(th_idx.loc[field, "threshold_mean"])
        if not np.isfinite(thr) or thr <= 0:
            continue
        conc = pd.to_numeric(cal[field], errors="coerce").astype(float)
        oav_frames.append(pd.DataFrame({"beer": cal["beer"].astype(int), "compound": field,
                                        "unit": str(th_idx.loc[field, "unit"]),
                                        "threshold_mean": thr, "conc": conc, "oav": conc / thr}))
    oav_long = pd.concat(oav_frames, ignore_index=True) if oav_frames else pd.DataFrame()
    mag = {}
    if len(oav_long):
        for comp in ["DMS", "X2.3.butanedione", "X4VG", "linalool", "ethyl_acetate", "furfural"]:
            sub = oav_long[oav_long.compound == comp]["oav"].dropna()
            if len(sub):
                mag[comp] = {"median": float(sub.median()), "max": float(sub.max()),
                             "unit": str(oav_long[oav_long.compound == comp]["unit"].iloc[0])}
    # 历史风险量化：若仍统一 10^v（旧版 common.py 的做法），线性列会错多少
    c = "X2.3.butanedione"
    v = f1[c].astype(float)
    cv = cal.set_index("beer").reindex(f1["beer"])[c].astype(float)
    ok = v.notna() & cv.notna() & (cv > 0)
    ratio = np.power(10.0, v[ok].values) / cv[ok].values
    facts["threshold_mapping"] = {
        "n_thresholds_with_mean": int(len(th)),
        "n_mapped_in_1csv": len(mapped),
        "mapped": mapped_rows,
        "defects": defect_rows,
        "oav_recheck": {
            "method": "conc 一律取 8.xlsx Calibrated chemical dataset，oav=conc/threshold_mean（按 field_name_R join）",
            "n_compounds_with_oav": int(oav_long.compound.nunique()) if len(oav_long) else 0,
            "magnitudes": mag,
            "units_are_threshold_units": True,
            "residual_risk": "Calibrated 表没有单位列；OAV 成立的前提是 cal 数值单位与 threshold 的 unit 一致。"
                             "该前提无法从数据内部验证，只能按作者标定表假设，必须在论文数据限制里写明。",
        },
        "historical_uniform_log10_error": {
            "column": c,
            "ratio_10v_over_true_median": float(np.median(ratio)),
            "ratio_p05": float(np.percentile(ratio, 5)),
            "ratio_p95": float(np.percentile(ratio, 95)),
            "note": "旧版 common.py 对所有阈值列统一 10^v；该列是线性浓度（已修，现行口径用 calibrated 浓度）",
        },
    }

    # --- 50 维目标 -> 5/6.csv 的 dim map（含 overall 的 CRLF/_x000D_ 归一化）
    sn = sensory_names.copy()
    sn["R"] = sn["R_name"].map(norm_name)
    sn["C"] = sn["CleanName_PanelFeedback"].map(norm_name)
    name_map = dict(zip(sn["R"], sn["C"]))
    c5 = [norm_name(c) for c in f5.columns]
    c6 = [norm_name(c) for c in f6.columns]
    dim_rows = []
    for t in targets:
        clean = name_map.get(t)
        dim_rows.append({
            "target": t, "sensory_clean_name": clean,
            "in_5csv": bool(clean in c5), "in_6csv": bool(clean in c6),
        })
    facts["dim_map"] = {
        "n_targets": len(targets),
        "n_matched_sensory_names": int(sum(1 for r in dim_rows if r["sensory_clean_name"])),
        "n_in_5csv": int(sum(1 for r in dim_rows if r["in_5csv"])),
        "n_in_6csv": int(sum(1 for r in dim_rows if r["in_6csv"])),
        "crlf_normalization_required": True,
        "overall_raw": [str(x) for x in sn.loc[sn.R == "overall", "CleanName_PanelFeedback"].tolist()],
        "5csv_6csv_columns_identical": bool(c5 == c6),
        "rows": dim_rows,
    }

    # --- Lead 数字逐条对比
    comparisons = [
        {"claim": "250 个样本", "lead": "250", "observed": f"{len(f1)} 行", "status": "match" if len(f1) == 250 else "mismatch"},
        {"claim": "231 个化合物", "lead": "231", "observed": f"{len(feats)} 列", "status": "match" if len(feats) == 231 else "mismatch"},
        {"claim": "50 个目标", "lead": "50", "observed": f"{len(targets)} 列", "status": "match" if len(targets) == 50 else "mismatch"},
        {"claim": "缺失 73 个/9 列/63 行", "lead": "73/9/63",
         "observed": f"{int(miss.sum())}/{len(miss)}/{int(f1.isna().any(axis=1).sum())}",
         "status": "match" if (int(miss.sum()) == 73 and len(miss) == 9 and int(f1.isna().any(axis=1).sum()) == 63) else "mismatch"},
        {"claim": "2.csv 是 Spearman", "lead": "Spearman",
         "observed": f"30 对里 {int((dfc.abs_diff_spearman <= 5e-4).sum())}/30 与 Spearman 一致；Pearson {int((dfc.abs_diff_pearson <= 5e-4).sum())}/30",
         "status": "match" if (dfc.abs_diff_spearman <= 5e-4).all() and not (dfc.abs_diff_pearson <= 5e-4).all() else "mismatch"},
        {"claim": "4/7.csv beer_id 脱敏（唯一值 96）", "lead": "96",
         "observed": f"4.csv={f4.beer_id.nunique()}, 7.csv={f7.beer_id.nunique()}",
         "status": "match" if (f4.beer_id.nunique() == 96 and f7.beer_id.nunique() == 96) else "mismatch"},
        {"claim": "三表 beer 顺序一致", "lead": "一致", "observed": f"1=4:{bool((f1.beer.values == f4.beer.values).all())}, 1=7:{bool((f1.beer.values == f7.beer.values).all())}",
         "status": "match" if (f1.beer.values == f4.beer.values).all() and (f1.beer.values == f7.beer.values).all() else "mismatch"},
        {"claim": "4.csv 每列不同取值数 172–249", "lead": "172–249",
         "observed": f"{int(nu.min())}–{int(nu.max())}（coriander/acetic={int(nu['coriander'])}/~106；5 列<200；{int((nu == 250).sum())} 列=250）",
         "status": "mismatch", "severity": "major",
         "impact": "仍可判为连续值，但 Lead/statement 的区间陈述不成立；若写进论文属于可核查错误"},
        {"claim": "1.csv 37 列 log10、其余线性", "lead": "37 log10 + 其余线性",
         "observed": f"可回算 70 列：log10={int((scale_df.scale == 'log10').sum())}, linear={int((scale_df.scale == 'linear').sum())}, ambiguous={int((scale_df.scale == 'ambiguous').sum())}; 另有 {len(feats) - len(cal_cols)} 列无校准参照",
         "status": "partial", "severity": "minor",
         "impact": "'其余线性'只对 70 个可回算列成立；161 个化合物列尺度未验证，不能写成已核实"},
        {"claim": "50 维经 R_name->CleanName 对齐 5/6.csv 50/50", "lead": "50/50",
         "observed": f"5.csv={sum(1 for r in dim_rows if r['in_5csv'])}/50, 6.csv={sum(1 for r in dim_rows if r['in_6csv'])}/50（需 _x000D_/CRLF 归一化）",
         "status": "match" if all(r["in_5csv"] and r["in_6csv"] for r in dim_rows) else "mismatch"},
    ]
    facts["lead_claims_comparison"] = comparisons

    # --- 划分与 LOD（Lead 第 1/4 条要求独立核）
    facts["split_checks"] = split_checks()
    facts["lod_censoring"] = lod_check()
    comparisons.extend([
        {"claim": "主分割 SPLIT-0001 未分层、test 缺 West Flanders ale（Lead 自述偏差）",
         "lead": "known deviation", "observed": json.dumps(facts["split_checks"].get("SPLIT-0001"), ensure_ascii=False),
         "status": "match" if facts["split_checks"].get("SPLIT-0001", {}).get("west_flanders_in_test") == 0 else "mismatch",
         "severity": "major", "impact": "holdout 数字不能外推到 West Flanders ale（7 样本全在训练侧）"},
        {"claim": "分层版覆盖 22/22 风格进 test",
         "lead": "22/22", "observed": f"{facts['split_checks'].get('stratified', {}).get('test_styles')}/22",
         "status": "match" if facts["split_checks"].get("stratified", {}).get("test_styles") == 22 else "mismatch"},
        {"claim": "calibrated==0 ↔ log10(最小正浓度/2)，共 755 格",
         "lead": "755", "observed": f"{facts['lod_censoring']['observed_lod2_cells']} 格；all_match={facts['lod_censoring']['all_match']}",
         "status": "match" if facts["lod_censoring"]["observed_lod2_cells"] == 755 and facts["lod_censoring"]["all_match"] else "mismatch",
         "severity": "minor", "impact": "LOD/2 删失替代码不是实测浓度，低浓度端不得做物理浓度解释"},
    ])
    facts["provenance"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            name: {"path": f"data/raw/{name}", "sha256": sha256_file(RAW / name)}
            for name in ["1.csv", "2.csv", "3.xlsx", "4.csv", "5.csv", "6.csv", "7.csv", "8.xlsx"]
            if (RAW / name).exists()
        },
    }
    return facts


# ----------------------------------------------------------------------------- ordinal / calibration
def ordinal_calibration() -> dict:
    f4 = pd.read_csv(RAW / "4.csv")
    targets = [c for c in f4.columns if c not in KEY_COLS]
    z = f4[targets].to_numpy(float)

    def grade(z_mat: np.ndarray, S: float) -> np.ndarray:
        return np.clip(np.floor(z_mat / S + 3.5), 0, 6).astype(int)

    results = {}
    base = None
    for S in S_VALUES:
        g = grade(z, S)
        counts = {int(k): int((g == k).sum()) for k in GRADES}
        n = g.size
        per_col_clip0 = float((g == 0).sum(axis=0).mean() / z.shape[0])
        per_col_clip6 = float((g == 6).sum(axis=0).mean() / z.shape[0])
        # "分级序 == z 序": 对每列，按 z 排序后 g 必须非降（clip+floor 恒真，用于证明该检查是重言式）
        order_violations = 0
        for j in range(z.shape[1]):
            order = np.argsort(z[:, j], kind="stable")
            if np.any(np.diff(g[order, j]) < 0):
                order_violations += 1
        # 与 z 的秩相关（含 ties）
        rho = [float(pd.Series(g[:, j]).corr(pd.Series(z[:, j]), method="spearman")) for j in range(z.shape[1])]
        entry = {
            "S": S,
            "grade_counts": counts,
            "grade_share": {k: round(v / n, 4) for k, v in counts.items()},
            "mean_grade": float(g.mean()),
            "frac_at_grade0": float((g == 0).mean()),
            "frac_at_grade6": float((g == 6).mean()),
            "per_column_mean_clip0_share": per_col_clip0,
            "per_column_mean_clip6_share": per_col_clip6,
            "columns_with_any_order_violation": order_violations,
            "mean_spearman_grade_vs_z": float(np.nanmean(rho)),
            "observed_sd_per_column": float(np.nanmean(z.std(axis=0))),
            "S_over_observed_sd": float(S / np.nanmean(z.std(axis=0))),
        }
        if S == 1.0:
            base = g
        else:
            entry["qwk_vs_S1"] = qwk(base, g)
            entry["agreement_with_S1"] = float((base == g).mean())
        results[f"S={S}"] = entry

    # 位置不可辨识：z 只有中心化后的形状；若原量表 mean != 3，grade 3 的锚点会整体平移
    results["identifiability"] = {
        "premise_in_common_py": "z 为 4.csv 的标准化值（均值 0、标准差 1）",
        "observed": {
            "column_mean_range": [float(f4[targets].mean().min()), float(f4[targets].mean().max())],
            "column_std_range": [float(f4[targets].std().min()), float(f4[targets].std().max())],
            "mean_column_sd": float(np.nanmean(z.std(axis=0))),
        },
        "verdict": "4.csv 列均值≈0 但列标准差≈0.57（不是 1）；S=1.0 相当于每个等级 1.75 个观测标准差。"
                   "4.csv 不含各维原始均值，故'grade 3 锚定 z=0'是假设而非可由数据验证的事实；"
                   "若某维原始均值≠3，整列分级会整体平移。",
        "falsifiable_checks": [
            "三档 S 下报告分级分布与跨 S 的 QWK；QWK 高说明分级对标定不敏感，低说明结论依赖假设",
            "报告每列 clip 到 0/6 的比例（信息损失）；比例高说明标定把分布压到端点",
            "报告 per-column sd 与 S 的比值；比值远离 1 说明 'S=1 个标准差' 的陈述不成立",
        ],
    }
    results["vacuous_check_note"] = (
        "g=clip(floor(z/S+3.5),0,6) 是 z 的单调非降函数，所以 '分级序与 z 序完全一致' 在任何 S 下恒成立"
        f"（实测违反列数：{results['S=1.0']['columns_with_any_order_violation']}）。该检查不能作为通过证据；"
        "有信息量的检查是 clip 比例、跨 S 的 QWK、以及分级分布是否退化。")
    return results


# ----------------------------------------------------------------------------- independent Q1 baseline
def _read_split_from_ledger():
    ledger_path = ROOT / "state" / "ledger.json"
    if not ledger_path.exists():
        return None
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    splits = ledger.get("splits") or []
    if not splits:
        return None
    split = sorted(splits, key=lambda s: str(s.get("createdAt") or ""))[-1]
    return split


def _baseline_one(assign_path, train_path, test_path) -> dict:
    from sklearn.cluster import SpectralClustering
    from sklearn.linear_model import RidgeCV

    f1 = pd.read_csv(RAW / "1.csv")
    f4 = pd.read_csv(RAW / "4.csv")
    feats = [c for c in f1.columns if c not in KEY_COLS]
    targets = [c for c in f4.columns if c not in KEY_COLS]
    assign = pd.read_csv(assign_path)
    if "row_index" in assign.columns:
        assign["beer"] = f1["beer"].values[assign["row_index"].astype(int)]
    assign["split"] = assign["split"].astype(str).str.strip().str.lower()
    test_rows = assign.loc[assign.split == "test", "row_index"].to_numpy() if "row_index" in assign.columns else None
    train_rows = assign.loc[assign.split == "train", "row_index"].to_numpy() if "row_index" in assign.columns else None

    tr = pd.read_csv(train_path) if train_path and Path(train_path).exists() else None
    te = pd.read_csv(test_path) if test_path and Path(test_path).exists() else None
    have_targets = bool(tr is not None and te is not None and all(t in tr.columns for t in targets))
    if have_targets:
        Xtr, Xte = tr[feats].astype(float), te[feats].astype(float)
        Ytr, Yte = tr[targets].astype(float), te[targets].astype(float)
        test_ids = te["beer"].to_numpy() if "beer" in te.columns else np.arange(len(te))
    else:
        Xall = f1[feats].astype(float)
        Yall = f4.set_index("beer").reindex(f1["beer"])[targets].astype(float)
        Xtr, Xte = Xall.iloc[train_rows], Xall.iloc[test_rows]
        Ytr, Yte = Yall.iloc[train_rows], Yall.iloc[test_rows]
        test_ids = f1["beer"].to_numpy()[test_rows]

    med = Xtr.median(axis=0)
    Xtr = Xtr.fillna(med).fillna(0.0)
    Xte = Xte.fillna(med).fillna(0.0)
    Ztr = ((Xtr - Xtr.mean()) / Xtr.std(ddof=0).replace(0, np.nan)).fillna(0.0)
    corr = np.nan_to_num(np.corrcoef(Ztr.to_numpy().T), nan=0.0)
    dist = 1.0 - np.abs(corr)
    np.fill_diagonal(dist, 0.0)
    n_families = min(20, max(5, len(feats) // 15))
    try:
        labels = SpectralClustering(n_clusters=n_families, affinity="precomputed",
                                    random_state=42, assign_labels="kmeans").fit_predict(dist)
    except Exception:
        labels = np.zeros(len(feats), int)
    Ftr = pd.DataFrame({f"fam_{k:02d}": Ztr[[feats[i] for i in range(len(feats)) if labels[i] == k]].mean(axis=1)
                        for k in range(n_families) if any(labels[i] == k for i in range(len(feats)))})
    Zte = ((Xte - Xtr.mean()) / Xtr.std(ddof=0).replace(0, np.nan)).fillna(0.0)
    Fte = pd.DataFrame({f"fam_{k:02d}": Zte[[feats[i] for i in range(len(feats)) if labels[i] == k]].mean(axis=1)
                        for k in range(n_families) if any(labels[i] == k for i in range(len(feats)))})
    model = RidgeCV(alphas=np.logspace(-3, 3, 13), fit_intercept=True)
    model.fit(Ftr.to_numpy(), Ytr.to_numpy())
    pred = np.clip(model.predict(Fte.to_numpy()), -10, 10)
    r2 = r2_cols(Yte.to_numpy(), pred)
    r2_base = r2_cols(Yte.to_numpy(), np.tile(np.nanmean(Ytr.to_numpy(), axis=0), (len(Yte), 1)))
    return {
        "n_train": int(len(Ytr)), "n_test": int(len(Yte)),
        "testBeerHead": [int(x) for x in test_ids[:5]],
        "r2_mean": float(np.nanmean(r2)), "r2_median": float(np.nanmedian(r2)),
        "mae_mean": float(np.nanmean(mae_cols(Yte.to_numpy(), pred))),
        "spearman_mean": float(np.nanmean(spearman_cols(Yte.to_numpy(), pred))),
        "r2_mean_baseline_mean_predictor": float(np.nanmean(r2_base)),
        "per_dim_r2": {d: float(v) for d, v in zip(targets, r2)},
    }


def independent_baseline() -> dict:
    """分折中位数插补 + 共表达族聚合 + Ridge（train-only 拟合）；SPLIT-0002 与 stratified 各算一遍。"""
    f1 = pd.read_csv(RAW / "1.csv")
    targets = [c for c in pd.read_csv(RAW / "4.csv", nrows=1).columns if c not in KEY_COLS]
    out = {"design": {
        "imputation": "train-fold median per feature",
        "aggregation": "train-only Spearman 1-|rho| 距离 + SpectralClustering 族均值",
        "model": "RidgeCV(alpha in logspace(-3,3,13))，50 维多输出，train-only",
        "clip": [-10, 10],
    }, "note": "reviewer 独立实现，只用于判断建模者 R² 是否离谱；不追求超越建模者。"}
    for tag, base in [("SPLIT-0002", "data/splits/SPLIT-0002"),
                      ("stratified", "data/splits/stratified")]:
        a = ROOT / base / "assignment.csv"
        tr = ROOT / base / "train.csv"
        te = ROOT / base / "test.csv"
        if a.exists() and tr.exists() and te.exists():
            try:
                out[tag] = _baseline_one(a, tr, te)
            except Exception as exc:
                out[tag] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        else:
            out[tag] = {"status": "missing"}
    main = out.get("SPLIT-0002") or {}
    if isinstance(main, dict) and "r2_mean" in main:
        out["metrics"] = {k: main[k] for k in ["r2_mean", "r2_median", "mae_mean", "spearman_mean",
                                               "r2_mean_baseline_mean_predictor"] if k in main}
        out["split"] = {"id": "SPLIT-0002", "trainRows": main["n_train"], "testRows": main["n_test"],
                        "testBeerHead": main.get("testBeerHead")}
    return out


# ----------------------------------------------------------------------------- Q3 checks
def _scale_map():
    """1.csv 各列的尺度（log10 / linear），只用 8.xlsx Calibrated 回算。"""
    f1 = pd.read_csv(RAW / "1.csv")
    cal = read_xlsx("Calibrated chemical dataset")
    keys = ["beer", "beer_id", "tasting_category_fine"]
    cols = [c for c in cal.columns if c in f1.columns and c not in keys]
    m = f1[["beer"] + cols].merge(cal[["beer"] + cols], on="beer", suffixes=("_v", "_cal"))
    out = {}
    for c in cols:
        v = m[c + "_v"].astype(float)
        cv = m[c + "_cal"].astype(float)
        ok = v.notna() & cv.notna() & (cv > 0)
        if int(ok.sum()) < 10:
            continue
        lh = float(((np.abs(np.power(10.0, v[ok]) - cv[ok]) / cv[ok]) <= 0.02).mean())
        nh = float(((np.abs(v[ok] - cv[ok]) / np.maximum(np.abs(cv[ok]), 1e-12)) <= 0.02).mean())
        out[c] = "log10" if lh >= 0.9 else ("linear" if nh >= 0.9 else "ambiguous")
    return out


def _to_conc(values, cols, scale):
    """1.csv 尺度 -> 物理浓度（log10 列 10^v，linear 列原值）。"""
    arr = np.asarray(values, float).copy()
    for j, c in enumerate(cols):
        if scale.get(c) == "log10":
            arr[:, j] = np.power(10.0, arr[:, j])
    return arr


def q3_checks() -> dict:
    import json as _json
    from sklearn.linear_model import LogisticRegression

    f1 = pd.read_csv(RAW / "1.csv")
    f4 = pd.read_csv(RAW / "4.csv")
    feats = [c for c in f1.columns if c not in KEY_COLS]
    targets = [c for c in f4.columns if c not in KEY_COLS]
    style = f1.set_index("beer")["tasting_category_fine"]

    gen_path = ROOT / "outputs/q3/generated_spectra.csv"
    metrics_path = ROOT / "outputs/q3/metrics.json"
    transfer_path = ROOT / "outputs/q3/transfer_pils_to_tripel.csv"
    if not gen_path.exists():
        return {"status": "missing", "reason": "outputs/q3/generated_spectra.csv 不存在"}
    gen = pd.read_csv(gen_path)
    reported = _json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}

    missing_cols = [c for c in feats if c not in gen.columns]
    out = {"status": "ok", "n_generated_rows": int(len(gen)), "missing_feature_columns": missing_cols,
           "seeds": sorted(set(int(x) for x in gen["seed"].unique())) if "seed" in gen.columns else None}

    # 训练支撑（SPLIT-0002 train）
    a = pd.read_csv(ROOT / "data/splits/SPLIT-0002/assignment.csv")
    a["beer"] = f1["beer"].values[a["row_index"].astype(int)]
    tr_beers = set(int(x) for x in a.loc[a.split == "train", "beer"])
    tr = f1[f1.beer.isin(tr_beers)].set_index("beer")

    # (1) 支撑与非负
    sub = gen[[c for c in feats if c in gen.columns]].astype(float)
    lo, hi = tr[sub.columns].min(), tr[sub.columns].max()
    below = int((sub < lo - 1e-9).sum().sum())
    above = int((sub > hi + 1e-9).sum().sum())
    n_cells = int(sub.shape[0] * sub.shape[1])
    scale = _scale_map()
    lin_cols = [c for c in sub.columns if scale.get(c) == "linear"]
    neg_lin = int((sub[lin_cols] < -1e-12).sum().sum()) if lin_cols else 0
    out["support_and_nonnegativity"] = {
        "cells": n_cells, "below_train_min": below, "above_train_max": above,
        "linear_negative_cells": neg_lin,
        "reported": (reported.get("support_and_nonnegativity") or {}),
        "pass": bool(below == 0 and above == 0 and neg_lin == 0),
    }

    # (2) 小样本：风格计数
    counts = style.value_counts()
    small = {s: int(counts.get(s, 0)) for s in ["Kriek", "Lambic", "Faro"]}
    sn = reported.get("small_n_uncertainty") or {}
    out["small_n"] = {
        "real_counts_in_1csv": small,
        "code_reported_styles": list((sn.get("styles") or {}).keys()),
        "has_ci": all(isinstance((sn.get("styles") or {}).get(s), dict) and "real" in (sn.get("styles") or {}).get(s, {})
                      for s in ["Kriek", "Lambic"]),
        "reported_description": sn.get("description"),
    }

    # (3) 缺陷 OAV 复核（seed=42，绝对阈值化合物 DMS / diacetyl / 4VG）
    thr = {"DMS": 17.25, "X2.3.butanedione": 0.29925, "X4VG": 0.206333333}
    gen42 = gen[gen["seed"] == 42] if "seed" in gen.columns else gen
    # LOD/2 删失码还原：log10 列 v <= log10(最小正浓度/2) -> 浓度 0（与 data/clean 口径一致）
    cal = read_xlsx("Calibrated chemical dataset")
    lod = {}
    for c in ["DMS", "X4VG"]:
        cv = cal.set_index("beer").reindex(f1["beer"])[c].astype(float)
        pos = cv[cv > 0]
        lod[c] = float(np.log10(pos.min() / 2.0)) if len(pos) else None
    sub_cols = [c for c in ["DMS", "X2.3.butanedione", "X4VG"] if c in gen42.columns]
    conc = _to_conc(gen42[sub_cols].values, sub_cols, scale)
    for j, c in enumerate(sub_cols):
        if c in lod and lod[c] is not None:
            conc[:, j] = np.where(gen42[c].astype(float).values <= lod[c], 0.0, conc[:, j])
    oav = conc / np.array([thr[c] for c in sub_cols])
    defect = {"all_styles": {}, "per_style": {}}
    for j, c in enumerate(sub_cols):
        defect["all_styles"][c] = {"oav_median": float(np.median(oav[:, j])),
                                   "exceed_rate": float((oav[:, j] > 1).mean())}
    for sty in sorted(gen42["style"].astype(str).unique()):
        mask = gen42["style"].astype(str).values == sty
        defect["per_style"][sty] = {c: {"oav_median": float(np.median(oav[mask, j])),
                                        "exceed_rate": float((oav[mask, j] > 1).mean())}
                                    for j, c in enumerate(sub_cols)}
    rep_def = ((reported.get("defect_check_generation") or {}).get("generated_seed42") or {})
    out["defect_generation"] = {"mine": defect, "reported_per_style": rep_def,
                                "note": "t2n / stale hops 无阈值，不能算绝对 OAV（见 method_findings §2）"}

    # (4) 风格保真度：独立分类器（train 200 训练，生成样本打分）
    Xtr = tr[feats].astype(float)
    med = Xtr.median(axis=0)
    Xtr = Xtr.fillna(med).fillna(0.0)
    mu, sd = Xtr.mean(), Xtr.std(ddof=0).replace(0, np.nan)
    Ztr = ((Xtr - mu) / sd).fillna(0.0)
    ytr = tr["tasting_category_fine"].astype(str).values
    clf = LogisticRegression(max_iter=3000, C=1.0)
    clf.fit(Ztr.to_numpy(), ytr)
    G = gen42[[c for c in feats if c in gen42.columns]].astype(float).fillna(med).fillna(0.0)
    Zg = ((G - mu) / sd).fillna(0.0)
    pred = clf.predict(Zg.to_numpy())
    hits = (pred == gen42["style"].astype(str).values)
    fid = {"classifier": "reviewer LogisticRegression(C=1) train=SPLIT-0002 train", "n": int(len(gen42)),
           "aggregate_hit_rate": float(hits.mean()),
           "per_style": {s: float(hits[gen42["style"].astype(str).values == s].mean())
                         for s in sorted(gen42["style"].astype(str).unique())}}
    out["style_fidelity"] = {"mine": fid,
                             "reported_aggregate": (reported.get("style_fidelity") or {}).get("aggregate_generated_hit_rate")}

    # (5) 能量距离（训练 z 空间；生成集 vs 同风格 holdout 真值）
    ho_beers = set(int(x) for x in a.loc[a.split == "test", "beer"])
    ref = f1[f1.beer.isin(ho_beers)].set_index("beer")
    R = ((ref[feats].astype(float).fillna(med).fillna(0.0) - mu) / sd).fillna(0.0).to_numpy()
    ref_styles = ref["tasting_category_fine"].astype(str).values

    def energy_distance(xa, xb):
        if len(xa) == 0 or len(xb) == 0:
            return None
        from scipy.spatial.distance import cdist
        d_ab = cdist(xa, xb).mean()
        d_aa = cdist(xa, xa).mean() if len(xa) > 1 else 0.0
        d_bb = cdist(xb, xb).mean() if len(xb) > 1 else 0.0
        val = 2.0 * d_ab - d_aa - d_bb
        return float(np.sqrt(max(val, 0.0)))

    ed = {}
    for s in ["Tripel", "Kriek", "Lambic"]:
        gm = Zg.to_numpy()[gen42["style"].astype(str).values == s]
        rm = R[ref_styles == s]
        ed[s] = {"n_gen": int(len(gm)), "n_ref": int(len(rm)), "ed": energy_distance(gm, rm)}
    rep_ed = ((reported.get("distribution_match") or {}).get("seed42_holdout") or {})
    out["energy_distance"] = {"mine": ed, "reported": {s: rep_ed.get(s) for s in ["Tripel", "Kriek", "Lambic"]},
                              "space": "训练集 z 空间（231 维，train 均值/标准差）"}

    # (6) 迁移：逐样本缺陷不增 + 支撑 + 独立分类器命中
    if transfer_path.exists():
        t = pd.read_csv(transfer_path)
        scale2 = scale
        lin_all = [c for c in feats if scale2.get(c) == "linear"]
        before_cols = [f"before_{c}" for c in feats if f"before_{c}" in t.columns]
        after_cols = [f"after_{c}" for c in feats if f"after_{c}" in t.columns]
        common = [c[7:] for c in before_cols if "after_" + c[7:] in t.columns]
        B = t[["before_" + c for c in common]].astype(float).to_numpy()
        A = t[["after_" + c for c in common]].astype(float).to_numpy()
        Bc = _to_conc(B, common, scale2)
        Ac = _to_conc(A, common, scale2)
        defect_cols = [c for c in ["DMS", "X2.3.butanedione", "X4VG", "X.E..2.nonenal",
                                   "X3.methyl.2.butenal", "X5.methylfurfural", "furfural"] if c in common]
        defect_check = {}
        tol = 1e-9
        for c in defect_cols:
            j = common.index(c)
            diff = Ac[:, j] - Bc[:, j]
            ratio = (Ac[:, j] + 1e-12) / (Bc[:, j] + 1e-12)
            defect_check[c] = {
                "max_conc_increase_abs": float(np.max(diff)),
                "max_conc_increase_ratio": float(np.max(ratio)),
                "n_abs_increase_gt_1e-6": int((diff > 1e-6).sum()),
                "n_relative_increase_gt_1e-9": int((ratio > 1 + tol).sum()),
                "is_absolute_threshold": c in ["DMS", "X2.3.butanedione", "X4VG"],
            }
        # 支撑：after 值必须在训练 [min,max]
        lo2, hi2 = tr[common].min(), tr[common].max()
        sup = {"below": int((A < lo2.values - 1e-9).sum()), "above": int((A > hi2.values + 1e-9).sum())}
        # 独立分类器：before/after 的 Tripel 命中
        Zb = ((pd.DataFrame(B, columns=common).reindex(columns=feats).astype(float).fillna(med).fillna(0.0) - mu) / sd).fillna(0.0)
        Za = ((pd.DataFrame(A, columns=common).reindex(columns=feats).astype(float).fillna(med).fillna(0.0) - mu) / sd).fillna(0.0)
        hit_b = (clf.predict(Zb.to_numpy()) == "Tripel").mean()
        hit_a = (clf.predict(Za.to_numpy()) == "Tripel").mean()
        # 到 Tripel 质心距离
        tripel_idx = (f1["tasting_category_fine"].astype(str).values == "Tripel") & f1["beer"].isin(tr_beers).values
        cen = ((tr["tasting_category_fine"].astype(str) == "Tripel").values)
        if cen.sum() > 0:
            ctr = Ztr.to_numpy()[cen]
            ctr = ctr.mean(axis=0)
            db = np.linalg.norm(Zb.to_numpy() - ctr, axis=1).mean()
            da = np.linalg.norm(Za.to_numpy() - ctr, axis=1).mean()
        else:
            db = da = None
        out["transfer"] = {
            "status": "present", "n_samples": int(len(t)),
            "solver_success": int(t["solver_success"].sum()) if "solver_success" in t.columns else None,
            "defect_conc_check": defect_check,
            "any_abs_increase_gt_1e-6": bool(any(v["n_abs_increase_gt_1e-6"] > 0 for v in defect_check.values())),
            "any_relative_increase_gt_1e-9": bool(any(v["n_relative_increase_gt_1e-9"] > 0 for v in defect_check.values())),
            "tolerance_note": "绝对差 1e-6 为 SLSQP 数值容差；相对 1e-9 是过严噪声门槛，两者都报",
            "support_violations": sup,
            "classifier_hit_as_tripel": {"before": float(hit_b), "after": float(hit_a)},
            "dist_to_tripel_centroid_z": {"before": None if db is None else float(db), "after": None if da is None else float(da)},
            "reported": _json.loads((ROOT / "outputs/q3/transfer_report.json").read_text(encoding="utf-8"))
            if (ROOT / "outputs/q3/transfer_report.json").exists() else None,
        }
    else:
        out["transfer"] = {"status": "pending", "reason": "outputs/q3/transfer_pils_to_tripel.csv 不存在；"
                                                          "Q3 迁移（Pils/Lager→Tripel）尚未实现，题面要求未完成"}
    out["reported_seed_stability"] = reported.get("seed_stability")
    return out


# ----------------------------------------------------------------------------- Q2 checks
def q2_checks() -> dict:
    """Q2：multiplicity（BH-FDR）、prior-consistency（6.csv 独立先验）、Top-3 稳定性。
    读 outputs/q2/ 下由 Q2 modeler 产出的 top3 / frequency / jaccard 文件（格式容错）。"""
    import json as _json
    from scipy.stats import spearmanr, mannwhitneyu

    q2 = ROOT / "outputs/q2"
    files = {name: q2 / name for name in [
        "top3_per_dimension.csv", "selection_frequency.csv", "method_jaccard.csv"]}
    out = {"status": "partial" if not all(v.exists() for v in files.values()) else "ok",
           "files": {k: v.exists() for k, v in files.items()},
           "missing_reason": "top3/selection_frequency/method_jaccard 尚未全部产出；multiplicity 与静态泄漏扫描已可独立计算"}

    f1 = pd.read_csv(RAW / "1.csv")
    f4 = pd.read_csv(RAW / "4.csv")
    feats = [c for c in f1.columns if c not in KEY_COLS]
    targets = [c for c in f4.columns if c not in KEY_COLS]
    X = f1[feats].astype(float)
    Y = f4.set_index("beer").reindex(f1["beer"])[targets].astype(float)

    # --- multiplicity：50x231 的 pairwise-complete Spearman 检验 + BH-FDR
    pvals = []
    for j, dim in enumerate(targets):
        y = Y[dim].to_numpy(float)
        for k, c in enumerate(feats):
            x = X[c].to_numpy(float)
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 10 or np.std(x[m]) == 0 or np.std(y[m]) == 0:
                pvals.append((dim, c, 1.0, 0.0))
                continue
            st = spearmanr(x[m], y[m])
            pvals.append((dim, c, float(st.pvalue) if np.isfinite(st.pvalue) else 1.0, float(st.statistic)))
    pv = pd.DataFrame(pvals, columns=["dim", "compound", "p", "rho"])
    order = np.argsort(pv["p"].to_numpy())
    ranked = pv["p"].to_numpy()[order]
    n = len(ranked)
    q = np.empty(n)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        val = ranked[i] * n / (i + 1)
        prev = min(prev, val)
        q[i] = prev
    qv = np.empty(n)
    qv[order] = q
    pv["q_bh"] = qv
    sig = pv[pv["q_bh"] < 0.05]
    out["multiplicity"] = {
        "n_tests": int(n), "n_significant_bh_q05": int(len(sig)),
        "n_dims_with_any_significant": int(sig["dim"].nunique()) if len(sig) else 0,
        "expected_under_null": 0.05 * n,
        "note": "50 维 x 231 化合物的 pairwise-complete Spearman；BH 在全部 50*231 个检验上做",
    }
    pv.to_csv(OUT / "multiplicity_reference.csv", index=False)
    # 与 modeler 的 univariate_fdr.csv 对照（若已落盘）：显著集合 Jaccard + p 值秩相关
    fdr_path = q2 / "univariate_fdr.csv"
    if fdr_path.exists():
        mf = pd.read_csv(fdr_path)
        cols = {c.lower(): c for c in mf.columns}
        dcol = next((cols[k] for k in cols if k in ("dim", "dimension", "target")), None)
        ccol = next((cols[k] for k in cols if k in ("compound", "feature", "chem", "column")), None)
        qcol = next((cols[k] for k in cols if k in ("q_bh", "q", "fdr", "qvalue")), None)
        pcol = next((cols[k] for k in cols if k in ("p", "p_value", "pvalue")), None)
        if dcol and ccol:
            mm = pd.DataFrame({"dim": mf[dcol].astype(str), "compound": mf[ccol].astype(str)})
            if qcol:
                mm["q_model"] = pd.to_numeric(mf[qcol], errors="coerce")
            if pcol:
                mm["p_model"] = pd.to_numeric(mf[pcol], errors="coerce")
            j = pv.merge(mm, on=["dim", "compound"], how="inner")
            comp = {"n_joined": int(len(j)), "n_model_rows": int(len(mf))}
            if "q_model" in j.columns:
                sig_m = set(map(tuple, j.loc[j.q_model < 0.05, ["dim", "compound"]].values.tolist()))
                sig_r = set(map(tuple, j.loc[j.q_bh < 0.05, ["dim", "compound"]].values.tolist()))
                inter = len(sig_m & sig_r)
                comp.update({"n_sig_model": len(sig_m), "n_sig_reviewer": len(sig_r),
                             "overlap": inter,
                             "jaccard": (inter / len(sig_m | sig_r)) if (sig_m | sig_r) else None})
            if "p_model" in j.columns:
                from scipy.stats import spearmanr as _spr
                ok = j[["p_model", "p"]].dropna()
                comp["p_spearman"] = float(_spr(ok.p_model, ok.p).statistic) if len(ok) > 10 else None
            out["multiplicity"]["vs_model_univariate_fdr"] = comp
        else:
            out["multiplicity"]["vs_model_univariate_fdr"] = {"status": "unrecognized-columns", "columns": list(mf.columns)}

    # --- Top-3 解析（容错；文件不存在时 top3=None，稳定性与 prior-consistency 标 missing）
    top3 = None
    if files["top3_per_dimension.csv"].exists():
        raw = pd.read_csv(files["top3_per_dimension.csv"])
        cols = [c.lower() for c in raw.columns]
        dim_col = next((c for c in raw.columns if "dim" in c.lower()), None)
        if dim_col is None:
            dim_col = raw.columns[0]
        comp_cols = [c for c in raw.columns if c.lower() in
                     ("compound", "compound_1", "compound_2", "compound_3", "top1", "top2", "top3",
                      "compound_rank_1", "compound_rank_2", "compound_rank_3")]
        rank_col = next((c for c in raw.columns if "rank" in c.lower()), None)
        rows = []
        if comp_cols:
            for _, r in raw.iterrows():
                for i, cc in enumerate(comp_cols):
                    if pd.notna(r[cc]):
                        rows.append({"dim": str(r[dim_col]), "rank": i + 1, "compound": str(r[cc])})
        elif rank_col:
            rows = [{"dim": str(r[dim_col]), "rank": int(r[rank_col]), "compound": str(r.get("compound"))}
                    for _, r in raw.iterrows()]
        top3 = pd.DataFrame(rows)
        out["top3"] = {"n_rows": int(len(top3)), "n_dims": int(top3["dim"].nunique()) if len(top3) else 0}

    # --- 稳定性：入选频率 + Jaccard
    stab = {}
    if files["selection_frequency.csv"].exists():
        sf = pd.read_csv(files["selection_frequency.csv"])
        fcol = next((c for c in sf.columns if "freq" in c.lower() or "prob" in c.lower()), None)
        dcol = next((c for c in sf.columns if "dim" in c.lower()), sf.columns[0])
        if fcol:
            stab["frequency"] = {
                "n_slots": int(len(sf)),
                "n_slots_freq_ge_0.80": int((sf[fcol] >= 0.80).sum()),
                "share_slots_freq_ge_0.80": float((sf[fcol] >= 0.80).mean()),
                "n_dims_all_top3_stable": int(sf.groupby(dcol)[fcol].apply(lambda v: (v >= 0.80).all()).sum())
                if len(sf) else 0,
            }
    if files["method_jaccard.csv"].exists():
        mj = pd.read_csv(files["method_jaccard.csv"])
        jcol = next((c for c in mj.columns if "jaccard" in c.lower() or c.lower() == "j"), None)
        if jcol:
            stab["jaccard"] = {"n_rows": int(len(mj)), "mean": float(mj[jcol].mean()),
                               "min": float(mj[jcol].min()), "max": float(mj[jcol].max()),
                               "share_ge_0.50": float((mj[jcol] >= 0.50).mean())}
    out["stability"] = stab

    # --- prior-consistency：6.csv 独立 |r| 与 Top-3 入选的秩相关
    f6 = pd.read_csv(RAW / "6.csv", index_col=0)
    sn = read_xlsx("Sensory names")
    sn["R"] = sn["R_name"].map(norm_name)
    sn["C"] = sn["CleanName_PanelFeedback"].map(norm_name)
    dim2clean = dict(zip(sn["R"], sn["C"]))
    c6 = {norm_name(c): c for c in f6.columns}
    corr2 = ROOT / "outputs/protocol/corr2_map.csv"
    feat2name = {}
    if corr2.exists():
        cm = pd.read_csv(corr2)
        feat2name = dict(zip(cm["col_1csv"], cm["name_2csv"]))
    r6 = {}
    for dim in targets:
        clean = dim2clean.get(dim)
        col6 = c6.get(norm_name(clean)) if clean else None
        if col6 is None:
            continue
        vals = {}
        for c in feats:
            nm = feat2name.get(c)
            if nm in f6.index:
                vals[c] = abs(float(f6.loc[nm, col6]))
        if len(vals) >= 5:
            r6[dim] = vals
    prior = {"dims_mapped": len(r6), "n_6csv_compounds": int(len(f6))}
    if top3 is not None and len(top3) and r6:
        rows = []
        for dim, g in top3.groupby("dim"):
            if dim not in r6:
                continue
            vals = r6[dim]
            top = [c for c in g["compound"].tolist() if c in vals]
            if not top:
                continue
            rest = [v for c, v in vals.items() if c not in top]
            if len(top) < 1 or len(rest) < 3:
                continue
            try:
                u = mannwhitneyu([vals[c] for c in top], rest, alternative="greater")
                rows.append({"dim": dim, "n_top_mapped": len(top), "mean_abs_r_top": float(np.mean([vals[c] for c in top])),
                             "mean_abs_r_rest": float(np.mean(rest)), "p_one_sided": float(u.pvalue)})
            except Exception:
                continue
        pr = pd.DataFrame(rows)
        if len(pr):
            # 跨维 BH
            p = pr["p_one_sided"].to_numpy()
            o = np.argsort(p)
            qq = np.empty(len(p))
            prev = 1.0
            for i in range(len(p) - 1, -1, -1):
                val = p[o][i] * len(p) / (i + 1)
                prev = min(prev, val)
                qq[o][i] = prev
            pr["q_bh"] = qq
            prior.update({
                "n_dims_tested": int(len(pr)),
                "mean_delta_abs_r": float((pr["mean_abs_r_top"] - pr["mean_abs_r_rest"]).mean()),
                "n_dims_top3_higher_uncorrected": int((pr["p_one_sided"] < 0.05).sum()),
                "n_dims_top3_higher_BH_q05": int((pr["q_bh"] < 0.05).sum()),
                "rows": pr.to_dict("records"),
            })
    out["prior_consistency"] = prior

    # --- 泄漏静态扫描：选择脚本是否读 6/7/SHAP（Q2 selection 脚本出现时生效）
    scan = {}
    import re as _re
    io_patterns = {
        "read_6csv": _re.compile(r"read_csv\([^)]*6\.csv"),
        "load_corr_cross": _re.compile(r"load_corr_cross\s*\("),
        "read_7csv": _re.compile(r"read_csv\([^)]*7\.csv"),
        "load_ratebeer": _re.compile(r"load_ratebeer\s*\("),
        "read_xlsx_gbm": _re.compile(r"read_excel\([^)]*8\.xlsx[^)]*(GBM|SHAP)", _re.S),
    }
    for path in sorted((ROOT / "src").glob("q2_*.py")) + sorted((ROOT / "src").glob("q3_*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits = {name: len(rx.findall(text)) for name, rx in io_patterns.items()}
        scan[path.name] = {k: v for k, v in hits.items() if v}
    out["static_leakage_scan"] = {"note": "只匹配真实 I/O 调用（read_csv/load_*），不匹配注释文本", "files": scan}
    return out


# ----------------------------------------------------------------------------- Q1 candidate recompute
def q1_recompute(experiment_id: str) -> dict:
    """从 experiments/<EXP>/predictions_long.csv 的 test 行独立重算 50 维 R²/MAE 与 overall，并与 metrics.json 对照。"""
    exp_dir = ROOT / "experiments" / experiment_id
    pl = exp_dir / "predictions_long.csv"
    if not pl.exists():
        for alt in ["predictions.csv", "pred_z.csv"]:
            if (exp_dir / alt).exists():
                pl = exp_dir / alt
                break
    if not pl.exists():
        return {"status": "missing", "reason": f"{experiment_id} 无可读预测文件（predictions_long.csv）"}
    d = pd.read_csv(pl)
    if "split" in d.columns:
        te = d[d.split.astype(str).str.lower() == "test"]
    else:
        te = d
    required = {"dim", "y_true", "y_pred"}
    if not required.issubset(set(te.columns)):
        return {"status": "unrecognized-format", "columns": list(te.columns)}
    r2, mae = {}, {}
    for dim, g in te.groupby("dim"):
        y = g.y_true.values.astype(float)
        yp = g.y_pred.values.astype(float)
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2[dim] = float(1 - ((y - yp) ** 2).sum() / ss_tot) if ss_tot > 0 else float("nan")
        mae[dim] = float(np.abs(y - yp).mean())
    out = {"status": "ok", "experimentId": experiment_id, "source": str(pl.relative_to(ROOT)),
           "n_holdout_rows": int(len(te)), "n_dims": int(len(r2)),
           "recomputed": {
               "r2_50dim": float(np.nanmean(list(r2.values()))),
               "r2_median": float(np.nanmedian(list(r2.values()))),
               "mae_50dim": float(np.nanmean(list(mae.values()))),
               "r2_overall": r2.get("overall"),
               "mae_overall": mae.get("overall"),
               "per_dim_r2": r2,
           }}
    if (exp_dir / "metrics.json").exists():
        rep = json.loads((exp_dir / "metrics.json").read_text(encoding="utf-8"))
        out["reported"] = {k: rep.get(k) for k in ["r2", "r2_50dim", "r2_overall", "mae", "holdout_r2_mean",
                                                    "holdout_r2_overall", "holdout_mae_mean"] if k in rep}
        # 与上报值对照（只对同口径的键）
        comp = {}
        # 语义（VP-0007 定稿）：r2 = overall 单列 R²；mae = overall 单列 MAE；r2_50dim/holdout_r2_mean = 50 维均值
        pairs = [("r2", out["recomputed"]["r2_overall"]),
                 ("r2_overall", out["recomputed"]["r2_overall"]),
                 ("mae", out["recomputed"]["mae_overall"]),
                 ("r2_50dim", out["recomputed"]["r2_50dim"]),
                 ("holdout_r2_mean", out["recomputed"]["r2_50dim"]),
                 ("holdout_r2_overall", out["recomputed"]["r2_overall"]),
                 ("holdout_mae_mean", out["recomputed"]["mae_50dim"])]
        for key, mine in pairs:
            if key in rep and rep[key] is not None and mine is not None:
                comp[key] = {"reported": float(rep[key]), "recomputed": float(mine),
                             "abs_delta": abs(float(rep[key]) - float(mine)),
                             "within_1e-6": bool(abs(float(rep[key]) - float(mine)) <= 1e-6)}
        out["comparison"] = comp
        out["passed_1e-6"] = bool(all(v["within_1e-6"] for v in comp.values())) if comp else None
    # 非有限预测检查
    n_nonfinite = int((~np.isfinite(te[["y_true", "y_pred"]].astype(float))).sum().sum())
    out["n_nonfinite_cells"] = n_nonfinite
    return out


# ----------------------------------------------------------------------------- auxiliary matrix provenance
def aux_matrix_provenance() -> dict:
    """检验 2/5/6.csv 是否可由 1.csv+4.csv 精确重建（即它们不是独立外部先验）。"""
    from scipy.stats import spearmanr
    f1 = pd.read_csv(RAW / "1.csv").set_index("beer")
    f4 = pd.read_csv(RAW / "4.csv").set_index("beer")
    f2 = pd.read_csv(RAW / "2.csv", index_col=0)
    f5 = pd.read_csv(RAW / "5.csv", index_col=0)
    f6 = pd.read_csv(RAW / "6.csv", index_col=0)
    feats = [c for c in f1.columns if c not in KEY_COLS]
    targets = [c for c in f4.columns if c not in KEY_COLS]
    out = {}
    # 2.csv：位置映射（已验证 offset=0）
    rows = []
    for i in range(0, len(feats), 7):
        for j in range(0, len(feats), 11):
            if i == j:
                continue
            m = f1[[feats[i], feats[j]]].notna().all(axis=1)
            if m.sum() < 10:
                continue
            r = spearmanr(f1[feats[i]][m], f1[feats[j]][m]).statistic
            rows.append(abs(float(f2.iloc[i, j]) - float(r)))
    out["2csv"] = {"n_pairs_sampled": len(rows), "max_abs_diff": max(rows) if rows else None,
                   "verdict": "2.csv == Spearman(1.csv)（同数据派生，不是外部图）"}
    # 5.csv / 6.csv：用 Sensory names 映射列名
    sn = read_xlsx("Sensory names")
    sn["R"] = sn["R_name"].map(norm_name)
    sn["C"] = sn["CleanName_PanelFeedback"].map(norm_name)
    d2c = dict(zip(sn["R"], sn["C"]))
    c5 = {norm_name(c): c for c in f5.columns}
    c6 = {norm_name(c): c for c in f6.columns}
    # 5.csv
    rows5 = []
    for i, d1 in enumerate(targets):
        c1 = c5.get(norm_name(d2c.get(d1))) if d2c.get(d1) else None
        if c1 is None:
            continue
        for d2 in targets[i:]:
            c2 = c5.get(norm_name(d2c.get(d2))) if d2c.get(d2) else None
            if c2 is None:
                continue
            m = np.isfinite(f4[d1]) & np.isfinite(f4[d2])
            r = spearmanr(f4[d1][m], f4[d2][m]).statistic
            rows5.append(abs(float(f5.loc[c1, c2]) - float(r)))
    out["5csv"] = {"n_pairs": len(rows5), "max_abs_diff": max(rows5) if rows5 else None,
                   "verdict": "5.csv == Spearman(4.csv)（同数据派生，不是外部先验）"}
    # 6.csv：行名 -> 1.csv 列（用阈值表 chemical_name / chemical_name_short）
    th = read_xlsx("Sensory thresholds")
    name2col = {}
    for _, r in th.iterrows():
        nm = str(r.get("chemical_name", "")).strip()
        short = str(r.get("chemical_name_short", "")).strip().lower()
        col = str(r.get("field_name_R", "")).strip()
        if col in f1.columns:
            if nm and nm != "nan":
                name2col[nm] = col
            if short and short != "nan":
                name2col[short] = col
    row_map = {}
    for nm in f6.index:
        key = str(nm).strip()
        if key in name2col:
            row_map[nm] = name2col[key]
        elif key.lower() in name2col:
            row_map[nm] = name2col[key.lower()]
    rows6 = []
    for dim in targets:
        clean = d2c.get(dim)
        col = c6.get(norm_name(clean)) if clean else None
        if col is None:
            continue
        y = f4[dim].astype(float)
        for nm, fc in row_map.items():
            x = f1[fc].astype(float)
            m = np.isfinite(x) & np.isfinite(y)
            if m.sum() < 10:
                continue
            r = spearmanr(x[m], y[m]).statistic
            rows6.append(abs(float(f6.loc[nm, col]) - float(r)))
    out["6csv"] = {"n_rows_mapped": len(row_map), "n_pairs": len(rows6),
                   "max_abs_diff": max(rows6) if rows6 else None,
                   "verdict": "6.csv == 同数据 Spearman(1.csv,4.csv)（不是独立先验；拿它做“独立核对”是循环验证）"}
    return out


# ----------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", default="all", choices=["data", "ordinal", "calibration", "baseline", "q1", "q2", "q3", "all"])
    parser.add_argument("--experiment", default=None, help="q1 复算的实验 id（如 EXP-0017）")
    args = parser.parse_args()
    done = {}
    if args.section in ("data", "all"):
        facts = data_facts()
        write_json(facts, "data_facts_recheck.json")
        done["data"] = "outputs/review/data_facts_recheck.json"
    if args.section in ("ordinal", "all"):
        ordinal = ordinal_calibration()
        write_json(ordinal, "ordinal_calibration.json")
        done["ordinal"] = "outputs/review/ordinal_calibration.json"
    if args.section in ("calibration", "all"):
        calib = calibration_verification()
        write_json(calib, "calibration_verification.json")
        done["calibration"] = "outputs/review/calibration_verification.json"
    if args.section in ("baseline", "all"):
        result = independent_baseline()
        write_json(result, "independent_baseline.json")
        done["baseline"] = "outputs/review/independent_baseline.json"
    if args.section in ("q1",) or (args.section == "all" and args.experiment):
        if args.experiment:
            q1 = q1_recompute(args.experiment)
            write_json(q1, f"q1_recompute_{args.experiment}.json")
            done["q1"] = f"outputs/review/q1_recompute_{args.experiment}.json"
    if args.section in ("q2", "all"):
        q2 = q2_checks()
        q2["aux_matrix_provenance"] = aux_matrix_provenance()
        write_json(q2, "q2_independent_checks.json")
        done["q2"] = "outputs/review/q2_independent_checks.json"
    if args.section in ("q3", "all"):
        q3 = q3_checks()
        write_json(q3, "q3_independent_checks.json")
        done["q3"] = "outputs/review/q3_independent_checks.json"
    print(json.dumps({"ok": True, "wrote": done}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
