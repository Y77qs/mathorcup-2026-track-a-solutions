"""Q1 训练内 OOF 重建（evaluationUse=train-only）。

目的：在**不接触 test/full/assignment** 的前提下，验证新插件的训练隔离执行通路：
  * 只读 MODELING_TRAIN_FILE（登记划分的 train 子表，含 50 个目标列）；
  * 随机性来自 modeling_contract.seed()；
  * 产物只写 MODELING_EXPERIMENT_DIR；
  * 只允许 src/*.py 作为冻结依赖（本文件不 import 项目内其它模块）。

两个族：
  constant-train-mean : 空特征，逐维训练折均值（用于确认执行通路与基线口径）
  ridge               : 折内 median 插补 + 1%/99% winsorize + 标准化 + clip(±8) + 多输出岭回归

输出（metrics，均为有限数值）：
  oof_r2_50dim / oof_r2_mean / oof_r2_median / oof_mae_mean / oof_rmse_mean /
  oof_spearman_mean / r2 / mae / n_train / n_features / n_folds / seed / alpha
另写：
  predictions_oof.csv        长表 row,beer,dim,y_true,y_pred,fold
  per_dim.json               逐维 R2/RMSE/MAE
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TARGET_DIMS = [
    "A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
    "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
    "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
    "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
    "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
    "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
    "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic",
    "stale_hops", "t2n", "orange", "coriander", "clove", "lactic", "acetic",
    "barnyard", "alcohol", "aftertaste", "body", "co2", "overall",
]
ID_COLS = ["beer", "beer_id", "tasting_category_fine"]


def seed() -> int:
    try:
        import modeling_contract as mc  # type: ignore

        return int(mc.seed())
    except Exception:
        return int(os.environ.get("MODELING_SEED", "42"))


def experiment_dir() -> Path:
    d = os.environ.get("MODELING_EXPERIMENT_DIR") or os.environ.get("EXPERIMENT_DIR")
    if not d:
        raise SystemExit("MODELING_EXPERIMENT_DIR is required (run via modeling_experiment run)")
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


def train_file() -> Path:
    p = os.environ.get("MODELING_TRAIN_FILE")
    if not p or not Path(p).exists():
        raise SystemExit("MODELING_TRAIN_FILE is required and must exist")
    return Path(p)


def r2_cols(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    out = np.full(y.shape[1], np.nan)
    for j in range(y.shape[1]):
        yt, yp = y[:, j], p[:, j]
        mask = np.isfinite(yt) & np.isfinite(yp)
        if mask.sum() < 3:
            continue
        yt, yp = yt[mask], yp[mask]
        ss_res = float(np.sum((yt - yp) ** 2))
        ss_tot = float(np.sum((yt - yt.mean()) ** 2))
        out[j] = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return out


def mae_cols(y, p):
    return np.nanmean(np.abs(y - p), axis=0)


def rmse_cols(y, p):
    return np.sqrt(np.nanmean((y - p) ** 2, axis=0))


def spearman_cols(y, p):
    from scipy.stats import spearmanr

    out = np.full(y.shape[1], np.nan)
    for j in range(y.shape[1]):
        mask = np.isfinite(y[:, j]) & np.isfinite(p[:, j])
        if mask.sum() >= 5 and np.std(y[mask, j]) > 0 and np.std(p[mask, j]) > 0:
            out[j] = float(spearmanr(y[mask, j], p[mask, j]).statistic)
    return out


def winsor_fit(A):
    lo = np.nanpercentile(A, 1, axis=0)
    hi = np.nanpercentile(A, 99, axis=0)
    return lo, hi


def prep_fit(A):
    med = np.nanmedian(A, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    A2 = np.where(np.isfinite(A), A, med)
    lo, hi = winsor_fit(A2)
    A2 = np.clip(A2, lo, hi)
    mu = A2.mean(axis=0)
    sd = A2.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    return {"med": med, "lo": lo, "hi": hi, "mu": mu, "sd": sd}


def prep_apply(A, st):
    A2 = np.where(np.isfinite(A), A, st["med"])
    A2 = np.clip(A2, st["lo"], st["hi"])
    A2 = (A2 - st["mu"]) / st["sd"]
    return np.clip(A2, -8.0, 8.0)


def fit_predict(family: str, Xtr, Ytr, Xva, seed_):
    if family == "constant-train-mean":
        return np.tile(np.nanmean(Ytr, axis=0), (len(Ytr), 1)), None
    if family != "ridge":
        raise SystemExit(f"unknown family {family!r}")
    from sklearn.linear_model import Ridge

    st = prep_fit(Xtr)
    Xa = prep_apply(Xtr, st)
    Xb = prep_apply(Xva, st)
    # 内层 3 折在**训练折内部**选 alpha（只用传入的训练折，不碰验证折）
    rng = np.random.RandomState(seed_)
    n = len(Xa)
    order = rng.permutation(n)
    folds = np.array_split(order, 3)
    alphas = [1.0, 10.0, 100.0, 1000.0]
    best, best_mse = None, np.inf
    for a in alphas:
        mse = []
        for k in range(3):
            va = folds[k]
            tr = np.concatenate([folds[j] for j in range(3) if j != k])
            m = Ridge(alpha=a).fit(Xa[tr], Ytr[tr])
            pred = m.predict(Xa[va])
            ss = np.nanmean((Ytr[va] - pred) ** 2)
            if np.isfinite(ss):
                mse.append(ss)
        score = float(np.mean(mse)) if mse else np.inf
        if score < best_mse:
            best, best_mse = a, score
    model = Ridge(alpha=best).fit(Xa, Ytr)
    return model.predict(Xb), best


def main(argv):
    family = "ridge"
    n_folds = 5
    if "--family" in argv:
        family = argv[argv.index("--family") + 1]
    if "--folds" in argv:
        n_folds = int(argv[argv.index("--folds") + 1])
    sd = seed()
    ed = experiment_dir()
    tf = train_file()
    df = pd.read_csv(tf)
    missing = [d for d in TARGET_DIMS if d not in df.columns]
    if missing:
        raise SystemExit(f"train file lacks target columns: {missing[:5]}")
    feats = [c for c in df.columns if c not in ID_COLS and c not in TARGET_DIMS]
    print(f"[train-only] file={tf.name} rows={len(df)} features={len(feats)} dims={len(TARGET_DIMS)} family={family} seed={sd}", flush=True)

    X = df[feats].to_numpy(float)
    Y = df[TARGET_DIMS].to_numpy(float)
    n = len(df)
    rng = np.random.RandomState(sd)
    fold_id = np.empty(n, int)
    order = rng.permutation(n)
    for k, idx in enumerate(np.array_split(order, n_folds)):
        fold_id[idx] = k

    oof = np.full_like(Y, np.nan)
    alphas_used = []
    for k in range(n_folds):
        tr = np.where(fold_id != k)[0]
        va = np.where(fold_id == k)[0]
        if family == "constant-train-mean":
            oof[va] = np.tile(np.nanmean(Y[tr], axis=0), (len(va), 1))
        else:
            pred, a = fit_predict(family, X[tr], Y[tr], X[va], sd + k)
            oof[va] = pred
            alphas_used.append(a)
        print(f"  fold {k}: n_tr={len(tr)} n_va={len(va)}", flush=True)

    per_dim = {}
    for j, d in enumerate(TARGET_DIMS):
        per_dim[d] = {
            "r2": float(r2_cols(Y[:, [j]], oof[:, [j]])[0]),
            "rmse": float(rmse_cols(Y[:, [j]], oof[:, [j]])[0]),
            "mae": float(mae_cols(Y[:, [j]], oof[:, [j]])[0]),
        }
    r2s = r2_cols(Y, oof)
    maes = mae_cols(Y, oof)
    rmses = rmse_cols(Y, oof)
    rhos = spearman_cols(Y, oof)
    j_overall = TARGET_DIMS.index("overall")
    metrics = {
        "oof_r2_50dim": float(np.nanmean(r2s)),
        "oof_r2_mean": float(np.nanmean(r2s)),
        "oof_r2_median": float(np.nanmedian(r2s)),
        "oof_r2_min": float(np.nanmin(r2s)),
        "oof_r2_max": float(np.nanmax(r2s)),
        "oof_n_dims_r2_positive": int(np.nansum(r2s > 0)),
        "oof_mae_mean": float(np.nanmean(maes)),
        "oof_rmse_mean": float(np.nanmean(rmses)),
        "oof_spearman_mean": float(np.nanmean(rhos)),
        "r2": float(r2s[j_overall]),
        "mae": float(maes[j_overall]),
        "n_train": int(n),
        "n_features": int(len(feats)),
        "n_folds": int(n_folds),
        "seed": int(sd),
    }
    if family == "ridge":
        metrics["alpha_mean"] = float(np.mean(alphas_used))
        metrics["alpha_min"] = float(np.min(alphas_used))
        metrics["alpha_max"] = float(np.max(alphas_used))

    try:
        import modeling_contract as mc  # type: ignore

        mc.emit_metrics(metrics)
        long = pd.DataFrame({
            "row": np.repeat(np.arange(n), len(TARGET_DIMS)),
            "beer": np.repeat(df["beer"].to_numpy(), len(TARGET_DIMS)),
            "dim": np.tile(TARGET_DIMS, n),
            "y_true": Y.reshape(-1),
            "y_pred": oof.reshape(-1),
            "fold": np.repeat(fold_id, len(TARGET_DIMS)),
        })
        mc.emit_predictions(long, "predictions_oof.csv")
        mc.emit_output("per_dim", per_dim)
        mc.emit_output("run_info", {
            "family": family, "seed": sd, "n_folds": n_folds,
            "features": feats, "targetDims": TARGET_DIMS,
            "trainFile": tf.name, "alphaByFold": alphas_used,
        })
    except Exception as exc:  # 退化为直接写目录，便于本地调试
        print(f"[train-only] modeling_contract unavailable ({exc}); writing files directly", flush=True)
        (ed / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        (ed / "per_dim.json").write_text(json.dumps(per_dim, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
