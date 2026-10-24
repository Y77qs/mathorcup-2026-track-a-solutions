"""Q1 训练内部的隔离复算（train-only，用于 independent-rerun 审计）。

只读 MODELING_TRAIN_FILE（split 工具的 train.csv，含特征与目标），完全不触碰 test 文件；
在 macOS seatbelt 隔离下运行（evaluationUse:'train-only'），因此不消耗 holdout 预算。
指标 mae = 5 折 OOF 的 50 维等权 MAE，与 EXP-0002 的 oof_mae_mean 同口径。
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
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

SEED = 20261024
ALPHA = 1000.0
KEYS = ["beer", "beer_id", "tasting_category_fine"]


def main() -> int:
    trp = os.environ.get("MODELING_TRAIN_FILE")
    assert trp and Path(trp).exists(), "train-only run needs MODELING_TRAIN_FILE"
    tr = pd.read_csv(trp)
    t50 = L.target_columns()
    feats = [c for c in tr.columns if c not in KEYS and c not in t50]
    X = tr[feats].to_numpy(float)
    Y = tr[t50].to_numpy(float)

    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    P = np.zeros_like(Y)
    for ia, ib in kf.split(X):
        med = np.nanmedian(X[ia], axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        Xi = np.where(np.isfinite(X[ia]), X[ia], med[None, :])
        lo = np.percentile(Xi, 1, axis=0)
        hi = np.percentile(Xi, 99, axis=0)
        Xi = np.clip(Xi, lo[None, :], hi[None, :])
        mu, sd = Xi.mean(0), Xi.std(0)
        sd = np.where(sd > 0, sd, 1.0)
        Xz = (Xi - mu) / sd
        Xb = np.where(np.isfinite(X[ib]), X[ib], med[None, :])
        Xb = np.clip(Xb, lo[None, :], hi[None, :])
        m = Ridge(alpha=ALPHA).fit(Xz, Y[ia])
        P[ib, :] = m.predict((Xb - mu) / sd)

    mae = float(np.nanmean(np.abs(Y - P)))
    m = {"mae": mae, "oof_mae_mean": mae, "n_train": int(len(tr)),
         "n_features": len(feats), "n_targets": len(t50),
         "alpha": ALPHA, "evaluation_use": "train-only (seatbelt isolated)",
         "note": "与 EXP-0002 的 oof_mae_mean 同口径；不读取 test，不消耗 holdout 预算"}
    E.metrics(m)
    print(json.dumps({"mae": mae, "n_train": len(tr), "n_features": len(feats),
                      "alpha": ALPHA}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
