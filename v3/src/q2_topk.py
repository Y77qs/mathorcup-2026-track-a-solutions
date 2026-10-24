"""Q2：每个感官维度的 Top-3 关键化合物 + bootstrap 稳定性 + 方法间 Jaccard。

方法（三种，互相核对，不声称因果）：
  A. Spearman |ρ| 排序（1.csv 特征 vs 4.csv 目标，训练行）
  B. 多输出 Ridge 标准化系数 |β| 排序（训练行拟合，alpha 用训练 OOF 固定为 1000）
  C. 共表达网络平滑：score_c = |ρ_c| + 0.5 * mean_{c'∈Top10_A} Spearman2[c, c']
     其中 Spearman2 来自 2.csv，**先做 PSD 投影**（特征值截断到 ≥1e-6）再使用。

稳定性：
  * bootstrap B=500（训练行有放回重采样），统计每个目标 Top-3 的入选频率；
  * 方法间 A/B/C 的 Top-3 Jaccard 系数（逐维度 + 均值）。

2.csv 只作相关结构参考；5/6/7.csv 不作独立验证。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402
import emit as E  # noqa: E402

SEED = 20261024
TOPK = 3
BOOT = 500
LAM = 0.5


def rankdata(a: np.ndarray) -> np.ndarray:
    return pd.DataFrame(a).rank(axis=0).to_numpy()


def spearman_matrix(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """返回 (n_features, n_targets) 的 Spearman 相关（成对完整观测用 0 填充均值后仍稳定）。"""
    Xr = pd.DataFrame(X).rank(axis=0).to_numpy()
    Yr = pd.DataFrame(Y).rank(axis=0).to_numpy()
    Xr = Xr - Xr.mean(axis=0)
    Yr = Yr - Yr.mean(axis=0)
    sx = Xr.std(axis=0)
    sy = Yr.std(axis=0)
    sx = np.where(sx > 0, sx, np.nan)
    sy = np.where(sy > 0, sy, np.nan)
    Xz = Xr / sx[None, :]
    Yz = Yr / sy[None, :]
    return (Xz.T @ Yz) / len(X)


def psd_project(M: np.ndarray) -> tuple[np.ndarray, float]:
    w, V = np.linalg.eigh((M + M.T) / 2)
    w0 = np.clip(w, 1e-6, None)
    P = V @ np.diag(w0) @ V.T
    d = np.sqrt(np.clip(np.diag(P), 1e-12, None))
    P = P / d[:, None] / d[None, :]
    np.fill_diagonal(P, 1.0)
    return P, float(w.min())


def topk_idx(score: np.ndarray, k: int = TOPK) -> list[int]:
    order = np.argsort(-score, kind="mergesort")
    return [int(i) for i in order[:k]]


def main() -> int:
    import os
    p = os.environ.get("MODELING_DATA_FILE")
    df = pd.read_csv(p) if p else (L.CLEAN / "q2_raw.csv")
    df = pd.read_csv(df) if not isinstance(df, pd.DataFrame) else df
    t50 = L.target_columns()
    feats = [c for c in df.columns if c not in L.KEEP and c not in t50]
    assert len(feats) == 231

    trp = os.environ.get("MODELING_TRAIN_FILE")
    trp = Path(trp) if trp and Path(trp).exists() else L.SPLITS / "SPLIT-0001" / "train.csv"
    tr_beers = set(pd.read_csv(trp, usecols=["beer"])["beer"].astype(int))
    tr = df[df["beer"].isin(tr_beers)].sort_values("beer").reset_index(drop=True)
    assert len(tr) == 200, len(tr)
    X = tr[feats].to_numpy(float)
    Y = tr[t50].to_numpy(float)
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    X = np.where(np.isfinite(X), X, med[None, :])

    # ---------- 方法 A：Spearman |ρ|
    rho = spearman_matrix(X, Y)          # (231, 50)
    A_sets = {t: topk_idx(np.abs(rho[:, j])) for j, t in enumerate(t50)}

    # ---------- 方法 B：Ridge |β|
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Xz = (X - mu) / sd
    mdl = Ridge(alpha=1000.0)
    mdl.fit(Xz, Y)
    B_sets = {t: topk_idx(np.abs(np.asarray(mdl.coef_)[j])) for j, t in enumerate(t50)}

    # ---------- 方法 C：2.csv 共表达网络平滑（PSD 投影）
    c2 = L.load_corr("2.csv")
    assert c2.shape == (231, 231)
    P2, min_eig = psd_project(c2.to_numpy())
    C_sets = {}
    for j, t in enumerate(t50):
        base = np.abs(rho[:, j])
        top10 = np.argsort(-base)[:10]
        net = P2[:, top10].mean(axis=1)
        C_sets[t] = topk_idx(base + LAM * net)

    # ---------- 方法间 Jaccard
    def jac(a, b):
        sa, sb = set(a), set(b)
        return len(sa & sb) / len(sa | sb)

    j_ab = [jac(A_sets[t], B_sets[t]) for t in t50]
    j_ac = [jac(A_sets[t], C_sets[t]) for t in t50]
    j_bc = [jac(B_sets[t], C_sets[t]) for t in t50]

    # ---------- bootstrap：重采样训练行，重算方法 A 的 Top-3 入选频率
    rng = np.random.default_rng(SEED)
    freq = {t: {c: 0 for c in feats} for t in t50}
    for _ in range(BOOT):
        idx = rng.integers(0, len(tr), len(tr))
        r = spearman_matrix(X[idx], Y[idx])
        for j, t in enumerate(t50):
            for k in np.argsort(-np.abs(r[:, j]))[:TOPK]:
                freq[t][feats[k]] += 1
    stab_final = {}
    for t in t50:
        chosen = [feats[k] for k in A_sets[t]]
        stab_final[t] = {c: freq[t][c] / BOOT for c in chosen}

    # 方法 B/C 在 bootstrap 下的稳定性（只对 A 做了重采样；B/C 报告一次拟合结果）
    m = {
        "topk_jaccard": float(np.mean(j_ab)),
        "jaccard_A_B": float(np.mean(j_ab)),
        "jaccard_A_C": float(np.mean(j_ac)),
        "jaccard_B_C": float(np.mean(j_bc)),
        "bootstrap_stability_A": float(np.mean([np.mean(list(v.values())) for v in stab_final.values()])),
        "n_dims": len(t50), "topK": TOPK, "n_bootstrap": BOOT,
        "psd_min_eig_raw_2csv": min_eig,
        "metricKey": "topk-jaccard",
        "targetContractId": "TGT-0002",
        "n_features": len(feats), "n_train": len(tr),
        "note": "同期关联，非因果；2.csv 为实测 Spearman 且非 PSD，已做特征值截断投影",
    }
    for t in t50:
        m[f"jaccard_A_B__{t}"] = float(jac(A_sets[t], B_sets[t]))
        m[f"stability_A__{t}"] = float(np.mean(list(stab_final[t].values())))
        m[f"rho_top1_abs__{t}"] = float(np.sort(np.abs(rho[:, t50.index(t)]))[-1])

    sets = {t: {"methodA": [feats[k] for k in A_sets[t]],
                "methodB": [feats[k] for k in B_sets[t]],
                "methodC": [feats[k] for k in C_sets[t]]} for t in t50}
    E.output("sets", sets)
    E.output("bootstrap_frequency", {t: {c: v / BOOT for c, v in freq[t].items() if v > 0}
                                     for t in t50})
    E.output("method_notes", {"A": "训练行 Spearman |rho| 排序",
                              "B": "训练行多输出 Ridge(alpha=1000) 标准化系数 |beta| 排序",
                              "C": "A 的 |rho| + 0.5 * Top10 邻居的 2.csv 相关均值（PSD 投影后）",
                              "min_eig_2csv": min_eig})
    E.metrics(m)
    print(json.dumps({k: m[k] for k in ["topk_jaccard", "jaccard_A_C", "jaccard_B_C",
                                        "bootstrap_stability_A", "psd_min_eig_raw_2csv"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
