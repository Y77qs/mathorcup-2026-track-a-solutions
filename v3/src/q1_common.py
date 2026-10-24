"""Q1 共享层：数据装载、折内预处理、多输出 MAE、预测长表。

边界：
  * 特征只有 1.csv 的 231 列（DATA-0002 内的同名列），目标只有 50 个 mapped grade 列；
  * 任何插补/截尾/标准化都只在训练折上 fit；
  * 2/5/6/7/8(MDI,SHAP,Prices) 一律不进入特征。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L

ROOT = L.ROOT
KEYS = ["beer", "beer_id", "tasting_category_fine"]


def dataset_path() -> Path:
    p = os.environ.get("MODELING_DATA_FILE")
    return Path(p) if p else L.CLEAN / "q1_mapped.csv"


def split_paths():
    tr = os.environ.get("MODELING_TRAIN_FILE")
    te = os.environ.get("MODELING_TEST_FILE")
    if tr and te and Path(tr).exists() and Path(te).exists():
        return Path(tr), Path(te)
    return L.SPLITS / "SPLIT-0002" / "train.csv", L.SPLITS / "SPLIT-0002" / "test.csv"


def load():
    df = pd.read_csv(dataset_path())
    t50 = L.target_columns()
    feats = [c for c in df.columns if c not in KEYS and c not in t50]
    assert len(feats) == 231, len(feats)
    trp, tep = split_paths()
    tr_beers = set(pd.read_csv(trp, usecols=["beer"])["beer"].astype(int))
    te_beers = set(pd.read_csv(tep, usecols=["beer"])["beer"].astype(int))
    assert not (tr_beers & te_beers)
    tr = df[df["beer"].isin(tr_beers)].sort_values("beer").reset_index(drop=True)
    te = df[df["beer"].isin(te_beers)].sort_values("beer").reset_index(drop=True)
    assert len(tr) == 200 and len(te) == 50, (len(tr), len(te))
    return {"df": df, "train": tr, "test": te, "features": feats, "targets": t50,
            "split_source": str(trp.parent.name)}


def fit_preprocess(X: np.ndarray, winsor: bool = True):
    """只在训练集上 fit：中位数插补 + 1%/99% 截尾 + 标准化。"""
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    Xi = np.where(np.isfinite(X), X, med[None, :])
    out = {"median": med}
    if winsor:
        lo = np.nanpercentile(Xi, 1, axis=0)
        hi = np.nanpercentile(Xi, 99, axis=0)
        out["lo"], out["hi"] = lo, hi
        Xi = np.clip(Xi, lo[None, :], hi[None, :])
    mu = Xi.mean(axis=0)
    sd = Xi.std(axis=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    out["mu"], out["sd"] = mu, sd
    return out


def transform(X: np.ndarray, pp: dict) -> np.ndarray:
    Xi = np.where(np.isfinite(X), X, pp["median"][None, :])
    if "lo" in pp:
        Xi = np.clip(Xi, pp["lo"][None, :], pp["hi"][None, :])
    return (Xi - pp["mu"][None, :]) / pp["sd"][None, :]


def mae_per_target(Y, P) -> np.ndarray:
    Y = np.asarray(Y, float)
    P = np.asarray(P, float)
    return np.nanmean(np.abs(Y - P), axis=0)


def r2_per_target(Y, P) -> np.ndarray:
    Y = np.asarray(Y, float)
    P = np.asarray(P, float)
    ss_res = np.nansum((Y - P) ** 2, axis=0)
    ss_tot = np.nansum((Y - Y.mean(axis=0)) ** 2, axis=0)
    return 1 - ss_res / np.where(ss_tot > 0, ss_tot, np.nan)


def prediction_frame(te: pd.DataFrame, P: np.ndarray, targets: list[str]) -> pd.DataFrame:
    out = pd.DataFrame({"row": np.arange(len(te)), "beer": te["beer"].astype(int).to_numpy()})
    for j, t in enumerate(targets):
        out[f"y_pred__{t}"] = P[:, j]
    return out


def long_frame(te: pd.DataFrame, P: np.ndarray, targets: list[str]) -> pd.DataFrame:
    rows = []
    for i, b in enumerate(te["beer"].astype(int).to_numpy()):
        for j, t in enumerate(targets):
            rows.append({"row": i, "beer": int(b), "target": t,
                         "y_true": float(te.iloc[i][t]), "y_pred": float(P[i, j])})
    return pd.DataFrame(rows)


def summarize(tag: str, Y, P, targets: list[str]) -> dict:
    mae = mae_per_target(Y, P)
    r2 = r2_per_target(Y, P)
    d = {
        f"{tag}_mae_mean": float(np.nanmean(mae)),
        f"{tag}_mae_median": float(np.nanmedian(mae)),
        f"{tag}_mae_max": float(np.nanmax(mae)),
        f"{tag}_r2_mean": float(np.nanmean(r2)),
        f"{tag}_n_targets": int(len(targets)),
    }
    for t, v in zip(targets, mae):
        d[f"{tag}_mae__{t}"] = float(v)
    for t, v in zip(targets, r2):
        d[f"{tag}_r2__{t}"] = float(v)
    return d


def out_dir(area: str = "q1") -> Path:
    p = ROOT / "outputs" / area
    p.mkdir(parents=True, exist_ok=True)
    return p
