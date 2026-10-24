"""B1 基线：全 231 特征 + 折内中位数插补 + 标准化 + 多输出岭回归。

这是本项目**第一个被登记并真跑通的实验**（B0 常数基线因 pack 拒绝空特征，
只能以 SCRIPT-0013 脚本运行的形式留档，见 outputs/q1/B0_constant_metrics.json）。

协议：
  * 训练集（SPLIT-0001 的 200）内做 5 折 OOF；α 由内层 5 折在**每折训练子集**上选；
  * 插补/标准化/Ridge 全部只在训练子集拟合；
  * holdout（50）只评估一次，用全部 200 训练；
  * 主指标：50 维 R² 的算术平均；次指标 MAE、Spearman 均值。
产物：
  outputs/q1/B1_ridge_predictions.csv（长表 row,beer,dim,y_true,y_pred,split,is_oof）
  outputs/q1/B1_ridge_metrics.json
  outputs/q1/B1_ridge_model.json（每折 alpha 与系数范数，供复核）
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import emit as E  # noqa: E402

ALPHAS = np.logspace(-1, 4, 21)


def load_split():
    for sid in ("SPLIT-0002", "SPLIT-0001"):
        p = Path(C.SPLITS) / sid / "assignment.csv"
        if p.exists():
            a = pd.read_csv(p)
            order = pd.read_csv(C.RAW / "1.csv")["beer"].tolist()
            a["beer"] = [order[i] for i in a["row_index"].astype(int)]
            return a[["beer", "split"]], sid
    raise SystemExit("no registered split found")


def _clip(x, lim=8.0):
    """标准化后裁剪：近零方差列在折内会把 test 样本放大成极值（实测 fold2 pred_sd=4.2 爆炸），
    裁剪到 ±8 是对该数值不稳定的显式防护，不改变任何目标定义。"""
    return np.clip(x, -lim, lim)


def make_pipe(alpha):
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("clip", FunctionTransformer(_clip)),
        ("ridge", Ridge(alpha=alpha)),
    ])


def inner_alpha(Xa, Ya, seed=42):
    """内层 5 折选 alpha（只用传入的训练子集）。

    选择准则用**尺度无关的均方误差**（目标已标准化，MSE 跨维可比）：
    若用逐折 R² 均值，近常数维会产生极端负 R² 并主导选择（实测把 alpha 推到网格上界），
    这是准则退化而非模型偏好。
    """
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    ystrat = np.arange(len(Xa)) % 5  # 与目标无关的确定性分层，避免小类问题
    mse = np.full((len(ALPHAS), 5), np.inf)
    for k, (ia, ib) in enumerate(skf.split(Xa, ystrat)):
        for ai, a in enumerate(ALPHAS):
            p = make_pipe(a).fit(Xa[ia], Ya[ia])
            mse[ai, k] = float(np.nanmean((Ya[ib] - p.predict(Xa[ib])) ** 2))
    best = ALPHAS[int(np.argmin(mse.mean(axis=1)))]
    return float(best), float(mse.mean(axis=1).min())


def main():
    mt = pd.read_csv(C.ROOT / "data/clean/model_table.csv", dtype={"beer_id": "int64"})
    feats = C.feature_columns()
    dims = C.TARGET_DIMS
    sp, sp_name = load_split()
    df = mt.merge(sp, on="beer", how="left")
    tr = df[df["split"] == "train"].reset_index(drop=True)
    te = df[df["split"] == "test"].reset_index(drop=True)
    Xtr, Ytr = tr[feats].values, tr[dims].values
    Xte, Yte = te[feats].values, te[dims].values
    print(f"[B1] split={sp_name} train={len(tr)} test={len(te)} feats={len(feats)} dims={len(dims)}")

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros_like(Ytr)
    folds = []
    for k, (ia, ib) in enumerate(skf.split(Xtr, tr["tasting_category_fine"])):
        a, mse_in = inner_alpha(Xtr[ia], Ytr[ia])
        p = make_pipe(a).fit(Xtr[ia], Ytr[ia])
        oof[ib] = p.predict(Xtr[ib])
        folds.append({"fold": k, "alpha": a, "inner_mse": mse_in, "n_fit": int(len(ia)),
                      "fold_r2_mean": float(np.nanmean(C.r2(Ytr[ib], oof[ib])))})
        print(f"  fold {k}: alpha={a:g} r2={folds[-1]['fold_r2_mean']:.4f}")

    a_all, mse_all = inner_alpha(Xtr, Ytr)
    p_all = make_pipe(a_all).fit(Xtr, Ytr)
    pred_te = p_all.predict(Xte)
    print(f"[B1] full-train alpha={a_all:g}")

    rows = []
    for i in range(len(tr)):
        b = int(tr.loc[i, "beer"])
        for j, d in enumerate(dims):
            rows.append({"row": b, "beer": b, "dim": d, "y_true": float(Ytr[i, j]),
                         "y_pred": float(oof[i, j]), "split": "train", "is_oof": True})
    for i in range(len(te)):
        b = int(te.loc[i, "beer"])
        for j, d in enumerate(dims):
            rows.append({"row": b, "beer": b, "dim": d, "y_true": float(Yte[i, j]),
                         "y_pred": float(pred_te[i, j]), "split": "test", "is_oof": False})
    pred = pd.DataFrame(rows)
    C.write_csv(pred, "outputs/q1/B1_ridge_predictions.csv")

    def block(Y, P, tag):
        r2v = C.r2(Y, P)
        return {
            f"{tag}_r2_mean": float(np.nanmean(r2v)),
            f"{tag}_r2_median": float(np.nanmedian(r2v)),
            f"{tag}_mae_mean": float(np.nanmean(C.mae(Y, P))),
            f"{tag}_spearman_mean": float(np.nanmean(C.spearman_per_col(Y, P))),
            f"{tag}_per_dim_r2": {d: float(v) for d, v in zip(dims, r2v)},
            f"{tag}_n_dims_r2_positive": int(np.sum(r2v > 0)),
        }

    coef_norm = float(np.linalg.norm(p_all.named_steps["ridge"].coef_))
    m = {
        "experiment": "B1 Ridge (all 231 features, in-fold median impute + standardize)",
        "split": sp_name, "n_train": int(len(tr)), "n_test": int(len(te)),
        "n_features": len(feats), "n_dims": len(dims), "targets": dims,
        "features": feats, "family": "ridge",
        "alpha_full_train": a_all, "alpha_grid": [float(x) for x in ALPHAS],
        "folds": folds, "coef_l2_norm_full": coef_norm,
        **block(Ytr, oof, "oof"),
        **block(Yte, pred_te, "holdout"),
        "prediction_schema": "long: row,beer,dim,y_true,y_pred,split,is_oof",
        "reproducibility": "deterministic given seed=42 (StratifiedKFold + fixed alpha grid)",
    }
    C.write_json(m, "outputs/q1/B1_ridge_metrics.json")
    C.write_json({"folds": folds, "alpha_full_train": a_all, "coef_l2_norm_full": coef_norm},
                 "outputs/q1/B1_ridge_model.json")

    # ---- 通过 emit 桥接层输出实验产物（runner 只接受有限数值 + 结构化 emit_output）
    flat = {
        "oof_r2_mean": m["oof_r2_mean"], "oof_r2_median": m["oof_r2_median"],
        "oof_mae_mean": m["oof_mae_mean"], "oof_spearman_mean": m["oof_spearman_mean"],
        "holdout_r2_mean": m["holdout_r2_mean"], "holdout_r2_median": m["holdout_r2_median"],
        "holdout_mae_mean": m["holdout_mae_mean"],
        "holdout_spearman_mean": m["holdout_spearman_mean"],
        "holdout_n_dims_r2_positive": m["holdout_n_dims_r2_positive"],
        "alpha_full_train": a_all, "inner_mse_full_train": mse_all,
        "coef_l2_norm_full": coef_norm,
        "n_train": m["n_train"], "n_test": m["n_test"],
        "n_features": m["n_features"], "n_dims": m["n_dims"],
    }
    # 逐维指标拍平成数值键（runner 要求有限数值）
    for d, v in m["holdout_per_dim_r2"].items():
        flat[f"holdout_r2__{d}"] = v
    for d, v in m["oof_per_dim_r2"].items():
        flat[f"oof_r2__{d}"] = v
    # VP-0004 单列合同：overall 维、按 test.csv 行序
    te_rows = [int(b) for b in te["beer"].values]
    j_overall = dims.index("overall")
    pred_overall = pd.DataFrame({
        "row": list(range(len(te_rows))),
        "beer": te_rows,
        "y_true": Yte[:, j_overall],
        "y_pred": pred_te[:, j_overall],
    })
    flat["holdout_r2_overall"] = float(C.r2(Yte[:, [j_overall]], pred_te[:, [j_overall]])[0])
    flat["holdout_mae_overall"] = float(C.mae(Yte[:, [j_overall]], pred_te[:, [j_overall]])[0])
    # 裸键（pack independent-rerun 依赖）
    flat["r2"] = flat["holdout_r2_mean"]
    flat["r2_overall"] = flat["holdout_r2_overall"]
    flat["mae"] = flat["holdout_mae_mean"]

    E.emit_metrics(flat, area="q1")
    E.emit_predictions(pred_overall, "predictions.csv", area="q1")
    E.emit_predictions(pred, "predictions_long.csv", area="q1")
    E.emit_output("folds", folds, area="q1")
    E.emit_output("model", {"alpha_full_train": a_all, "coef_l2_norm_full": coef_norm}, area="q1")
    print("[B1] emitted: metrics + predictions.csv + predictions_overall.csv ; in_runner=",
          E.IN_RUNNER)
    print(json.dumps({k: round(float(flat[k]), 4) for k in
                      ["oof_r2_mean", "holdout_r2_mean", "holdout_mae_mean",
                       "holdout_spearman_mean", "holdout_n_dims_r2_positive",
                       "holdout_r2_overall"]}, indent=2))


if __name__ == "__main__":
    main()
