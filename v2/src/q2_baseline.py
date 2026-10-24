"""Q2 简单基线：全局统一排序（所有维度共用同一 Top-3），用于锚定"逐维排序"是否真的有增量。

做法：在训练行上计算每个化合物与 50 个目标维度的 Spearman |ρ| 的平均值，取全局 Top-3，
然后与逐维 Spearman Top-3（EXP-0007 的 methodA）逐维算 Jaccard。基线越接近逐维结果，说明逐维建模越没增量。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L  # noqa: E402
import emit as E  # noqa: E402

TOPK = 3


def main() -> int:
    p = os.environ.get("MODELING_DATA_FILE")
    df = pd.read_csv(p) if p else pd.read_csv(L.CLEAN / "q2_raw.csv")
    t50 = L.target_columns()
    feats = [c for c in df.columns if c not in L.KEEP and c not in t50]
    trp = os.environ.get("MODELING_TRAIN_FILE")
    trp = Path(trp) if trp and Path(trp).exists() else L.SPLITS / "SPLIT-0001" / "train.csv"
    tr_beers = set(pd.read_csv(trp, usecols=["beer"])["beer"].astype(int))
    tr = df[df["beer"].isin(tr_beers)].reset_index(drop=True)
    X = tr[feats].to_numpy(float)
    Y = tr[t50].to_numpy(float)
    med = np.nanmedian(X, axis=0)
    X = np.where(np.isfinite(X), X, med[None, :])
    Xr = pd.DataFrame(X).rank(axis=0).to_numpy()
    Yr = pd.DataFrame(Y).rank(axis=0).to_numpy()
    Xr = Xr - Xr.mean(0); Yr = Yr - Yr.mean(0)
    sx = np.where(Xr.std(0) > 0, Xr.std(0), np.nan)
    sy = np.where(Yr.std(0) > 0, Yr.std(0), np.nan)
    rho = ((Xr / sx).T @ (Yr / sy)) / len(tr)          # (n_feat, n_dim)
    mean_abs = np.nanmean(np.abs(rho), axis=1)
    global_top = [feats[i] for i in np.argsort(-mean_abs)[:TOPK]]

    per_dim_top = {}
    for j, t in enumerate(t50):
        per_dim_top[t] = [feats[i] for i in np.argsort(-np.abs(rho[:, j]))[:TOPK]]

    def jac(a, b):
        sa, sb = set(a), set(b)
        return len(sa & sb) / len(sa | sb)

    j = [jac(global_top, per_dim_top[t]) for t in t50]
    m = {
        "baseline_kind": "global-uniform-top3 (no per-dimension modelling)",
        "topk_jaccard": float(np.mean(j)),
        "jaccard_global_vs_perdim": float(np.mean(j)),
        "n_dims": len(t50), "topK": TOPK, "n_features": len(feats), "n_train": len(tr),
        "globalTop3": global_top,
        "globalMeanAbsRho": {feats[i]: float(mean_abs[i]) for i in np.argsort(-mean_abs)[:10]},
        "note": "该基线说明：不同感官维度不能共用同一个 Top-3；逐维 Jaccard 越低说明逐维建模越必要",
        "metricKey": "topk-jaccard",
        "targetContractId": "TGT-0002",
    }
    E.output("baseline_sets", {"globalTop3": global_top, "perDimA": per_dim_top})
    E.metrics(m)
    print(json.dumps({k: m[k] for k in ["topk_jaccard", "n_dims", "n_features", "globalTop3"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
