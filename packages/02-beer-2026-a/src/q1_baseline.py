"""Q1 基线 B0：constant-per-target（每个目标 = 训练集均值，空特征）。

用途：证明管线端到端可跑、给出"什么都不学"的 MAE 下界；不是候选模型。
预测契约：predictions.csv = row, beer, y_pred__<target>×50（与 50 个目标一一对应）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q1_common as Q  # noqa: E402
import emit as E  # noqa: E402
from sklearn.model_selection import KFold


def main() -> int:
    D = Q.load()
    tr, te, targets = D["train"], D["test"], D["targets"]
    Ytr = tr[targets].to_numpy(float)
    Yte = te[targets].to_numpy(float)

    mu = np.nanmean(Ytr, axis=0)
    Pte = np.tile(mu[None, :], (len(te), 1))

    # 训练集 5 折 OOF（常数基线 = 折内训练均值）
    oof = np.zeros_like(Ytr)
    kf = KFold(n_splits=5, shuffle=True, random_state=20261024)
    for ia, ib in kf.split(Ytr):
        oof[ib, :] = np.nanmean(Ytr[ia], axis=0)[None, :]

    m = {"n_train": len(tr), "n_test": len(te), "n_targets": len(targets),
         "features_used": 0, "model_family": "constant-per-target",
         **Q.summarize("oof", Ytr, oof, targets),
         **Q.summarize("holdout", Yte, Pte, targets)}
    m["mae"] = m["holdout_mae_mean"]
    m["metricKey"] = "mae"
    m["aggregation"] = "uniform-average"
    m["targetContractId"] = "TGT-0001"
    m["labelNature"] = "mapped grade (transformed, non-original 0-6)"

    pred = Q.prediction_frame(te, Pte, targets)
    E.predictions(pred, "predictions.csv")
    E.predictions(Q.long_frame(te, Pte, targets), "predictions_long.csv")
    E.output("constant_values", {t: float(v) for t, v in zip(targets, mu)})
    E.metrics(m)
    print(json.dumps({"holdout_mae_mean": m["holdout_mae_mean"],
                      "oof_mae_mean": m["oof_mae_mean"],
                      "holdout_r2_mean": m["holdout_r2_mean"],
                      "n_test": len(te), "n_targets": len(targets)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
