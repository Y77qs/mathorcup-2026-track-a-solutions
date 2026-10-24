"""Q3：风格条件生成 + 跨风格迁移 + 缺陷约束检查（生成合理性，不是真实酿造验证）。

协议（先写在代码里，避免事后挑口径）：
  * 风格留出：Tripel / Kriek / Lambic 整类不参与**生成模型拟合**（DATA-0003 的 style_holdout=1）。
  * 生成模型：每个已见风格一个高斯（均值 μ_s、协方差向全局对角收缩 λ=n/(n+5)），在标准化化学空间采样。
  * 少样本风格适配（明确披露）：仅用每个留出风格的极少量样本（Tripel 5、Kriek 3、Lambic 3）估计目标原型 μ_T，
    其余留出样本**只用于评估**；这属于 few-shot 适配，不是 zero-shot 生成。
  * 跨风格迁移：x' = x_source + (μ_T_adapt − μ_source_style)，来源样本取 Pils/Lager。
  * 缺陷不恶化：逐样本比较迁移前后 OAV（原始浓度 / 8.xlsx threshold_mean），并比较超阈值比例；
    缺少阈值的化合物（trans-2-nonenal、3-methyl-2-butenal、5-methylfurfural）如实报告"无法判定"。
  * 单位风险：8.xlsx 阈值单位逐化合物不同（DMS=ug/L，diacetyl/4VG/furfural=mg/L），Calibrated 数据集量纲未逐一实测，
    绝对 OAV 可能差 10^3；因此**主判据用单位不变的"不恶化"比例**，绝对超阈值率仅作参考并披露。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.linear_model import Ridge

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402
import emit as E  # noqa: E402

SEED = 20261024
HOLDOUT = ["Tripel", "Kriek", "Lambic"]
ADAPT_N = {"Tripel": 5, "Kriek": 3, "Lambic": 3}
SOURCE_STYLE = "Pils/Lager"

# 缺陷化合物：label -> (column, threshold key, scale verdict)
DEFECTS = [
    ("DMS", "DMS"),
    ("Diacetyl", "X2.3.butanedione"),
    ("4VG", "X4VG"),
    ("trans-2-nonenal", "X.E..2.nonenal"),
    ("Stale hops", "X3.methyl.2.butenal"),
    ("Stale hops", "furfural"),
    ("Stale hops", "X5.methylfurfural"),
]


def energy_distance(A: np.ndarray, B: np.ndarray) -> float:
    if len(A) == 0 or len(B) == 0:
        return float("nan")
    d_ab = cdist(A, B, "euclidean").mean()
    d_aa = cdist(A, A, "euclidean").mean()
    d_bb = cdist(B, B, "euclidean").mean()
    v = 2 * d_ab - d_aa - d_bb
    return float(np.sqrt(max(v, 0.0)))


def to_conc(col: str, v: float, smap: dict) -> float:
    sc = smap.get(col, {}).get("verdict", "unverified")
    if sc == "log10":
        return float(10.0 ** v)
    if sc == "linear":
        return float(v)
    return float("nan")


def main() -> int:
    import os
    p = os.environ.get("MODELING_DATA_FILE")
    df = pd.read_csv(p) if p else pd.read_csv(L.CLEAN / "q3.csv")
    t50 = L.target_columns()
    feats = [c for c in df.columns if c not in L.KEEP and c not in t50
             and not c.startswith("threshold") and c not in ("style_holdout", "split_role")]
    assert len(feats) == 231, len(feats)
    smap = L.scale_map()
    styles = df["tasting_category_fine"].astype(str)
    seen = [s for s in sorted(styles.unique()) if s not in HOLDOUT]

    Xraw = df[feats].to_numpy(float)
    med = np.nanmedian(Xraw[styles.isin(seen)], axis=0)
    Ximp = np.where(np.isfinite(Xraw), Xraw, med[None, :])
    tr_mask = styles.isin(seen).to_numpy()
    mu = Ximp[tr_mask].mean(axis=0)
    sd = Ximp[tr_mask].std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (Ximp - mu) / sd

    # ---------- 已见风格的条件高斯 + 收缩协方差
    rng = np.random.default_rng(SEED)
    gen, gen_stats = {}, {}
    for s in seen:
        idx = np.where(styles.to_numpy() == s)[0]
        n = len(idx)
        Zs = Z[idx]
        m_s = Zs.mean(axis=0)
        C = np.cov(Zs, rowvar=False) if n > 2 else np.cov(Z[tr_mask], rowvar=False)
        lam = n / (n + 5.0)
        C = (1 - lam) * C + lam * np.diag(np.diag(np.cov(Z[tr_mask], rowvar=False)))
        C = C + 1e-6 * np.eye(len(feats))
        G = rng.multivariate_normal(m_s, C, size=max(50, n), method="eigh")
        gen[s] = G
        gen_stats[s] = {"n_train": int(n), "shrinkage": float(lam),
                        "energy_distance_to_train": energy_distance(G, Zs)}

    # ---------- 留出风格的少样本适配 + 生成 + 迁移（受约束 vs 不受约束）
    pils = Z[np.where(styles.to_numpy() == SOURCE_STYLE)[0]]
    mu_pils = pils.mean(axis=0)
    defect_idx = sorted({feats.index(c) for _, c in DEFECTS if c in feats})
    adapt_report, transfer_rows, defect_rows = {}, [], []
    holdout_profiles = {}
    for s in HOLDOUT:
        idx = np.where(styles.to_numpy() == s)[0]
        k = min(ADAPT_N[s], max(1, len(idx) // 3))
        adapt_idx, eval_idx = idx[:k], idx[k:]
        mu_T = Z[adapt_idx].mean(axis=0)
        C = np.diag(np.diag(np.cov(Z[tr_mask], rowvar=False))) + 1e-6 * np.eye(len(feats))
        G = rng.multivariate_normal(mu_T, C, size=50, method="eigh")
        ed_gen = energy_distance(G, Z[eval_idx])
        delta = mu_T - mu_pils
        delta_con = delta.copy()
        delta_con[defect_idx] = 0.0          # 约束投影：缺陷化合物不随风格平移
        Xf_raw = pils + delta
        Xf_con = pils + delta_con
        ed_base = energy_distance(pils, Z[eval_idx])
        ed_raw = energy_distance(Xf_raw, Z[eval_idx])
        ed_con = energy_distance(Xf_con, Z[eval_idx])
        holdout_profiles[s] = {"generated": G, "transferred_raw": Xf_raw,
                               "transferred_constrained": Xf_con}
        adapt_report[s] = {"n_adapt": int(k), "n_eval": int(len(eval_idx)),
                           "energy_generated_vs_eval": ed_gen,
                           "energy_source_baseline_vs_eval": ed_base,
                           "energy_transferred_raw_vs_eval": ed_raw,
                           "energy_transferred_constrained_vs_eval": ed_con,
                           "gain_raw_vs_source": ed_base - ed_raw,
                           "gain_constrained_vs_source": ed_base - ed_con}
        for i in range(min(5, len(Xf_con))):
            transfer_rows.append({"target_style": s, "source_style": SOURCE_STYLE, "row": i})

        # 缺陷 OAV：不受约束 vs 受约束 两种迁移
        for variant, Xf in (("raw", Xf_raw), ("constrained", Xf_con)):
            for label, comp in DEFECTS:
                thr_s = df[f"threshold__{comp}"].dropna()
                thr = float(thr_s.iloc[0]) if len(thr_s) else np.nan
                ci = feats.index(comp)
                src_v = pils[:, ci] * sd[ci] + mu[ci]
                tgt_v = Xf[:, ci] * sd[ci] + mu[ci]
                if not np.isfinite(thr):
                    defect_rows.append({"target_style": s, "variant": variant, "label": label,
                                        "compound": comp, "threshold": None,
                                        "status": "no_threshold_in_8xlsx", "nonworsen_rate": None})
                    continue
                src_c = np.array([to_conc(comp, v, smap) for v in src_v])
                tgt_c = np.array([to_conc(comp, v, smap) for v in tgt_v])
                with np.errstate(invalid="ignore", divide="ignore"):
                    src_oav = src_c / thr
                    tgt_oav = tgt_c / thr
                ok = np.isfinite(src_oav) & np.isfinite(tgt_oav)
                defect_rows.append({
                    "target_style": s, "variant": variant, "label": label, "compound": comp,
                    "threshold": thr, "scale_in_1csv": smap.get(comp, {}).get("verdict"),
                    "nonworsen_rate": float(np.mean(tgt_oav[ok] <= src_oav[ok] + 1e-9)) if ok.sum() else None,
                    "exceed_rate_before": float(np.mean(src_oav[ok] > 1)) if ok.sum() else None,
                    "exceed_rate_after": float(np.mean(tgt_oav[ok] > 1)) if ok.sum() else None,
                    "median_oav_before": float(np.median(src_oav[ok])) if ok.sum() else None,
                    "median_oav_after": float(np.median(tgt_oav[ok])) if ok.sum() else None,
                })

    # ---------- 感官画像：用 Q1 Ridge（DATA-0002 + SPLIT-0002 训练行）预测生成谱
    q1 = pd.read_csv(L.CLEAN / "q1_mapped.csv")
    tr_beers = set(pd.read_csv(L.SPLITS / "SPLIT-0002" / "train.csv", usecols=["beer"])["beer"].astype(int))
    q1tr = q1[q1["beer"].isin(tr_beers)]
    Xq = q1tr[feats].to_numpy(float)
    mq = np.nanmedian(Xq, axis=0)
    mq = np.where(np.isfinite(mq), mq, 0.0)
    Xq = np.where(np.isfinite(Xq), Xq, mq[None, :])
    qmu, qsd = Xq.mean(axis=0), Xq.std(axis=0)
    qsd = np.where(qsd > 0, qsd, 1.0)
    sens_mdl = Ridge(alpha=1000.0).fit((Xq - qmu) / qsd, q1tr[t50].to_numpy(float))
    sens_image = {}
    for s, G in gen.items():
        Xg = np.where(np.isfinite(G), G, 0.0) * sd + mu
        pred = sens_mdl.predict((Xg - qmu) / qsd)
        sens_image[s] = {t: float(np.mean(pred[:, j])) for j, t in enumerate(t50)}
    for s, d in holdout_profiles.items():
        for tag in ("generated", "transferred_constrained"):
            Xg = np.where(np.isfinite(d[tag]), d[tag], 0.0) * sd + mu
            pred = sens_mdl.predict((Xg - qmu) / qsd)
            sens_image[f"{s}::{tag}"] = {t: float(np.mean(pred[:, j])) for j, t in enumerate(t50)}
    for s, d in holdout_profiles.items():
        for tag in ("generated", "transferred_constrained"):
            Xg = np.where(np.isfinite(d[tag]), d[tag], 0.0) * sd + mu
            pred = sens_mdl.predict((Xg - qmu) / qsd)
            sens_image[f"{s}::{tag}"] = {t: float(np.mean(pred[:, j])) for j, t in enumerate(t50)}

    # ---------- 汇总指标
    nw_raw = [r["nonworsen_rate"] for r in defect_rows
              if r["variant"] == "raw" and r["nonworsen_rate"] is not None]
    nw_con = [r["nonworsen_rate"] for r in defect_rows
              if r["variant"] == "constrained" and r["nonworsen_rate"] is not None]
    have_thr = [r for r in defect_rows if r["threshold"] is not None]
    m = {
        "constraint_satisfaction": float(np.mean(nw_con)) if nw_con else float("nan"),
        "defect_nonworsen_rate_raw": float(np.mean(nw_raw)) if nw_raw else float("nan"),
        "defect_nonworsen_rate_constrained": float(np.mean(nw_con)) if nw_con else float("nan"),
        "n_defect_checks": len(defect_rows),
        "n_defect_checks_with_threshold": len(have_thr),
        "n_defect_checks_no_threshold": len(defect_rows) - len(have_thr),
        "exceed_rate_before": float(np.mean([r["exceed_rate_before"] for r in have_thr
                                             if r["exceed_rate_before"] is not None])),
        "exceed_rate_after_raw": float(np.mean([r["exceed_rate_after"] for r in have_thr
                                                if r["variant"] == "raw" and r["exceed_rate_after"] is not None])),
        "exceed_rate_after_constrained": float(np.mean([r["exceed_rate_after"] for r in have_thr
                                                        if r["variant"] == "constrained" and r["exceed_rate_after"] is not None])),
        "energy_seen_styles_mean": float(np.mean([v["energy_distance_to_train"] for v in gen_stats.values()])),
        "energy_holdout_generated_mean": float(np.mean([v["energy_generated_vs_eval"] for v in adapt_report.values()])),
        "energy_holdout_source_baseline_mean": float(np.mean([v["energy_source_baseline_vs_eval"] for v in adapt_report.values()])),
        "energy_holdout_transferred_raw_mean": float(np.mean([v["energy_transferred_raw_vs_eval"] for v in adapt_report.values()])),
        "energy_holdout_transferred_constrained_mean": float(np.mean([v["energy_transferred_constrained_vs_eval"] for v in adapt_report.values()])),
        "transfer_gain_raw_mean": float(np.mean([v["gain_raw_vs_source"] for v in adapt_report.values()])),
        "transfer_gain_constrained_mean": float(np.mean([v["gain_constrained_vs_source"] for v in adapt_report.values()])),
        "n_seen_styles": len(seen), "n_holdout_styles": len(HOLDOUT),
        "n_features": len(feats),
        "metricKey": "constraint-satisfaction",
        "modelContractId": "MCON-0001",
        "note": "生成合理性/约束满足；few-shot 适配披露；绝对 OAV 受单位不确定性影响",
    }
    E.output("generated_profiles", {s: {"mean_z": G.mean(axis=0).tolist(),
                                        "n_gen": int(len(G))} for s, G in gen.items()})
    E.output("adapt_report", adapt_report)
    E.output("transfer_examples", transfer_rows[:50])
    E.output("defect_checks", defect_rows)
    E.output("sensory_image", sens_image)
    E.output("protocol", {
        "holdout_styles": HOLDOUT, "adapt_n": ADAPT_N, "source_style": SOURCE_STYLE,
        "generator": "per-style Gaussian with shrinkage lambda=n/(n+5)",
        "transfer": "x' = x_source + (mu_T_fewshot - mu_source)",
        "few_shot_disclosure": "每个留出风格用 3–5 个样本估计原型，其余样本只评估；不是 zero-shot",
        "unit_risk": "8.xlsx 阈值单位逐化合物不同；绝对 OAV 可能差 10^3，主判据用不恶化比例",
    })
    E.metrics(m)
    print(json.dumps({k: v for k, v in m.items() if isinstance(v, float)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
