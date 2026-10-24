"""Q1 候选模型：多输出 Ridge / 多输出 HistGradientBoosting。

纪律：
  * 所有预处理（中位数插补、1%/99% 截尾、标准化）只在训练折 fit；
  * 超参只用训练集 5 折 OOF MAE 选择，**不看 holdout**；
  * holdout 只评估一次（本脚本在选定配置后一次性输出）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q1_common as Q  # noqa: E402
import emit as E  # noqa: E402


def make_model(family: str, alpha: float = 10.0):
    if family == "ridge":
        return Ridge(alpha=alpha)
    if family == "gbm":
        return MultiOutputRegressor(
            HistGradientBoostingRegressor(
                max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
                min_samples_leaf=10, l2_regularization=1.0, random_state=20261024))
    raise ValueError(family)


def oof_predict(X, Y, family, alpha, n_splits=5):
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=20261024)
    P = np.zeros_like(Y)
    for ia, ib in kf.split(X):
        pp = Q.fit_preprocess(X[ia])
        m = make_model(family, alpha)
        m.fit(Q.transform(X[ia], pp), Y[ia])
        P[ib, :] = m.predict(Q.transform(X[ib], pp))
    return P


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="ridge", choices=["ridge", "gbm"])
    args = ap.parse_args()

    D = Q.load()
    tr, te, feats, targets = D["train"], D["test"], D["features"], D["targets"]
    Xtr_raw = tr[feats].to_numpy(float)
    Xte_raw = te[feats].to_numpy(float)
    Ytr = tr[targets].to_numpy(float)
    Yte = te[targets].to_numpy(float)

    tuned = {}
    if args.family == "ridge":
        best = None
        for a in [1.0, 10.0, 100.0, 1000.0, 1e4, 1e5]:
            Po = oof_predict(Xtr_raw, Ytr, "ridge", a)
            mae = float(np.nanmean(Q.mae_per_target(Ytr, Po)))
            tuned[str(a)] = mae
            if best is None or mae < best[0]:
                best = (mae, a)
        alpha = best[1]
        oof = oof_predict(Xtr_raw, Ytr, "ridge", alpha)
    else:
        alpha = 0.0
        oof = oof_predict(Xtr_raw, Ytr, "gbm", alpha)

    pp = Q.fit_preprocess(Xtr_raw)
    model = make_model(args.family, alpha)
    model.fit(Q.transform(Xtr_raw, pp), Ytr)
    Pte = model.predict(Q.transform(Xte_raw, pp))

    m = {"n_train": len(tr), "n_test": len(te), "n_targets": len(targets),
         "n_features": len(feats), "model_family": args.family, "alpha": alpha,
         "tuning_oof_mae": tuned,
         "features_used": len(feats),
         **Q.summarize("oof", Ytr, oof, targets),
         **Q.summarize("holdout", Yte, Pte, targets)}
    m["mae"] = m["holdout_mae_mean"]
    m["metricKey"] = "mae"
    m["aggregation"] = "uniform-average"
    m["targetContractId"] = "TGT-0001"
    m["labelNature"] = "mapped grade (transformed, non-original 0-6)"

    E.predictions(Q.prediction_frame(te, Pte, targets), "predictions.csv")
    E.predictions(Q.long_frame(te, Pte, targets), "predictions_long.csv")
    E.output("oof_predictions", {"beer": tr["beer"].astype(int).tolist(),
                                 "targets": targets,
                                 "y_true": Ytr.tolist(), "y_pred": oof.tolist()})
    E.output("feature_importance", _importance(model, feats, args.family))
    E.metrics(m)
    print(json.dumps({"family": args.family, "alpha": alpha,
                      "oof_mae_mean": m["oof_mae_mean"],
                      "holdout_mae_mean": m["holdout_mae_mean"],
                      "holdout_r2_mean": m["holdout_r2_mean"],
                      "tuning": tuned}, ensure_ascii=False, indent=2))
    return 0


def _importance(model, feats, family):
    try:
        if family == "ridge":
            coef = np.asarray(model.coef_)
            imp = np.abs(coef).mean(axis=0)
        else:
            ests = model.estimators_
            imp = np.zeros(len(feats))
            for e in ests:
                # HistGradientBoosting 无 feature_importances_，用 permutation-free 代理：0
                imp += 0.0
            return {"note": "HistGBM 不提供内置重要性；Q1 特征重要性以 Ridge 系数为准"}
        order = np.argsort(-imp)[:30]
        return {feats[i]: float(imp[i]) for i in order}
    except Exception as e:  # noqa
        return {"note": f"importance unavailable: {e}"}


if __name__ == "__main__":
    raise SystemExit(main())
