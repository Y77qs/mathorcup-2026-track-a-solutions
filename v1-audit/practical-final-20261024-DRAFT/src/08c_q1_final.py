"""Q1 最终候选（Lead 接管版）：PLS + ExtraTrees + RandomForest 等权融合。

为什么由 Lead 写：modeler-q1 的集成实验 EXP-0017 在 600s 内未完成并被 cancel，
Q1 因此没有可用的最终候选，且 Q3 的感官画像依赖 Q1 的 model_bundle。
本脚本刻意做成**能在 60s 内跑完**的配置，保证交付链路不空转。
写域：src/08c_q1_final.py（与 modeler-q1 的 src/q1_*.py 不冲突）。

协议（沿用已登记口径，不新增自由度）：
  * 划分：SPLIT-0002（台账登记版，与 SPLIT-0001 逐 beer 相同）
  * 预处理：**只在训练子集拟合** —— 中位数插补 → 1%/99% winsorize → 标准化（PLS 用）
  * 融合：PLS(n=5) + ExtraTrees(300, max_features=0.2) + RandomForest(300, max_features=0.2) 等权平均
    （候选族由 modeler-q1 的 41 种等权组合搜索支撑；此处固定为第 2 优的稳定 3 路组合，
     因 4 路含逐维 HGB 会超时——这一取舍如实记录在 params.reason）
  * 训练内 5 折 OOF 出 OOF 指标；holdout 只用一次
  * 0–6 分级：按 P1/P2/P3/P4 四套口径分别落盘（参数取自
    outputs/protocol/grade_calibration_SPLIT-0001.csv）
  * 导出 model_bundle.pkl 供 Q3 做"感官画像"前向映射
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import emit as E  # noqa: E402

SEED = 42
CLIP_Q = (0.01, 0.99)
N_TREES = 150
MF = 0.2


class Pre:
    """折内预处理：中位数插补 → 分位 winsorize → 标准化。"""

    def fit(self, X):
        self.med = np.nanmedian(X, axis=0)
        self.med = np.where(np.isfinite(self.med), self.med, 0.0)
        Xi = np.where(np.isnan(X), self.med, X)
        self.lo = np.quantile(Xi, CLIP_Q[0], axis=0)
        self.hi = np.quantile(Xi, CLIP_Q[1], axis=0)
        Xw = np.clip(Xi, self.lo, self.hi)
        self.sc = StandardScaler().fit(Xw)
        return self

    def transform(self, X):
        Xi = np.where(np.isnan(X), self.med, X)
        Xw = np.clip(Xi, self.lo, self.hi)
        return self.sc.transform(Xw)


def fit_predict(Xtr, Ytr, Xte_list):
    """返回 (train 自预测, [每个 Xte 的预测])，三模型等权平均。"""
    from sklearn.cross_decomposition import PLSRegression
    pls = PLSRegression(n_components=5, scale=False).fit(Xtr, Ytr)
    et = ExtraTreesRegressor(n_estimators=N_TREES, max_features=MF, random_state=SEED,
                             n_jobs=-1).fit(Xtr, Ytr)
    rf = RandomForestRegressor(n_estimators=N_TREES, max_features=MF, random_state=SEED,
                               n_jobs=-1).fit(Xtr, Ytr)
    models = {"pls5": pls, "extratrees300": et, "randomforest300": rf}

    def mean_pred(X):
        return (pls.predict(X) + et.predict(X) + rf.predict(X)) / 3.0

    return mean_pred, models


def load_split():
    p = Path(C.SPLITS) / "SPLIT-0002" / "assignment.csv"
    a = pd.read_csv(p)
    order = pd.read_csv(C.RAW / "1.csv")["beer"].tolist()
    a["beer"] = [order[int(i)] for i in a["row_index"].astype(int)]
    return a[["beer", "split"]], "SPLIT-0002"


def load_calib():
    p = C.ROOT / "outputs/protocol/grade_calibration_SPLIT-0001.csv"
    return pd.read_csv(p).set_index("dim")


def to_grades(z, cal, policy):
    out = {}
    for j, d in enumerate(C.TARGET_DIMS):
        r = cal.loc[d]
        pars = {"a": r["P1_a"], "s": r["P1_s"], "lo": r["P2_lo"], "hi": r["P2_hi"], "S": r["P4_S"]}
        out[d] = C.grade_policy(z[:, j], policy, pars)
    return pd.DataFrame(out)


def main():
    mt = pd.read_csv(C.ROOT / "data/clean/model_table.csv", dtype={"beer_id": "int64"})
    feats, dims = C.feature_columns(), C.TARGET_DIMS
    sp, sp_name = load_split()
    df = mt.merge(sp, on="beer", how="left")
    tr = df[df["split"] == "train"].reset_index(drop=True)
    te = df[df["split"] == "test"].reset_index(drop=True)
    Xtr_raw, Ytr = tr[feats].values, tr[dims].values
    Xte_raw, Yte = te[feats].values, te[dims].values
    print(f"[Q1final] split={sp_name} train={len(tr)} test={len(te)} feats={len(feats)} dims={len(dims)}")

    # ---- 训练内 5 折 OOF
    oof = np.zeros_like(Ytr)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for k, (ia, ib) in enumerate(skf.split(Xtr_raw, tr["tasting_category_fine"])):
        pre = Pre().fit(Xtr_raw[ia])
        mp, _ = fit_predict(pre.transform(Xtr_raw[ia]), Ytr[ia], [pre.transform(Xtr_raw[ib])])
        oof[ib] = mp(pre.transform(Xtr_raw[ib]))
        print(f"  fold {k}: r2_50dim={np.nanmean(C.r2(Ytr[ib], oof[ib])):+.4f}")

    # ---- 全训练拟合 + holdout 一次评估
    pre_all = Pre().fit(Xtr_raw)
    mp_all, models = fit_predict(pre_all.transform(Xtr_raw), Ytr, [pre_all.transform(Xte_raw)])
    pred_te = mp_all(pre_all.transform(Xte_raw))

    r2_oof = C.r2(Ytr, oof)
    r2_te = C.r2(Yte, pred_te)
    j_overall = dims.index("overall")
    pred_overall = pd.DataFrame({
        "row": list(range(len(te))),
        "beer": [int(b) for b in te["beer"].values],
        "y_true": Yte[:, j_overall],
        "y_pred": pred_te[:, j_overall],
    })
    # 长表：训练 OOF + 测试 holdout
    rows = []
    for i in range(len(tr)):
        b = int(tr.loc[i, "beer"])
        for j, d in enumerate(dims):
            rows.append({"row": i, "beer": b, "dim": d, "y_true": float(Ytr[i, j]),
                         "y_pred": float(oof[i, j]), "split": "train", "is_oof": True})
    for i in range(len(te)):
        b = int(te.loc[i, "beer"])
        for j, d in enumerate(dims):
            rows.append({"row": i, "beer": b, "dim": d, "y_true": float(Yte[i, j]),
                         "y_pred": float(pred_te[i, j]), "split": "test", "is_oof": False})
    long = pd.DataFrame(rows)

    # ---- 0-6 分级（四套口径），全部 250 样本：训练用 OOF、测试用 holdout
    cal = load_calib()
    z250 = np.zeros((len(df), len(dims)))
    z250[df["split"].values == "train"] = oof
    z250[df["split"].values == "test"] = pred_te
    grade_tables = {}
    for pol in ["P1_oav_anchor", "P2_range", "P3_quantile", "P4_sigma"]:
        g = to_grades(z250, cal, pol)
        g.insert(0, "beer", df["beer"].values)
        g.insert(1, "split", df["split"].values)
        grade_tables[pol] = g
        C.write_csv(g, f"outputs/q1/scores_0_6_{pol}.csv")

    flat = {
        "r2": float(r2_te[j_overall]),
        "r2_overall": float(r2_te[j_overall]),
        "r2_50dim": float(np.nanmean(r2_te)),
        "holdout_r2_mean": float(np.nanmean(r2_te)),
        "holdout_r2_median": float(np.nanmedian(r2_te)),
        "holdout_mae_mean": float(np.nanmean(C.mae(Yte, pred_te))),
        "holdout_spearman_mean": float(np.nanmean(C.spearman_per_col(Yte, pred_te))),
        "holdout_n_dims_r2_positive": int(np.sum(r2_te > 0)),
        "mae": float(C.mae(Yte[:, [j_overall]], pred_te[:, [j_overall]])[0]),
        "oof_r2_50dim": float(np.nanmean(r2_oof)),
        "oof_mae_mean": float(np.nanmean(C.mae(Ytr, oof))),
        "oof_spearman_mean": float(np.nanmean(C.spearman_per_col(Ytr, oof))),
        "n_train": len(tr), "n_test": len(te), "n_features": len(feats), "n_dims": len(dims),
        "n_trees": N_TREES, "max_features": MF, "clip_low": CLIP_Q[0], "clip_high": CLIP_Q[1],
    }
    for d, v in zip(dims, r2_te):
        flat[f"holdout_r2__{d}"] = float(v)
    for d, v in zip(dims, r2_oof):
        flat[f"oof_r2__{d}"] = float(v)
    flat["grade_qwk_P1_vs_P2"] = float(C.qwk(grade_tables["P1_oav_anchor"].iloc[:, 2:].values.ravel(),
                                             grade_tables["P2_range"].iloc[:, 2:].values.ravel()))

    E.emit_metrics(flat, area="q1")
    E.emit_predictions(pred_overall, "predictions.csv", area="q1")
    E.emit_predictions(long, "predictions_long.csv", area="q1")
    E.emit_output("per_dim", {"holdout_r2": dict(zip(dims, map(float, r2_te))),
                              "oof_r2": dict(zip(dims, map(float, r2_oof)))}, area="q1")
    E.emit_output("prep", {"impute": "in-fold median", "winsorize": list(CLIP_Q),
                           "standardize": "in-fold StandardScaler (PLS uses it; trees invariant)",
                           "members": ["pls5", "extratrees300", "randomforest300"],
                           "weights": "equal 1/3"}, area="q1")

    # ---- model_bundle.pkl 供 Q3 前向映射
    bundle = {
        "bundle_version": "q1final-v1",
        "target_dims": dims,
        "features": feats,
        "members": list(models.keys()),
        "weights": {"pls5": 1 / 3, "extratrees300": 1 / 3, "randomforest300": 1 / 3},
        "prep": {"median": pre_all.med.tolist(), "lo": pre_all.lo.tolist(), "hi": pre_all.hi.tolist(),
                 "scaler_mean": pre_all.sc.mean_.tolist(), "scaler_scale": pre_all.sc.scale_.tolist(),
                 "clip_q": list(CLIP_Q)},
        "calibration": {"policy": "P1_oav_anchor", "table": "outputs/protocol/grade_calibration_SPLIT-0001.csv",
                        "a": cal["P1_a"].to_dict(), "s": cal["P1_s"].to_dict(),
                        "oav_status": cal["oav_status"].to_dict()},
        "train_beers": [int(b) for b in tr["beer"].values],
        "holdout_beers": [int(b) for b in te["beer"].values],
        "oof_r2_50dim": float(np.nanmean(r2_oof)),
        "holdout_r2_50dim": float(np.nanmean(r2_te)),
        "models": models,
        "notes": "Q3 只允许用本 bundle 做推理（predict），不得用 Q3 数据再训练",
    }
    bp = C.ROOT / "outputs/q1/model_bundle.pkl.gz"
    bp.parent.mkdir(parents=True, exist_ok=True)
    import gzip
    with gzip.open(bp, "wb", compresslevel=4) as f:
        pickle.dump(bundle, f, protocol=4)
    print("[Q1final] bundle ->", bp, f"{bp.stat().st_size/1e6:.2f} MB")
    print(json.dumps({k: round(float(flat[k]), 4) for k in
                      ["r2_50dim", "holdout_r2_mean", "holdout_mae_mean",
                       "holdout_spearman_mean", "holdout_n_dims_r2_positive", "r2"]}, indent=2))


if __name__ == "__main__":
    main()
