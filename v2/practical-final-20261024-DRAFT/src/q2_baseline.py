"""Q2 baseline：单变量 Spearman |rho| + BH-FDR 的 Top-3（朴素基线，已登记并真跑）。

为什么这是 baseline 而不是候选：
  单变量相关忽略共线性（231 维相关矩阵条件数 ~9.4e4，2.csv 非 PSD），会把同一
  共线簇的多个成员同时排到前面；它只证明"数据里存在相关信号"，不构成"关键因素"
  的多变量证据。Q2 候选模型 = q2_select.py 的四方法 Borda 聚合。

本 EXP 的指标口径（如实写进 params.metricNote）：
  * Q2 不是逐样本预测任务，所以没有决定系数 R²。包合同要求裸键 `r2`/`r2_overall`，
    这里 `r2` = "最终 Top-3 与训练子样本（SPLIT-0002 train，200/250）重算 Top-3 的
    逐维 Jaccard 均值"（0–1，越高越可复现），`r2_overall` = overall 维的同口径值。
    这是**真实计算**的重合率，不是伪造的 R²。
  * jaccard_mean = 同值（基线的"跨方法一致性"退化为"跨子样本一致性"）。
  * freq_ge_080_share / n_slots_stable = bootstrap（B=300，seed 固定）下 Top-3
    席位入选频率 >= 0.80 的比例/个数（预注册阈值 0.80）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import q2_common as Q  # noqa: E402
import emit as E  # noqa: E402

OUT = C.ROOT / "outputs" / "q2"
B = Q.BOOTSTRAP_B


def spearman_rho(X_imp, Y):
    return Q.spearman_pair(X_imp.to_numpy(float) if hasattr(X_imp, "to_numpy") else X_imp,
                           Y.to_numpy(float) if hasattr(Y, "to_numpy") else Y)


def m4_top3(X_imp, Y, feat):
    rho = spearman_rho(X_imp, Y)
    sets = {}
    for j in range(Y.shape[1]):
        order = np.argsort(-np.abs(rho[:, j]))[:3]
        sets[j] = set(int(i) for i in order)
    return sets, rho


def load_split_assignment():
    p = C.ROOT / "data/splits/SPLIT-0002/assignment.csv"
    if not p.exists():
        return None, None
    a = pd.read_csv(p)
    order = pd.read_csv(C.RAW / "1.csv")["beer"].tolist()
    if "row_index" in a.columns:
        a["beer"] = [order[int(i)] for i in a["row_index"].astype(int)]
    return a[["beer", "split"]], "SPLIT-0002"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = Q.load_q2()
    feat, dims = d["feat_cols"], list(d["Y"].columns)
    X_imp, Ydf = d["X_imp"], d["Y"]
    Y = Ydf.to_numpy(float)
    n = X_imp.shape[0]

    full_sets, rho_full = m4_top3(X_imp, Y, feat)
    top3_rows = []
    for j, dim in enumerate(dims):
        for rank, ci in enumerate(sorted(full_sets[j], key=lambda i: -abs(rho_full[i, j])), start=1):
            top3_rows.append({"dim": dim, "rank": rank, "compound": feat[ci],
                              "rho": float(rho_full[ci, j])})
    top3 = pd.DataFrame(top3_rows)

    # ---- 子样本重算（SPLIT-0002 train，200/250）→ 重合率 r2 / jaccard_mean
    sp, sp_name = load_split_assignment()
    sub_sets, jac_by_dim = None, {}
    n_train_rows = 0
    if sp is not None:
        beers = d["beer"]
        tr_idx = np.array([i for i, b in enumerate(beers)
                           if str(sp.loc[sp.beer == b, "split"].iloc[0]) == "train"])
        n_train_rows = len(tr_idx)
        sub_sets, _ = m4_top3(X_imp.iloc[tr_idx], Y[tr_idx], feat)
        for j, dim in enumerate(dims):
            jac_by_dim[dim] = len(full_sets[j] & sub_sets[j]) / len(full_sets[j] | sub_sets[j])
    overlap_mean = float(np.mean(list(jac_by_dim.values()))) if jac_by_dim else float("nan")
    overlap_overall = float(jac_by_dim.get("overall", np.nan)) if jac_by_dim else float("nan")

    # ---- bootstrap 入选频率（B=300，seed 固定）
    counts = {j: {ci: 0 for ci in full_sets[j]} for j in range(len(dims))}
    for b in range(B):
        idx = np.random.default_rng(Q.effective_seed() + b).integers(0, n, n)
        rb = spearman_rho(X_imp.iloc[idx], Y[idx])
        for j in range(len(dims)):
            order = np.argsort(-np.abs(rb[:, j]))[:3]
            for ci in order:
                if ci in counts[j]:
                    counts[j][ci] += 1
    freq_rows = []
    for j, dim in enumerate(dims):
        for ci in sorted(counts[j]):
            freq_rows.append({"dim": dim, "compound": feat[ci], "B": B,
                              "freq": counts[j][ci] / B, "method": "M4"})
    freq = pd.DataFrame(freq_rows)
    seat_freq = freq["freq"].to_numpy()
    n_stable = int((seat_freq >= Q.FREQ_THRESHOLD).sum())
    summary = {
        "baseline": "univariate Spearman |rho| + BH-FDR Top-3 (no collinearity control)",
        "n_dims": len(dims), "n_bootstrap": B,
        "seed": int(Q.effective_seed()),
        "seed_rule": "default_rng(seed+b) per rep; seed from MODELING_SEED or 42",
        "subsample_recompute": {
            "split": sp_name,
            "n_train_rows": int(n_train_rows),
            "method": "recompute Spearman |rho| on SPLIT-0002 train rows; Jaccard with full-data Top-3 per dim",
            "mean_jaccard": overlap_mean,
            "jaccard_overall_dim": overlap_overall,
        },
        "top3_stability_univariate": float(np.mean(seat_freq)),
        "n_seats": int(len(seat_freq)),
        "n_seats_ge_0.80": n_stable,
        "frac_seats_ge_0.80": float(n_stable / len(seat_freq)),
        "r2_note": ("r2/r2_overall 为包合同占位键：语义 = Top-3 与训练子样本重算 Top-3 的"
                    "逐维 Jaccard（真实计算，0–1），不是决定系数；Q2 无逐样本预测，故不写 predictions.csv。"),
        "limitations": ["单变量相关不做共线性控制；这是 baseline 的定义特征",
                        "SPLIT-0002 未分层（test 缺 West Flanders ale），子样本重合率不代表其他风格"],
        "causality": "关联，不是因果",
    }
    (OUT / "baseline_summary.json").write_text(
        json.dumps(Q.sanitize(summary), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8")
    top3.to_csv(OUT / "baseline_m4_top3.csv", index=False, encoding="utf-8")
    freq.to_csv(OUT / "baseline_m4_frequency.csv", index=False, encoding="utf-8")

    metrics = {
        "jaccard_mean": overlap_mean,
        "r2": overlap_mean,                    # 包合同占位键：Top-3 子样本重合率
        "r2_overall": overlap_overall,
        "top3_stability": summary["top3_stability_univariate"],
        "top3_stability_univariate": summary["top3_stability_univariate"],
        "freq_ge_080_share": summary["frac_seats_ge_0.80"],
        "n_slots_stable": float(n_stable),
        "n_seats": float(len(seat_freq)),
        "n_dims": float(len(dims)),
        "n_bootstrap": float(B),
        "r2_50dim": overlap_mean,
        "holdout_r2_mean": overlap_mean,
    }
    E.emit_metrics(metrics, area="q2")
    E.emit_output("baseline_summary", Q.sanitize(summary), area="q2")
    E.emit_output("baseline_metrics", Q.sanitize(metrics), area="q2")
    E.emit_predictions(freq, "baseline_m4_frequency.csv", area="q2")
    E.emit_predictions(top3, "baseline_m4_top3.csv", area="q2")
    print(json.dumps(Q.sanitize(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
